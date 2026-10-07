from flask import Flask

from blueprints.terraform import terraform_bp
from core.infrastructure_validation import validate_infrastructure_design


def test_valid_design_has_no_issues():
    design = {
        "names": {
            "resource_group": "rg-prod-platform",
            "virtual_network": "vnet-hub",
            "subnet": "AzureFirewallSubnet",
            "storage_account": "stplatform01",
            "aks_cluster": "aks-prod-01",
        },
        "virtual_networks": [
            {
                "name": "hub",
                "cidr": "10.0.0.0/16",
                "subnets": [
                    {"name": "firewall", "cidr": "10.0.0.0/26"},
                    {"name": "app", "cidr": "10.0.1.0/24"},
                ],
            },
            {
                "name": "spoke",
                "cidr": "10.1.0.0/16",
                "subnets": [{"name": "workloads", "cidr": "10.1.1.0/24"}],
            },
        ],
        "role_assignments": [
            {
                "principal_id": "00000000-0000-0000-0000-000000000001",
                "role": "Reader",
                "scope": "/subscriptions/00000000-0000-0000-0000-000000000002",
            }
        ],
    }

    assert validate_infrastructure_design(design) == []


def test_detects_invalid_and_overlapping_networks():
    design = {
        "virtual_networks": [
            {"name": "hub", "cidr": "10.0.0.0/16", "subnets": [
                {"name": "first", "cidr": "10.0.1.0/24"},
                {"name": "second", "cidr": "10.0.1.128/25"},
                {"name": "outside", "cidr": "10.2.0.0/24"},
            ]},
            {"name": "spoke", "cidr": "10.0.0.0/17", "subnets": []},
            {"name": "invalid", "cidr": "10.3.0.1/24", "subnets": []},
        ]
    }

    issues = validate_infrastructure_design(design)
    codes = {issue["code"] for issue in issues}
    assert "subnet.overlap" in codes
    assert "subnet.outside_vnet" in codes
    assert "cidr.overlap" in codes
    assert "cidr.invalid" in codes


def test_validates_resource_names_and_duplicate_rbac_assignments():
    assignment = {
        "principal_id": "user-1",
        "role": "Owner",
        "scope": "/subscriptions/00000000-0000-0000-0000-000000000001",
    }
    issues = validate_infrastructure_design({
        "names": {"storage_account": "Not-A-Valid-Storage-Name"},
        "role_assignments": [assignment, assignment],
    })

    codes = [issue["code"] for issue in issues]
    assert "name.invalid" in codes
    assert "rbac.assignment_duplicate" in codes
    assert "rbac.broad_role" in codes


def test_rejects_wrong_top_level_shapes_without_throwing():
    assert validate_infrastructure_design(None)[0]["code"] == "design.object_required"
    assert validate_infrastructure_design({"virtual_networks": {}})[0]["code"] == "network.list_required"


def test_validation_api_reports_conflicts_and_rejects_missing_json():
    app = Flask(__name__)
    app.register_blueprint(terraform_bp)
    client = app.test_client()

    missing = client.post("/api/terraform/validate-design")
    result = client.post("/api/terraform/validate-design", json={"virtual_networks": []})

    assert missing.status_code == 400
    assert result.status_code == 200
    assert result.json["ok"] is False
    assert result.json["issues"][0]["code"] == "network.required"

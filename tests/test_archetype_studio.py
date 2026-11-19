import json
import io
import zipfile
from pathlib import Path
from types import SimpleNamespace

from flask import Flask, jsonify

from app_features.archetype_studio import init
from managers.feature_loader import load_features


ROOT = Path(__file__).resolve().parents[1]


def make_client(tmp_path, allow=True):
    app = Flask(__name__)
    ctx = SimpleNamespace(
        root=tmp_path,
        directory=ROOT / "app_features" / "archetype_studio",
        admin_page=lambda is_json: None if allow else (jsonify(error="denied"), 403),
        admin_post=lambda: None if allow else (jsonify(error="denied"), 403),
        render_page=lambda name: "Archetype Studio",
        audit=lambda *args, **kwargs: None,
    )
    app.register_blueprint(init(app, ctx))
    return app.test_client()


def test_whiteboard_save_open_and_overwrite(tmp_path):
    client = make_client(tmp_path)
    doc = {"version": 1, "title": "First", "nodes": [], "edges": []}
    endpoint = "/ext/archetype_studio/api/diagrams/First"
    assert client.put(endpoint, json=doc).status_code == 200
    assert client.get(endpoint).get_json()["diagram"] == doc
    assert client.get("/ext/archetype_studio/api/diagrams").get_json()["diagrams"] == ["First"]
    assert client.put(endpoint, json=doc).status_code == 409
    assert client.put(endpoint + "?overwrite=1", json=doc).status_code == 200
    assert json.loads((tmp_path / "data" / "archetype_studio" / "First.json").read_text()) == doc


def test_whiteboard_rejects_invalid_documents_and_names(tmp_path):
    client = make_client(tmp_path)
    endpoint = "/ext/archetype_studio/api/diagrams/First"
    assert client.put(endpoint, json={"version": 2, "nodes": [], "edges": []}).status_code == 400
    assert client.put("/ext/archetype_studio/api/diagrams/.hidden", json={}).status_code == 400
    assert client.get(endpoint).status_code == 404
    assert client.put(endpoint, data="x" * (4 * 1024 * 1024 + 1), content_type="application/json").status_code == 413


def test_whiteboard_routes_require_access(tmp_path):
    client = make_client(tmp_path, allow=False)
    assert client.get("/ext/archetype_studio/").status_code == 403
    assert client.get("/ext/archetype_studio/assets/studio.js").status_code == 403
    assert client.get("/ext/archetype_studio/api/diagrams").status_code == 403
    assert client.put("/ext/archetype_studio/api/diagrams/A", json={}).status_code == 403


def test_whiteboard_is_discovered_and_loaded():
    app = Flask(__name__)
    statuses = load_features(app, ROOT, "", lambda _: None, lambda: None)
    studio = next(item for item in statuses if item["slug"] == "archetype_studio")
    assert studio["state"] == "loaded", studio["error"]
    response = app.test_client().get("/ext/archetype_studio/")
    assert response.status_code == 200
    assert b"Archetype Studio" in response.data


def configured_diagram():
    return {"version": 1, "nodes": [
        {"id": "rg", "kind": "resource-group", "label": "RG", "iac": {"name": "rg-prod", "location": "eastus"}},
        {"id": "vnet", "kind": "network", "label": "VNet", "iac": {"name": "vnet-prod", "location": "eastus", "resource_group": "rg", "address": "10.0.0.0/16"}},
        {"id": "sub", "kind": "subnet", "label": "Subnet", "iac": {"name": "subnet-prod", "vnet": "vnet", "address": "10.0.1.0/24"}},
        {"id": "storage", "kind": "storage", "label": "Storage", "iac": {"name": "examplestorage123", "location": "eastus", "resource_group": "rg", "sku": "Standard_LRS"}},
        {"id": "nsg", "kind": "nsg", "label": "NSG", "iac": {"name": "nsg-prod", "location": "eastus", "resource_group": "rg"}},
    ], "edges": []}


def test_iac_validated_export_contains_only_configured_resources(tmp_path):
    client = make_client(tmp_path)
    payload = {"diagram": configured_diagram(), "mode": "validated"}
    preview = client.post("/ext/archetype_studio/api/iac/preview", json=payload).get_json()["report"]
    assert preview["can_export"]
    assert len(preview["resources"]) == 5
    response = client.post("/ext/archetype_studio/api/iac/export", json=payload)
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
        tf = json.loads(archive.read("main.tf.json"))
        assert tf["resource"]["azurerm_subnet"]["shape_sub"]["address_prefixes"] == ["10.0.1.0/24"]
        assert tf["resource"]["azurerm_storage_account"]["shape_storage"]["public_network_access_enabled"] is False
        assert json.loads(archive.read("review-report.json"))["issues"] == []


def test_iac_draft_reports_omissions_and_validated_blocks(tmp_path):
    client = make_client(tmp_path)
    diagram = configured_diagram()
    diagram["nodes"].extend([
        {"id": "vm", "kind": "vm", "label": "VM"},
        {"id": "bad", "kind": "subnet", "label": "Bad subnet", "iac": {"name": "bad", "vnet": "vnet", "address": "192.168.1.0/24"}},
    ])
    payload = {"diagram": diagram, "mode": "validated"}
    assert client.post("/ext/archetype_studio/api/iac/export", json=payload).status_code == 422
    payload["mode"] = "draft"
    response = client.post("/ext/archetype_studio/api/iac/export", json=payload)
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
        assert "main.tf.json" not in archive.namelist()
        report = json.loads(archive.read("review-report.json"))
        assert {issue["id"] for issue in report["issues"]} == {"vm", "bad"}


def test_iac_blocks_dependency_errors_and_malformed_fields(tmp_path):
    client = make_client(tmp_path)
    diagram = configured_diagram()
    diagram["nodes"][0]["iac"]["location"] = ["invalid"]
    response = client.post("/ext/archetype_studio/api/iac/preview", json={"diagram": diagram, "mode": "draft"})
    assert response.status_code == 200
    report = response.get_json()["report"]
    assert not report["can_export"]
    assert {issue["id"] for issue in report["issues"]} == {"rg", "vnet", "sub", "storage", "nsg", ""}


def test_iac_export_requires_guard(tmp_path):
    client = make_client(tmp_path, allow=False)
    for path in ["preview", "export"]:
        assert client.post(f"/ext/archetype_studio/api/iac/{path}", json={}).status_code == 403


def test_iac_peering_is_explicit_and_overlaps_are_blocked(tmp_path):
    client = make_client(tmp_path)
    diagram = configured_diagram()
    diagram["nodes"].extend([
        {"id": "spoke", "kind": "network", "label": "Spoke", "iac": {
            "name": "spoke", "location": "eastus", "resource_group": "rg", "address": "10.1.0.0/16"}},
        {"id": "peer", "kind": "peering", "label": "Peer", "iac": {
            "name": "hub-to-spoke", "source": "vnet", "target": "spoke"}},
    ])
    payload = {"diagram": diagram, "mode": "validated"}
    report = client.post("/ext/archetype_studio/api/iac/preview", json=payload).get_json()["report"]
    assert report["can_export"]
    peer = report["terraform"]["resource"]["azurerm_virtual_network_peering"]["shape_peer"]
    assert peer["remote_virtual_network_id"] == "${azurerm_virtual_network.shape_spoke.id}"
    diagram["nodes"][-2]["iac"]["address"] = "10.0.0.0/16"
    report = client.post("/ext/archetype_studio/api/iac/preview", json=payload).get_json()["report"]
    assert not report["can_export"]
    assert any("must not overlap" in " ".join(issue["messages"]) for issue in report["issues"])


def network_security_diagram():
    diagram = configured_diagram()
    diagram["nodes"][2]["iac"]["nsg"] = "nsg"
    diagram["nodes"].extend([
        {"id": "rule", "kind": "nsg-rule", "label": "HTTPS", "iac": {
            "name": "allow-https", "nsg": "nsg", "priority": "100", "direction": "Inbound",
            "access": "Allow", "protocol": "Tcp", "source_port": "*", "destination_port": "443",
            "source_address": "VirtualNetwork", "destination_address": "10.0.1.0/24"}},
        {"id": "zone", "kind": "private-dns-zone", "label": "Blob DNS", "iac": {
            "name": "privatelink.blob.core.windows.net", "resource_group": "rg"}},
        {"id": "link", "kind": "private-dns-link", "label": "VNet link", "iac": {
            "name": "vnet-link", "zone": "zone", "vnet": "vnet"}},
        {"id": "endpoint", "kind": "private-endpoint", "label": "Blob endpoint", "iac": {
            "name": "blob-endpoint", "location": "eastus", "resource_group": "rg",
            "subnet": "sub", "storage": "storage", "zone": "zone", "subresource": "blob"}},
    ])
    return diagram


def test_network_security_private_endpoint_and_dns_export(tmp_path):
    client = make_client(tmp_path)
    result = client.post("/ext/archetype_studio/api/iac/preview",
                         json={"diagram": network_security_diagram(), "mode": "validated"})
    report = result.get_json()["report"]
    assert report["can_export"], report["issues"]
    resources = report["terraform"]["resource"]
    assoc = resources["azurerm_subnet_network_security_group_association"]["shape_sub"]
    assert assoc["network_security_group_id"] == "${azurerm_network_security_group.shape_nsg.id}"
    rule = resources["azurerm_network_security_rule"]["shape_rule"]
    assert (rule["priority"], rule["destination_port_range"], rule["access"]) == (100, "443", "Allow")
    endpoint = resources["azurerm_private_endpoint"]["shape_endpoint"]
    assert endpoint["private_service_connection"][0]["subresource_names"] == ["blob"]
    assert endpoint["private_dns_zone_group"][0]["private_dns_zone_ids"] == ["${azurerm_private_dns_zone.shape_zone.id}"]
    assert resources["azurerm_private_dns_zone_virtual_network_link"]["shape_link"]["registration_enabled"] is False


def test_network_security_invalid_references_and_rules_are_not_exported(tmp_path):
    client = make_client(tmp_path)
    diagram = network_security_diagram()
    diagram["nodes"][-4]["iac"]["destination_port"] = "99999"
    diagram["nodes"][-3]["iac"]["name"] = "privatelink.file.core.windows.net"
    payload = {"diagram": diagram, "mode": "draft"}
    report = client.post("/ext/archetype_studio/api/iac/preview", json=payload).get_json()["report"]
    assert {issue["id"] for issue in report["issues"]} == {"rule", "endpoint"}
    assert "azurerm_private_endpoint" not in report["terraform"]["resource"]
    assert "azurerm_network_security_rule" not in report["terraform"]["resource"]
    assert client.post("/ext/archetype_studio/api/iac/export",
                       json={"diagram": diagram, "mode": "validated"}).status_code == 422


def test_invalid_nsg_blocks_subnet_and_dependent_endpoint(tmp_path):
    client = make_client(tmp_path)
    diagram = network_security_diagram()
    diagram["nodes"][4]["iac"]["location"] = "INVALID"
    report = client.post("/ext/archetype_studio/api/iac/preview",
                         json={"diagram": diagram, "mode": "draft"}).get_json()["report"]
    ids = {issue["id"] for issue in report["issues"]}
    assert {"nsg", "sub", "rule", "endpoint"} <= ids
    assert "azurerm_subnet" not in report["terraform"]["resource"]


def test_duplicate_rule_priority_and_dns_link_blocked(tmp_path):
    client = make_client(tmp_path)
    diagram = network_security_diagram()
    rule = dict(diagram["nodes"][-4])
    rule["id"] = "other-rule"
    rule["iac"] = {**rule["iac"], "name": "other-rule", "priority": "0100"}
    link = dict(diagram["nodes"][-2])
    link["id"] = "other-link"
    link["iac"] = {**link["iac"], "name": "other-link"}
    diagram["nodes"].extend([rule, link])
    report = client.post("/ext/archetype_studio/api/iac/preview",
                         json={"diagram": diagram, "mode": "validated"}).get_json()["report"]
    assert not report["can_export"]
    assert {"rule", "other-rule", "link", "other-link"} <= {issue["id"] for issue in report["issues"]}


def test_missing_dns_link_is_reported(tmp_path):
    diagram = network_security_diagram()
    diagram["nodes"] = [node for node in diagram["nodes"] if node["id"] != "link"]
    report = make_client(tmp_path).post("/ext/archetype_studio/api/iac/preview",
                                       json={"diagram": diagram, "mode": "validated"}).get_json()["report"]
    assert report["can_export"]
    assert any("no matching DNS link" in warning for warning in report["warnings"])

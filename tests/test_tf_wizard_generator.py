import io
import zipfile

import pytest

from tf_wizard.generator import generate_module_zip, tf_type_from_spec


def _read_archive(spec):
    archive = zipfile.ZipFile(io.BytesIO(generate_module_zip(spec)))
    return {name: archive.read(name).decode("utf-8") for name in archive.namelist()}


def test_generates_escaped_strings_and_nested_terraform_blocks():
    files = _read_archive({
        "module_name": "guided-starter",
        "providers": [{"name": "azurerm", "source": "hashicorp/azurerm", "version": ">= 4.0.0"}],
        "resources": [{
            "type": "azurerm_virtual_machine_extension",
            "name": "odbc_setup",
            "attributes": {
                "settings": '{"commandToExecute":"powershell -NoProfile -Command Write-Output OdbcSetup-Review-Required"}',
                "protected_settings": {"__tf_block": {"script": "line one\nline two"}}
            }
        }]
    })

    assert 'provider "azurerm" {\n  features {}\n}' in files["guided-starter/versions.tf"]
    assert 'settings = "{\\"commandToExecute\\":\\"powershell -NoProfile -Command Write-Output OdbcSetup-Review-Required\\"}"' in files["guided-starter/main.tf"]
    assert 'protected_settings {\n    script = "line one\\nline two"\n  }' in files["guided-starter/main.tf"]


def test_sandbox_ci_and_hooks_are_packaged_without_apply_steps():
    files = _read_archive({
        "module_name": "sandbox",
        "pipeline": "github-actions",
        "sandbox_local": True,
        "sandbox_azure": True,
        "hooks": ["Slack"],
    })

    assert "sandbox/.github/workflows/terraform.yml" in files
    assert "terraform validate" in files["sandbox/.github/workflows/terraform.yml"]
    assert "terraform apply" not in files["sandbox/.github/workflows/terraform.yml"]
    assert "sandbox/sandbox/validate.ps1" in files
    assert "sandbox/sandbox/compose.yaml" in files
    assert "sandbox/sandbox/azure-sandbox/README.md" in files
    assert "Slack" in files["sandbox/integrations/README.md"]
    assert "does not create, apply, or destroy resources automatically" in files["sandbox/sandbox/azure-sandbox/README.md"]


def test_rejects_module_names_that_could_escape_the_archive_directory():
    with pytest.raises(ValueError, match="module_name"):
        generate_module_zip({"module_name": "../outside"})


def test_expression_allowlist_and_schema_type_mapping():
    assert tf_type_from_spec({"type": "array", "items": {"type": "number"}}) == "list(number)"
    with pytest.raises(ValueError, match="Unsupported Terraform expression"):
        _read_archive({
            "module_name": "unsafe",
            "resources": [{
                "type": "azurerm_resource_group",
                "name": "main",
                "attributes": {"name": {"__tf_expr": "file(\"secret\")"}}
            }]
        })

"""Built-in and user-defined code archetypes for editor templates."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CUSTOM_ARCHETYPES_FILE = PROJECT_ROOT / "data" / "code_archetypes_custom.json"
MAX_CUSTOM_ARCHETYPES = 50
MAX_CODE_BYTES = 100_000

BUILTIN_ARCHETYPES: list[dict[str, Any]] = [
    {
        "id": "python-cli",
        "title": "Python CLI tool",
        "category": "Application",
        "language": "python",
        "hub": "Python CLI application",
        "description": "A small command-line application with argument parsing and a clear entry point.",
        "nodes": ["CLI arguments", "Input validation", "run() core logic", "Console output"],
        "edges": [
            {"from": "CLI arguments", "to": "Input validation"},
            {"from": "Input validation", "to": "run() core logic"},
            {"from": "run() core logic", "to": "Console output"},
        ],
        "code": '''"""A small command-line tool."""
import argparse


def run(name: str) -> str:
    return f"Hello, {name}!"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="MasterChief")
    args = parser.parse_args()
    print(run(args.name))


if __name__ == "__main__":
    main()
''',
    },
    {
        "id": "flask-json-api",
        "title": "Flask JSON API",
        "category": "Application",
        "language": "python",
        "hub": "Flask JSON API",
        "description": "A minimal JSON endpoint with input validation and a health check.",
        "nodes": ["GET /health route", "POST /echo route", "Request validation", "JSON response"],
        "edges": [
            {"from": "POST /echo route", "to": "Request validation"},
            {"from": "Request validation", "to": "JSON response"},
            {"from": "GET /health route", "to": "JSON response", "label": "health response"},
        ],
        "code": '''"""Minimal Flask JSON API archetype."""
from flask import Flask, jsonify, request

app = Flask(__name__)


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/echo")
def echo():
    payload = request.get_json(silent=True) or {}
    message = payload.get("message")
    if not isinstance(message, str) or not message.strip():
        return jsonify({"error": "message must be a non-empty string"}), 400
    return jsonify({"message": message.strip()})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
''',
    },
    {
        "id": "terraform-azure-network",
        "title": "Azure network foundation",
        "category": "Infrastructure",
        "language": "terraform",
        "hub": "Azure network deployment",
        "description": "A Terraform starter for an Azure resource group and virtual network.",
        "nodes": ["Terraform configuration", "Azure provider", "Resource group", "Virtual network"],
        "edges": [
            {"from": "Terraform configuration", "to": "Azure provider"},
            {"from": "Azure provider", "to": "Resource group"},
            {"from": "Resource group", "to": "Virtual network"},
        ],
        "code": '''terraform {
  required_version = ">= 1.5.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
}

variable "location" {
  type        = string
  description = "Azure region for the network resources."
  default     = "eastus"
}

resource "azurerm_resource_group" "main" {
  name     = "mc-network-rg"
  location = var.location
}

resource "azurerm_virtual_network" "main" {
  name                = "mc-vnet"
  address_space       = ["10.20.0.0/16"]
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
}
''',
    },
    {
        "id": "github-actions-python-ci",
        "title": "GitHub Actions Python CI",
        "category": "Automation",
        "language": "yaml",
        "hub": "Python CI workflow",
        "description": "A basic Python lint-and-test workflow for pushes and pull requests.",
        "nodes": ["Push / pull request trigger", "GitHub-hosted runner", "Python and dependencies", "pytest suite"],
        "edges": [
            {"from": "Push / pull request trigger", "to": "GitHub-hosted runner"},
            {"from": "GitHub-hosted runner", "to": "Python and dependencies"},
            {"from": "Python and dependencies", "to": "pytest suite"},
        ],
        "code": '''name: Python CI

on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python -m pip install -r requirements.txt
      - run: python -m pytest -q
''',
    },
    {
        "id": "powershell-admin-task",
        "title": "PowerShell admin task",
        "category": "Automation",
        "language": "powershell",
        "hub": "Parameterized PowerShell task",
        "description": "A parameterized PowerShell task with validation and explicit error handling.",
        "nodes": ["Required parameters", "Input validation", "Administrative action", "Error handling and result"],
        "edges": [
            {"from": "Required parameters", "to": "Input validation"},
            {"from": "Input validation", "to": "Administrative action"},
            {"from": "Administrative action", "to": "Error handling and result"},
        ],
        "code": '''[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateNotNullOrEmpty()]
    [string]$Name
)

$ErrorActionPreference = 'Stop'

try {
    Write-Output "Processing: $Name"
    # Add the intended operation here.
}
catch {
    Write-Error "Task failed: $($_.Exception.Message)"
    exit 1
}
''',
    },
    {
        "id": "azure-arm-resource",
        "title": "Azure ARM resource template",
        "category": "Infrastructure",
        "language": "json",
        "hub": "Azure ARM deployment template",
        "description": "A minimal ARM deployment template with a location parameter.",
        "nodes": ["Location parameter", "ARM deployment template", "Resource declarations", "Deployment output"],
        "edges": [
            {"from": "Location parameter", "to": "ARM deployment template"},
            {"from": "ARM deployment template", "to": "Resource declarations"},
            {"from": "Resource declarations", "to": "Deployment output"},
        ],
        "code": '''{
  "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
  "contentVersion": "1.0.0.0",
  "parameters": {
    "location": {
      "type": "string",
      "defaultValue": "[resourceGroup().location]"
    }
  },
  "resources": [],
  "outputs": {
    "deploymentLocation": {
      "type": "string",
      "value": "[parameters('location')]"
    }
  }
}
''',
    },
]


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")[:60]


def _load_custom(path: Path = CUSTOM_ARCHETYPES_FILE) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Custom archetype storage must contain a JSON list.")
    return [item for item in data if isinstance(item, dict)]


def list_archetypes(path: Path = CUSTOM_ARCHETYPES_FILE) -> list[dict[str, Any]]:
    return [*BUILTIN_ARCHETYPES, *_load_custom(path)]


def save_custom_archetype(payload: dict[str, Any], path: Path = CUSTOM_ARCHETYPES_FILE) -> dict[str, Any]:
    title = str(payload.get("title", "")).strip()
    language = str(payload.get("language", "")).strip().casefold()
    code = payload.get("code")
    category = str(payload.get("category", "Custom")).strip() or "Custom"
    description = str(payload.get("description", "")).strip()
    hub = str(payload.get("hub") or title).strip()
    nodes = payload.get("nodes")
    edges = payload.get("edges", [])

    if not title or len(title) > 80:
        raise ValueError("Archetype title must be between 1 and 80 characters.")
    if not re.fullmatch(r"[a-z0-9_+#.-]{1,24}", language):
        raise ValueError("Language must be 1–24 letters, digits, or . _ + # - characters.")
    if not isinstance(code, str) or not code.strip() or len(code.encode("utf-8")) > MAX_CODE_BYTES:
        raise ValueError(f"Code must contain 1 to {MAX_CODE_BYTES} UTF-8 bytes.")
    if len(category) > 40 or len(description) > 500:
        raise ValueError("Category must be at most 40 characters and description at most 500.")
    if not hub or len(hub) > 80:
        raise ValueError("Architecture hub must be between 1 and 80 characters.")
    if not isinstance(nodes, list) or not 2 <= len(nodes) <= 12:
        raise ValueError("Provide between 2 and 12 visualization components.")
    clean_nodes = [str(node).strip() for node in nodes]
    if any(not node or len(node) > 50 for node in clean_nodes):
        raise ValueError("Each visualization component must be 1–50 characters.")
    if not isinstance(edges, list) or len(edges) > 24:
        raise ValueError("Provide no more than 24 architecture connections.")
    clean_edges: list[dict[str, str]] = []
    valid_components = {hub, *clean_nodes}
    for edge in edges:
        if not isinstance(edge, dict):
            raise ValueError("Each architecture connection must be an object.")
        source = str(edge.get("from", "")).strip()
        target = str(edge.get("to", "")).strip()
        label = str(edge.get("label", "")).strip()
        if source not in valid_components or target not in valid_components or source == target:
            raise ValueError("Architecture connection endpoints must match the hub or a component.")
        if len(label) > 40:
            raise ValueError("Architecture connection labels must be at most 40 characters.")
        clean_edges.append({"from": source, "to": target, "label": label})

    custom = _load_custom(path)
    if len(custom) >= MAX_CUSTOM_ARCHETYPES:
        raise ValueError(f"A maximum of {MAX_CUSTOM_ARCHETYPES} custom archetypes is supported.")
    archetype_id = "custom-" + _slug(title)
    all_ids = {item["id"] for item in BUILTIN_ARCHETYPES}
    all_ids.update(str(item.get("id")) for item in custom)
    all_titles = {
        str(item.get("title", "")).strip().casefold()
        for item in [*BUILTIN_ARCHETYPES, *custom]
    }
    if archetype_id in all_ids or title.casefold() in all_titles:
        raise ValueError("An archetype with this title already exists.")

    archetype = {
        "id": archetype_id,
        "title": title,
        "category": category,
        "language": language,
        "hub": hub,
        "description": description,
        "nodes": clean_nodes,
        "edges": clean_edges,
        "code": code,
    }
    custom.append(archetype)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(custom, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)
    return archetype

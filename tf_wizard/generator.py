"""
TF Wizard Generator – generates Terraform module ZIP archives from a spec dict.

Public API
----------
- generate_module_zip(spec: dict) -> bytes
- tf_type_from_spec(meta: dict | str) -> str
"""

from __future__ import annotations

import io
import json
import re
import textwrap
import zipfile
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Type mapping helpers
# ---------------------------------------------------------------------------

_JS_TO_TF: Dict[str, str] = {
    "string": "string",
    "number": "number",
    "integer": "number",
    "boolean": "bool",
    "bool": "bool",
    "array": "list(string)",
    "object": "map(string)",
    "list": "list(string)",
    "map": "map(string)",
}


def tf_type_from_spec(meta: Any) -> str:
    """Convert a JSON‑schema property description (or a plain type string) to
    a Terraform type expression.

    Supports:
    * plain string type names – ``"string"`` → ``"string"``
    * dict with ``type`` key – ``{"type": "array", "items": {"type": "number"}}``
      → ``"list(number)"``
    * nested objects – ``{"type": "object", "properties": {...}}`` → ``object({...})``
    """
    if isinstance(meta, str):
        return _JS_TO_TF.get(meta.lower(), "string")

    if not isinstance(meta, dict):
        return "string"

    js_type = (meta.get("type") or "string").lower()

    # ----- array -----
    if js_type == "array":
        items = meta.get("items", {})
        inner = tf_type_from_spec(items) if isinstance(items, dict) else "string"
        return f"list({inner})"

    # ----- object with properties -----
    if js_type == "object" and isinstance(meta.get("properties"), dict):
        parts: List[str] = []
        for k, v in meta["properties"].items():
            parts.append(f"    {k} = {tf_type_from_spec(v)}")
        inner_block = "\n".join(parts)
        return f"object({{\n{inner_block}\n  }})"

    # ----- plain object (map) -----
    if js_type == "object":
        return "map(string)"

    return _JS_TO_TF.get(js_type, "string")


# ---------------------------------------------------------------------------
# Terraform file renderers
# ---------------------------------------------------------------------------

def _render_variable_block(var: dict) -> str:
    """Render a single ``variable`` block for *variables.tf*."""
    name = var.get("name", "unnamed")
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError(f"Invalid Terraform variable name: {name!r}")
    tf_type = var.get("tf_type") or tf_type_from_spec(var.get("type", "string"))
    description = var.get("description", "")
    default = var.get("default")
    sensitive = var.get("sensitive", False)
    validation = var.get("validation")

    lines = [f'variable "{name}" {{']
    lines.append(f'  type        = {tf_type}')
    if description:
        lines.append(f'  description = {json.dumps(description)}')
    if default is not None:
        lines.append(f'  default     = {_tf_value(default)}')
    if sensitive:
        lines.append("  sensitive   = true")
    if validation and isinstance(validation, dict):
        cond = validation.get("condition", "true")
        err  = validation.get("error_message", "Invalid value.")
        lines.append("  validation {")
        lines.append(f'    condition     = {cond}')
        lines.append(f'    error_message = {json.dumps(err)}')
        lines.append("  }")
    lines.append("}\n")
    return "\n".join(lines)


def _render_output_block(out: dict) -> str:
    name = out.get("name", "unnamed")
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError(f"Invalid Terraform output name: {name!r}")
    value = out.get("value", '""')
    description = out.get("description", "")
    lines = [f'output "{name}" {{']
    lines.append(f"  value       = {value}")
    if description:
        lines.append(f'  description = {json.dumps(description)}')
    lines.append("}\n")
    return "\n".join(lines)


def _tf_value(val: Any) -> str:
    """Render a Python value as a Terraform literal."""
    if isinstance(val, dict) and set(val) == {"__tf_expr"}:
        expression = val["__tf_expr"]
        if not isinstance(expression, str) or not re.fullmatch(
            r"(?:var|local|azurerm_[a-z0-9_]+|aws_[a-z0-9_]+|google_[a-z0-9_]+|data\.[a-z0-9_]+)\.[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*|file\(var\.[A-Za-z_][A-Za-z0-9_]*\)",
            expression,
        ):
            raise ValueError(f"Unsupported Terraform expression: {expression!r}")
        return expression
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, str):
        return json.dumps(val)
    if isinstance(val, list):
        inner = ", ".join(_tf_value(v) for v in val)
        return f"[{inner}]"
    if isinstance(val, dict):
        inner = ", ".join(f'{k} = {_tf_value(v)}' for k, v in val.items())
        return f"{{{inner}}}"
    return f'"{val}"'


def _render_resource_attributes(attributes: dict) -> List[str]:
    lines: List[str] = []
    for key, value in attributes.items():
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise ValueError(f"Invalid Terraform attribute name: {key!r}")
        blocks = value.get("__tf_block") if isinstance(value, dict) and set(value) == {"__tf_block"} else None
        if blocks is not None:
            if isinstance(blocks, dict):
                blocks = [blocks]
            if not isinstance(blocks, list) or not blocks:
                raise ValueError(f"Terraform block {key!r} must contain one or more objects")
            for block in blocks:
                if not isinstance(block, dict) or not block:
                    raise ValueError(f"Terraform block {key!r} must be a non-empty object")
                lines.append(f"  {key} {{")
                for block_key, block_value in block.items():
                    if not isinstance(block_key, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", block_key):
                        raise ValueError(f"Invalid Terraform block attribute: {block_key!r}")
                    lines.append(f"    {block_key} = {_tf_value(block_value)}")
                lines.append("  }")
        else:
            lines.append(f"  {key} = {_tf_value(value)}")
    return lines


# ---------------------------------------------------------------------------
# Main ZIP generator
# ---------------------------------------------------------------------------

def generate_module_zip(spec: dict) -> bytes:
    """Generate a Terraform module as an in‑memory ZIP file and return raw
    bytes.

    Expected *spec* keys:

    * ``module_name`` – name used for the root folder inside the zip
    * ``variables``   – list of variable dicts (name, type, description, default, …)
    * ``outputs``     – list of output dicts  (name, value, description)
    * ``providers``   – list of provider dicts (name, source, version)
    * ``resources``   – list of resource dicts (type, name, attributes)
    * ``backend``     – optional backend config dict
    """
    module_name: str = spec.get("module_name", "module")
    if not isinstance(module_name, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", module_name):
        raise ValueError("module_name must be 1–64 letters, numbers, underscores, or hyphens.")
    variables: List[dict] = spec.get("variables", [])
    outputs: List[dict] = spec.get("outputs", [])
    providers: List[dict] = spec.get("providers", [])
    resources: List[dict] = spec.get("resources", [])
    backend: Optional[dict] = spec.get("backend")
    pipeline = spec.get("pipeline", "")
    if not isinstance(pipeline, str) or pipeline not in {"", "github-actions", "azure-devops", "gitlab-ci"}:
        raise ValueError(f"Unsupported CI/CD template: {pipeline}")
    sandbox_local = spec.get("sandbox_local") is True
    sandbox_azure = spec.get("sandbox_azure") is True
    hooks = spec.get("hooks", [])
    if not isinstance(hooks, list) or any(not isinstance(hook, str) for hook in hooks):
        raise ValueError("hooks must be a list of hook names.")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        prefix = f"{module_name}/"

        # --- versions.tf (terraform block) ---
        tf_block_lines = ['terraform {']
        if providers:
            tf_block_lines.append("  required_providers {")
            for p in providers:
                pname = p.get("name", "aws")
                source = p.get("source", f"hashicorp/{pname}")
                version = p.get("version", ">= 1.0")
                if not isinstance(pname, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", pname):
                    raise ValueError(f"Invalid Terraform provider name: {pname!r}")
                if not isinstance(source, str) or not re.fullmatch(r"[A-Za-z0-9.-]+/[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)?", source):
                    raise ValueError(f"Invalid Terraform provider source: {source!r}")
                if not isinstance(version, str) or any(character in version for character in '"\r\n'):
                    raise ValueError("Terraform provider version must be a single-line constraint.")
                tf_block_lines.append(f"    {pname} = {{")
                tf_block_lines.append(f"      source  = {json.dumps(source)}")
                tf_block_lines.append(f"      version = {json.dumps(version)}")
                tf_block_lines.append("    }")
            tf_block_lines.append("  }")
        if backend:
            btype = backend.get("type", "local")
            if not isinstance(btype, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", btype):
                raise ValueError(f"Invalid Terraform backend type: {btype!r}")
            tf_block_lines.append(f'  backend "{btype}" {{')
            for bk, bv in backend.items():
                if bk == "type":
                    continue
                if not isinstance(bk, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", bk):
                    raise ValueError(f"Invalid Terraform backend setting: {bk!r}")
                if not isinstance(bv, str):
                    raise ValueError(f"Terraform backend setting {bk!r} must be a string.")
                tf_block_lines.append(f"    {bk} = {json.dumps(bv)}")
            tf_block_lines.append("  }")
        tf_block_lines.append("}\n")
        if any(provider.get("name") == "azurerm" for provider in providers):
            tf_block_lines.extend(['provider "azurerm" {', "  features {}", "}\n"])
        zf.writestr(prefix + "versions.tf", "\n".join(tf_block_lines))

        # --- variables.tf ---
        var_blocks = [_render_variable_block(v) for v in variables]
        zf.writestr(prefix + "variables.tf", "\n".join(var_blocks) if var_blocks else "# No variables defined\n")

        # --- outputs.tf ---
        out_blocks = [_render_output_block(o) for o in outputs]
        zf.writestr(prefix + "outputs.tf", "\n".join(out_blocks) if out_blocks else "# No outputs defined\n")

        # --- main.tf (resources) ---
        main_lines: List[str] = []
        for r in resources:
            rtype = r.get("type", "null_resource")
            rname = r.get("name", "this")
            attrs = r.get("attributes", {})
            if not isinstance(rtype, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", rtype):
                raise ValueError(f"Invalid Terraform resource type: {rtype!r}")
            if not isinstance(rname, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", rname):
                raise ValueError(f"Invalid Terraform resource name: {rname!r}")
            if not isinstance(attrs, dict):
                raise ValueError(f"Terraform resource {rname!r} attributes must be an object.")
            main_lines.append(f'resource "{rtype}" "{rname}" {{')
            main_lines.extend(_render_resource_attributes(attrs))
            main_lines.append("}\n")
        zf.writestr(prefix + "main.tf", "\n".join(main_lines) if main_lines else "# Add resources here\n")

        # --- README.md ---
        readme = textwrap.dedent(f"""\
            # {module_name}

            Terraform module generated by **MasterChief TF Wizard**.

            ## Variables

            | Name | Type | Description |
            |------|------|-------------|
            """)
        for v in variables:
            readme += f"| {v.get('name','')} | {v.get('type','string')} | {v.get('description','')} |\n"
        readme += textwrap.dedent("""\

            ## Review before use

            Generated Terraform is a starting point, not a deployment approval or a guarantee that every selected service is available in the chosen region/subscription. Check provider documentation and schema, names, quotas, CIDR overlap, identity permissions, network exposure, and all required variables. Run `terraform fmt`, `terraform validate`, and inspect `terraform plan`; no apply or destroy is generated or run automatically.

            AKS, SQL, Front Door/WAF, gateways, public IPs, and monitoring can incur ongoing charges. Estimate cost separately and use a dedicated sandbox subscription for experiments. Globally unique Azure names may need adjustment.

            AD DS, AD FS, AD CS, SOFS, and ODBC VM extensions are harmless review-required placeholders. They do not install roles, join domains, create certificates, configure clusters, or install drivers. Provide and review the appropriate scripts and credentials through approved processes before enabling any extension.
            """)
        zf.writestr(prefix + "README.md", readme)

        if pipeline == "github-actions":
            zf.writestr(prefix + ".github/workflows/terraform.yml", textwrap.dedent("""\
                name: Terraform checks
                on:
                  pull_request:
                  workflow_dispatch:
                permissions:
                  contents: read
                  id-token: write
                jobs:
                  validate-and-plan:
                    runs-on: ubuntu-latest
                    steps:
                      - uses: actions/checkout@v4
                      - uses: hashicorp/setup-terraform@v3
                      - run: terraform fmt -check -recursive
                      - run: terraform init -backend=false
                      - run: terraform validate
                      - run: terraform plan -input=false -refresh=false
                        env:
                          ARM_SUBSCRIPTION_ID: ${{ secrets.ARM_SUBSCRIPTION_ID }}
                          ARM_TENANT_ID: ${{ secrets.ARM_TENANT_ID }}
                          ARM_CLIENT_ID: ${{ secrets.ARM_CLIENT_ID }}
                          ARM_USE_OIDC: "true"
            """))
        elif pipeline == "azure-devops":
            zf.writestr(prefix + "azure-pipelines.yml", textwrap.dedent("""\
                trigger:
                  - main
                pr:
                  - main
                pool:
                  vmImage: ubuntu-latest
                steps:
                  - checkout: self
                  - script: terraform fmt -check -recursive
                    displayName: Terraform format
                  - script: terraform init -backend=false
                    displayName: Terraform init (no remote backend)
                  - script: terraform validate
                    displayName: Terraform validate
                  - script: terraform plan -input=false -refresh=false
                    displayName: Terraform plan (configure Azure service connection first)
            """))
        elif pipeline == "gitlab-ci":
            zf.writestr(prefix + ".gitlab-ci.yml", textwrap.dedent("""\
                stages: [validate, plan]
                terraform-validate:
                  image: hashicorp/terraform:1.9
                  stage: validate
                  script:
                    - terraform fmt -check -recursive
                    - terraform init -backend=false
                    - terraform validate
                terraform-plan:
                  image: hashicorp/terraform:1.9
                  stage: plan
                  script:
                    - terraform init -backend=false
                    - terraform plan -input=false -refresh=false
                  rules:
                    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'
            """))

        if sandbox_local:
            zf.writestr(prefix + "sandbox/README.md", textwrap.dedent("""\
                # Local sandbox

                This workflow validates Terraform locally and optionally starts Azurite for Azure Storage-dependent development. Azurite emulates Azure Storage only; it does not emulate Azure networking, AKS, SQL, Active Directory, ExpressRoute, or the other Azure control-plane services.

                ## Validate without Azure credentials

                Run `./validate.sh` on macOS/Linux or `.\validate.ps1` on Windows. Provider plugins must be downloadable. These commands run `fmt`, `init -backend=false`, and `validate`; they do not create Azure resources.

                ## Optional local plan

                `terraform plan -refresh=false` may still require Azure provider authentication, subscription settings, valid variables, and provider-specific lookups. Configure credentials only in your shell or approved secret store. Do not put credentials in `.tf` files.

                ## Azurite

                Run `docker compose -f compose.yaml up` from this directory. The emulator binds only to localhost and is for development/test data only. Do not point production clients at it.
            """))
            zf.writestr(prefix + "sandbox/validate.sh", textwrap.dedent("""\
                #!/usr/bin/env sh
                set -eu
                cd "$(dirname "$0")/.."
                terraform fmt -check -recursive
                terraform init -backend=false
                terraform validate
                printf '%s\\n' 'Validation completed. For an authenticated plan, run terraform plan -refresh=false after setting approved Azure credentials.'
            """))
            zf.writestr(prefix + "sandbox/validate.ps1", textwrap.dedent("""\
                $ErrorActionPreference = 'Stop'
                Set-Location (Split-Path -Parent $PSScriptRoot)
                terraform fmt -check -recursive
                terraform init -backend=false
                terraform validate
                Write-Host 'Validation completed. For an authenticated plan, run terraform plan -refresh=false after setting approved Azure credentials.'
            """))
            zf.writestr(prefix + "sandbox/compose.yaml", textwrap.dedent("""\
                services:
                  azurite:
                    image: mcr.microsoft.com/azure-storage/azurite:3.33.0
                    command: azurite --blobHost 0.0.0.0 --queueHost 0.0.0.0 --tableHost 0.0.0.0
                    ports:
                      - "127.0.0.1:10000:10000"
                      - "127.0.0.1:10001:10001"
                      - "127.0.0.1:10002:10002"
                    volumes:
                      - azurite-data:/data
                volumes:
                  azurite-data:
            """))

        if sandbox_azure:
            zf.writestr(prefix + "sandbox/azure-sandbox/README.md", textwrap.dedent("""\
                # Isolated Azure sandbox

                This module is a starting point for an isolated, explicitly approved Azure sandbox. It does not create, apply, or destroy resources automatically.

                1. Use a dedicated non-production subscription or a dedicated sandbox resource group and least-privilege identity.
                2. Set a unique environment/name prefix, region, owner, and cost-center tags; confirm every selected resource and its estimated cost.
                3. Configure authentication through Azure CLI/OIDC or an approved secret store. Never add secrets to Terraform source or commit state files.
                4. Run `terraform init`, `terraform validate`, and `terraform plan`; inspect the plan and provider/API versions.
                5. Apply only after an authorized person reviews and explicitly approves the plan.
                6. Track budgets/alerts and clean up only resources that the sandbox owner has positively identified as disposable.

                AKS, SQL, public endpoints, gateways, and logging can create ongoing charges. A plan is not a cost estimate and can require cloud authentication.
            """))

        if hooks:
            hook_list = "\n".join(f"- {hook}" for hook in hooks)
            zf.writestr(prefix + "integrations/README.md", textwrap.dedent(f"""\
                # Optional integration hooks

                Selected integrations:

                {hook_list}

                Store webhook URLs/tokens as protected CI variables or in a secret manager. This starter does not send notifications, create third-party accounts, or configure external services automatically. Add and review provider-specific workflow steps before enabling a hook.
            """))

    return buf.getvalue()

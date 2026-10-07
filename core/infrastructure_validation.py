"""Validation for cloud network designs and Azure resource names."""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Mapping
from typing import Any


_AZURE_RESOURCE_GROUP = re.compile(r"^[A-Za-z0-9._()-]{1,90}$")
_AZURE_VNET = re.compile(r"^[A-Za-z0-9._-]{2,64}$")
_AZURE_SUBNET = re.compile(r"^[A-Za-z0-9._-]{1,80}$")
_AZURE_STORAGE_ACCOUNT = re.compile(r"^[a-z0-9]{3,24}$")
_AZURE_AKS_CLUSTER = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
_AZURE_SCOPE = re.compile(
    r"^/subscriptions/[0-9a-fA-F-]{36}"
    r"(?:/resourceGroups/[^/]+)?"
    r"(?:/providers/[^/]+(?:/[^/]+/[^/]+)*)?$",
    re.IGNORECASE,
)
_BROAD_AZURE_ROLES = {"owner", "user access administrator"}


def _issue(severity: str, code: str, path: str, message: str) -> dict[str, str]:
    return {
        "severity": severity,
        "code": code,
        "path": path,
        "message": message,
    }


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _network(value: Any, path: str, issues: list[dict[str, str]]) -> ipaddress.IPv4Network | ipaddress.IPv6Network | None:
    if not isinstance(value, str) or not value.strip():
        issues.append(_issue("error", "cidr.required", path, "CIDR is required."))
        return None
    try:
        return ipaddress.ip_network(value.strip(), strict=True)
    except ValueError:
        issues.append(_issue("error", "cidr.invalid", path, "Enter a canonical network CIDR, such as 10.20.0.0/16."))
        return None


def _validate_names(design: Mapping[str, Any], issues: list[dict[str, str]]) -> None:
    names = _mapping(design.get("names"))
    validators = {
        "resource_group": (_AZURE_RESOURCE_GROUP, "Azure resource group names allow 1-90 letters, digits, periods, underscores, parentheses, or hyphens."),
        "virtual_network": (_AZURE_VNET, "Azure virtual network names must be 2-64 characters and contain only letters, digits, periods, underscores, or hyphens."),
        "subnet": (_AZURE_SUBNET, "Azure subnet names must be 1-80 characters and contain only letters, digits, periods, underscores, or hyphens."),
        "storage_account": (_AZURE_STORAGE_ACCOUNT, "Storage account names must be 3-24 lowercase letters or digits."),
        "aks_cluster": (_AZURE_AKS_CLUSTER, "AKS cluster names must be 1-63 alphanumeric characters or hyphens, and start and end with an alphanumeric character."),
    }
    for resource_type, (pattern, message) in validators.items():
        value = names.get(resource_type)
        if value is None:
            continue
        path = f"names.{resource_type}"
        if not isinstance(value, str) or not pattern.fullmatch(value):
            issues.append(_issue("error", "name.invalid", path, message))


def _validate_networks(design: Mapping[str, Any], issues: list[dict[str, str]]) -> None:
    networks = design.get("virtual_networks", [])
    if not isinstance(networks, list):
        issues.append(_issue("error", "network.list_required", "virtual_networks", "Virtual networks must be a list."))
        return
    if not networks:
        issues.append(_issue("error", "network.required", "virtual_networks", "Add at least one virtual network to validate the design."))
        return

    parsed_networks: list[tuple[str, ipaddress.IPv4Network | ipaddress.IPv6Network]] = []
    seen_names: set[str] = set()
    for index, raw_network in enumerate(networks):
        path = f"virtual_networks[{index}]"
        network_data = _mapping(raw_network)
        name = network_data.get("name")
        if not isinstance(name, str) or not _AZURE_VNET.fullmatch(name):
            issues.append(_issue("error", "name.invalid", f"{path}.name", "Virtual network names must be 2-64 characters and contain only letters, digits, periods, underscores, or hyphens."))
        elif name.casefold() in seen_names:
            issues.append(_issue("error", "name.duplicate", f"{path}.name", f"Virtual network name '{name}' is duplicated."))
        else:
            seen_names.add(name.casefold())

        network = _network(network_data.get("cidr"), f"{path}.cidr", issues)
        if network is not None:
            for other_name, other_network in parsed_networks:
                if network.version == other_network.version and network.overlaps(other_network):
                    issues.append(_issue("error", "cidr.overlap", f"{path}.cidr", f"Network overlaps virtual network '{other_name}'."))
            parsed_networks.append((str(name or index), network))

        subnets = network_data.get("subnets", [])
        if not isinstance(subnets, list):
            issues.append(_issue("error", "subnet.list_required", f"{path}.subnets", "Subnets must be a list."))
            continue
        parsed_subnets: list[tuple[str, ipaddress.IPv4Network | ipaddress.IPv6Network]] = []
        subnet_names: set[str] = set()
        for subnet_index, raw_subnet in enumerate(subnets):
            subnet_path = f"{path}.subnets[{subnet_index}]"
            subnet_data = _mapping(raw_subnet)
            subnet_name = subnet_data.get("name")
            if not isinstance(subnet_name, str) or not _AZURE_SUBNET.fullmatch(subnet_name):
                issues.append(_issue("error", "name.invalid", f"{subnet_path}.name", "Subnet names must be 1-80 characters and contain only letters, digits, periods, underscores, or hyphens."))
            elif subnet_name.casefold() in subnet_names:
                issues.append(_issue("error", "name.duplicate", f"{subnet_path}.name", f"Subnet name '{subnet_name}' is duplicated within the virtual network."))
            else:
                subnet_names.add(subnet_name.casefold())

            subnet_network = _network(subnet_data.get("cidr"), f"{subnet_path}.cidr", issues)
            if subnet_network is None:
                continue
            if network is not None and (
                subnet_network.version != network.version or not subnet_network.subnet_of(network)
            ):
                issues.append(_issue("error", "subnet.outside_vnet", f"{subnet_path}.cidr", "Subnet CIDR must be contained in its virtual network CIDR."))
            for other_name, other_subnet in parsed_subnets:
                if subnet_network.version == other_subnet.version and subnet_network.overlaps(other_subnet):
                    issues.append(_issue("error", "subnet.overlap", f"{subnet_path}.cidr", f"Subnet overlaps subnet '{other_name}' in this virtual network."))
            parsed_subnets.append((str(subnet_name or subnet_index), subnet_network))


def _validate_role_assignments(design: Mapping[str, Any], issues: list[dict[str, str]]) -> None:
    assignments = design.get("role_assignments", [])
    if not isinstance(assignments, list):
        issues.append(_issue("error", "rbac.list_required", "role_assignments", "Role assignments must be a list."))
        return

    seen: set[tuple[str, str, str]] = set()
    for index, raw_assignment in enumerate(assignments):
        path = f"role_assignments[{index}]"
        assignment = _mapping(raw_assignment)
        principal_id = assignment.get("principal_id")
        role = assignment.get("role")
        scope = assignment.get("scope")
        if not isinstance(principal_id, str) or not principal_id.strip():
            issues.append(_issue("error", "rbac.principal_required", f"{path}.principal_id", "Principal ID is required."))
        if not isinstance(role, str) or not role.strip():
            issues.append(_issue("error", "rbac.role_required", f"{path}.role", "Role name or role definition ID is required."))
        if not isinstance(scope, str) or not _AZURE_SCOPE.fullmatch(scope):
            issues.append(_issue("error", "rbac.scope_invalid", f"{path}.scope", "Scope must be a valid Azure subscription, resource-group, or resource ID."))
        if not all(isinstance(value, str) and value.strip() for value in (principal_id, role, scope)):
            continue

        key = (principal_id.casefold(), role.casefold(), scope.casefold())
        if key in seen:
            issues.append(_issue("error", "rbac.assignment_duplicate", path, "Duplicate principal, role, and scope assignment."))
        seen.add(key)
        if role.casefold() in _BROAD_AZURE_ROLES:
            issues.append(_issue("warning", "rbac.broad_role", f"{path}.role", f"'{role}' grants broad privileges; verify least-privilege requirements."))


def validate_infrastructure_design(design: Any) -> list[dict[str, str]]:
    """Return actionable errors and warnings for a proposed Azure design."""
    if not isinstance(design, Mapping):
        return [_issue("error", "design.object_required", "$", "Design must be a JSON object.")]

    issues: list[dict[str, str]] = []
    _validate_names(design, issues)
    _validate_networks(design, issues)
    _validate_role_assignments(design, issues)
    return issues

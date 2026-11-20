"""Translate explicitly configured whiteboard resources to Terraform JSON."""
from __future__ import annotations

import ipaddress
import json
import re
from collections import Counter

SUPPORTED = {"resource-group", "network", "subnet", "peering", "nsg", "storage",
             "nsg-rule", "private-endpoint", "private-dns-zone", "private-dns-link"}
ANNOTATIONS = {"boundary", "note", "decision", "user", "external"}
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,78}[A-Za-z0-9_]$")
LOCATION = re.compile(r"^[a-z][a-z0-9]{1,39}$")
STORAGE = re.compile(r"^[a-z0-9]{3,24}$")
SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
SKU = {"Standard_LRS", "Standard_ZRS", "Standard_GRS", "Standard_RAGRS", "Standard_GZRS", "Standard_RAGZRS"}
STORAGE_DNS = {name: f"privatelink.{name}.core.windows.net" for name in ("blob", "file", "queue", "table", "dfs")}


def _port(value):
    if value == "*":
        return True
    if not isinstance(value, str) or not re.fullmatch(r"\d{1,5}(?:-\d{1,5})?", value):
        return False
    bounds = [int(part) for part in value.split("-")]
    return all(0 <= port <= 65535 for port in bounds) and bounds[0] <= bounds[-1]


def _address(value):
    if value in {"*", "VirtualNetwork", "AzureLoadBalancer", "Internet"}:
        return True
    try:
        ipaddress.ip_network(value, strict=False)
        return True
    except ValueError:
        return False


def build(diagram: dict, mode: str) -> dict:
    if mode not in {"draft", "validated"}:
        raise ValueError("Choose draft or validated mode.")
    if not isinstance(diagram, dict) or diagram.get("version") != 1:
        raise ValueError("Invalid diagram version.")
    nodes = diagram.get("nodes")
    edges = diagram.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list) or len(nodes) > 300 or len(edges) > 600:
        raise ValueError("Invalid diagram nodes or connections.")
    if any(not isinstance(node, dict) or not isinstance(node.get("id"), str)
           or not SAFE_ID.fullmatch(node["id"]) or not isinstance(node.get("kind"), str) for node in nodes):
        raise ValueError("Every shape needs a valid ID and type.")
    by_id = {node["id"]: node for node in nodes}
    if len(by_id) != len(nodes):
        raise ValueError("Shape IDs must be unique.")
    if len({ident.replace("-", "_") for ident in by_id}) != len(by_id):
        raise ValueError("Shape IDs collide when converted to Terraform identifiers.")

    issues: dict[str, list[str]] = {}
    configs = {}
    networks = {}
    for node in nodes:
        kind, ident = node["kind"], node["id"]
        if kind in ANNOTATIONS:
            continue
        errors: list[str] = []
        issues[ident] = errors
        if kind not in SUPPORTED:
            errors.append(f"Unsupported shape type: {kind}.")
            continue
        cfg = node.get("iac")
        if not isinstance(cfg, dict):
            errors.append("Configure this shape in the IaC inspector.")
            continue
        if any(not isinstance(key, str) or not isinstance(value, str) for key, value in cfg.items()):
            errors.append("Configuration fields must contain text values.")
            continue
        configs[ident] = cfg
        name = cfg.get("name")
        if not isinstance(name, str) or not (STORAGE.fullmatch(name) if kind == "storage" else NAME.fullmatch(name)):
            errors.append("Enter a valid Azure resource name" + (" (3–24 lowercase letters and digits)." if kind == "storage" else "."))
        if kind in {"resource-group", "network", "nsg", "storage", "private-endpoint"}:
            if not isinstance(cfg.get("location"), str) or not LOCATION.fullmatch(cfg["location"]):
                errors.append("Enter an Azure region code, such as eastus.")
        if kind == "storage" and cfg.get("sku") not in SKU:
            errors.append("Select a supported storage redundancy SKU.")
        if kind == "private-dns-zone" and name not in STORAGE_DNS.values():
            errors.append("Select a supported Azure Storage private DNS zone.")
        if kind == "private-endpoint" and cfg.get("subresource") not in STORAGE_DNS:
            errors.append("Select a supported Azure Storage subresource.")
        if kind == "nsg-rule":
            priority = cfg.get("priority", "")
            if not re.fullmatch(r"\d{1,4}", priority) or not 100 <= int(priority or "0") <= 4096:
                errors.append("Priority must be between 100 and 4096.")
            for field, values in {"direction": {"Inbound", "Outbound"}, "access": {"Allow", "Deny"},
                                  "protocol": {"Tcp", "Udp", "Icmp", "Esp", "Ah", "*"}}.items():
                if cfg.get(field) not in values:
                    errors.append(f"Select a valid {field}.")
            for field in ("source_port", "destination_port"):
                if not _port(cfg.get(field, "")):
                    errors.append(f"Enter a valid {field.replace('_', ' ')}: *, a port, or a range.")
            if cfg.get("protocol") in {"Icmp", "Esp", "Ah"} and (
                    cfg.get("source_port") != "*" or cfg.get("destination_port") != "*"):
                errors.append("ICMP, ESP and AH rules must use * for both port ranges.")
            for field in ("source_address", "destination_address"):
                if not _address(cfg.get(field, "")):
                    errors.append(f"Enter a valid {field.replace('_', ' ')}: IP, CIDR, *, or supported service tag.")
        if kind in {"network", "subnet"}:
            try:
                address = cfg.get("address")
                if not isinstance(address, str):
                    raise ValueError()
                cidr = ipaddress.ip_network(address, strict=True)
                if cidr.version != 4:
                    raise ValueError()
                if kind == "subnet" and not 2 <= cidr.prefixlen <= 29:
                    raise ValueError()
                networks[ident] = cidr
            except ValueError:
                errors.append("Enter a valid IPv4 CIDR network address" + (" with prefix /2 through /29." if kind == "subnet" else "."))
        references = {
            "network": {"resource_group": "resource-group"},
            "nsg": {"resource_group": "resource-group"},
            "storage": {"resource_group": "resource-group"},
            "subnet": {"vnet": "network"},
            "peering": {"source": "network", "target": "network"},
            "nsg-rule": {"nsg": "nsg"},
            "private-dns-zone": {"resource_group": "resource-group"},
            "private-dns-link": {"zone": "private-dns-zone", "vnet": "network"},
            "private-endpoint": {"resource_group": "resource-group", "subnet": "subnet",
                                 "storage": "storage", "zone": "private-dns-zone"},
        }.get(kind, {})
        for field, expected in references.items():
            target = cfg.get(field)
            if not isinstance(target, str) or target not in by_id or by_id[target]["kind"] != expected:
                errors.append(f"Select a valid {field.replace('_', ' ')} ({expected}).")
        if kind == "peering" and cfg.get("source") and cfg.get("source") == cfg.get("target"):
            errors.append("Peering source and target must differ.")
        if kind == "subnet" and cfg.get("nsg"):
            target = cfg["nsg"]
            if target not in by_id or by_id[target]["kind"] != "nsg":
                errors.append("Select a valid network security group.")

    names = Counter((node["kind"], str(configs.get(node["id"], {}).get("name", "")).lower())
                    for node in nodes if node["id"] in configs and configs[node["id"]].get("name"))
    for node in nodes:
        ident, kind = node["id"], node["kind"]
        cfg = configs.get(ident, {})
        if ident not in issues or not cfg:
            continue
        if kind in {"resource-group", "storage"} and names[(kind, str(cfg.get("name", "")).lower())] > 1:
            issues[ident].append("Duplicate resource name.")
        if kind == "subnet" and ident in networks and cfg.get("vnet") in networks:
            if not networks[ident].subnet_of(networks[cfg["vnet"]]):
                issues[ident].append("Subnet CIDR must be contained in its VNet CIDR.")
    scoped_names = Counter()
    for node in nodes:
        cfg = configs.get(node["id"], {})
        if node["kind"] in {"network", "nsg", "subnet", "peering", "private-endpoint", "private-dns-link"} and cfg.get("name"):
            scope = cfg.get("resource_group") if node["kind"] in {"network", "nsg", "private-endpoint"} else cfg.get("vnet") if node["kind"] == "subnet" else cfg.get("zone") if node["kind"] == "private-dns-link" else cfg.get("source")
            scoped_names[(node["kind"], scope, str(cfg["name"]).lower())] += 1
    for node in nodes:
        cfg = configs.get(node["id"], {})
        kind = node["kind"]
        if kind in {"network", "nsg", "subnet", "peering", "private-endpoint", "private-dns-link"} and cfg.get("name"):
            scope = cfg.get("resource_group") if kind in {"network", "nsg", "private-endpoint"} else cfg.get("vnet") if kind == "subnet" else cfg.get("zone") if kind == "private-dns-link" else cfg.get("source")
            if scoped_names[(kind, scope, str(cfg["name"]).lower())] > 1:
                issues[node["id"]].append("Duplicate name within the same parent.")
    subnets = [n for n in nodes if n["kind"] == "subnet" and n["id"] in networks]
    for index, first in enumerate(subnets):
        for second in subnets[index + 1:]:
            if configs[first["id"]].get("vnet") == configs[second["id"]].get("vnet") and networks[first["id"]].overlaps(networks[second["id"]]):
                issues[first["id"]].append(f"Subnet overlaps {second['id']}.")
                issues[second["id"]].append(f"Subnet overlaps {first['id']}.")
    peers = [n for n in nodes if n["kind"] == "peering" and n["id"] in configs]
    pairs = Counter((configs[n["id"]].get("source"), configs[n["id"]].get("target")) for n in peers)
    for node in peers:
        cfg = configs[node["id"]]
        source, target = cfg.get("source"), cfg.get("target")
        if source in networks and target in networks and networks[source].overlaps(networks[target]):
            issues[node["id"]].append("Peered VNet address spaces must not overlap.")
        if source and target and pairs[(source, target)] > 1:
            issues[node["id"]].append("Only one directional peering per VNet pair is allowed.")

    rules = [n for n in nodes if n["kind"] == "nsg-rule" and n["id"] in configs]
    def priority_key(cfg):
        value = cfg.get("priority", "")
        return int(value) if re.fullmatch(r"\d{1,4}", value) else value

    priorities = Counter((configs[n["id"]].get("nsg"), configs[n["id"]].get("direction"),
                          priority_key(configs[n["id"]])) for n in rules)
    rule_names = Counter((configs[n["id"]].get("nsg"), configs[n["id"]].get("name", "").lower()) for n in rules)
    for node in rules:
        cfg = configs[node["id"]]
        if priorities[(cfg.get("nsg"), cfg.get("direction"), priority_key(cfg))] > 1:
            issues[node["id"]].append("Priority must be unique within the NSG and direction.")
        if rule_names[(cfg.get("nsg"), cfg.get("name", "").lower())] > 1:
            issues[node["id"]].append("Rule name must be unique within the NSG.")
    for node in nodes:
        ident, kind = node["id"], node["kind"]
        if ident not in configs:
            continue
        cfg = configs[ident]
        if kind == "private-endpoint":
            zone = configs.get(cfg.get("zone"), {})
            if cfg.get("subresource") in STORAGE_DNS and zone.get("name") and zone["name"] != STORAGE_DNS[cfg["subresource"]]:
                issues[ident].append("Private DNS zone must match the selected storage subresource.")
            subnet = configs.get(cfg.get("subnet"), {})
            vnet = configs.get(subnet.get("vnet"), {})
            if cfg.get("location") and vnet.get("location") and cfg["location"] != vnet["location"]:
                issues[ident].append("Private endpoint and subnet VNet must use the same region.")
        if kind == "subnet" and cfg.get("nsg") in configs:
            vnet = configs.get(cfg.get("vnet"), {})
            nsg = configs[cfg["nsg"]]
            if vnet.get("location") and nsg.get("location") and vnet["location"] != nsg["location"]:
                issues[ident].append("Subnet VNet and NSG must use the same region.")

    links = [n for n in nodes if n["kind"] == "private-dns-link" and n["id"] in configs]
    link_pairs = Counter((configs[n["id"]].get("zone"), configs[n["id"]].get("vnet")) for n in links)
    zone_names = Counter((configs[n["id"]].get("resource_group"), configs[n["id"]].get("name", "").lower())
                         for n in nodes if n["kind"] == "private-dns-zone" and n["id"] in configs)
    for node in nodes:
        ident = node["id"]
        if ident not in configs:
            continue
        cfg = configs[ident]
        if node["kind"] == "private-dns-zone" and zone_names[(cfg.get("resource_group"), cfg.get("name", "").lower())] > 1:
            issues[ident].append("Private DNS zone already exists in this resource group.")
        if node["kind"] == "private-dns-link" and link_pairs[(cfg.get("zone"), cfg.get("vnet"))] > 1:
            issues[ident].append("This DNS zone is already linked to this VNet.")

    # A generated resource may never reference a skipped or invalid resource.
    changed = True
    while changed:
        changed = False
        for ident, cfg in configs.items():
            kind = by_id[ident]["kind"]
            fields = {"network": ["resource_group"], "nsg": ["resource_group"],
                      "storage": ["resource_group"], "subnet": ["vnet"],
                      "peering": ["source", "target"], "nsg-rule": ["nsg"],
                      "private-dns-zone": ["resource_group"],
                      "private-dns-link": ["zone", "vnet"],
                      "private-endpoint": ["resource_group", "subnet", "storage", "zone"]}.get(kind, [])
            if kind == "subnet" and cfg.get("nsg"):
                fields = [*fields, "nsg"]
            for field in fields:
                ref = cfg.get(field)
                message = f"Referenced {field.replace('_', ' ')} is incomplete or invalid."
                if isinstance(ref, str) and ref in issues and issues[ref] and message not in issues[ident]:
                    issues[ident].append(message)
                    changed = True

    resources = {}
    summaries = []
    def add(kind, ident, attrs):
        resources.setdefault(kind, {})["shape_" + ident.replace("-", "_")] = attrs

    for node in nodes:
        ident, kind = node["id"], node["kind"]
        if ident not in configs or issues.get(ident):
            continue
        c = configs[ident]
        tfname = lambda ref: "shape_" + ref.replace("-", "_")
        rg_expr = lambda ref: "${azurerm_resource_group." + tfname(ref) + ".name}"
        if kind == "resource-group":
            add("azurerm_resource_group", ident, {"name": c["name"], "location": c["location"]})
        elif kind in {"network", "nsg", "storage"}:
            attrs = {"name": c["name"], "location": c["location"], "resource_group_name": rg_expr(c["resource_group"])}
            if kind == "network":
                attrs["address_space"] = [c["address"]]
            if kind == "storage":
                attrs.update({"account_tier": "Standard", "account_replication_type": c["sku"].split("_", 1)[1],
                              "min_tls_version": "TLS1_2", "allow_nested_items_to_be_public": False,
                              "public_network_access_enabled": False})
            add({"network": "azurerm_virtual_network", "nsg": "azurerm_network_security_group",
                 "storage": "azurerm_storage_account"}[kind], ident, attrs)
        elif kind == "subnet":
            parent = configs[c["vnet"]]
            add("azurerm_subnet", ident, {"name": c["name"], "resource_group_name": rg_expr(parent["resource_group"]),
                                         "virtual_network_name": "${azurerm_virtual_network." + tfname(c["vnet"]) + ".name}",
                                         "address_prefixes": [c["address"]]})
            if c.get("nsg"):
                add("azurerm_subnet_network_security_group_association", ident, {
                    "subnet_id": "${azurerm_subnet." + tfname(ident) + ".id}",
                    "network_security_group_id": "${azurerm_network_security_group." + tfname(c["nsg"]) + ".id}"})
        elif kind == "peering":
            source = configs[c["source"]]
            add("azurerm_virtual_network_peering", ident, {
                "name": c["name"], "resource_group_name": rg_expr(source["resource_group"]),
                "virtual_network_name": "${azurerm_virtual_network." + tfname(c["source"]) + ".name}",
                "remote_virtual_network_id": "${azurerm_virtual_network." + tfname(c["target"]) + ".id}",
                "allow_virtual_network_access": True, "allow_forwarded_traffic": False,
                "allow_gateway_transit": False, "use_remote_gateways": False})
        elif kind == "nsg-rule":
            parent = configs[c["nsg"]]
            add("azurerm_network_security_rule", ident, {
                "name": c["name"], "resource_group_name": rg_expr(parent["resource_group"]),
                "network_security_group_name": "${azurerm_network_security_group." + tfname(c["nsg"]) + ".name}",
                "priority": int(c["priority"]), "direction": c["direction"], "access": c["access"],
                "protocol": c["protocol"], "source_port_range": c["source_port"],
                "destination_port_range": c["destination_port"], "source_address_prefix": c["source_address"],
                "destination_address_prefix": c["destination_address"]})
        elif kind == "private-dns-zone":
            add("azurerm_private_dns_zone", ident, {"name": c["name"], "resource_group_name": rg_expr(c["resource_group"])})
        elif kind == "private-dns-link":
            zone = configs[c["zone"]]
            add("azurerm_private_dns_zone_virtual_network_link", ident, {
                "name": c["name"], "resource_group_name": rg_expr(zone["resource_group"]),
                "private_dns_zone_name": "${azurerm_private_dns_zone." + tfname(c["zone"]) + ".name}",
                "virtual_network_id": "${azurerm_virtual_network." + tfname(c["vnet"]) + ".id}",
                "registration_enabled": False})
        elif kind == "private-endpoint":
            add("azurerm_private_endpoint", ident, {
                "name": c["name"], "location": c["location"], "resource_group_name": rg_expr(c["resource_group"]),
                "subnet_id": "${azurerm_subnet." + tfname(c["subnet"]) + ".id}",
                "private_service_connection": [{"name": "storage-connection", "is_manual_connection": False,
                    "private_connection_resource_id": "${azurerm_storage_account." + tfname(c["storage"]) + ".id}",
                    "subresource_names": [c["subresource"]]}],
                "private_dns_zone_group": [{"name": "default",
                    "private_dns_zone_ids": ["${azurerm_private_dns_zone." + tfname(c["zone"]) + ".id}"]}]})
        summaries.append({"id": ident, "label": str(node.get("label", ""))[:160], "type": kind, "configuration": c})
    errors = [{"id": ident, "label": str(by_id[ident].get("label", ""))[:160], "messages": messages}
              for ident, messages in issues.items() if messages]
    if not summaries:
        errors.append({"id": "", "label": "Diagram", "messages": ["No fully configured supported resources."]})
    warnings = [
        "Diagram lines are visual only and are not translated into dependencies or network settings.",
        "Peering is directional. Add and configure a second peering shape for the reverse direction.",
        "NSGs retain Azure default rules; custom rules and subnet associations are generated only when explicitly configured.",
        "Storage public network access is disabled. Configure private endpoints, matching DNS zones, and links explicitly for every client VNet.",
        "Review provider settings, identity, security, cost, connectivity and naming; validation is not a production-readiness guarantee.",
    ]
    for node in nodes:
        if node["kind"] != "private-endpoint" or node["id"] not in configs or issues.get(node["id"]):
            continue
        cfg = configs[node["id"]]
        subnet = configs.get(cfg["subnet"], {})
        if not any(not issues.get(link["id"]) and configs[link["id"]].get("zone") == cfg["zone"]
                   and configs[link["id"]].get("vnet") == subnet.get("vnet") for link in links):
            warnings.append(f"Private endpoint {node.get('label', node['id'])}: no matching DNS link to its VNet; DNS resolution requires separate configuration.")
    return {
        "mode": mode, "can_export": bool(summaries) and (mode == "draft" or not errors),
        "issues": errors, "warnings": warnings, "resources": summaries,
        "terraform": {
            "terraform": {"required_version": ">= 1.5.0", "required_providers": {
                "azurerm": {"source": "hashicorp/azurerm", "version": "~> 4.0"}}},
            "provider": {"azurerm": {"features": [{}]}},
            "resource": resources,
        },
    }


def terraform_json(report: dict) -> str:
    return json.dumps(report["terraform"], indent=2, ensure_ascii=False) + "\n"

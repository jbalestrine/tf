# Archetype Studio

Archetype Studio is a separately loadable MasterChief feature. Restart the app
after adding it; the feature loader discovers it under `app_features` and adds
the **Archetype Studio** navigation entry. It uses the host's admin and
same-origin guards. It is also available at `/ext/archetype_studio/`.

Click a stencil to add it. Drag shapes, edit labels and dimensions in the
inspector, and use Connect to add labeled solid or dashed arrows. Boundaries
can be resized around other shapes. Pan with the Pan tool and zoom using the
mouse wheel or toolbar. The hub-and-spoke button replaces the canvas with an
editable starter; confirm replacement before continuing.

The searchable starter library covers diagramming, compute, networking, data,
integration, identity, security, operations, analytics, AI, DevOps and
governance. Its built-in entries are labeled generic shapes, not official
Azure artwork or deployable resource definitions. The library is a starter
set, not an exhaustive catalog of enterprise services.

Download JSON to back up or transfer a diagram and reopen it later. Server
saves are stored under `data/archetype_studio/` and are shared between users
who have feature access; back up this directory separately. Saving an existing
name requires explicit confirmation. The directory is Git-ignored, not
encrypted. Never store credentials or private keys in diagram content.

To use official Azure artwork, obtain SVG files from
[Microsoft's Azure icon library](https://learn.microsoft.com/en-us/azure/architecture/icons/)
and use **Import SVG / PNG**. Review Microsoft's usage terms. Imported image
data is embedded in the diagram; keep diagrams below 4 MB. Microsoft supplies
its Azure icons as SVGs, not VSSX stencils.

## Terraform export (first increment)

Select each resource group, virtual network, subnet, peering, network security
group, NSG rule, storage account, private endpoint, private DNS zone or VNet
link and complete its **IaC configuration** in the
inspector. References are explicitly selected, not inferred from drawn lines
or containment. Save the diagram to retain this configuration.

Use **Review IaC** to inspect the configuration, omissions, and limitations.
Validated mode blocks export if a resource is unsupported or incomplete.
Draft mode exports only complete supported resources and lists every omitted
shape. Draft JSON is deliberately not named `.tf.json` to avoid accidental
application; it is not deployment-ready. Validated output is `main.tf.json`
and uses AzureRM provider 4.x; supply credentials and `ARM_SUBSCRIPTION_ID`
separately. Do not store credentials in diagrams.

Peerings are directional; configure two shapes for bidirectional peering.
Lines are visual only. To associate an NSG, select it in the subnet inspector.
Add individual NSG rule shapes for explicit allow/deny rules; Azure's default
rules remain in effect. Rules support IPv4/IPv6 addresses, CIDRs, `*` and the
VirtualNetwork, AzureLoadBalancer, and Internet service tags. Priority is
unique per NSG and direction.

Storage is provisioned with public network access disabled. For private access,
add a private DNS zone for each selected storage subresource (blob, file,
queue, table or dfs), a private endpoint selecting that zone, storage account
and subnet, and DNS VNet link shapes for every client VNet that needs to resolve
the name. DNS links do not enable VM autoregistration. For ADLS Gen2, both dfs
and blob endpoints may be needed; hierarchical namespace configuration is not
yet supported. Links and endpoint configuration are explicit; the exporter
does not infer them from visual lines or guarantee connectivity. Review route
tables, DNS forwarding, NSG rules, private endpoint network policies, firewall
and client access separately. Existing Azure resources are not imported into Terraform state.
The checks cover the supported fields, not every Azure naming rule, policy,
quota, regional availability, security control or production requirement.
Review the generated report, `terraform validate` and `terraform plan`, and
obtain appropriate approval before applying. Generating code never deploys.

ARM export, VMs, databases, ExpressRoute, non-storage private endpoints, Entra ID, native
Visio stencil import and Visio export are not yet implemented. In particular,
the existing architecture export does
not preserve whiteboard positions or image artwork and is not offered here as
a faithful Visio export.

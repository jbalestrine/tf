# Reference example supplied by the project owner.
# This file is indexed for Echo's local Terraform examples; it is not wired into deployment.
# Review provider/API compatibility, subnet sizing, DNS resolution, and environment-specific
# values before adapting it for a real Azure deployment.

# ==============================================================================
# 1. TERRAFORM & PROVIDER CONFIGURATION
# ==============================================================================
terraform {
  required_version = ">= 1.7.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

provider "azurerm" {
  features {
    resource_group {
      prevent_deletion_if_contains_resources = true
    }
    key_vault {
      purge_soft_delete_on_destroy    = false
      recover_soft_deleted_key_vaults = true
    }
  }
}

# ==============================================================================
# 2. VARIABLES SCHEMA
# ==============================================================================
variable "azure_region" {
  type        = string
  description = "Target geographical cloud data center deployment quadrant."
  default     = "eastus2"
}

variable "enterprise_prefix" {
  type        = string
  description = "Globally unique 3-4 alphanumeric identifier matching corporate namespace conventions."
  default     = "corp"
}

variable "environment" {
  type        = string
  description = "Target operational lifecycle environment matrix label."
  default     = "prod"
}

variable "enable_immutability_locks" {
  type        = bool
  description = "Toggle governance layer management constraints."
  default     = true
}

variable "global_tags" {
  type        = map(string)
  description = "Strict corporate cost-center tracking tracking labels."
  default = {
    DeploymentEngine = "Terraform-v1.x"
    Classification   = "Highly-Confidential"
    Architecture     = "Hub-Spoke-PrivateLink"
    CostCenter       = "FinOps-Enterprise-Core"
  }
}

# ==============================================================================
# 3. BASE RESOURCE CONTAINER
# ==============================================================================
resource "azurerm_resource_group" "core" {
  name     = "rg-${var.enterprise_prefix}-${var.environment}-core"
  location = var.azure_region
  tags     = var.global_tags
}

# ==============================================================================
# 4. HUB-SPOKE NETWORKING TOPOLOGY
# ==============================================================================
# Shared Infrastructure Hub Virtual Network
resource "azurerm_virtual_network" "hub" {
  name                = "vnet-${var.enterprise_prefix}-${var.environment}-hub"
  location            = azurerm_resource_group.core.location
  resource_group_name = azurerm_resource_group.core.name
  address_space       = ["10.100.0.0/16"]
  tags                = var.global_tags
}

resource "azurerm_subnet" "firewall" {
  name                 = "AzureFirewallSubnet" # Mandatory Azure-native naming
  resource_group_name  = azurerm_resource_group.core.name
  virtual_network_name = azurerm_virtual_network.hub.name
  address_prefixes     = ["10.100.1.0/24"]
}

# Isolated Application Workload Spoke Virtual Network
resource "azurerm_virtual_network" "spoke" {
  name                = "vnet-${var.enterprise_prefix}-${var.environment}-spoke"
  location            = azurerm_resource_group.core.location
  resource_group_name = azurerm_resource_group.core.name
  address_space       = ["10.200.0.0/16"]
  tags                = var.global_tags
}

resource "azurerm_subnet" "app_integration" {
  name                 = "snet-app-vnet-integration"
  resource_group_name  = azurerm_resource_group.core.name
  virtual_network_name = azurerm_virtual_network.spoke.name
  address_prefixes     = ["10.200.1.0/24"]

  delegation {
    name = "app_service_delegation"
    service_delegation {
      name    = "Microsoft.Web/serverFarms"
      actions = ["Microsoft.Network/virtualNetworks/subnets/action"]
    }
  }
}

resource "azurerm_subnet" "private_endpoints" {
  name                 = "snet-private-endpoints"
  resource_group_name  = azurerm_resource_group.core.name
  virtual_network_name = azurerm_virtual_network.spoke.name
  address_prefixes     = ["10.200.2.0/24"]
}

# Bi-directional Zero-Trust Network Peering Core Matrix
resource "azurerm_virtual_network_peering" "hub_to_spoke" {
  name                         = "peer-hub-to-spoke"
  resource_group_name          = azurerm_resource_group.core.name
  virtual_network_name         = azurerm_virtual_network.hub.name
  remote_virtual_network_id    = azurerm_virtual_network.spoke.id
  allow_virtual_network_access = true
  allow_forwarded_traffic      = true
}

resource "azurerm_virtual_network_peering" "spoke_to_hub" {
  name                         = "peer-spoke-to-hub"
  resource_group_name          = azurerm_resource_group.core.name
  virtual_network_name         = azurerm_virtual_network.spoke.name
  remote_virtual_network_id    = azurerm_virtual_network.hub.id
  allow_virtual_network_access = true
  allow_forwarded_traffic      = true
}

# Private DNS Zone architecture for completely internal App routing
resource "azurerm_private_dns_zone" "appservice" {
  name                = "privatelink.azurewebsites.net"
  resource_group_name = azurerm_resource_group.core.name
}

resource "azurerm_private_dns_zone_virtual_network_link" "dns_hub_link" {
  name                  = "link-dns-to-hub"
  resource_group_name   = azurerm_resource_group.core.name
  private_dns_zone_name = azurerm_private_dns_zone.appservice.name
  virtual_network_id    = azurerm_virtual_network.hub.id
}

# ==============================================================================
# 5. COMPUTE COMPONENT (ISOLATED LINUX WEB APP)
# ==============================================================================
# Dedicated, scalable Production Linux Service Plan
resource "azurerm_service_plan" "app_hosting" {
  name                = "asp-${var.enterprise_prefix}-${var.environment}-compute"
  location            = azurerm_resource_group.core.location
  resource_group_name = azurerm_resource_group.core.name
  os_type             = "Linux"
  sku_name            = "P1v3" # Production tier supporting VNet configurations
  tags                = var.global_tags
}

# Network hardened Linux Web App
resource "azurerm_linux_web_app" "enterprise_app" {
  name                          = "app-${var.enterprise_prefix}-${var.environment}-service"
  location                      = azurerm_resource_group.core.location
  resource_group_name           = azurerm_resource_group.core.name
  service_plan_id               = azurerm_service_plan.app_hosting.id
  public_network_access_enabled = false # Disables raw internet entry points
  https_only                    = true

  site_config {
    minimum_tls_version = "1.2"
    ftps_state          = "Disabled"
    application_stack {
      python_version = "3.11"
    }
  }

  identity {
    type = "SystemAssigned" # Managed identity configuration for passwordless storage/vault access
  }

  tags = var.global_tags
}

# Outbound Regional VNet Integration
resource "azurerm_app_service_virtual_network_swift_connection" "outbound_integration" {
  app_service_id = azurerm_linux_web_app.enterprise_app.id
  subnet_id      = azurerm_subnet.app_integration.id
}

# Inbound Route Hardening via Private Endpoint
resource "azurerm_private_endpoint" "app_ingress" {
  name                = "pe-app-${var.enterprise_prefix}-${var.environment}"
  location            = azurerm_resource_group.core.location
  resource_group_name = azurerm_resource_group.core.name
  subnet_id           = azurerm_subnet.private_endpoints.id

  private_service_connection {
    name                           = "psc-app-secure-link"
    private_connection_resource_id = azurerm_linux_web_app.enterprise_app.id
    subresource_names              = ["sites"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "dns-group-apps"
    private_dns_zone_ids = [azurerm_private_dns_zone.appservice.id]
  }
}

# ==============================================================================
# 6. GOVERNANCE & TELEMETRY SAFEGUARDS
# ==============================================================================
# Central Audit and Diagnostic Log Engine
resource "azurerm_log_analytics_workspace" "audit_hub" {
  name                = "law-${var.enterprise_prefix}-${var.environment}-logs"
  location            = azurerm_resource_group.core.location
  resource_group_name = azurerm_resource_group.core.name
  sku                 = "PerGB2018"
  retention_in_days   = 90
  tags                = var.global_tags
}

# Advanced Diagnostics Streams capturing control plane adjustments
resource "azurerm_monitor_diagnostic_setting" "vnet_audit" {
  name                       = "ds-vnet-hub-telemetry"
  target_resource_id         = azurerm_virtual_network.hub.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.audit_hub.id

  enabled_log {
    category_group = "allLogs"
  }

  metric {
    category = "AllMetrics"
    enabled  = true
  }
}

# Structural Lock ensuring critical infra cannot be dropped by manual overrides
resource "azurerm_management_lock" "hub_network_lock" {
  count      = var.enable_immutability_locks ? 1 : 0
  name       = "lock-hub-delete-protection"
  scope      = azurerm_virtual_network.hub.id
  lock_level = "CanNotDelete"
  notes      = "Enforced corporate control layer. Deletion requests require explicit pipeline token bypass rules."
}

# ==============================================================================
# 7. TELEMETRY OUTPUTS
# ==============================================================================
output "landing_zone_resource_group" {
  value       = azurerm_resource_group.core.name
  description = "Assigned container reference moniker."
}

output "hub_virtual_network_id" {
  value       = azurerm_virtual_network.hub.id
  description = "Core network platform identity mapping resource path."
}

output "isolated_application_url" {
  value       = "https://${azurerm_linux_web_app.enterprise_app.default_hostname}"
  description = "Application hostname; private network access is required."
}

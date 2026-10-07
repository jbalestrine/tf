/* ── TF Wizard – CAF-compliant client logic ──────────────────────── */

// ── State ───────────────────────────────────────────────────────────
let activeTab = 'versions';
let previewMode = 'diagram';
const previewCache = {};          // file -> string

const ARCHETYPES = {
  landing_zone: {
    module_name: 'azure_landing_zone',
    backend_type: 'azurerm',
    providers: [
      { name: 'azurerm', source: 'hashicorp/azurerm', version: '>= 3.100.0' },
      { name: 'random', source: 'hashicorp/random', version: '>= 3.6.0' }
    ],
    variables: [
      { name: 'location', type: 'string', description: 'Primary Azure region', default: 'eastus2' },
      { name: 'environment', type: 'string', description: 'Environment name', default: 'prod' },
      { name: 'org_prefix', type: 'string', description: 'Naming prefix', default: 'mc' },
      { name: 'subscription_id', type: 'string', description: 'Target subscription id', default: '' }
    ],
    resources: [
      { type: 'azurerm_resource_group', name: 'platform' },
      { type: 'azurerm_log_analytics_workspace', name: 'ops' },
      { type: 'azurerm_virtual_network', name: 'hub' }
    ],
    outputs: [
      { name: 'resource_group_name', value: 'azurerm_resource_group.platform.name', description: 'Platform resource group name' },
      { name: 'vnet_id', value: 'azurerm_virtual_network.hub.id', description: 'Hub VNet id' }
    ]
  },
  aks_platform: {
    module_name: 'aks_platform',
    backend_type: 'azurerm',
    providers: [
      { name: 'azurerm', source: 'hashicorp/azurerm', version: '>= 3.100.0' },
      { name: 'kubernetes', source: 'hashicorp/kubernetes', version: '>= 2.25.0' }
    ],
    variables: [
      { name: 'location', type: 'string', description: 'Azure region', default: 'eastus' },
      { name: 'cluster_name', type: 'string', description: 'AKS cluster name', default: 'mc-aks' },
      { name: 'node_count', type: 'number', description: 'System node count', default: '3' },
      { name: 'kubernetes_version', type: 'string', description: 'AKS version', default: '1.30' }
    ],
    resources: [
      { type: 'azurerm_resource_group', name: 'aks' },
      { type: 'azurerm_kubernetes_cluster', name: 'main' },
      { type: 'azurerm_container_registry', name: 'acr' }
    ],
    outputs: [
      { name: 'cluster_id', value: 'azurerm_kubernetes_cluster.main.id', description: 'AKS cluster id' },
      { name: 'kube_admin_config', value: 'azurerm_kubernetes_cluster.main.kube_admin_config_raw', description: 'Admin kubeconfig' }
    ]
  },
  serverless_api: {
    module_name: 'serverless_api',
    backend_type: 's3',
    providers: [
      { name: 'aws', source: 'hashicorp/aws', version: '>= 5.0' }
    ],
    variables: [
      { name: 'region', type: 'string', description: 'AWS region', default: 'us-east-1' },
      { name: 'project_name', type: 'string', description: 'Project name', default: 'shock-api' },
      { name: 'runtime', type: 'string', description: 'Lambda runtime', default: 'python3.12' },
      { name: 'memory_size', type: 'number', description: 'Lambda memory MB', default: '512' }
    ],
    resources: [
      { type: 'aws_iam_role', name: 'lambda_exec' },
      { type: 'aws_lambda_function', name: 'api' },
      { type: 'aws_apigatewayv2_api', name: 'http' }
    ],
    outputs: [
      { name: 'api_endpoint', value: 'aws_apigatewayv2_api.http.api_endpoint', description: 'HTTP API endpoint' }
    ]
  },
  data_platform: {
    module_name: 'data_platform_foundation',
    backend_type: 'azurerm',
    providers: [
      { name: 'azurerm', source: 'hashicorp/azurerm', version: '>= 3.100.0' }
    ],
    variables: [
      { name: 'location', type: 'string', description: 'Azure region', default: 'westus2' },
      { name: 'workspace_name', type: 'string', description: 'Synapse workspace name', default: 'mc-synapse' },
      { name: 'storage_replication', type: 'string', description: 'Storage replication type', default: 'LRS' },
      { name: 'enable_private_endpoints', type: 'bool', description: 'Use private endpoints', default: 'true' }
    ],
    resources: [
      { type: 'azurerm_resource_group', name: 'data' },
      { type: 'azurerm_storage_account', name: 'lake' },
      { type: 'azurerm_synapse_workspace', name: 'analytics' }
    ],
    outputs: [
      { name: 'storage_account_id', value: 'azurerm_storage_account.lake.id', description: 'Data lake storage id' },
      { name: 'synapse_workspace_id', value: 'azurerm_synapse_workspace.analytics.id', description: 'Synapse workspace id' }
    ]
  }
};

const GUIDED_TEMPLATES = {
  enterprise: ['resource_group', 'hub_spoke', 'ip_scope', 'nsg', 'dns', 'key_vault', 'guardrails', 'monitoring', 'private_access'],
  web: ['resource_group', 'hub_spoke', 'nsg', 'web_app', 'sql', 'key_vault', 'monitoring', 'private_access'],
  aks: ['resource_group', 'hub_spoke', 'ip_scope', 'aks', 'nsg', 'key_vault', 'monitoring', 'private_access'],
  hub: ['resource_group', 'hub_spoke', 'ip_scope', 'nsg', 'dns'],
  custom: []
};

let guidedStep = 0;

function selectGuidedTemplate(template) {
  const selected = GUIDED_TEMPLATES[template] || [];
  document.querySelectorAll('.guided-component-grid input').forEach(input => {
    input.checked = selected.includes(input.value);
  });
  updateGuidedReview();
}

function showGuidedStep(step) {
  guidedStep = Math.max(0, Math.min(3, step));
  document.querySelectorAll('[data-wizard-panel]').forEach(panel => {
    panel.hidden = Number(panel.dataset.wizardPanel) !== guidedStep;
  });
  document.querySelectorAll('.wizard-step-tab').forEach(tab => {
    const active = Number(tab.dataset.wizardStep) === guidedStep;
    tab.classList.toggle('active', active);
    tab.setAttribute('aria-selected', String(active));
  });
  if (guidedStep === 3) updateGuidedReview();
}

function moveGuidedStep(direction) {
  showGuidedStep(guidedStep + direction);
}

function selectedGuidedComponents() {
  return Array.from(document.querySelectorAll('.guided-component-grid input:checked')).map(input => input.value);
}

function updateGuidedReview() {
  const review = document.getElementById('guided-review');
  if (!review) return;
  const template = document.getElementById('guided-template');
  const pipeline = document.getElementById('guided-pipeline');
  const components = selectedGuidedComponents();
  const hooks = Array.from(document.querySelectorAll('.guided-hook:checked')).map(input => input.value);
  const labels = components.map(value =>
    Array.from(document.querySelectorAll('.guided-component-grid input')).find(input => input.value === value)?.parentElement.textContent.trim() || value
  );
  review.textContent = [
    `Starter: ${template?.selectedOptions[0]?.textContent || 'Custom'}`,
    `Components (${labels.length}): ${labels.join(', ') || 'none selected'}`,
    `CI/CD: ${pipeline?.selectedOptions[0]?.textContent || 'None'}`,
    `Sandbox: ${[
      document.getElementById('guided-local-sandbox')?.checked ? 'local validation/Azurite' : '',
      document.getElementById('guided-azure-sandbox')?.checked ? 'isolated Azure instructions' : ''
    ].filter(Boolean).join(', ') || 'none'}`,
    `Integration guidance: ${hooks.join(', ') || 'none'}`,
    'Build adds to the current Terraform form; it does not replace existing entries or deploy resources.'
  ].join('\n');
}

function addResourceIfMissing(type, name, attributes) {
  const exists = Array.from(document.querySelectorAll('.resource-row')).some(row =>
    selectedResourceType(row) === type && row.querySelector('.res-name')?.value.trim() === name
  );
  if (!exists) addResource(type, name, attributes);
}

function ensureGuidedVariable(name, type, description, defaultValue, sensitive) {
  const exists = Array.from(document.querySelectorAll('.var-row')).some(row =>
    row.querySelector('.var-name')?.value.trim() === name
  );
  if (!exists) addVariable(name, type, description, defaultValue, sensitive);
}

function ensureGuidedOutput(name, value, description) {
  const exists = Array.from(document.querySelectorAll('.output-row')).some(row =>
    row.querySelector('.out-name')?.value.trim() === name
  );
  if (!exists) addOutput(name, value, description);
}

function ensureAzureProvider() {
  const rows = Array.from(document.querySelectorAll('.provider-row'));
  const exists = rows.some(row =>
    row.querySelector('.prov-name')?.value.trim() === 'azurerm'
  );
  if (exists) return;
  const isUntouchedAwsDefault = rows.length === 1 &&
    rows[0].querySelector('.prov-name')?.value.trim() === 'aws' &&
    rows[0].querySelector('.prov-source')?.value.trim() === 'hashicorp/aws' &&
    rows[0].querySelector('.prov-version')?.value.trim() === '>= 5.0' &&
    document.querySelectorAll('.resource-row').length === 0;
  if (isUntouchedAwsDefault) setProviders([{ name: 'azurerm', source: 'hashicorp/azurerm', version: '>= 4.0.0' }]);
  else addProvider('azurerm', 'hashicorp/azurerm', '>= 4.0.0');
}

function addGuidedNetwork() {
  const expr = value => ({ __tf_expr: value });
  const group = resourceDefaults('azurerm_resource_group', 'network');
  addResourceIfMissing('azurerm_resource_group', 'network', group);
  [
    ['hub', ['10.0.0.0/16']],
    ['spoke1', ['10.1.0.0/16']],
    ['spoke2', ['10.2.0.0/16']]
  ].forEach(([name, cidrs]) => addResourceIfMissing('azurerm_virtual_network', name, {
    ...resourceDefaults('azurerm_virtual_network', name),
    address_space: cidrs
  }));
  addResourceIfMissing('azurerm_subnet', 'hub_gateway', {
    name: 'GatewaySubnet',
    resource_group_name: expr('azurerm_resource_group.network.name'),
    virtual_network_name: expr('azurerm_virtual_network.hub.name'),
    address_prefixes: ['10.0.0.0/27']
  });
  addResourceIfMissing('azurerm_subnet', 'spoke1_workload', {
    name: 'workload',
    resource_group_name: expr('azurerm_resource_group.network.name'),
    virtual_network_name: expr('azurerm_virtual_network.spoke1.name'),
    address_prefixes: ['10.1.1.0/24']
  });
  addResourceIfMissing('azurerm_subnet', 'spoke2_workload', {
    name: 'workload',
    resource_group_name: expr('azurerm_resource_group.network.name'),
    virtual_network_name: expr('azurerm_virtual_network.spoke2.name'),
    address_prefixes: ['10.2.1.0/24']
  });
  ['hub_to_spoke1', 'spoke1_to_hub', 'hub_to_spoke2', 'spoke2_to_hub'].forEach(name =>
    addResourceIfMissing('azurerm_virtual_network_peering', name, resourceDefaults('azurerm_virtual_network_peering', name))
  );
  ensureGuidedOutput('hub_vnet_id', 'azurerm_virtual_network.hub.id', 'Hub VNet resource ID');
  ensureGuidedOutput('spoke1_vnet_id', 'azurerm_virtual_network.spoke1.id', 'First spoke VNet resource ID');
  ensureGuidedOutput('spoke2_vnet_id', 'azurerm_virtual_network.spoke2.id', 'Second spoke VNet resource ID');
}

function addGuidedWindowsVm() {
  const expr = value => ({ __tf_expr: value });
  addGuidedNetwork();
  ensureGuidedVariable('vm_admin_password', 'string', 'Windows VM administrator password', '', true);
  addResourceIfMissing('azurerm_subnet', 'workload', {
    name: 'workload',
    resource_group_name: expr('azurerm_resource_group.network.name'),
    virtual_network_name: expr('azurerm_virtual_network.hub.name'),
    address_prefixes: ['10.0.1.0/24']
  });
  addResourceIfMissing('azurerm_network_interface', 'main', {
    ...resourceDefaults('azurerm_network_interface', 'main'),
    ip_configuration: { __tf_block: {
      name: 'internal',
      subnet_id: expr('azurerm_subnet.workload.id'),
      private_ip_address_allocation: 'Dynamic'
    } }
  });
  addResourceIfMissing('azurerm_windows_virtual_machine', 'main', resourceDefaults('azurerm_windows_virtual_machine', 'main'));
}

function addGuidedHookExtension(name, placeholderName) {
  addResourceIfMissing('azurerm_virtual_machine_extension', name, {
    name,
    virtual_machine_id: { __tf_expr: 'azurerm_windows_virtual_machine.main.id' },
    publisher: 'Microsoft.Compute',
    type: 'CustomScriptExtension',
    type_handler_version: '1.10',
    settings: JSON.stringify({ commandToExecute: `powershell -NoProfile -Command Write-Output ${placeholderName}-Review-Required` })
  });
}

function applyGuidedSetup() {
  const selected = selectedGuidedComponents();
  if (!selected.length) {
    setStatus('Select at least one component before building the starter.', true);
    return;
  }
  const project = (document.getElementById('guided-project').value || '')
    .toLowerCase().replace(/[^a-z0-9-]/g, '-').replace(/-+/g, '-').replace(/^-+|-+$/g, '').slice(0, 24) || 'masterchief';
  const environment = document.getElementById('guided-environment').value;
  const location = document.getElementById('guided-location').value.trim();
  if (!/^[a-z0-9-]{2,32}$/.test(project) || !/^[a-z0-9-]{2,32}$/.test(environment)) {
    setStatus('Use a 2–32 character lowercase project prefix and a valid environment name.', true);
    return;
  }
  if (!/^[a-z0-9]+(?:[a-z0-9-]*[a-z0-9])?$/.test(location)) {
    setStatus('Enter a valid Azure region identifier, such as eastus2.', true);
    return;
  }

  document.getElementById('module_name').value = `${project}_${environment}_starter`;
  ensureGuidedVariable('location', 'string', 'Primary Azure region', location, false);
  ensureGuidedVariable('environment', 'string', 'Deployment environment', environment, false);
  ensureGuidedVariable('project_prefix', 'string', 'Resource naming prefix', project, false);
  ensureAzureProvider();

  if (selected.length) {
    addResourceIfMissing('azurerm_resource_group', 'network', {
      ...resourceDefaults('azurerm_resource_group', 'network'),
      name: `${project}-${environment}-rg`
    });
  }
  if (selected.includes('hub_spoke') || selected.includes('ip_scope') || selected.includes('expressroute') ||
      selected.includes('private_access') || selected.includes('dns') || selected.includes('ilb') ||
      selected.includes('public_lb') || selected.includes('nsg')) {
    addGuidedNetwork();
  }
  if (selected.includes('ip_scope')) {
    ensureGuidedVariable('hub_cidr', 'string', 'Hub VNet CIDR', '10.0.0.0/16', false);
    ensureGuidedVariable('spoke1_cidr', 'string', 'Spoke 1 VNet CIDR', '10.1.0.0/16', false);
    ensureGuidedVariable('spoke2_cidr', 'string', 'Spoke 2 VNet CIDR', '10.2.0.0/16', false);
    ensureGuidedVariable('workload_subnet_cidr', 'string', 'Workload subnet CIDR', '10.0.1.0/24', false);
    const cidrs = { hub: 'hub_cidr', spoke1: 'spoke1_cidr', spoke2: 'spoke2_cidr' };
    Object.entries(cidrs).forEach(([name, variable]) => {
      const row = Array.from(document.querySelectorAll('.resource-row')).find(item =>
        selectedResourceType(item) === 'azurerm_virtual_network' && item.querySelector('.res-name')?.value.trim() === name
      );
      if (row) {
        const attrs = JSON.parse(row.querySelector('.res-attributes').value || '{}');
        attrs.address_space = [{ __tf_expr: `var.${variable}` }];
        row.querySelector('.res-attributes').value = JSON.stringify(attrs, null, 2);
      }
    });
    Array.from(document.querySelectorAll('.resource-row')).forEach(row => {
      if (selectedResourceType(row) !== 'azurerm_subnet') return;
      const name = row.querySelector('.res-name')?.value.trim();
      const variable = {
        workload: 'workload_subnet_cidr',
        spoke1_workload: 'spoke1_subnet_cidr',
        spoke2_workload: 'spoke2_subnet_cidr',
        hub_gateway: 'hub_gateway_cidr'
      }[name];
      if (!variable) return;
      ensureGuidedVariable(variable, 'string', `${name.replace(/_/g, ' ')} CIDR`, {
        workload: '10.0.1.0/24',
        spoke1_subnet_cidr: '10.1.1.0/24',
        spoke2_subnet_cidr: '10.2.1.0/24',
        hub_gateway_cidr: '10.0.0.0/27'
      }[variable], false);
      const attrs = JSON.parse(row.querySelector('.res-attributes').value || '{}');
      attrs.address_prefixes = [{ __tf_expr: `var.${variable}` }];
      row.querySelector('.res-attributes').value = JSON.stringify(attrs, null, 2);
    });
  }

  if (selected.includes('sql')) {
    ensureGuidedVariable('sql_admin_password', 'string', 'Azure SQL administrator password', '', true);
    addResourceIfMissing('azurerm_mssql_server', 'main', {
      ...resourceDefaults('azurerm_mssql_server', 'main'),
      name: `${project}-${environment}-sql`
    });
    addResourceIfMissing('azurerm_mssql_database', 'main', resourceDefaults('azurerm_mssql_database', 'main'));
    ensureGuidedOutput('sql_server_id', 'azurerm_mssql_server.main.id', 'Azure SQL server resource ID');
  }
  if (selected.includes('web_app')) {
    addResourceIfMissing('azurerm_service_plan', 'web', {
      ...resourceDefaults('azurerm_service_plan', 'web'),
      name: `${project}-${environment}-plan`
    });
    addResourceIfMissing('azurerm_linux_web_app', 'web', {
      ...resourceDefaults('azurerm_linux_web_app', 'web'),
      name: `${project}-${environment}-web`
    });
    ensureGuidedOutput('web_app_url', 'azurerm_linux_web_app.web.default_hostname', 'Linux Web App hostname');
  }
  if (selected.includes('aks')) {
    addResourceIfMissing('azurerm_kubernetes_cluster', 'main', {
      ...resourceDefaults('azurerm_kubernetes_cluster', 'main'),
      name: `${project}-${environment}-aks`,
      dns_prefix: `${project}-${environment}`
    });
    addResourceIfMissing('azurerm_container_registry', 'main', {
      ...resourceDefaults('azurerm_container_registry', 'main'),
      name: `${project.replace(/-/g, '')}${environment.replace(/-/g, '')}acr`.slice(0, 50)
    });
    ensureGuidedOutput('aks_cluster_id', 'azurerm_kubernetes_cluster.main.id', 'AKS cluster resource ID');
  }
  if (selected.includes('vm') || selected.includes('odbc') ||
      selected.some(item => ['adds', 'adfs', 'adcs', 'sofs'].includes(item))) {
    addGuidedWindowsVm();
  }
  if (selected.includes('odbc')) {
    addGuidedHookExtension('odbc_setup', 'OdbcSetupScript');
  }
  if (selected.includes('adds')) {
    addGuidedHookExtension('adds_role_setup', 'AddsRoleScript');
  }
  if (selected.includes('adfs')) {
    addGuidedHookExtension('adfs_role_setup', 'AdfsRoleScript');
  }
  if (selected.includes('adcs')) {
    addGuidedHookExtension('adcs_role_setup', 'AdcsRoleScript');
  }
  if (selected.includes('sofs')) {
    addGuidedHookExtension('sofs_role_setup', 'SofsRoleScript');
  }
  if (selected.includes('expressroute')) {
    addResourceIfMissing('azurerm_express_route_circuit', 'main', resourceDefaults('azurerm_express_route_circuit', 'main'));
    addResourceIfMissing('azurerm_public_ip', 'gateway', {
      ...resourceDefaults('azurerm_public_ip', 'gateway'), name: 'gateway-public-ip'
    });
    addResourceIfMissing('azurerm_virtual_network_gateway', 'main', resourceDefaults('azurerm_virtual_network_gateway', 'main'));
    addResourceIfMissing('azurerm_express_route_circuit_peering', 'private', resourceDefaults('azurerm_express_route_circuit_peering', 'private'));
    addResourceIfMissing('azurerm_virtual_network_gateway_connection', 'main', resourceDefaults('azurerm_virtual_network_gateway_connection', 'main'));
    ensureGuidedOutput('expressroute_circuit_id', 'azurerm_express_route_circuit.main.id', 'ExpressRoute circuit resource ID');
  }
  if (selected.includes('ilb') || selected.includes('public_lb')) {
    const isPublic = selected.includes('public_lb');
    const expr = value => ({ __tf_expr: value });
    if (isPublic) addResourceIfMissing('azurerm_public_ip', 'load_balancer', {
      ...resourceDefaults('azurerm_public_ip', 'load_balancer'), name: 'load-balancer-public-ip'
    });
    else addResourceIfMissing('azurerm_subnet', 'load_balancer', {
      name: 'load-balancer',
      resource_group_name: expr('azurerm_resource_group.network.name'),
      virtual_network_name: expr('azurerm_virtual_network.hub.name'),
      address_prefixes: ['10.0.2.0/24']
    });
    addResourceIfMissing('azurerm_lb', isPublic ? 'public' : 'internal', {
      name: `${project}-${environment}-${isPublic ? 'public' : 'internal'}-lb`,
      location: expr('var.location'),
      resource_group_name: expr('azurerm_resource_group.network.name'),
      sku: 'Standard',
      frontend_ip_configuration: { __tf_block: {
        name: 'frontend',
        ...(isPublic
          ? { public_ip_address_id: expr('azurerm_public_ip.load_balancer.id') }
          : { subnet_id: expr('azurerm_subnet.load_balancer.id'), private_ip_address_allocation: 'Dynamic' })
      } }
    });
    addResourceIfMissing('azurerm_lb_backend_address_pool', isPublic ? 'public' : 'internal', {
      name: `${isPublic ? 'public' : 'internal'}-backend`,
      loadbalancer_id: expr(`azurerm_lb.${isPublic ? 'public' : 'internal'}.id`)
    });
  }
  if (selected.includes('dns')) {
    addResourceIfMissing('azurerm_private_dns_zone', 'internal', {
      name: 'internal.example.com',
      resource_group_name: { __tf_expr: 'azurerm_resource_group.network.name' }
    });
    addResourceIfMissing('azurerm_private_dns_zone_virtual_network_link', 'hub', {
      name: `${project}-${environment}-dns-link`,
      resource_group_name: { __tf_expr: 'azurerm_resource_group.network.name' },
      private_dns_zone_name: { __tf_expr: 'azurerm_private_dns_zone.internal.name' },
      virtual_network_id: { __tf_expr: 'azurerm_virtual_network.hub.id' },
      registration_enabled: false
    });
  }
  if (selected.includes('nsg')) {
    addResourceIfMissing('azurerm_network_security_group', 'workload', resourceDefaults('azurerm_network_security_group', 'workload'));
  }
  if (selected.includes('key_vault')) {
    ensureGuidedVariable('tenant_id', 'string', 'Azure tenant ID for Key Vault', '', false);
    addResourceIfMissing('azurerm_key_vault', 'main', {
      ...resourceDefaults('azurerm_key_vault', 'main'),
      name: `${project.replace(/-/g, '')}${environment.replace(/-/g, '')}kv`.slice(0, 24)
    });
    ensureGuidedOutput('key_vault_id', 'azurerm_key_vault.main.id', 'Key Vault resource ID');
  }
  if (selected.includes('guardrails')) {
    ensureGuidedVariable('subscription_id', 'string', 'Target Azure subscription ID', '', false);
    ensureGuidedVariable('policy_definition_id', 'string', 'Existing built-in or custom policy definition resource ID', '', false);
    addResourceIfMissing('azurerm_subscription_policy_assignment', 'baseline', resourceDefaults('azurerm_subscription_policy_assignment', 'baseline'));
  }
  if (selected.includes('monitoring')) {
    addResourceIfMissing('azurerm_log_analytics_workspace', 'ops', resourceDefaults('azurerm_log_analytics_workspace', 'ops'));
    ensureGuidedOutput('log_analytics_id', 'azurerm_log_analytics_workspace.ops.id', 'Log Analytics workspace resource ID');
  }
  if (selected.includes('private_access')) {
    if (!selected.includes('key_vault')) {
      ensureGuidedVariable('tenant_id', 'string', 'Azure tenant ID for Key Vault', '', false);
      addResourceIfMissing('azurerm_key_vault', 'main', {
        ...resourceDefaults('azurerm_key_vault', 'main'),
        name: `${project.replace(/-/g, '')}${environment.replace(/-/g, '')}kv`.slice(0, 24)
      });
    }
    addResourceIfMissing('azurerm_private_dns_zone', 'key_vault', {
      name: 'privatelink.vaultcore.azure.net',
      resource_group_name: { __tf_expr: 'azurerm_resource_group.network.name' }
    });
    addResourceIfMissing('azurerm_private_dns_zone_virtual_network_link', 'key_vault', {
      name: `${project}-${environment}-kv-dns-link`,
      resource_group_name: { __tf_expr: 'azurerm_resource_group.network.name' },
      private_dns_zone_name: { __tf_expr: 'azurerm_private_dns_zone.key_vault.name' },
      virtual_network_id: { __tf_expr: 'azurerm_virtual_network.hub.id' },
      registration_enabled: false
    });
    addResourceIfMissing('azurerm_subnet', 'private_endpoints', {
      name: 'private-endpoints',
      resource_group_name: { __tf_expr: 'azurerm_resource_group.network.name' },
      virtual_network_name: { __tf_expr: 'azurerm_virtual_network.hub.name' },
      address_prefixes: ['10.0.3.0/24'],
      private_endpoint_network_policies: 'Disabled'
    });
    addResourceIfMissing('azurerm_private_endpoint', 'key_vault', {
      name: `${project}-${environment}-kv-pe`,
      location: { __tf_expr: 'var.location' },
      resource_group_name: { __tf_expr: 'azurerm_resource_group.network.name' },
      subnet_id: { __tf_expr: 'azurerm_subnet.private_endpoints.id' },
      private_service_connection: { __tf_block: {
        name: `${project}-${environment}-kv-connection`,
        is_manual_connection: false,
        private_connection_resource_id: { __tf_expr: 'azurerm_key_vault.main.id' },
        subresource_names: ['vault']
      } },
      private_dns_zone_group: { __tf_block: {
        name: 'default',
        private_dns_zone_ids: [{ __tf_expr: 'azurerm_private_dns_zone.key_vault.id' }]
      } }
    });
  }
  if (selected.includes('waf')) {
    addResourceIfMissing('azurerm_cdn_frontdoor_profile', 'main', {
      ...resourceDefaults('azurerm_cdn_frontdoor_profile', 'main'),
      name: `${project}-${environment}-frontdoor`
    });
    addResourceIfMissing('azurerm_cdn_frontdoor_firewall_policy', 'main', {
      ...resourceDefaults('azurerm_cdn_frontdoor_firewall_policy', 'main'),
      name: `${project.replace(/-/g, '')}${environment.replace(/-/g, '')}waf`.slice(0, 128)
    });
  }

  livePreview();
  updateGuidedReview();
  setStatus('Guided starter added to the Terraform editor. Review the generated code and required variables before validation or deployment.', false);
}

// ── Sidebar toggle ──────────────────────────────────────────────────
function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('collapsed');
}

// ── Tab switching ───────────────────────────────────────────────────
function showTab(btn) {
  document.querySelectorAll('.file-tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  activeTab = btn.dataset.file;
  renderPreview();
}

// ── Add / Remove helpers ────────────────────────────────────────────
function addProvider(name, source, version) {
  const row = document.createElement('div');
  row.className = 'entry-row provider-row';
  const pname = esc(name);
  const psource = esc(source);
  const pversion = esc(version);
  row.innerHTML = `
    <input type="text" placeholder="Name" class="prov-name" value="${pname}" oninput="livePreview()" />
    <input type="text" placeholder="Source" class="prov-source" value="${psource}" oninput="livePreview()" />
    <input type="text" placeholder="Version" class="prov-version" value="${pversion}" oninput="livePreview()" />
    <button class="btn danger" onclick="this.parentElement.remove();livePreview()">&#x2715;</button>`;
  document.getElementById('providers-list').appendChild(row);
  livePreview();
}

function setProviders(providers) {
  const container = document.getElementById('providers-list');
  container.innerHTML = '';
  (providers || []).forEach(p => addProvider(p.name, p.source, p.version));
}

function addVariable(name, type, desc, def_val, sensitive) {
  const row = document.createElement('div');
  row.className = 'entry-row var-row';
  row.innerHTML = `
    <input type="text" placeholder="Name" class="var-name" value="${esc(name)}" oninput="livePreview()" />
    <select class="var-type" onchange="livePreview()">
      <option value="string" ${type==='string'?'selected':''}>string</option>
      <option value="number" ${type==='number'?'selected':''}>number</option>
      <option value="bool"   ${type==='bool'?'selected':''}>bool</option>
      <option value="list"   ${type==='list'?'selected':''}>list</option>
      <option value="map"    ${type==='map'?'selected':''}>map</option>
    </select>
    <input type="text" placeholder="Description" class="var-desc" value="${esc(desc)}" oninput="livePreview()" />
    <input type="text" placeholder="Default" class="var-default" value="${esc(def_val)}" oninput="livePreview()" />
    <label class="sensitive-toggle"><input type="checkbox" class="var-sensitive" ${sensitive ? 'checked' : ''} onchange="livePreview()" /> Sensitive</label>
    <button class="btn danger" onclick="this.parentElement.remove();livePreview()">&#x2715;</button>`;
  document.getElementById('vars-list').appendChild(row);
  livePreview();
}

function resourceDefaults(type_, rname) {
  const expr = value => ({ __tf_expr: value });
  const sharedAzure = {
    name: rname,
    location: expr('var.location'),
    resource_group_name: expr('azurerm_resource_group.network.name')
  };
  const templates = {
    azurerm_resource_group: { name: rname, location: expr('var.location') },
    azurerm_virtual_network: {
      ...sharedAzure,
      address_space: [({ hub: '10.0.0.0/16', spoke1: '10.1.0.0/16', spoke2: '10.2.0.0/16' }[rname] || '10.0.0.0/16')]
    },
    azurerm_subnet: {
      name: rname, resource_group_name: expr('azurerm_resource_group.network.name'),
      virtual_network_name: expr('azurerm_virtual_network.hub.name'),
      address_prefixes: ['10.0.1.0/24']
    },
    azurerm_virtual_network_peering: {
      name: rname, resource_group_name: expr('azurerm_resource_group.network.name'),
      virtual_network_name: expr(`azurerm_virtual_network.${({
        hub_to_spoke1: 'hub', spoke1_to_hub: 'spoke1',
        hub_to_spoke2: 'hub', spoke2_to_hub: 'spoke2'
      }[rname] || 'hub')}.name`),
      remote_virtual_network_id: expr(`azurerm_virtual_network.${({
        hub_to_spoke1: 'spoke1', spoke1_to_hub: 'hub',
        hub_to_spoke2: 'spoke2', spoke2_to_hub: 'hub'
      }[rname] || 'spoke1')}.id`),
      allow_forwarded_traffic: true, allow_gateway_transit: false,
      use_remote_gateways: false
    },
    azurerm_mssql_server: {
      ...sharedAzure, version: '12.0', administrator_login: 'sqladmin',
      administrator_login_password: expr('var.sql_admin_password')
    },
    azurerm_mssql_database: {
      name: rname, server_id: expr('azurerm_mssql_server.main.id'),
      sku_name: 'S0', max_size_gb: 10
    },
    azurerm_mssql_firewall_rule: {
      name: rname, server_id: expr('azurerm_mssql_server.main.id'),
      start_ip_address: '0.0.0.0', end_ip_address: '0.0.0.0'
    },
    azurerm_linux_virtual_machine: {
      ...sharedAzure, size: 'Standard_B2s', admin_username: 'azureuser',
      network_interface_ids: [expr('azurerm_network_interface.main.id')],
      disable_password_authentication: true,
      os_disk: { __tf_block: {
        caching: 'ReadWrite', storage_account_type: 'Standard_LRS'
      } },
      admin_ssh_key: { __tf_block: {
        username: 'azureuser', public_key: expr('var.ssh_public_key')
      } },
      source_image_reference: { __tf_block: {
        publisher: 'Canonical', offer: '0001-com-ubuntu-server-jammy',
        sku: '22_04-lts', version: 'latest'
      } }
    },
    azurerm_windows_virtual_machine: {
      ...sharedAzure, size: 'Standard_B2s', admin_username: 'azureuser',
      admin_password: expr('var.vm_admin_password'),
      network_interface_ids: [expr('azurerm_network_interface.main.id')],
      os_disk: { __tf_block: {
        caching: 'ReadWrite', storage_account_type: 'Standard_LRS'
      } },
      source_image_reference: { __tf_block: {
        publisher: 'MicrosoftWindowsServer', offer: 'WindowsServer',
        sku: '2022-datacenter-azure-edition', version: 'latest'
      } }
    },
    azurerm_virtual_machine_extension: {
      name: rname, virtual_machine_id: expr('azurerm_windows_virtual_machine.main.id'),
      publisher: 'Microsoft.Compute', type: 'CustomScriptExtension',
      type_handler_version: '1.10',
      settings: JSON.stringify({ commandToExecute: 'powershell -NoProfile -Command Write-Output Review-Required' })
    },
    azurerm_express_route_circuit: {
      ...sharedAzure, service_provider_name: 'Equinix',
      peering_location: 'Silicon Valley', bandwidth_in_mbps: 50,
      sku: { __tf_block: { tier: 'Standard', family: 'MeteredData' } },
      allow_classic_operations: false
    },
    azurerm_virtual_network_gateway: {
      ...sharedAzure, type: 'ExpressRoute', vpn_type: 'RouteBased',
      active_active: false, enable_bgp: false, sku: 'Standard',
      ip_configuration: { __tf_block: {
        name: 'gateway-ip-configuration',
        public_ip_address_id: expr('azurerm_public_ip.gateway.id'),
        subnet_id: expr('azurerm_subnet.gateway.id')
      } }
    },
    azurerm_express_route_circuit_peering: {
      peering_type: 'AzurePrivatePeering',
      express_route_circuit_name: expr('azurerm_express_route_circuit.main.name'),
      resource_group_name: expr('azurerm_resource_group.network.name'),
      primary_peer_address_prefix: '10.0.0.0/30',
      secondary_peer_address_prefix: '10.0.0.4/30',
      vlan_id: 100, peer_asn: 65000
    },
    azurerm_virtual_network_gateway_connection: {
      name: rname, resource_group_name: expr('azurerm_resource_group.network.name'),
      location: expr('var.location'), type: 'ExpressRoute',
      virtual_network_gateway_id: expr('azurerm_virtual_network_gateway.main.id'),
      express_route_circuit_id: expr('azurerm_express_route_circuit.main.id')
    },
    azurerm_express_route_connection: {
      name: rname, express_route_circuit_id: expr('azurerm_express_route_circuit.main.id'),
      express_route_gateway_id: expr('azurerm_express_route_gateway.main.id')
    },
    azurerm_network_interface: {
      ...sharedAzure,
      ip_configuration: { __tf_block: {
        name: 'internal', subnet_id: expr('azurerm_subnet.workload.id'),
        private_ip_address_allocation: 'Dynamic'
      } }
    },
    azurerm_public_ip: {
      ...sharedAzure, allocation_method: 'Static', sku: 'Standard'
    },
    azurerm_network_security_group: {
      ...sharedAzure
    },
    azurerm_service_plan: {
      ...sharedAzure, os_type: 'Linux', sku_name: 'B1'
    },
    azurerm_linux_web_app: {
      ...sharedAzure,
      service_plan_id: expr('azurerm_service_plan.web.id'),
      https_only: true,
      site_config: { __tf_block: {
        minimum_tls_version: '1.2', ftps_state: 'Disabled', always_on: false
      } }
    },
    azurerm_kubernetes_cluster: {
      ...sharedAzure, dns_prefix: 'masterchief-dev',
      default_node_pool: { __tf_block: {
        name: 'system', node_count: 2, vm_size: 'Standard_D2s_v3'
      } },
      identity: { __tf_block: { type: 'SystemAssigned' } }
    },
    azurerm_container_registry: {
      ...sharedAzure, name: 'masterchiefdevacr', sku: 'Standard', admin_enabled: false
    },
    azurerm_key_vault: {
      ...sharedAzure,
      name: 'mc-dev-kv',
      tenant_id: expr('var.tenant_id'),
      sku_name: 'standard',
      soft_delete_retention_days: 7,
      purge_protection_enabled: true,
      enable_rbac_authorization: true,
      public_network_access_enabled: false
    },
    azurerm_log_analytics_workspace: {
      ...sharedAzure, sku: 'PerGB2018', retention_in_days: 30
    },
    azurerm_private_dns_zone: {
      name: 'internal.example.com',
      resource_group_name: expr('azurerm_resource_group.network.name')
    },
    azurerm_cdn_frontdoor_profile: {
      name: 'masterchief-dev-frontdoor',
      resource_group_name: expr('azurerm_resource_group.network.name'),
      sku_name: 'Standard_AzureFrontDoor'
    },
    azurerm_cdn_frontdoor_firewall_policy: {
      name: 'masterchiefdevwaf',
      resource_group_name: expr('azurerm_resource_group.network.name'),
      sku_name: 'Standard_AzureFrontDoor',
      enabled: true,
      mode: 'Prevention'
    },
    azurerm_subscription_policy_assignment: {
      name: 'masterchief-baseline',
      display_name: 'MasterChief baseline policy assignment',
      subscription_id: expr('var.subscription_id'),
      policy_definition_id: expr('var.policy_definition_id')
    },
    azurerm_lb: {
      ...sharedAzure, sku: 'Standard',
      frontend_ip_configuration: { __tf_block: {
        name: 'frontend',
        subnet_id: expr('azurerm_subnet.load_balancer.id'),
        private_ip_address_allocation: 'Dynamic'
      } }
    },
    azurerm_lb_backend_address_pool: {
      name: rname, loadbalancer_id: expr('azurerm_lb.internal.id')
    },
    azurerm_private_endpoint: {
      ...sharedAzure, subnet_id: expr('azurerm_subnet.workload.id'),
      private_service_connection: { __tf_block: {
        name: `${rname}-connection`, is_manual_connection: false,
        private_connection_resource_id: expr('azurerm_mssql_server.main.id'),
        subresource_names: ['sqlServer']
      } }
    },
    aws_vpc: { cidr_block: '10.0.0.0/16', enable_dns_support: true, enable_dns_hostnames: true },
    aws_instance: { ami: 'ami-REPLACE_ME', instance_type: 't3.micro' },
    aws_db_instance: { allocated_storage: 20, engine: 'postgres', instance_class: 'db.t3.micro' },
    google_compute_network: { name: rname, auto_create_subnetworks: false },
    google_compute_subnetwork: {
      name: rname, ip_cidr_range: '10.0.1.0/24',
      region: expr('var.region'), network: expr('google_compute_network.main.id')
    }
  };
  return templates[type_] || {};
}

function addResource(type_, rname, attributes) {
  const row = document.createElement('div');
  row.className = 'entry-row resource-row';
  const template = document.getElementById('resource-preset');
  const typeSelect = document.createElement('select');
  typeSelect.className = 'res-type';
  const placeholder = document.createElement('option');
  placeholder.value = '';
  placeholder.textContent = 'Select resource type…';
  typeSelect.appendChild(placeholder);
  Array.from(template.children).slice(1).forEach(optionGroup => {
    typeSelect.appendChild(optionGroup.cloneNode(true));
  });
  const customOption = document.createElement('option');
  customOption.value = '__custom__';
  customOption.textContent = 'Custom resource type…';
  typeSelect.appendChild(customOption);

  const knownTypes = Array.from(typeSelect.options).map(option => option.value);
  const selectedType = type_ === '__custom__'
    ? '__custom__'
    : (type_ && knownTypes.includes(type_) ? type_ : (type_ ? '__custom__' : ''));
  typeSelect.value = selectedType;
  typeSelect.onchange = () => handleResourceTypeChange(typeSelect);

  const customType = document.createElement('input');
  customType.type = 'text';
  customType.className = 'res-type-custom';
  customType.placeholder = 'Terraform resource type';
  customType.value = selectedType === '__custom__' && type_ !== '__custom__' ? String(type_) : '';
  customType.hidden = selectedType !== '__custom__';
  customType.oninput = livePreview;

  const nameInput = document.createElement('input');
  nameInput.type = 'text';
  nameInput.className = 'res-name';
  nameInput.placeholder = 'Terraform local name';
  nameInput.value = rname == null ? '' : String(rname);
  nameInput.oninput = livePreview;

  const removeButton = document.createElement('button');
  removeButton.type = 'button';
  removeButton.className = 'btn danger';
  removeButton.textContent = '×';
  removeButton.setAttribute('aria-label', 'Remove resource');
  removeButton.onclick = () => {
    row.remove();
    livePreview();
  };
  const attributesInput = document.createElement('textarea');
  attributesInput.className = 'res-attributes';
  attributesInput.rows = 4;
  attributesInput.spellcheck = false;
  attributesInput.setAttribute('aria-label', `Terraform attributes for ${rname || 'resource'}`);
  attributesInput.placeholder = '{"name": "example", "location": {"__tf_expr": "var.location"}}';
  attributesInput.value = JSON.stringify(attributes || resourceDefaults(type_, rname || 'main'), null, 2);
  attributesInput.oninput = livePreview;
  row.append(typeSelect, customType, nameInput, removeButton, attributesInput);
  document.getElementById('resources-list').appendChild(row);
  livePreview();
}

function handleResourceTypeChange(typeSelect) {
  const customType = typeSelect.parentElement.querySelector('.res-type-custom');
  const isCustom = typeSelect.value === '__custom__';
  customType.hidden = !isCustom;
  if (!isCustom) customType.value = '';
  const row = typeSelect.parentElement;
  const name = row.querySelector('.res-name')?.value.trim() || 'main';
  const attributes = row.querySelector('.res-attributes');
  if (attributes) {
    attributes.value = JSON.stringify(
      isCustom ? {} : resourceDefaults(typeSelect.value, name),
      null,
      2
    );
  }
  livePreview();
}

function selectedResourceType(row) {
  const selected = row.querySelector('.res-type')?.value || '';
  return selected === '__custom__'
    ? row.querySelector('.res-type-custom')?.value.trim() || ''
    : selected;
}

function addSelectedResource() {
  const type = document.getElementById('resource-preset').value;
  if (!type) {
    setStatus('Choose a resource type first', true);
    return;
  }
  const shortName = type.replace(/^(azurerm|aws|google)_/, '').replace(/[^a-zA-Z0-9]+/g, '_');
  addResource(type, shortName || 'main', resourceDefaults(type, shortName || 'main'));
  const provider = type.startsWith('azurerm_') ? 'azurerm'
    : (type.startsWith('aws_') ? 'aws' : (type.startsWith('google_') ? 'google' : ''));
  if (provider) ensureTerraformProvider(provider);
  document.getElementById('resource-preset').value = '';
  setStatus(`Added ${type}`, false);
}

function addNetworkPreset(preset) {
  const presets = {
    azure_vnet: {
      provider: 'azurerm',
      resources: [
        ['azurerm_resource_group', 'network'],
        ['azurerm_virtual_network', 'main']
      ]
    },
    azure_hub_spoke: {
      provider: 'azurerm',
      resources: [
        ['azurerm_resource_group', 'network'],
        ['azurerm_virtual_network', 'hub', {
          ...resourceDefaults('azurerm_virtual_network', 'hub'), address_space: ['10.0.0.0/16']
        }],
        ['azurerm_virtual_network', 'spoke1', {
          ...resourceDefaults('azurerm_virtual_network', 'spoke1'), address_space: ['10.1.0.0/16']
        }],
        ['azurerm_virtual_network', 'spoke2', {
          ...resourceDefaults('azurerm_virtual_network', 'spoke2'), address_space: ['10.2.0.0/16']
        }],
        ['azurerm_subnet', 'hub_gateway', {
          name: 'GatewaySubnet', resource_group_name: { __tf_expr: 'azurerm_resource_group.network.name' },
          virtual_network_name: { __tf_expr: 'azurerm_virtual_network.hub.name' },
          address_prefixes: ['10.0.0.0/27']
        }],
        ['azurerm_subnet', 'spoke1_workload', {
          name: 'workload', resource_group_name: { __tf_expr: 'azurerm_resource_group.network.name' },
          virtual_network_name: { __tf_expr: 'azurerm_virtual_network.spoke1.name' },
          address_prefixes: ['10.1.1.0/24']
        }],
        ['azurerm_subnet', 'spoke2_workload', {
          name: 'workload', resource_group_name: { __tf_expr: 'azurerm_resource_group.network.name' },
          virtual_network_name: { __tf_expr: 'azurerm_virtual_network.spoke2.name' },
          address_prefixes: ['10.2.1.0/24']
        }],
        ['azurerm_virtual_network_peering', 'hub_to_spoke1'],
        ['azurerm_virtual_network_peering', 'spoke1_to_hub'],
        ['azurerm_virtual_network_peering', 'hub_to_spoke2'],
        ['azurerm_virtual_network_peering', 'spoke2_to_hub']
      ],
      variables: [
        ['location', 'string', 'Azure region', 'eastus2']
      ],
      outputs: [
        ['hub_vnet_id', 'azurerm_virtual_network.hub.id', 'Hub VNet resource ID'],
        ['spoke1_vnet_id', 'azurerm_virtual_network.spoke1.id', 'First spoke VNet resource ID'],
        ['spoke2_vnet_id', 'azurerm_virtual_network.spoke2.id', 'Second spoke VNet resource ID']
      ]
    },
    aws_vpc: {
      provider: 'aws',
      resources: [
        ['aws_vpc', 'main'],
        ['aws_subnet', 'public'],
        ['aws_subnet', 'private'],
        ['aws_internet_gateway', 'main'],
        ['aws_route_table', 'public']
      ]
    },
    gcp_vpc: {
      provider: 'google',
      resources: [
        ['google_compute_network', 'main'],
        ['google_compute_subnetwork', 'main']
      ]
    },
    azure_vm_sql_odbc: {
      provider: 'azurerm',
      resources: [
        ['azurerm_resource_group', 'network'],
        ['azurerm_virtual_network', 'hub', {
          ...resourceDefaults('azurerm_virtual_network', 'hub'), address_space: ['10.0.0.0/16']
        }],
        ['azurerm_subnet', 'workload', {
          name: 'workload', resource_group_name: { __tf_expr: 'azurerm_resource_group.network.name' },
          virtual_network_name: { __tf_expr: 'azurerm_virtual_network.hub.name' },
          address_prefixes: ['10.0.1.0/24']
        }],
        ['azurerm_network_interface', 'main', {
          ...resourceDefaults('azurerm_network_interface', 'main'),
          ip_configuration: { __tf_block: {
            name: 'internal', subnet_id: { __tf_expr: 'azurerm_subnet.workload.id' },
            private_ip_address_allocation: 'Dynamic'
          } }
        }],
        ['azurerm_linux_virtual_machine', 'main', {
          ...resourceDefaults('azurerm_linux_virtual_machine', 'main'),
          source_image_reference: { __tf_block: {
            publisher: 'Canonical', offer: '0001-com-ubuntu-server-jammy',
            sku: '22_04-lts', version: 'latest'
          } }
        }],
        ['azurerm_mssql_server', 'main'],
        ['azurerm_mssql_database', 'main'],
        ['azurerm_private_endpoint', 'sql'],
        ['azurerm_virtual_machine_extension', 'odbc_client']
      ],
      variables: [
        ['location', 'string', 'Azure region', 'eastus2'],
        ['sql_admin_password', 'string', 'Azure SQL administrator password', '', true],
        ['ssh_public_key', 'string', 'SSH public key for Linux VM access', 'ssh-ed25519 REPLACE_WITH_PUBLIC_KEY', false]
      ],
      outputs: [
        ['sql_server_fqdn', 'azurerm_mssql_server.main.fully_qualified_domain_name', 'Azure SQL server hostname'],
        ['sql_database_name', 'azurerm_mssql_database.main.name', 'Azure SQL database name']
      ]
    },
    azure_expressroute: {
      provider: 'azurerm',
      resources: [
        ['azurerm_resource_group', 'network'],
        ['azurerm_virtual_network', 'hub', {
          ...resourceDefaults('azurerm_virtual_network', 'hub'), address_space: ['10.0.0.0/16']
        }],
        ['azurerm_subnet', 'gateway', {
          name: 'GatewaySubnet', resource_group_name: { __tf_expr: 'azurerm_resource_group.network.name' },
          virtual_network_name: { __tf_expr: 'azurerm_virtual_network.hub.name' },
          address_prefixes: ['10.0.0.0/27']
        }],
        ['azurerm_public_ip', 'gateway', resourceDefaults('azurerm_public_ip', 'gateway')],
        ['azurerm_virtual_network_gateway', 'main', resourceDefaults('azurerm_virtual_network_gateway', 'main')],
        ['azurerm_express_route_circuit', 'main', resourceDefaults('azurerm_express_route_circuit', 'main')],
        ['azurerm_express_route_circuit_peering', 'private', resourceDefaults('azurerm_express_route_circuit_peering', 'private')],
        ['azurerm_virtual_network_gateway_connection', 'main', resourceDefaults('azurerm_virtual_network_gateway_connection', 'main')]
      ],
      variables: [
        ['location', 'string', 'Azure region', 'eastus2'],
        ['expressroute_authorization_key', 'string', 'Optional circuit authorization key', '', true]
      ],
      outputs: [
        ['circuit_id', 'azurerm_express_route_circuit.main.id', 'ExpressRoute circuit ID'],
        ['gateway_id', 'azurerm_virtual_network_gateway.main.id', 'Virtual network gateway ID']
      ]
    }
  };
  const selected = presets[preset];
  if (!selected) return;
  selected.resources.forEach(([type, name, attributes]) =>
    addResource(type, name, attributes || resourceDefaults(type, name)));
  (selected.variables || []).forEach(([name, type, description, value, sensitive]) =>
    addVariable(name, type, description, value, sensitive));
  (selected.outputs || []).forEach(([name, value, description]) =>
    addOutput(name, value, description));
  ensureTerraformProvider(selected.provider);
  setStatus(`Added ${preset.replace(/_/g, ' ')} starter resources. Review provider requirements, secrets, network ranges and service-provider details before deployment.`, false);
}

function ensureTerraformProvider(providerName) {
  const providers = Array.from(document.querySelectorAll('.provider-row .prov-name'))
    .map(input => input.value.trim());
  if (providers.includes(providerName)) return;
  const defaults = {
    azurerm: ['hashicorp/azurerm', '>= 3.100.0'],
    aws: ['hashicorp/aws', '>= 5.0'],
    google: ['hashicorp/google', '>= 5.0']
  };
  const [source, version] = defaults[providerName] || [`hashicorp/${providerName}`, '>= 1.0'];
  addProvider(providerName, source, version);
}

function addOutput(name, value, desc) {
  const row = document.createElement('div');
  row.className = 'entry-row output-row';
  row.innerHTML = `
    <input type="text" placeholder="Name" class="out-name" value="${esc(name)}" oninput="livePreview()" />
    <input type="text" placeholder="Value expression" class="out-value" value="${esc(value)}" oninput="livePreview()" />
    <input type="text" placeholder="Description" class="out-desc" value="${esc(desc)}" oninput="livePreview()" />
    <button class="btn danger" onclick="this.parentElement.remove();livePreview()">&#x2715;</button>`;
  document.getElementById('outputs-list').appendChild(row);
  livePreview();
}

function esc(v) { return (v == null ? '' : String(v)).replace(/"/g, '&quot;'); }

// ── Clear all ───────────────────────────────────────────────────────
function clearAll(silent) {
  document.getElementById('module_name').value = 'my_module';
  document.getElementById('backend_type').value = '';
  document.getElementById('providers-list').innerHTML = `
    <div class="entry-row provider-row">
      <input type="text" placeholder="Name" value="aws" class="prov-name" oninput="livePreview()" />
      <input type="text" placeholder="Source" value="hashicorp/aws" class="prov-source" oninput="livePreview()" />
      <input type="text" placeholder="Version" value=">= 5.0" class="prov-version" oninput="livePreview()" />
    </div>`;
  ['vars-list','resources-list','outputs-list'].forEach(id => document.getElementById(id).innerHTML = '');
  document.getElementById('json-schema').value = '';
  const archetypeSelect = document.getElementById('archetype_select');
  if (archetypeSelect) archetypeSelect.value = '';
  livePreview();
  if (!silent) setStatus('Form cleared', false);
}

function applyArchetypeSelection() {
  const key = document.getElementById('archetype_select').value;
  if (!key) {
    setStatus('Pick an archetype first', true);
    return;
  }
  applyArchetype(key);
}

function quickArchetype(key) {
  const archetypeSelect = document.getElementById('archetype_select');
  if (archetypeSelect) archetypeSelect.value = key;
  applyArchetype(key);
}

function applyArchetype(key) {
  const archetype = ARCHETYPES[key];
  if (!archetype) {
    setStatus('Unknown archetype selected', true);
    return;
  }

  clearAll(true);
  document.getElementById('module_name').value = archetype.module_name;
  document.getElementById('backend_type').value = archetype.backend_type || '';

  setProviders(archetype.providers);
  document.getElementById('vars-list').innerHTML = '';
  document.getElementById('resources-list').innerHTML = '';
  document.getElementById('outputs-list').innerHTML = '';

  (archetype.variables || []).forEach(v => addVariable(v.name, v.type, v.description, v.default));
  (archetype.resources || []).forEach(r => addResource(r.type, r.name, r.attributes || {}));
  (archetype.outputs || []).forEach(o => addOutput(o.name, o.value, o.description));

  livePreview();
  setStatus(`Archetype loaded: ${key.replace('_', ' ')}`, false);
}

function injectArchetypeSchema() {
  const key = document.getElementById('archetype_select').value;
  if (!key || !ARCHETYPES[key]) {
    setStatus('Select an archetype to inject schema', true);
    return;
  }

  const props = {};
  (ARCHETYPES[key].variables || []).forEach(v => {
    const schemaType = v.type === 'bool' ? 'boolean' : (v.type === 'list' ? 'array' : (v.type === 'map' ? 'object' : v.type));
    props[v.name] = {
      type: schemaType || 'string',
      description: v.description || ''
    };
    if (v.default !== '' && v.default != null) {
      props[v.name].default = v.default;
    }
  });

  const schema = {
    title: `${key.replace('_', ' ')} module schema`,
    type: 'object',
    properties: props
  };

  document.getElementById('json-schema').value = JSON.stringify(schema, null, 2);
  setStatus('Archetype schema injected into JSON Schema editor', false);
}

// ── Build spec from form ────────────────────────────────────────────
function buildSpec() {
  const module_name = document.getElementById('module_name').value.trim() || 'module';
  const backend_type = document.getElementById('backend_type').value;

  const providers = [];
  document.querySelectorAll('.provider-row').forEach(r => {
    const name = r.querySelector('.prov-name')?.value.trim();
    if (name) providers.push({
      name,
      source: r.querySelector('.prov-source')?.value.trim() || `hashicorp/${name}`,
      version: r.querySelector('.prov-version')?.value.trim() || '>= 1.0'
    });
  });

  const variables = [];
  const resourceErrors = [];
  document.querySelectorAll('.var-row').forEach(r => {
    const name = r.querySelector('.var-name')?.value.trim();
    if (name) {
      const type = r.querySelector('.var-type')?.value || 'string';
      const rawDefault = r.querySelector('.var-default')?.value.trim() || '';
      let defaultValue = rawDefault || null;
      if (rawDefault && ['number', 'bool', 'list', 'map'].includes(type)) {
        try {
          defaultValue = JSON.parse(rawDefault);
          const valid = type === 'number' ? typeof defaultValue === 'number' && Number.isFinite(defaultValue)
            : type === 'bool' ? typeof defaultValue === 'boolean'
              : type === 'list' ? Array.isArray(defaultValue)
                : typeof defaultValue === 'object' && defaultValue !== null && !Array.isArray(defaultValue);
          if (!valid) throw new Error(`Default must be a ${type}`);
        } catch (error) {
          resourceErrors.push(`Variable ${name}: ${error.message}`);
          defaultValue = null;
        }
      }
      variables.push({
        name,
        type,
        description: r.querySelector('.var-desc')?.value.trim() || '',
        default: defaultValue,
        sensitive: r.querySelector('.var-sensitive')?.checked || false
      });
    }
  });

  const resources = [];
  document.querySelectorAll('.resource-row').forEach(r => {
    const type = selectedResourceType(r);
    const rname = r.querySelector('.res-name')?.value.trim();
    const editor = r.querySelector('.res-attributes');
    let attributes = {};
    if (editor && editor.value.trim()) {
      try {
        attributes = JSON.parse(editor.value);
        if (!attributes || Array.isArray(attributes) || typeof attributes !== 'object') {
          throw new Error('Attributes must be a JSON object');
        }
        editor.removeAttribute('aria-invalid');
      } catch (error) {
        editor.setAttribute('aria-invalid', 'true');
        resourceErrors.push(`${rname || type}: ${error.message}`);
      }
    }
    if (type && rname) resources.push({ type, name: rname, attributes });
  });

  const outputs = [];
  document.querySelectorAll('.output-row').forEach(r => {
    const name = r.querySelector('.out-name')?.value.trim();
    if (name) outputs.push({
      name,
      value: r.querySelector('.out-value')?.value.trim() || '""',
      description: r.querySelector('.out-desc')?.value.trim() || ''
    });
  });

  const backend = backend_type ? { type: backend_type } : undefined;
  const hooks = Array.from(document.querySelectorAll('.guided-hook:checked')).map(input => input.value);
  return {
    module_name,
    providers,
    variables,
    resources,
    outputs,
    backend,
    resourceErrors,
    pipeline: document.getElementById('guided-pipeline')?.value || '',
    sandbox_local: document.getElementById('guided-local-sandbox')?.checked || false,
    sandbox_azure: document.getElementById('guided-azure-sandbox')?.checked || false,
    hooks
  };
}

// ── Live preview rendering ──────────────────────────────────────────
function livePreview() {
  const spec = buildSpec();

  // versions.tf
  let ver = 'terraform {\n';
  if (spec.providers.length) {
    ver += '  required_providers {\n';
    spec.providers.forEach(p => {
      ver += `    ${p.name} = {\n      source  = "${p.source}"\n      version = "${p.version}"\n    }\n`;
    });
    ver += '  }\n';
  }
  if (spec.backend) {
    ver += `  backend "${spec.backend.type}" {}\n`;
  }
  ver += '}\n';
  if (spec.providers.some(provider => provider.name === 'azurerm')) {
    ver += '\nprovider "azurerm" {\n  features {}\n}\n';
  }
  previewCache.versions = ver;

  // variables.tf
  let vars = '';
  spec.variables.forEach(v => {
    const tfType = v.type === 'list' ? 'list(string)' : (v.type === 'map' ? 'map(string)' : v.type);
    vars += `variable "${v.name}" {\n  type        = ${tfType}\n`;
    if (v.description) vars += `  description = ${JSON.stringify(v.description)}\n`;
    if (v.default !== null) vars += `  default     = ${renderTerraformValue(v.default)}\n`;
    if (v.sensitive)   vars += '  sensitive   = true\n';
    vars += '}\n\n';
  });
  previewCache.variables = vars || '# No variables defined\n';

  // main.tf
  let main = '';
  spec.resources.forEach(r => {
    main += `resource "${r.type}" "${r.name}" {\n`;
    Object.entries(r.attributes).forEach(([key, value]) => {
      main += renderResourceAttribute(key, value);
    });
    if (!Object.keys(r.attributes).length) main += '  # Add required provider attributes\n';
    main += '}\n\n';
  });
  if (spec.resourceErrors.length) {
    main = `# Fix invalid resource attributes JSON before generating:\n${spec.resourceErrors.map(error => `# ${error}`).join('\n')}\n\n${main}`;
  }
  previewCache.main = main || '# Add resources here\n';

  // outputs.tf
  let outs = '';
  spec.outputs.forEach(o => {
    outs += `output "${o.name}" {\n  value       = ${o.value}\n`;
    if (o.description) outs += `  description = "${o.description}"\n`;
    outs += '}\n\n';
  });
  previewCache.outputs = outs || '# No outputs defined\n';

  renderPreview();
  renderArchitecturePreview(spec);
}

function renderTerraformValue(value) {
  if (value && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).length === 1) {
    if (typeof value.__tf_expr === 'string') return value.__tf_expr;
    if (value.__tf_block) return value.__tf_block;
  }
  if (Array.isArray(value)) return `[${value.map(renderTerraformValue).join(', ')}]`;
  if (value && typeof value === 'object') {
    return `{ ${Object.entries(value).map(([key, child]) => `${key} = ${renderTerraformValue(child)}`).join(', ')} }`;
  }
  return JSON.stringify(value);
}

function renderResourceAttribute(key, value) {
  if (value && typeof value === 'object' && !Array.isArray(value) && value.__tf_block) {
    const blocks = Array.isArray(value.__tf_block) ? value.__tf_block : [value.__tf_block];
    return blocks.map(block => `  ${key} {\n${Object.entries(block).map(([childKey, childValue]) =>
      `    ${childKey} = ${renderTerraformValue(childValue)}\n`).join('')}  }\n`).join('');
  }
  return `  ${key} = ${renderTerraformValue(value)}\n`;
}

function renderPreview() {
  const code = previewCache[activeTab] || '# Select a tab...';
  document.getElementById('preview-code').textContent = code;
}

function showPreviewMode(mode) {
  previewMode = mode === 'code' ? 'code' : 'diagram';
  document.getElementById('architecture-preview').hidden = previewMode !== 'diagram';
  document.getElementById('code-preview-pane').hidden = previewMode !== 'code';
  document.getElementById('diagram-view-button').classList.toggle('active', previewMode === 'diagram');
  document.getElementById('code-view-button').classList.toggle('active', previewMode === 'code');
}

function renderArchitecturePreview(spec) {
  const resources = spec.resources;
  const known = new Map(resources.map(resource => [`${resource.type}.${resource.name}`, resource]));
  const nodes = resources.map(resource => {
    const addressSpace = resource.attributes.address_space;
    const prefixes = resource.attributes.address_prefixes;
    const ranges = Array.isArray(addressSpace) ? addressSpace
      : (Array.isArray(prefixes) ? prefixes : []);
    const details = ranges.map(value => {
      if (typeof value === 'string') return value;
      if (value && typeof value.__tf_expr === 'string') return value.__tf_expr;
      return '';
    }).filter(Boolean).join(', ');
    return {
      id: `${resource.type}.${resource.name}`,
      label: resource.name,
      subtitle: `${resource.type}${details ? ` · ${details}` : ''}`,
      kind: resource.type.startsWith('azurerm_') ? 'Azure'
        : resource.type.startsWith('aws_') ? 'AWS'
          : resource.type.startsWith('google_') ? 'Google Cloud' : 'Terraform'
    };
  });
  const edges = [];
  function findReferences(value, results) {
    if (Array.isArray(value)) {
      value.forEach(item => findReferences(item, results));
    } else if (value && typeof value === 'object') {
      if (typeof value.__tf_expr === 'string') {
        const match = value.__tf_expr.match(/^((?:azurerm|aws|google)_[a-z0-9_]+)\.([A-Za-z_][A-Za-z0-9_]*)\./);
        if (match) results.add(`${match[1]}.${match[2]}`);
      } else {
        Object.values(value).forEach(item => findReferences(item, results));
      }
    }
  }
  resources.forEach(resource => {
    const refs = new Set();
    findReferences(resource.attributes, refs);
    refs.forEach(reference => {
      if (known.has(reference) && reference !== `${resource.type}.${resource.name}`) {
        edges.push({
          from: reference,
          to: `${resource.type}.${resource.name}`,
          label: 'depends on'
        });
      }
    });
    if (resource.type === 'azurerm_virtual_network_peering') {
      const local = resource.attributes.virtual_network_name?.__tf_expr?.match(/^azurerm_virtual_network\.([A-Za-z_][A-Za-z0-9_]*)\./)?.[1];
      const remote = resource.attributes.remote_virtual_network_id?.__tf_expr?.match(/^azurerm_virtual_network\.([A-Za-z_][A-Za-z0-9_]*)\./)?.[1];
      if (local && remote) {
        edges.push({ from: `azurerm_virtual_network.${local}`, to: `azurerm_virtual_network.${remote}`, label: 'VNet peering' });
      }
    }
  });
  window.renderArchitectureDiagram(document.getElementById('architecture-diagram'), {
    title: spec.module_name || 'Terraform architecture',
    subtitle: `${resources.length} configured Terraform resources · code preview is generated from this model`,
    hub: spec.module_name || 'Terraform module',
    nodes,
    edges
  });
}

function currentArchitectureSpec() {
  const spec = buildSpec();
  const resources = spec.resources;
  const nodes = resources.map(resource => ({
    id: `${resource.type}.${resource.name}`,
    label: resource.name,
    kind: resource.type
  }));
  const edges = [];
  resources.forEach(resource => {
    Object.entries(resource.attributes).forEach(([key, value]) => {
      if (value && typeof value === 'object' && typeof value.__tf_expr === 'string') {
        const match = value.__tf_expr.match(/^((?:azurerm|aws|google)_[a-z0-9_]+)\.([A-Za-z_][A-Za-z0-9_]*)\./);
        if (match) edges.push({
          from: `${match[1]}.${match[2]}`,
          to: `${resource.type}.${resource.name}`,
          label: key.replace(/_/g, ' ')
        });
      }
    });
  });
  return {
    title: spec.module_name || 'Terraform architecture',
    hub: spec.module_name || 'Terraform module',
    nodes,
    edges
  };
}

function downloadCurrentSvg() {
  try {
    window.downloadArchitectureSvg(
      document.getElementById('architecture-diagram'),
      document.getElementById('module_name').value || 'terraform-architecture'
    );
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function downloadCurrentVisio() {
  try {
    const response = await fetch('/api/architecture/visio', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(currentArchitectureSpec())
    });
    if (!response.ok) {
      const payload = await response.json();
      throw new Error(payload.error || `Visio export failed (${response.status})`);
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `${document.getElementById('module_name').value || 'terraform-architecture'}.vsdx`;
    anchor.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    setStatus(error.message, true);
  }
}

// ── Copy preview ────────────────────────────────────────────────────
function copyPreview() {
  const code = previewCache[activeTab] || '';
  navigator.clipboard.writeText(code).then(() => setStatus('Copied to clipboard', false));
}

// ── Validate ────────────────────────────────────────────────────────
function validateSpec() {
  const spec = buildSpec();
  const errors = [];
  if (!spec.module_name) errors.push('Module name is required');
  if (!spec.providers.length) errors.push('At least one provider is required');
  spec.variables.forEach(v => { if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(v.name)) errors.push(`Invalid variable name: ${v.name}`); });
  spec.resources.forEach(r => { if (!r.type.includes('_')) errors.push(`Resource type "${r.type}" should contain an underscore`); });
  errors.push(...spec.resourceErrors);

  if (errors.length) {
    setStatus(`Validation failed: ${errors.join('; ')}`, true);
  } else {
    setStatus('Validation passed &#x2705;', false);
  }
}

async function validateInfrastructureDesign() {
  const result = document.getElementById('infrastructure-validation');
  result.textContent = 'Validating design...';
  let design;
  try {
    design = JSON.parse(document.getElementById('infrastructure-design').value);
  } catch (error) {
    result.textContent = `Invalid JSON: ${error.message}`;
    return;
  }

  try {
    const response = await fetch('/api/terraform/validate-design', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(design)
    });
    const payload = await response.json();
    if (!response.ok) {
      result.textContent = payload.error || `Validation request failed (${response.status})`;
      return;
    }
    result.replaceChildren();
    if (payload.ok) {
      const success = document.createElement('p');
      success.className = 'validation-success';
      success.textContent = 'No CIDR, naming, or RBAC conflicts found.';
      result.appendChild(success);
    }
    (payload.issues || []).forEach(issue => {
      const item = document.createElement('p');
      item.className = issue.severity === 'error' ? 'validation-error' : 'validation-warning';
      item.textContent = `${issue.severity.toUpperCase()} ${issue.path}: ${issue.message}`;
      result.appendChild(item);
    });
  } catch (error) {
    result.textContent = `Validation request failed: ${error.message}`;
  }
}

// ── Apply JSON Schema ───────────────────────────────────────────────
async function applySchema() {
  const raw = document.getElementById('json-schema').value.trim();
  if (!raw) return setStatus('Paste a JSON Schema first', true);
  let schema;
  try { schema = JSON.parse(raw); } catch { return setStatus('Invalid JSON', true); }

  try {
    const resp = await fetch('/tf_wizard/schema/apply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ schema })
    });
    const data = await resp.json();
    if (!resp.ok) return setStatus(data.error || 'Schema error', true);
    (data.variables || []).forEach(v => addVariable(v.name, v.type, v.description, v.default));
    setStatus(`Imported ${data.variables.length} variable(s) from schema`, false);
  } catch (e) {
    setStatus('Network error: ' + e.message, true);
  }
}

// ── Generate Module ZIP ─────────────────────────────────────────────
async function generateModule() {
  const spec = buildSpec();
  if (spec.resourceErrors.length) {
    return setStatus(`Fix invalid resource attributes JSON: ${spec.resourceErrors.join('; ')}`, true);
  }
  setStatus('Generating...', false);
  try {
    const resp = await fetch('/tf_wizard/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(spec)
    });
    if (!resp.ok) {
      const err = await resp.json();
      return setStatus(err.error || 'Generation failed', true);
    }
    const blob = await resp.blob();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `terraform_module_${spec.module_name || 'module'}.zip`;
    a.click();
    URL.revokeObjectURL(a.href);
    setStatus('Module downloaded!', false);
  } catch (e) {
    setStatus('Network error: ' + e.message, true);
  }
}

// ── Status bar ──────────────────────────────────────────────────────
function setStatus(msg, isError) {
  const el = document.getElementById('status-msg');
  el.innerHTML = msg;
  el.className = isError ? 'status-error' : 'status-success';
  if (!isError) setTimeout(() => { el.textContent = 'Ready'; el.className = ''; }, 5000);
}

// ── Init ────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const filter = document.getElementById('resource-filter');
  const catalog = document.getElementById('resource-preset');
  filter?.addEventListener('input', () => {
    const query = filter.value.trim().toLowerCase();
    Array.from(catalog.options).forEach(option => {
      option.hidden = Boolean(query) && !option.textContent.toLowerCase().includes(query);
    });
    Array.from(catalog.querySelectorAll('optgroup')).forEach(group => {
      group.hidden = Boolean(query) && !Array.from(group.options).some(option => !option.hidden);
    });
  });
  document.querySelectorAll('.guided-component-grid input, .guided-hook, #guided-pipeline, #guided-local-sandbox, #guided-azure-sandbox')
    .forEach(input => input.addEventListener('change', updateGuidedReview));
  selectGuidedTemplate(document.getElementById('guided-template')?.value || 'enterprise');
  showGuidedStep(0);
  livePreview();
});

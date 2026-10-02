/* ── TF Wizard – CAF-compliant client logic ──────────────────────── */

// ── State ───────────────────────────────────────────────────────────
let activeTab = 'versions';
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

function addVariable(name, type, desc, def_val) {
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
    <button class="btn danger" onclick="this.parentElement.remove();livePreview()">&#x2715;</button>`;
  document.getElementById('vars-list').appendChild(row);
  livePreview();
}

function addResource(type_, rname) {
  const row = document.createElement('div');
  row.className = 'entry-row resource-row';
  row.innerHTML = `
    <input type="text" placeholder="Type (e.g. aws_instance)" class="res-type" value="${esc(type_)}" oninput="livePreview()" />
    <input type="text" placeholder="Name" class="res-name" value="${esc(rname)}" oninput="livePreview()" />
    <button class="btn danger" onclick="this.parentElement.remove();livePreview()">&#x2715;</button>`;
  document.getElementById('resources-list').appendChild(row);
  livePreview();
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
  (archetype.resources || []).forEach(r => addResource(r.type, r.name));
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
  document.querySelectorAll('.var-row').forEach(r => {
    const name = r.querySelector('.var-name')?.value.trim();
    if (name) variables.push({
      name,
      type: r.querySelector('.var-type')?.value || 'string',
      description: r.querySelector('.var-desc')?.value.trim() || '',
      default: r.querySelector('.var-default')?.value.trim() || null
    });
  });

  const resources = [];
  document.querySelectorAll('.resource-row').forEach(r => {
    const type = r.querySelector('.res-type')?.value.trim();
    const rname = r.querySelector('.res-name')?.value.trim();
    if (type && rname) resources.push({ type, name: rname, attributes: {} });
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
  return { module_name, providers, variables, resources, outputs, backend };
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
  previewCache.versions = ver;

  // variables.tf
  let vars = '';
  spec.variables.forEach(v => {
    vars += `variable "${v.name}" {\n  type        = ${v.type}\n`;
    if (v.description) vars += `  description = "${v.description}"\n`;
    if (v.default)     vars += `  default     = ${JSON.stringify(v.default)}\n`;
    vars += '}\n\n';
  });
  previewCache.variables = vars || '# No variables defined\n';

  // main.tf
  let main = '';
  spec.resources.forEach(r => {
    main += `resource "${r.type}" "${r.name}" {\n  # TODO: add attributes\n}\n\n`;
  });
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
}

function renderPreview() {
  const code = previewCache[activeTab] || '# Select a tab...';
  document.getElementById('preview-code').textContent = code;
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

  if (errors.length) {
    setStatus(`Validation failed: ${errors.join('; ')}`, true);
  } else {
    setStatus('Validation passed &#x2705;', false);
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
document.addEventListener('DOMContentLoaded', () => livePreview());

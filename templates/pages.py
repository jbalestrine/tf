"""
MasterChief Page Templates

Contains page-specific HTML templates.
"""

# Dashboard template
DASHBOARD_TEMPLATE = """{% extends "base.html" %}
{% block content %}
<div class="dashboard-grid">
<div class="card">
<h3>CPU Usage</h3>
<div class="stat-value" id="cpu-value">{{ stats.cpu.percent }}%</div>
<div class="progress-bar"><div class="progress-fill" id="cpu-progress" style="width:{{ stats.cpu.percent }}%"></div></div>
<div class="stat-label">{{ stats.cpu.count }} Cores</div>
</div>
<div class="card">
<h3>Memory Usage</h3>
<div class="stat-value" id="mem-value">{{ stats.memory.percent }}%</div>
<div class="progress-bar"><div class="progress-fill" id="mem-progress" style="width:{{ stats.memory.percent }}%"></div></div>
<div class="stat-label">{{ (stats.memory.used/1024/1024/1024)|round(2) }} GB / {{ (stats.memory.total/1024/1024/1024)|round(2) }} GB</div>
</div>
<div class="card">
<h3>Disk Usage</h3>
<div class="stat-value" id="disk-value">{{ stats.disk.percent }}%</div>
<div class="progress-bar"><div class="progress-fill" id="disk-progress" style="width:{{ stats.disk.percent }}%"></div></div>
<div class="stat-label">{{ (stats.disk.used/1024/1024/1024)|round(2) }} GB / {{ (stats.disk.total/1024/1024/1024)|round(2) }} GB</div>
</div>
<div class="card">
<h3>System Uptime</h3>
<div class="stat-value">{{ (stats.uptime/3600)|int }}h</div>
<div class="stat-label">{{ (stats.uptime/60)|int }} minutes</div>
</div>
</div>
<div class="section">
<h3>Quick Actions</h3>
<a href="/scripts" class="btn">Script Manager</a>
<a href="/processes" class="btn">Process Monitor</a>
<a href="/services" class="btn">Service Monitor</a>
<a href="/addons" class="btn">Install Addons</a>
<a href="/web_ide" class="btn">Web IDE</a>
<a href="/masterchief_code_ui" class="btn">MasterChief Code UI</a>
<a href="/iac_manager" class="btn">IAC Manager</a>
<a href="/arm_creator" class="btn">ARM Template Creator</a>
<a href="/tf_wizard" class="btn">TF Wizard</a>
<a href="/gallery" class="btn">Art Gallery</a>
<a href="/github" class="btn">GitHub Integration</a>
</div>
{% endblock %}"""

# Scripts templates
SCRIPTS_TEMPLATE = """{% extends "base.html" %}
{% block content %}
<div class="section">
<h2>Script Manager</h2>
<div style="display:flex;gap:8px;align-items:center;">
<button onclick="openModal('addScriptModal')" class="btn">Add New Script</button>
<button onclick="refreshIndex()" class="btn">Refresh Index</button>
</div>
<table>
<thead>
<tr>
<th>Name</th>
<th>Type</th>
<th>Size</th>
<th>Modified</th>
<th>Actions</th>
</tr>
</thead>
<tbody>
{% for script in scripts %}
<tr>
<td>{{ script.name }}</td>
<td>{{ script.type }}</td>
<td>{{ (script.size/1024)|round(2) }} KB</td>
<td>{{ script.modified[:16] }}</td>
<td>
{% if script.source=='repo' %}
<a href="/scripts/edit/{{ script.path | b64encode }}" class="btn btn-info">Edit</a>
<a href="/scripts/exec_path/{{ script.path | b64encode }}" class="btn">Execute</a>
{% else %}
<a href="/scripts/view/{{ script.name }}" class="btn btn-info">View</a>
<a href="/scripts/execute/{{ script.name }}" class="btn">Execute</a>
<a href="/scripts/delete/{{ script.name }}" class="btn btn-danger" onclick="return confirmDelete('{{ script.name }}');">Delete</a>
{% endif %}
</td>
</tr>
{% endfor %}
</tbody>
</table>
</div>
<div id="addScriptModal" class="modal">
<div class="modal-content">
<span class="close" onclick="closeModal('addScriptModal')">&times;</span>
<h2>Add New Script</h2>
<form method="POST" action="/scripts/add">
<div class="form-group">
<label>Script Name (include extension: .sh, .py, .ps1)</label>
<input type="text" name="filename" required placeholder="backup.sh">
</div>
<div class="form-group">
<label>Script Content</label>
<textarea name="content" rows="15" required placeholder="#!/bin/bash&#10;echo 'Hello World'"></textarea>
</div>
<button type="submit" class="btn">Add Script</button>
</form>
</div>
</div>
{% endblock %}"""

SCRIPT_VIEW_TEMPLATE = """{% extends "base.html" %}
{% block content %}
<div class="section">
<h2>Script: {{ filename }}</h2>
<pre><code>{{ content }}</code></pre>
<a href="/scripts" class="btn btn-warning">Back to Scripts</a>
<a href="/scripts/execute/{{ filename }}" class="btn">Execute</a>
</div>
{% endblock %}"""

SCRIPT_EXECUTE_TEMPLATE = """{% extends "base.html" %}
{% block content %}
<div class="section">
<h2>Execute Script: {{ filename }}</h2>
<form method="POST" action="/scripts/run/{{ filename }}">
<div class="form-group">
<label>Arguments (optional)</label>
<input type="text" name="args" placeholder="arg1 arg2 arg3">
</div>
<button type="submit" class="btn">Run Script</button>
<a href="/scripts" class="btn btn-warning">Cancel</a>
</form>
{% if result %}
<h3>Execution Result</h3>
<p><strong>Success:</strong> {{ result.success }}</p>
{% if result.returncode is defined %}
<p><strong>Return Code:</strong> {{ result.returncode }}</p>
{% endif %}
{% if result.stdout %}
<h4>Output:</h4>
<pre><code>{{ result.stdout }}</code></pre>
{% endif %}
{% if result.stderr %}
<h4>Errors:</h4>
<pre style="border-left-color:#f44336;"><code>{{ result.stderr }}</code></pre>
{% endif %}
{% if result.error %}
<div class="alert alert-error">{{ result.error }}</div>
{% endif %}
{% endif %}
</div>
{% endblock %}"""

# Modules template
MODULES_TEMPLATE = """{% extends "base.html" %}
{% block content %}
<div class="section">
<h2>Module Manager</h2>
<p>Configure which modules are enabled in your MasterChief installation.</p>
<form method="POST" action="/modules/save">
{% for module_name, module_config in enabled_modules.items() %}
<div class="card">
<h3>{{ module_name.title() }} Module</h3>
<div class="form-group">
<label>
<input type="checkbox" name="enabled_{{ module_name }}" {% if module_config.enabled %}checked{% endif %}>
Enable {{ module_name.title() }} Module
</label>
</div>
{% if module_config.get('db_path') %}
<div class="form-group">
<label>Database Path: {{ module_config.db_path }}</label>
</div>
{% endif %}
</div>
{% endfor %}
<button type="submit" class="btn">Save Configuration</button>
</form>
</div>
<div class="section">
<h2>Manager Status</h2>
<table>
<thead>
<tr>
<th>Manager</th>
<th>Status</th>
<th>Description</th>
</tr>
</thead>
<tbody>
{% for name, manager in managers.items() %}
<tr>
<td>{{ name }}</td>
<td><span class="status-badge status-{{ 'running' if manager.available else 'stopped' }}">{{ 'Available' if manager.available else 'Unavailable' }}</span></td>
<td>{{ manager.description }}</td>
</tr>
{% endfor %}
</tbody>
</table>
</div>
{% endblock %}"""

# Resources template
ECHO_RESOURCES_TEMPLATE = """{% extends "base.html" %}

{% block content %}

<h3>Resources: Reference / Templates / Examples</h3>

<div style="display:flex;gap:20px;align-items:flex-start;">

<div style="flex:1;max-width:420px;">

<form id="uploadForm" enctype="multipart/form-data" onsubmit="uploadResource(event)">

<label>File: <input type="file" name="file" required></label><br><br>

<label>Category:

<select name="category">

<option value="reference">Reference Dictionary</option>

<option value="template">Template Ingestion</option>

<option value="examples">Chat Examples</option>

</select></label><br><br>

<label><input type="checkbox" name="for_training"> Use for training</label><br>

<label><input type="checkbox" name="for_ingestion" checked> Use for ingestion</label><br>

<label><input type="checkbox" name="persona"> Upload as Personality (persona)</label><br><br>

<button class="btn btn-primary" type="submit">Upload</button>

</form>

<div id="uploadMsg" style="margin-top:10px;color:#6c6"></div>

</div>

<div style="flex:2;">

<h4>Existing Resources</h4>

</div>

<div style="flex:2;">

<h4>Existing Resources</h4>

<div style="margin-bottom:10px;">

Session id: <input id="sessionIdInput" placeholder="session id (optional)" style="width:220px;margin-right:8px;"> <button onclick="fetchPersonaStatus()">Check Persona</button>

<select id="resourceSelect" style="width:60%;margin-left:8px"></select>

<button onclick="enableSelectedPersona()">Enable persona for session</button>

<div id="personaStatus" style="margin-top:6px;color:#8f8"></div>

</div>

<div id="resourcesList">(loading...)</div>

</div>

</div>

<script>

        // Training page render helper

        function showTrainingPage(){

            const el = document.getElementById('trainingPage');

            if(!el) return;

        }

function uploadResource(e){

 e.preventDefault();

 const f = document.getElementById('uploadForm');

const fd = new FormData(f);



fetch('/api/resources/upload',{method:'POST',body:fd}).then(r=>r.json()).then(j=>{

     document.getElementById('uploadMsg').textContent = j.message || JSON.stringify(j);

     loadResources();

 }).catch(e=>{document.getElementById('uploadMsg').textContent='Upload failed';console.error(e)});

}

function loadResources(){

 fetch('/api/resources/list').then(r=>r.json()).then(j=>{

     const el=document.getElementById('resourcesList');

     el.innerHTML='';

     const idx=j || {};

     const sel = document.getElementById('resourceSelect'); sel.innerHTML='';

     Object.keys(idx).forEach(k=>{

         const r = idx[k];

         const div=document.createElement('div');

         div.style.border='1px solid #333';div.style.padding='8px';div.style.marginBottom='6px';

         let personaBadge = r.persona ? ' <span style="color:#ffb86b;font-weight:bold">[PERSONA]</span>' : '';

         div.innerHTML = '<b>'+r.filename+'</b> '+personaBadge+' <small>['+r.category+']</small><br>'+

             '<button class="btn btn-sm" onclick="loadIntoSession(\''+encodeURIComponent(k)+'\')">Load into session</button> '

             +'<button class="btn btn-sm btn-danger" onclick="deleteResource(\''+encodeURIComponent(k)+'\')">Delete</button>';

         // also add to select

         const opt = document.createElement('option'); opt.value = k; opt.text = r.filename + (r.persona ? ' [PERSONA]' : ''); sel.appendChild(opt);

         el.appendChild(div);

     });

 }).catch(e=>{document.getElementById('resourcesList').textContent='Failed to load resources';console.error(e)});

}

function fetchPersonaStatus(){

    const sid = document.getElementById('sessionIdInput').value || '';

    fetch('/api/personality/status?session_id='+encodeURIComponent(sid)).then(r=>r.json()).then(j=>{

        const p = j.personality;

        const out = document.getElementById('personaStatus');

        if(p && p.enabled){

            out.textContent = `Enabled: ${p.id}`;

        } else {

            out.textContent = 'No persona enabled for session';

        }

    }).catch(e=>{console.error(e)});

}



function enableSelectedPersona(){

    const sel = document.getElementById('resourceSelect');

    if(!sel.value){ alert('Select a resource first'); return; }

    const sid = document.getElementById('sessionIdInput').value || '';

    fetch('/api/resources/load',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id: decodeURIComponent(sel.value), session_id: sid || '', use_persona: true, for_ingestion: true})}).then(r=>r.json()).then(j=>{

        alert(j.message || JSON.stringify(j));

        fetchPersonaStatus();

    }).catch(e=>{console.error(e)});

}

function deleteResource(id){ if(!confirm('Delete resource?')) return; fetch('/api/resources/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:decodeURIComponent(id)})}).then(r=>r.json()).then(j=>{ loadResources(); }).catch(e=>console.error(e)); }

function loadIntoSession(id){ const sid = prompt('Load into which session id? (leave blank for current page session)'); fetch('/api/resources/load',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:decodeURIComponent(id), session_id: sid || ''})}).then(r=>r.json()).then(j=>{ alert(j.message||JSON.stringify(j)); }).catch(e=>console.error(e)); }

loadResources();

</script>

{% endblock %}"""

# Addons modules template
ADDONS_MODULES_TEMPLATE = """{% extends "base.html" %}

{% block content %}

<div class="section">

<h2>🧩 Addons Modules</h2>

<p>Manage installed addon modules, configure settings, install dependencies, and run services.</p>
<link rel="stylesheet" href="/static/css/management-navigation.css">
<nav class="management-navigation" data-management-page="addons" aria-label="Management Center"><a href="/master-menu">Management Center</a></nav>
<script src="/static/js/management-navigation.js" defer></script>
<div id="management-inventory"></div>
<script src="/static/js/management-inventory.js" defer></script>

{% if installed_modules %}

<h3>Installed Modules ({{ installed_modules|length }} modules)</h3>

<div style="margin-bottom: 20px;">
<button class="btn" style="background: #f44336; color: white;" onclick="deleteAllModules()" id="delete-all-btn">🗑️ Delete All Modules</button>
<span id="delete-status" style="margin-left: 10px; display: none;"></span>
</div>

<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; margin-top: 20px;">

{% for module in installed_modules %}

<div class="card" style="border-left-color: #FF6B35;" id="module-card-{{ module.name }}">

<h3 style="color: #FF6B35;">{{ module.name }}{% if module.build_commands %} <span style="font-size: 0.7em; background: #FF5722; color: white; padding: 2px 6px; border-radius: 3px;">🔨</span>{% endif %}</h3>

<div style="margin: 10px 0;">

<span class="status-badge" style="background: #4CAF50;">{{ module.language|upper }}</span>

<span class="status-badge" style="background: #2196F3;">{{ module.files }} files</span>

<span class="status-badge" style="background: #FF9800;">{{ (module.size/1024)|round(1) }} KB</span>

{% if module.build_commands %}

<span style="margin-left: 10px;">

<form method="POST" action="/addons/modules/{{ module.name }}/build" style="display: inline;">

<button type="submit" class="btn" style="background: #FF5722; font-size: 0.8em; padding: 4px 8px;" onclick="return confirm('Build/compile {{ module.name }}?')">🔨 Build</button>

</form>

</span>

{% endif %}

</div>

<p><strong>Path:</strong> {{ module.path }}</p>

<p><strong>Modified:</strong> {{ module.modified }}</p>

<div style="margin-top: 15px; display:flex; gap:8px; flex-wrap:wrap; align-items:center;">
<a href="/addons/modules/{{ module.name }}/manager" class="btn" style="background:#2196F3;">🗂️ Manage Files</a>
{% if module.name in ui_modules %}
<button id="pin-btn-{{ module.name }}" class="btn" style="background:#c62828;" onclick="unpinModule('{{ module.name }}')">📌 Unpin from Nav</button>
{% else %}
<button id="pin-btn-{{ module.name }}" class="btn" style="background:#4CAF50;" onclick="pinModule('{{ module.name }}')">📌 Pin to Nav</button>
{% endif %}
<span id="pin-status-{{ module.name }}" style="font-size:0.8em;"></span>
</div>

<div style="margin-top: 15px;">

<h4>Configuration Files</h4>

{% if module.config_files %}

<ul style="margin: 5px 0; padding-left: 20px;">

{% for config in module.config_files %}

<li><a href="/addons/modules/{{ module.name }}/config/{{ config }}" class="btn btn-info" style="font-size: 0.8em; padding: 4px 8px;">📝 {{ config }}</a></li>

{% endfor %}

</ul>

{% else %}

<p style="color: #888; font-style: italic;">No config files found</p>

{% endif %}

</div>

<div style="margin-top: 15px;">

<h4>Setup & Dependencies</h4>

{% if module.requirements_files %}

<form method="POST" action="/addons/modules/{{ module.name }}/install_deps" style="display: inline;">

<button type="submit" class="btn" style="background: #4CAF50;">📦 Install Dependencies</button>

</form>

{% endif %}

{% if module.setup_scripts %}

<h5>Setup Scripts:</h5>

<ul style="margin: 5px 0; padding-left: 20px;">

{% for script in module.setup_scripts %}

<li>
{% if script.endswith('.php') %}
<a href="/addons/modules/{{ module.name }}/web/{{ script }}" class="btn" style="background: #9C27B0;" target="_blank">🌐 View {{ script }}</a>
<span style="font-size: 0.8em; color: #888;"> (Web-based installer)</span>
{% else %}
<form method="POST" action="/addons/modules/{{ module.name }}/run_setup/{{ script }}" style="display: inline;">
<button type="submit" class="btn" style="background: #FF9800;" onclick="return confirm('Run setup script: {{ script }}?')">▶️ {{ script }}</button>
</form>
{% endif %}
</li>

{% endfor %}

</ul>

{% endif %}

</div>

{% if module.build_commands %}

<div style="margin-top: 15px;">

<h4>Build & Compile</h4>

<p style="font-size: 0.9em; color: #888;">Project Type: {{ module.project_type }}{% if module.frameworks %} | Frameworks: {{ module.frameworks|join(', ') }}{% endif %}</p>

<form method="POST" action="/addons/modules/{{ module.name }}/build" style="display: inline;">

<button type="submit" class="btn" style="background: #FF5722;" onclick="return confirm('Build/compile {{ module.name }}? This may take several minutes.')">🔨 Build Project</button>

</form>

<p style="font-size: 0.8em; color: #666; margin-top: 5px;">{{ module.build_commands|length }} build step(s) detected</p>

</div>

{% endif %}

<div style="margin-top: 15px;">

<h4>Service Control</h4>

<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
<button class="btn" style="background: #4CAF50;" onclick="startService('{{ module.name }}')">▶️ Start</button>
<button class="btn btn-warning" onclick="stopService('{{ module.name }}')">⏹️ Stop</button>
<button class="btn btn-info" onclick="checkServiceStatus('{{ module.name }}')">📊 Status</button>
<a id="open-app-btn-{{ module.name }}" href="#" target="_blank"
   class="btn" style="background:#7B1FA2;display:none;">🌐 Open App</a>
<button class="btn" style="background:#c62828;margin-left:auto;" onclick="deleteModule('{{ module.name }}')">🗑️ Delete</button>
</div>

<div id="service-status-{{ module.name }}" style="margin-top: 10px; padding: 10px; background: #1a1a1a; border-radius: 5px; display: none;"></div>

</div>

<div style="margin-top: 15px;">

<h4>Documentation</h4>

{% if module.readme_files %}

<ul style="margin: 5px 0; padding-left: 20px;">

{% for readme in module.readme_files %}

<li><a href="/addons/modules/{{ module.name }}/config/{{ readme }}" class="btn" style="background: #9C27B0; font-size: 0.8em; padding: 4px 8px;">📖 {{ readme }}</a></li>

{% endfor %}

</ul>

{% else %}

<p style="color: #888; font-style: italic;">No documentation found</p>

{% endif %}

</div>

</div>

{% endfor %}

</div>

{% else %}

<h3>No Installed Modules</h3>

<p>No addon modules are currently installed. Install addons from the <a href="/addons">Addons</a> page to see them here.</p>

{% endif %}

</div>

<script>

function _showOpenBtn(moduleName, url) {
    const btn = document.getElementById('open-app-btn-' + moduleName);
    if (btn && url) {
        btn.href = url;
        btn.style.display = 'inline-block';
    }
}

function _hideOpenBtn(moduleName) {
    const btn = document.getElementById('open-app-btn-' + moduleName);
    if (btn) btn.style.display = 'none';
}

function _setStatus(moduleName, html) {
    const d = document.getElementById('service-status-' + moduleName);
    if (d) { d.style.display = 'block'; d.innerHTML = html; }
}

function startService(moduleName) {
    _setStatus(moduleName, '⏳ Starting…');
    fetch(`/addons/modules/${moduleName}/start`, { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                _setStatus(moduleName, `<span style="color:#f44336">❌ ${data.error}</span>`);
                return;
            }
            const proxyUrl = data.proxy_url || data.url || null;
            if (data.status === 'blueprint') {
                _setStatus(moduleName,
                    `<span style="color:#4CAF50">✅ Loaded as Blueprint (routes live in this server)</span><br>` +
                    (proxyUrl ? `<a href="${proxyUrl}" target="_blank" style="color:#7B1FA2">🌐 Open App</a>` : ''));
                if (proxyUrl) _showOpenBtn(moduleName, proxyUrl);
            } else if (data.status === 'html') {
                _setStatus(moduleName, `🌐 Static HTML app — <a href="${proxyUrl}" target="_blank">open in new tab</a>`);
                _showOpenBtn(moduleName, proxyUrl);
            } else {
                const portInfo = data.port ? ` on port <b>${data.port}</b>` : '';
                const pidInfo  = data.pid  ? ` (PID ${data.pid})`          : '';
                const appUrl = data.port ? `http://${window.location.hostname}:${data.port}` : proxyUrl;
                _setStatus(moduleName,
                    `<span style="color:#4CAF50">✅ ${data.entry_point || 'App'} started${portInfo}${pidInfo}</span><br>` +
                    (appUrl ? `<a href="${appUrl}" target="_blank" style="color:#7B1FA2">🌐 Open App</a>` : '') +
                    `<br><small style="color:#888">The app may take a few seconds to be ready.</small>`);
                if (appUrl) _showOpenBtn(moduleName, appUrl);
            }
        })
        .catch(e => _setStatus(moduleName, `<span style="color:#f44336">❌ ${e}</span>`));
}

function stopService(moduleName) {
    fetch(`/addons/modules/${moduleName}/stop`, { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            _setStatus(moduleName, data.message || 'Service stopped');
            _hideOpenBtn(moduleName);
        })
        .catch(e => _setStatus(moduleName, 'Error: ' + e));
}

function checkServiceStatus(moduleName) {
    fetch(`/addons/modules/${moduleName}/status`)
        .then(r => r.json())
        .then(data => {
            if (data.status === 'running') {
                const appUrl = data.port ? `http://${window.location.hostname}:${data.port}` : (data.proxy_url || null);
                _setStatus(moduleName,
                    `<span style="color:#4CAF50">● Running</span> — ` +
                    `PID: <b>${data.pid}</b>, Port: <b>${data.port || 'N/A'}</b><br>` +
                    (data.entry_point ? `Entry: <code>${data.entry_point}</code><br>` : '') +
                    (appUrl ? `<a href="${appUrl}" target="_blank" style="color:#7B1FA2">🌐 Open App</a>` : ''));
                if (appUrl) _showOpenBtn(moduleName, appUrl);
            } else if (data.status === 'blueprint') {
                const proxyUrl = data.proxy_url || null;
                _setStatus(moduleName,
                    `<span style="color:#4CAF50">● Blueprint (live routes)</span><br>` +
                    (proxyUrl ? `<a href="${proxyUrl}" target="_blank" style="color:#7B1FA2">🌐 Open App</a>` : ''));
                if (proxyUrl) _showOpenBtn(moduleName, proxyUrl);
            } else {
                _setStatus(moduleName, '<span style="color:#888">● Stopped</span>');
                _hideOpenBtn(moduleName);
            }
        })
        .catch(e => _setStatus(moduleName, 'Error: ' + e));
}

// Auto-check status for all modules on page load
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[id^="service-status-"]').forEach(el => {
        const name = el.id.replace('service-status-', '');
        checkServiceStatus(name);
    });
});

function deleteModule(moduleName) {
    if (!confirm(`Delete module "${moduleName}"? This will stop the service and remove all files.`)) return;
    fetch(`/addons/modules/${moduleName}/delete`, { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                const card = document.getElementById('module-card-' + moduleName);
                if (card) {
                    card.style.transition = 'opacity 0.3s';
                    card.style.opacity = '0';
                    setTimeout(() => card.remove(), 300);
                } else {
                    window.location.reload();
                }
            } else {
                alert('Error deleting module: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(e => alert('Error: ' + e));
}

function deleteAllModules() {
    if (!confirm('Are you sure you want to delete ALL installed modules? This action cannot be undone!')) {
        return;
    }
    
    const btn = document.getElementById('delete-all-btn');
    const status = document.getElementById('delete-status');
    
    btn.disabled = true;
    btn.textContent = '🗑️ Deleting...';
    status.style.display = 'inline';
    status.textContent = 'Deleting all modules...';
    status.style.color = '#ff9800';
    
    fetch('/addons/modules/delete_all', { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                status.textContent = 'All modules deleted successfully!';
                status.style.color = '#4CAF50';
                // Reload the page after a short delay
                setTimeout(() => {
                    window.location.reload();
                }, 2000);
            } else {
                status.textContent = 'Error: ' + (data.error || 'Unknown error');
                status.style.color = '#f44336';
                btn.disabled = false;
                btn.textContent = '🗑️ Delete All Modules';
            }
        })
        .catch(e => {
            status.textContent = 'Error: ' + e;
            status.style.color = '#f44336';
            btn.disabled = false;
            btn.textContent = '🗑️ Delete All Modules';
        });
}

function pinModule(moduleName) {
    const btn = document.getElementById('pin-btn-' + moduleName);
    const status = document.getElementById('pin-status-' + moduleName);
    if (btn) { btn.disabled = true; btn.textContent = '⏳ Pinning…'; }
    fetch(`/addons/modules/${moduleName}/api/ui_integration`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'add' })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            if (btn) { btn.textContent = '📌 Unpin from Nav'; btn.style.background = '#c62828'; btn.onclick = () => unpinModule(moduleName); btn.disabled = false; }
            if (status) { status.textContent = '✅ Pinned!'; status.style.color = '#4CAF50'; }
        } else {
            if (btn) { btn.textContent = '📌 Pin to Nav'; btn.disabled = false; }
            if (status) { status.textContent = '❌ ' + (data.error || 'Failed'); status.style.color = '#f44336'; }
        }
    })
    .catch(e => {
        if (btn) { btn.textContent = '📌 Pin to Nav'; btn.disabled = false; }
        if (status) { status.textContent = '❌ ' + e; status.style.color = '#f44336'; }
    });
}

function unpinModule(moduleName) {
    const btn = document.getElementById('pin-btn-' + moduleName);
    const status = document.getElementById('pin-status-' + moduleName);
    if (btn) { btn.disabled = true; btn.textContent = '⏳ Unpinning…'; }
    fetch(`/addons/modules/${moduleName}/api/ui_integration`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'remove' })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            if (btn) { btn.textContent = '📌 Pin to Nav'; btn.style.background = '#4CAF50'; btn.onclick = () => pinModule(moduleName); btn.disabled = false; }
            if (status) { status.textContent = '✅ Unpinned'; status.style.color = '#888'; }
        } else {
            if (btn) { btn.textContent = '📌 Unpin from Nav'; btn.disabled = false; }
            if (status) { status.textContent = '❌ ' + (data.error || 'Failed'); status.style.color = '#f44336'; }
        }
    })
    .catch(e => {
        if (btn) { btn.textContent = '📌 Unpin from Nav'; btn.disabled = false; }
        if (status) { status.textContent = '❌ ' + e; status.style.color = '#f44336'; }
    });
}

</script>

{% endblock %}"""

# Module manager template
MODULE_MANAGER_TEMPLATE = """{% extends "base.html" %}

{% block content %}

<div class="container">

<header>

<h1>⚡ MasterChief</h1>

<p class="subtitle">Module Manager - {{ module.name }}</p>

<div style="position:absolute;right:20px;top:24px;">

    <a href="/addons/modules" class="btn" style="background:#666;">← Back to Modules</a>

    <label style="color:#ccc;font-size:0.9em;margin-left:20px;">Language: <select id="langSelect"        

style="background:#1a1a1a;color:#eee;border:1px solid

#333;padding:6px;border-radius:6px;"><option value="en">English</option><option

value="es">Español</option></select></label>

    </div>

</header>

<nav>

<a href="/" class="">Dashboard</a>

<a href="/echo-chat" class="">🌙 Echo Chat</a>

<a href="/scripts" class="">Scripts</a>

<a href="/processes" class="">Processes</a>

<a href="/services" class="">Services</a>

<a href="/addons" class="active">Addons</a>

<a href="/addons/modules" class="">🧩 Modules</a>

<a href="/echo-train" class="">Training</a>

</nav>

<div class="section">

<h2>🗂️ Module Manager: {{ module.name }}</h2>

<div style="display: flex; gap: 20px; margin-bottom: 20px;">

<div style="flex: 1;">

<h3>📁 Module Information</h3>

<div class="card">

<p><strong>Name:</strong> {{ module.name }}</p>

<p><strong>Path:</strong> {{ module.path }}</p>

<p><strong>Files:</strong> {{ module.file_count }}</p>

<p><strong>Directories:</strong> {{ module.dir_count }}</p>

<p><strong>Total Size:</strong> {{ "%.1f"|format(module.total_size/1024) }} KB</p>

</div>

<h3>⚙️ Module Configuration</h3>

<div class="card">

<h4>UI Integration</h4>

<p>Add this module to the main navigation menu for quick access.</p>

<button id="addToUI" class="btn" style="background:#4CAF50;" onclick="toggleUIIntegration('add')">➕ Add to Main UI</button>

<button id="removeFromUI" class="btn btn-danger" style="display:none;" onclick="toggleUIIntegration('remove')">➖ Remove from Main UI</button>

<div id="uiStatus" style="margin-top:10px;"></div>

</div>

</div>

<div style="flex: 2;">

<h3>📂 File Explorer</h3>

<div class="card">

<div style="display: flex; gap: 10px; margin-bottom: 15px;">

<button class="btn" onclick="refreshFiles()">🔄 Refresh</button>

<label class="btn" for="fileUpload" style="background:#2196F3;">📤 Upload File</label>

<input type="file" id="fileUpload" style="display:none;" onchange="uploadFile()">

<button class="btn" onclick="createNewFile()" style="background:#FF9800;">📄 New File</button>

<button class="btn" onclick="createNewFolder()" style="background:#9C27B0;">📁 New Folder</button>

</div>

<div id="fileTree" style="max-height: 400px; overflow-y: auto; border: 1px solid #333; border-radius: 5px; padding: 10px; background: #1a1a1a;">

<!-- File tree will be loaded here -->

</div>

</div>

</div>

</div>

<div class="section">

<h3>📝 File Editor</h3>

<div id="editorContainer" style="display: none;">

<div class="card">

<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">

<h4 id="editorTitle">Editing: <span id="currentFile"></span></h4>

<div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;">

<button class="btn" onclick="saveFile()" style="background:#4CAF50;">💾 Save</button>

<button class="btn" onclick="saveAndReload()" style="background:#00897B;">💾🔄 Save &amp; Reload</button>

<button class="btn btn-danger" onclick="deleteFile()">🗑️ Delete</button>

<button class="btn" onclick="closeEditor()">❌ Close</button>

<button class="btn" onclick="toggleSnippets()" style="background:#7B1FA2;">✂️ Snippets</button>

<span id="saveStatus" style="font-size:0.85em;margin-left:8px;"></span>

</div>

</div>

<div style="display:flex;gap:12px;">

<div id="snippetsPanel" style="display:none;width:240px;flex-shrink:0;background:#1a1a1a;border:1px solid #444;border-radius:6px;padding:10px;overflow-y:auto;max-height:420px;">
<h5 style="color:#9C27B0;margin:0 0 10px 0;">✂️ Snippets</h5>
<div id="snippetList"></div>
</div>

<textarea id="fileEditor" style="flex:1;height:420px;background:#1a1a1a;color:#e0e0e0;border:1px solid #3a3a3a;border-radius:5px;padding:10px;font-family:'Courier New',monospace;font-size:14px;resize:vertical;"></textarea>

</div>

</div>

</div>

</div>

<!-- Modals -->

<!-- New File Modal -->
<div id="newFileModal" class="modal">
<div class="modal-content">
<span class="close" onclick="closeModal('newFileModal')">&times;</span>
<h2>📄 Create New File</h2>
<input type="text" id="newFileName" placeholder="filename.txt" style="width:100%;margin:10px 0;padding:8px;">
<button class="btn" onclick="createFile()">Create File</button>
</div>
</div>

<!-- New Folder Modal -->
<div id="newFolderModal" class="modal">
<div class="modal-content">
<span class="close" onclick="closeModal('newFolderModal')">&times;</span>
<h2>📁 Create New Folder</h2>
<input type="text" id="newFolderName" placeholder="folder_name" style="width:100%;margin:10px 0;padding:8px;">
<button class="btn" onclick="createFolder()">Create Folder</button>
</div>
</div>

<!-- Upload Modal -->
<div id="uploadModal" class="modal">
<div class="modal-content">
<span class="close" onclick="closeModal('uploadModal')">&times;</span>
<h2>📤 Upload File</h2>
<form id="uploadForm" enctype="multipart/form-data">
<input type="file" id="uploadFileInput" name="file" style="width:100%;margin:10px 0;">
<div id="uploadPathContainer" style="margin:10px 0;">
<label>Upload to folder (optional):</label>
<input type="text" id="uploadPath" placeholder="path/to/folder" style="width:100%;padding:8px;">
</div>
<button type="button" class="btn" onclick="doUpload()">Upload</button>
</form>
<div id="uploadStatus"></div>
</div>
</div>

</div>

<script>

// Global variables
let currentModule = '{{ module.name }}';
let currentFile = null;
let fileTree = {};

function init() {
    loadFiles();
    checkUIIntegration();
}

function loadFiles() {
    fetch(`/addons/modules/${currentModule}/api/files`)
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                alert('Error loading files: ' + data.error);
                return;
            }
            renderFileTree(data.files);
        })
        .catch(e => alert('Error: ' + e));
}

function renderFileTree(files) {
    fileTree = {};
    
    // Organize files by directory
    files.forEach(file => {
        const pathParts = file.path.split('/');
        let current = fileTree;
        
        for (let i = 0; i < pathParts.length - 1; i++) {
            const part = pathParts[i];
            if (!current[part]) {
                current[part] = { __type: 'directory', __children: {} };
            }
            current = current[part].__children;
        }
        
        const fileName = pathParts[pathParts.length - 1];
        current[fileName] = { 
            __type: file.type, 
            ...file,
            __children: file.type === 'directory' ? {} : undefined
        };
    });
    
    const treeHtml = renderTreeNode(fileTree, '', 0);
    document.getElementById('fileTree').innerHTML = treeHtml || '<p style="color:#888;">No files found</p>';
}

function renderTreeNode(node, path, depth) {
    let html = '';
    const indent = '  '.repeat(depth);
    
    for (const [name, item] of Object.entries(node)) {
        if (name.startsWith('__')) continue;
        
        const fullPath = path ? `${path}/${name}` : name;
        const isDir = item.__type === 'directory';
        const icon = isDir ? '📁' : getFileIcon(item.extension);
        
        html += `${indent}<div style="margin: 2px 0;">
            <span onclick="toggleDirectory('${fullPath}')" style="cursor: pointer; ${isDir ? 'font-weight: bold;' : ''}">
                ${icon} ${name}
            </span>
            ${!isDir ? ` <button class="btn" style="font-size:0.7em;padding:2px 6px;" onclick="editFile('${fullPath}')">Edit</button>` : ''}
        </div>`;
        
        if (isDir && item.__expanded) {
            html += renderTreeNode(item.__children || {}, fullPath, depth + 1);
        }
    }
    
    return html;
}

function toggleDirectory(path) {
    let current = fileTree;
    const parts = path.split('/');
    
    for (const part of parts) {
        if (current[part] && current[part].__type === 'directory') {
            current[part].__expanded = !current[part].__expanded;
            current = current[part].__children;
        }
    }
    
    renderFileTree(expandTreeToFiles(fileTree));
}

function expandTreeToFiles(node) {
    const files = [];
    
    function traverse(current, path) {
        for (const [name, item] of Object.entries(current)) {
            if (name.startsWith('__')) continue;
            
            const fullPath = path ? `${path}/${name}` : name;
            files.push({
                name: item.name || name,
                path: fullPath,
                type: item.__type,
                extension: item.extension || '',
                size: item.size || 0,
                modified: item.modified || ''
            });
            
            if (item.__type === 'directory' && item.__children) {
                traverse(item.__children, fullPath);
            }
        }
    }
    
    traverse(node, '');
    return files;
}

function getFileIcon(ext) {
    const icons = {
        '.py': '🐍', '.js': '📜', '.html': '🌐', '.css': '🎨', '.json': '📋',
        '.md': '📖', '.txt': '📄', '.xml': '📄', '.yml': '📋', '.yaml': '📋',
        '.sh': '⚡', '.bat': '⚡', '.ps1': '⚡', '.php': '🐘', '.sql': '🗄️',
        '.png': '🖼️', '.jpg': '🖼️', '.jpeg': '🖼️', '.gif': '🖼️', '.svg': '🖼️'
    };
    return icons[ext] || '📄';
}

function editFile(path) {
    fetch(`/addons/modules/${currentModule}/api/file?path=${encodeURIComponent(path)}`)
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                alert('Error loading file: ' + data.error);
                return;
            }
            
            currentFile = path;
            document.getElementById('currentFile').textContent = path;
            document.getElementById('fileEditor').value = data.content;
            document.getElementById('editorContainer').style.display = 'block';
            document.getElementById('fileEditor').focus();
        })
        .catch(e => alert('Error: ' + e));
}

function saveFile() {
    if (!currentFile) return;
    
    const content = document.getElementById('fileEditor').value;
    const statusEl = document.getElementById('saveStatus');
    statusEl.textContent = 'Saving…';
    statusEl.style.color = '#FFA726';
    
    fetch(`/addons/modules/${currentModule}/api/file?path=${encodeURIComponent(currentFile)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: content })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            statusEl.textContent = '✅ Saved';
            statusEl.style.color = '#4CAF50';
            setTimeout(() => { statusEl.textContent = ''; }, 3000);
        } else {
            statusEl.textContent = '❌ ' + (data.error || 'Save failed');
            statusEl.style.color = '#f44336';
        }
    })
    .catch(e => {
        statusEl.textContent = '❌ ' + e;
        statusEl.style.color = '#f44336';
    });
}

function saveAndReload() {
    if (!currentFile) return;
    const content = document.getElementById('fileEditor').value;
    const statusEl = document.getElementById('saveStatus');
    statusEl.textContent = 'Saving…';
    statusEl.style.color = '#FFA726';

    fetch(`/addons/modules/${currentModule}/api/file?path=${encodeURIComponent(currentFile)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: content })
    })
    .then(r => r.json())
    .then(data => {
        if (!data.success) throw new Error(data.error || 'Save failed');
        statusEl.textContent = 'Reloading…';
        statusEl.style.color = '#FFA726';
        return fetch(`/addons/load/${currentModule}`);
    })
    .then(r => r.json())
    .then(d => {
        statusEl.textContent = d.success ? '✅ Saved & reloaded' : '⚠️ Saved, reload: ' + (d.error || d.message || '');
        statusEl.style.color = d.success ? '#4CAF50' : '#FFA726';
        setTimeout(() => { statusEl.textContent = ''; }, 4000);
    })
    .catch(e => {
        statusEl.textContent = '❌ ' + e;
        statusEl.style.color = '#f44336';
    });
}

function deleteFile() {
    if (!currentFile) return;
    
    if (!confirm(`Are you sure you want to delete "${currentFile}"?`)) return;
    
    fetch(`/addons/modules/${currentModule}/api/file?path=${encodeURIComponent(currentFile)}`, {
        method: 'DELETE'
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            alert('File deleted successfully!');
            closeEditor();
            loadFiles();
        } else {
            alert('Error deleting file: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(e => alert('Error: ' + e));
}

function closeEditor() {
    document.getElementById('editorContainer').style.display = 'none';
    currentFile = null;
    document.getElementById('fileEditor').value = '';
    document.getElementById('saveStatus').textContent = '';
}

const SNIPPETS = [
    { label: 'Flask route (GET)', ext: ['.py'], code: "@bp.route('/path', methods=['GET'])\\ndef my_route():\\n    return jsonify({'status': 'ok'})\\n" },
    { label: 'Flask route (POST)', ext: ['.py'], code: "@bp.route('/path', methods=['POST'])\\ndef my_post():\\n    data = request.get_json() or {}\\n    return jsonify({'received': data})\\n" },
    { label: 'SQLite get_db()', ext: ['.py'], code: 'from db import get_db\\n\\nwith get_db() as conn:\\n    rows = conn.execute("SELECT * FROM entries").fetchall()\\n' },
    { label: 'Background thread', ext: ['.py'], code: 'import threading\\n\\ndef run_in_bg(func, *args):\\n    t = threading.Thread(target=func, args=args, daemon=True)\\n    t.start()\\n    return t\\n' },
    { label: 'init(app) Blueprint', ext: ['.py'], code: 'def init(app):\\n    app.register_blueprint(bp)\\n    print(f"Module registered")\\n' },
    { label: 'HTML page skeleton', ext: ['.html'], code: '<!DOCTYPE html>\\n<html>\\n<head><meta charset="utf-8"><title>Page</title></head>\\n<body style="background:#1a1a1a;color:#e0e0e0;padding:40px;">\\n<h1>Title</h1>\\n<p>Content</p>\\n</body>\\n</html>\\n' },
    { label: 'fetch() POST JSON', ext: ['.js', '.html'], code: "fetch('/api/action', {\\n    method: 'POST',\\n    headers: {'Content-Type': 'application/json'},\\n    body: JSON.stringify({key: 'value'})\\n}).then(r => r.json()).then(d => console.log(d));\\n" },
    { label: 'JSON config read', ext: ['.py'], code: 'import json\\nfrom pathlib import Path\\n\\nconfig_file = Path(__file__).parent / "config.json"\\nif config_file.exists():\\n    config = json.loads(config_file.read_text())\\nelse:\\n    config = {}\\n' },
    { label: 'Scheduled task stub', ext: ['.py'], code: 'from scheduler import start_scheduler\\n\\ndef init(app):\\n    app.register_blueprint(bp)\\n    start_scheduler(interval_seconds=300)\\n' },
    { label: 'RBAC @require_role', ext: ['.py'], code: "@bp.route('/admin')\\n@require_role('admin', 'superadmin')\\ndef admin_page():\\n    return 'Admin only'\\n" },
];

function toggleSnippets() {
    const panel = document.getElementById('snippetsPanel');
    if (panel.style.display === 'none') {
        renderSnippets();
        panel.style.display = 'block';
    } else {
        panel.style.display = 'none';
    }
}

function renderSnippets() {
    const ext = currentFile ? '.' + currentFile.split('.').pop().toLowerCase() : '';
    const list = document.getElementById('snippetList');
    list.innerHTML = '';
    SNIPPETS.forEach(s => {
        if (s.ext.length && ext && !s.ext.includes(ext) && ext !== '.') return;
        const btn = document.createElement('button');
        btn.textContent = s.label;
        btn.title = s.code;
        btn.style.cssText = 'display:block;width:100%;text-align:left;background:#2a1a3a;color:#e0e0e0;border:1px solid #9C27B0;border-radius:4px;padding:6px 8px;margin:4px 0;cursor:pointer;font-size:0.8em;';
        btn.onmouseenter = () => btn.style.background = '#4a2a5a';
        btn.onmouseleave = () => btn.style.background = '#2a1a3a';
        btn.onclick = () => insertSnippet(s.code);
        list.appendChild(btn);
    });
    if (!list.children.length) list.innerHTML = '<p style="color:#888;font-size:0.8em;">No snippets for this file type.</p>';
}

function insertSnippet(code) {
    const ta = document.getElementById('fileEditor');
    const start = ta.selectionStart;
    const before = ta.value.substring(0, start);
    const after = ta.value.substring(ta.selectionEnd);
    ta.value = before + code + after;
    ta.selectionStart = ta.selectionEnd = start + code.length;
    ta.focus();
}

function createNewFile() {
    document.getElementById('newFileName').value = '';
    document.getElementById('newFileModal').style.display = 'block';
}

function createFile() {
    const fileName = document.getElementById('newFileName').value.trim();
    if (!fileName) {
        alert('Please enter a file name');
        return;
    }
    
    // For now, create in root directory
    editFile(fileName);
    closeModal('newFileModal');
}

function createNewFolder() {
    document.getElementById('newFolderName').value = '';
    document.getElementById('newFolderModal').style.display = 'block';
}

function createFolder() {
    const folderName = document.getElementById('newFolderName').value.trim();
    if (!folderName) {
        alert('Please enter a folder name');
        return;
    }
    
    // Create empty directory by "creating" a file in it and then deleting it
    const tempFile = `${folderName}/.gitkeep`;
    
    fetch(`/addons/modules/${currentModule}/api/file?path=${encodeURIComponent(tempFile)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: '' })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            loadFiles();
            closeModal('newFolderModal');
        } else {
            alert('Error creating folder: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(e => alert('Error: ' + e));
}

function uploadFile() {
    const fileInput = document.getElementById('fileUpload');
    if (fileInput.files.length === 0) return;
    
    document.getElementById('uploadFileInput').files = fileInput.files;
    document.getElementById('uploadModal').style.display = 'block';
}

function doUpload() {
    const fileInput = document.getElementById('uploadFileInput');
    const uploadPath = document.getElementById('uploadPath').value.trim();
    const statusDiv = document.getElementById('uploadStatus');
    
    if (fileInput.files.length === 0) {
        statusDiv.textContent = 'No file selected';
        statusDiv.style.color = 'red';
        return;
    }
    
    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    if (uploadPath) {
        formData.append('path', uploadPath);
    }
    
    statusDiv.textContent = 'Uploading...';
    statusDiv.style.color = 'orange';
    
    fetch(`/addons/modules/${currentModule}/api/upload`, {
        method: 'POST',
        body: formData
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            statusDiv.textContent = data.message;
            statusDiv.style.color = 'green';
            loadFiles();
            setTimeout(() => closeModal('uploadModal'), 2000);
        } else {
            statusDiv.textContent = 'Error: ' + (data.error || 'Unknown error');
            statusDiv.style.color = 'red';
        }
    })
    .catch(e => {
        statusDiv.textContent = 'Error: ' + e;
        statusDiv.style.color = 'red';
    });
}

function toggleUIIntegration(action) {
    const statusDiv = document.getElementById('uiStatus');
    statusDiv.textContent = action === 'add' ? 'Adding to UI...' : 'Removing from UI...';
    statusDiv.style.color = 'orange';
    
    fetch(`/addons/modules/${currentModule}/api/ui_integration`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: action })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            statusDiv.textContent = data.message;
            statusDiv.style.color = 'green';
            checkUIIntegration();
        } else {
            statusDiv.textContent = 'Error: ' + (data.error || 'Unknown error');
            statusDiv.style.color = 'red';
        }
    })
    .catch(e => {
        statusDiv.textContent = 'Error: ' + e;
        statusDiv.style.color = 'red';
    });
}

function checkUIIntegration() {
    fetch(`/addons/modules/${currentModule}/api/ui_integration`)
        .then(r => r.json())
        .then(data => {
            const isInUI = data.in_ui === true;
            document.getElementById('addToUI').style.display = isInUI ? 'none' : 'inline-block';
            document.getElementById('removeFromUI').style.display = isInUI ? 'inline-block' : 'none';
            if (isInUI && data.url) {
                let statusDiv = document.getElementById('uiStatus');
                statusDiv.innerHTML = '✅ Pinned to nav — <a href="' + data.url + '" target="_blank" style="color:#4CAF50;">Open</a>';
                statusDiv.style.color = 'green';
            }
        })
        .catch(() => {
            document.getElementById('addToUI').style.display = 'inline-block';
            document.getElementById('removeFromUI').style.display = 'none';
        });
}

function refreshFiles() {
    loadFiles();
}

function closeModal(modalId) {
    document.getElementById(modalId).style.display = 'none';
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', init);

</script>

<style>
.modal {
    display: none;
    position: fixed;
    z-index: 1000;
    left: 0;
    top: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(0,0,0,0.8);
}

.modal-content {
    background-color: #2d2d2d;
    margin: 10% auto;
    padding: 20px;
    border-radius: 10px;
    width: 80%;
    max-width: 500px;
    color: #e0e0e0;
}

.close {
    color: #aaa;
    float: right;
    font-size: 28px;
    font-weight: bold;
    cursor: pointer;
}

.close:hover {
    color: #4CAF50;
}

.card {
    background: #2d2d2d;
    border: 1px solid #444;
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 20px;
}
</style>

{% endblock %}"""



# Addons module config template
ADDONS_MODULE_CONFIG_TEMPLATE = """{% extends "base.html" %}

{% block content %}

<div class="section">

<h2>⚙️ Module Configuration</h2>

<p class="subtitle">Module Manager - {{ module.name }}</p>

<div class="card">
<p>Configuration options for this module will be displayed here.</p>
</div>

</div>

{% endblock %}"""

# Echo training template
ECHO_TRAINING_TEMPLATE = """{% extends "base.html" %}

{% block content %}

<h2>Training Center</h2>

<div style="display:flex;gap:20px;align-items:flex-start;">

<div style="flex:1;max-width:420px;">

<form id="trainForm" onsubmit="startTrain(event)">

<label>Model path (relative to project): <input name="model" value="models/Phi-3-mini-4k-instruct-q4.gguf"></label>

<label>Training file (data/echo_training/...): <input name="training_file" value=""></label>

<label>Engine: <select name="engine"><option value="stub">stub</option><option value="peft">peft</option></select></label>

<label>Epochs: <input name="epochs" value="1"></label>

<label>Batch size: <input name="batch_size" value="8"></label>

<label>Learning rate: <input name="lr" value="0.0001"></label>

<button class="btn" type="submit">Start Training</button>

</form>

<div style="margin-top:12px;">Training jobs:</div>

<div id="trainingJobsList" style="margin-top:8px;"></div>

</div>

<div style="flex:2">

<h3>Logs</h3>

<div id="trainLogModal" class="modal"><div class="modal-content"><span class="close" onclick="closeModal('trainLogModal')">&times;</span><pre id="trainLogContent">(logs)</pre></div></div>

<p>Use the form to start a training job. The <b>peft</b> engine requires additional dependencies and GPUs for practical runs.</p>

</div>

</div>

<script>loadTrainJobs();</script>

{% endblock %}

"""
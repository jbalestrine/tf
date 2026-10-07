"""
MasterChief HTML Templates

Contains all HTML templates used by the Flask application.
"""

# Base HTML template with navigation and styling
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>MasterChief - DevOps Platform</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;}
body{font-family:Arial,sans-serif;background:#1a1a1a;color:#e0e0e0;line-height:1.6;}
.container{max-width:1400px;margin:0 auto;padding:20px;}
header{background:#2d2d2d;padding:20px;margin-bottom:30px;border-bottom:3px solid #4CAF50;}
h1{color:#4CAF50;font-size:2.5em;margin-bottom:10px;}
.subtitle{color:#888;font-size:1.1em;}
nav{position:sticky;top:8px;z-index:500;background:rgba(18,22,31,0.94);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);padding:10px 14px;margin-bottom:24px;border-radius:16px;display:flex;flex-wrap:wrap;gap:8px;align-items:center;border:1px solid rgba(148,163,184,0.18);box-shadow:0 8px 24px rgba(15,23,42,0.38);}
.nav-group{position:relative;display:inline-block;}
.nav-group > summary.dropbtn{list-style:none;cursor:pointer;background:linear-gradient(135deg,rgba(22,27,39,0.9),rgba(15,118,110,0.2));color:#8ae2a0;border:1px solid rgba(122,217,167,0.32);border-radius:12px;padding:9px 12px;font-weight:700;text-decoration:none;display:inline-block;transition:background-color 0.15s ease,color 0.15s ease;box-shadow:inset 0 1px 0 rgba(255,255,255,0.06),0 4px 12px rgba(16,185,129,0.08);}
.nav-group > summary.dropbtn::-webkit-details-marker{display:none;}
.nav-group[open] > summary.dropbtn,.nav-group > summary.dropbtn:hover,.nav-group > summary.dropbtn:focus-visible{background:linear-gradient(135deg,#4CAF50,#2b6b43);color:#fff;box-shadow:0 8px 18px rgba(76,175,80,0.22);}
.nav-group-content{display:none;position:absolute;left:0;top:calc(100% + 6px);min-width:240px;max-height:min(70vh,540px);overflow-y:auto;background:rgba(15,23,42,0.98);border:1px solid rgba(148,163,184,0.18);border-radius:12px;box-shadow:0 14px 30px rgba(2,6,23,0.5);z-index:501;padding:6px 0;margin-top:0;}
.nav-group[open] .nav-group-content{display:block;}
.nav-group-content a{display:block;color:#dbeafe;text-decoration:none;padding:8px 12px;border-left:3px solid transparent;white-space:normal;font-size:0.94rem;transition:background-color 0.12s ease,color 0.12s ease;}
.nav-group-content a:hover,.nav-group-content a.active{background:linear-gradient(90deg,rgba(76,175,80,0.15),rgba(59,130,246,0.08));border-left-color:#4CAF50;color:#9ae6b4;}
nav a{color:#9ae6b4;text-decoration:none;margin-right:0;padding:9px 12px;border-radius:10px;display:inline-block;transition:all 0.25s ease;border:1px solid transparent;}
nav a:hover,nav a.active{background:linear-gradient(135deg,#4CAF50,#2e7d32);color:#fff;border-color:rgba(255,255,255,0.08);box-shadow:0 10px 20px rgba(76,175,80,0.18);}
.nav-search{order:-1;display:flex;align-items:center;gap:8px;margin-right:auto;min-width:min(100%,260px);}
.nav-search input{width:100%;max-width:300px;padding:9px 12px;background:#111827;border:1px solid rgba(148,163,184,0.3);border-radius:10px;color:#f8fafc;font-size:0.94rem;}
.nav-search input:focus{border-color:#4CAF50;box-shadow:0 0 0 3px rgba(76,175,80,0.15);outline:none;}
.nav-search-status{font-size:0.78rem;color:#94a3b8;white-space:nowrap;}
.nav-group-content a[hidden],nav > a[hidden],.nav-group[hidden]{display:none!important;}
.nav-group-content .nav-subgroup-label{padding:9px 14px 4px;color:#94a3b8;text-transform:uppercase;font-size:0.72rem;font-weight:700;letter-spacing:.08em;}
.nav-group-content a:focus-visible,nav > a:focus-visible{outline:2px solid #86efac;outline-offset:2px;}
.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0;}
@media(max-width:720px){nav{position:relative;top:auto;padding:8px;gap:6px}.nav-search{flex:1 0 100%;margin:0 0 4px}.nav-search input{max-width:none}.nav-group{flex:1 1 auto}.nav-group>summary.dropbtn{width:100%;text-align:center}.nav-group[open] .nav-group-content{position:relative;left:auto;top:auto;min-width:100%;max-height:50vh;box-shadow:none;margin-top:4px}}
.dashboard-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:20px;margin-bottom:30px;}
.card{background:#2d2d2d;padding:25px;border-radius:10px;border-left:4px solid #4CAF50;box-shadow:0 4px 6px rgba(0,0,0,0.3);}
.card h3{color:#4CAF50;margin-bottom:15px;font-size:1.4em;}
.stat-value{font-size:2.5em;font-weight:bold;color:#fff;margin:10px 0;}
.stat-label{color:#888;font-size:0.9em;text-transform:uppercase;}
.progress-bar{background:#1a1a1a;height:20px;border-radius:10px;overflow:hidden;margin:10px 0;}
.progress-fill{background:linear-gradient(90deg,#4CAF50,#8BC34A);height:100%;transition:width 0.3s;}
table{width:100%;border-collapse:collapse;margin-top:15px;}
th,td{padding:12px;text-align:left;border-bottom:1px solid #3a3a3a;}
th{background:#252525;color:#4CAF50;font-weight:bold;}
tr:hover{background:#333;}
.btn{background:#4CAF50;color:#fff;border:none;padding:10px 20px;border-radius:5px;cursor:pointer;text-decoration:none;display:inline-block;margin:5px;transition:all 0.3s;}
.btn:hover{background:#45a049;transform:translateY(-2px);}
.btn-danger{background:#f44336;}
.btn-danger:hover{background:#da190b;}
.btn-warning{background:#ff9800;}
.btn-warning:hover{background:#e68900;}
.btn-info{background:#2196F3;}
.btn-info:hover{background:#0b7dda;}
.form-group{margin-bottom:20px;}
label{display:block;margin-bottom:8px;color:#4CAF50;font-weight:bold;}
input,textarea,select{width:100%;padding:12px;background:#1a1a1a;border:1px solid #3a3a3a;color:#e0e0e0;border-radius:5px;font-size:1em;}
input:focus,textarea:focus,select:focus{outline:none;border-color:#4CAF50;}
.section{background:#2d2d2d;padding:25px;border-radius:10px;margin-bottom:25px;}
.status-badge{padding:5px 12px;border-radius:15px;font-size:0.85em;font-weight:bold;}
.status-running{background:#4CAF50;color:#fff;}
.status-stopped{background:#f44336;color:#fff;}
.alert{padding:15px;margin-bottom:20px;border-radius:5px;border-left:4px solid;}
.alert-success{background:#1b5e20;border-color:#4CAF50;color:#c8e6c9;}
.alert-error{background:#b71c1c;border-color:#f44336;color:#ffcdd2;}
.alert-info{background:#0d47a1;border-color:#2196F3;color:#bbdefb;}
.modal{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.8);z-index:1000;}
.modal-content{background:#2d2d2d;margin:50px auto;padding:30px;border-radius:10px;max-width:600px;position:relative;}
.close{position:absolute;top:15px;right:20px;font-size:30px;cursor:pointer;color:#888;}
.close:hover{color:#4CAF50;}
pre{background:#1a1a1a;padding:15px;border-radius:5px;overflow-x:auto;border-left:3px solid #4CAF50;}
code{color:#4CAF50;}
.file-upload{border:2px dashed #4CAF50;padding:40px;text-align:center;border-radius:10px;cursor:pointer;transition:all 0.3s;}
.file-upload:hover{background:#252525;border-color:#8BC34A;}
</style>
</head>
<body>
<div class="container">
<header id="masterchief-site-brand" role="banner" style="position:relative;display:flex;align-items:center;min-height:92px;">
<a href="/" aria-label="MasterChief home" style="display:inline-flex;align-items:center;"><img src="/static/masterchief-logo.svg" alt="MasterChief - Echo Starlite DevOps Suite" style="display:block;width:min(360px,75vw);height:auto;"></a>
<div style="position:absolute;right:20px;top:24px;">
    <label style="color:#ccc;font-size:0.9em;">Language: <select id="langSelect" style="background:#1a1a1a;color:#eee;border:1px solid #333;padding:6px;border-radius:6px;"><option value="en">English</option><option value="es">Español</option></select></label>
    </div>
</header>
<nav aria-label="Main navigation">
  <a href="/" class="{{ 'active' if request.path=='/' else '' }}">Dashboard</a>
  <label class="nav-search"><span class="sr-only">Search pages</span><input id="nav-search" type="search" placeholder="Find a page…  Ctrl+K" autocomplete="off" aria-label="Find a page"><span id="nav-search-status" class="nav-search-status" aria-live="polite"></span></label>

  <details class="nav-group {{ 'active' if request.path.startswith('/master-menu') or request.path.startswith('/manager') or request.path.startswith('/site-map') or request.path.startswith('/sys/') or request.path.startswith('/cloud') or request.path.startswith('/notifications') or request.path.startswith('/scripts') or request.path.startswith('/processes') or request.path.startswith('/services') or request.path.startswith('/chaos-monkey') else '' }}">
    <summary class="dropbtn">Operate</summary>
    <div class="nav-group-content">
      <a href="/master-menu" class="{{ 'active' if '/master-menu' in request.path else '' }}">🧭 Master Menu</a>
      <a href="/manager" class="{{ 'active' if '/manager' in request.path else '' }}">📋 Manager</a>
      <a href="/site-map" class="{{ 'active' if '/site-map' in request.path else '' }}">🗺 Unified Site Map</a>
      <a href="/sys/diagnostics" class="{{ 'active' if '/sys/diagnostics' in request.path else '' }}">🔬 Diagnostics</a>
      <a href="/sys/scm" class="{{ 'active' if '/sys/scm' in request.path else '' }}">🗂 SCM</a>
      <a href="/sys/ops" class="{{ 'active' if '/sys/ops' in request.path else '' }}">🧭 Ops Center</a>
      <a href="/cloud" class="{{ 'active' if '/cloud' in request.path else '' }}">☁️ Cloud</a>
      <a href="/notifications" class="{{ 'active' if '/notifications' in request.path else '' }}">🔔 Notifications</a>
      <a href="/scripts" class="{{ 'active' if '/scripts' in request.path else '' }}">📝 Scripts</a>
      <a href="/chaos-monkey" class="{{ 'active' if request.path.startswith('/chaos-monkey') else '' }}">🐒 Chaos Monkey Area</a>
      <a href="/processes" class="{{ 'active' if '/processes' in request.path else '' }}">⚙️ Processes</a>
      <a href="/services" class="{{ 'active' if '/services' in request.path else '' }}">🛠 Services</a>
      <a href="/about" class="{{ 'active' if '/about' in request.path else '' }}">ℹ️ About</a>
      <a href="/github" class="{{ 'active' if '/github' in request.path else '' }}">🐙 GitHub</a>
    </div>
  </details>

  <details class="nav-group {{ 'active' if request.path.startswith('/pipelines') or request.path.startswith('/modules') or request.path.startswith('/addons') or request.path.startswith('/arm_creator') or request.path.startswith('/iac_manager') or request.path.startswith('/blueprint-wizard') or request.path.startswith('/tf_wizard') or request.path.startswith('/archetypes') or request.path.startswith('/features') else '' }}">
    <summary class="dropbtn">Build</summary>
    <div class="nav-group-content">
      <a href="/pipelines" class="{{ 'active' if '/pipelines' in request.path else '' }}">🚀 Pipelines</a>
      <a href="/observability" class="{{ 'active' if '/observability' in request.path else '' }}">📈 Observability</a>
      <a href="/modules" class="{{ 'active' if request.path=='/modules' else '' }}">🧱 Modules</a>
      <a href="/addons" class="{{ 'active' if '/addons' in request.path and '/modules' not in request.path else '' }}">📦 Addons</a>
      <a href="/addons/modules" class="{{ 'active' if '/addons/modules' in request.path else '' }}">🧩 Addon Modules</a>
      <a href="/blueprint-wizard" class="{{ 'active' if '/blueprint-wizard' in request.path else '' }}">🧩 Blueprint Wizard</a>
      <a href="/tf_wizard" class="{{ 'active' if request.path.startswith('/tf_wizard') else '' }}">🏗 Terraform Wizard</a>
      <a href="/arm_creator" class="{{ 'active' if '/arm_creator' in request.path else '' }}">🧱 ARM Creator</a>
      <a href="/iac_manager" class="{{ 'active' if '/iac_manager' in request.path else '' }}">🏗 IaC Manager</a>
      <a href="/archetypes?return={{ request.path|urlencode }}" class="{{ 'active' if '/archetypes' in request.path else '' }}">🧭 Code Archetypes</a>
      <a href="/features" class="{{ 'active' if '/features' in request.path else '' }}">⚡ Features</a>
      {% if ui_modules is defined and ui_modules %}
      <div class="nav-subgroup-label">Pinned Add-ons</div>
      {% for _mod_name, _mod in ui_modules.items() %}
      <a href="{{ _mod.url }}" class="{{ 'active' if _mod.url in request.path else '' }}" title="Add-on module: {{ _mod_name }}">{{ _mod.icon }} {{ _mod_name }}</a>
      {% endfor %}
      {% endif %}
    </div>
  </details>

  <details class="nav-group {{ 'active' if request.path.startswith('/echo-') or request.path.startswith('/echo') or request.path.startswith('/web_ide') or request.path.startswith('/masterchief_code_ui') else '' }}">
    <summary class="dropbtn">AI &amp; Tools</summary>
    <div class="nav-group-content">
      <a href="/echo-chat" class="{{ 'active' if '/echo-chat' in request.path else '' }}">🌙 Echo Chat</a>
      <a href="/echo-commands" class="{{ 'active' if '/echo-commands' in request.path else '' }}">⌨ Echo Commands</a>
      <a href="/echo-train" class="{{ 'active' if '/echo-train' in request.path else '' }}">🎓 Training</a>
      <a href="/echo-memory" class="{{ 'active' if '/echo-memory' in request.path else '' }}">🧠 Echo Memory</a>
      <a href="/web_ide" class="{{ 'active' if '/web_ide' in request.path else '' }}">💻 Web IDE</a>
      <a href="/masterchief_code_ui" class="{{ 'active' if '/masterchief_code_ui' in request.path else '' }}">🧠 MasterChief Code UI</a>
    </div>
  </details>

  <details class="nav-group {{ 'active' if request.path.startswith('/rbac') or request.path.startswith('/secrets') or request.path.startswith('/teams') or request.path.startswith('/okta') or request.path.startswith('/google-services') else '' }}">
    <summary class="dropbtn">Secure &amp; Connect</summary>
    <div class="nav-group-content">
      <a href="/rbac" class="{{ 'active' if '/rbac' in request.path else '' }}">🛡 RBAC</a>
      <a href="/secrets" class="{{ 'active' if '/secrets' in request.path else '' }}">🔐 Secrets</a>
      <a href="/teams" class="{{ 'active' if request.path=='/teams' else '' }}">📅 Teams</a>
      <a href="/okta" class="{{ 'active' if request.path=='/okta' else '' }}">🔒 Okta</a>
      <a href="/google-services" class="{{ 'active' if '/google-services' in request.path else '' }}">🌐 Google Services</a>
    </div>
  </details>

  <details class="nav-group {{ 'active' if request.path.startswith('/gallery') or request.path.startswith('/marketplace') or request.path.startswith('/media') or request.path.startswith('/roku') else '' }}">
    <summary class="dropbtn">Media</summary>
    <div class="nav-group-content">
      <a href="/gallery" class="{{ 'active' if '/gallery' in request.path else '' }}">🖼 Gallery</a>
      <a href="/marketplace" class="{{ 'active' if '/marketplace' in request.path else '' }}">🛍 Marketplace</a>
      {% if current_user.is_authenticated and ('*' in current_user.permissions or 'rbac' in current_user.permissions) %}
      <a href="/media/roku" class="{{ 'active' if '/media/roku' in request.path or '/roku-builder' in request.path else '' }}">📺 Roku Builder</a>
      {% endif %}
    </div>
  </details>
</nav>
{% with messages=get_flashed_messages(with_categories=true) %}
{% if messages %}
{% for category,message in messages %}
<div class="alert alert-{{ category }}">{{ message }}</div>
{% endfor %}
{% endif %}
{% endwith %}
{% block content %}{% endblock %}
</div>
<script src="/static/navigation.js" defer></script>
<script src="/static/code_archetypes.js" defer></script>
<script>
function confirmDelete(item){return confirm('Are you sure you want to delete '+item+'?');}
function openModal(modalId){document.getElementById(modalId).style.display='block';}
function closeModal(modalId){document.getElementById(modalId).style.display='none';}
function refreshStats(){
const ids=['cpu-value','cpu-progress','mem-value','mem-progress','disk-value','disk-progress'];
if(!ids.every(id=>document.getElementById(id))) return;
fetch('/api/stats').then(r=>{if(!r.ok)throw new Error('Stats request failed: '+r.status);return r.json();}).then(data=>{
if(!data.cpu||!data.memory||!data.disk)throw new Error('Stats response is incomplete');
document.getElementById('cpu-value').textContent=data.cpu.percent.toFixed(1)+'%';
document.getElementById('cpu-progress').style.width=data.cpu.percent+'%';
document.getElementById('mem-value').textContent=data.memory.percent.toFixed(1)+'%';
document.getElementById('mem-progress').style.width=data.memory.percent+'%';
document.getElementById('disk-value').textContent=data.disk.percent.toFixed(1)+'%';
document.getElementById('disk-progress').style.width=data.disk.percent+'%';
}).catch(err=>console.error('Failed to refresh stats:',err));}
if(document.getElementById('cpu-value')) setInterval(refreshStats,5000);
function refreshIndex(){
        fetch('/scripts/refresh_index',{method:'POST'}).then(async r => {
        // Training UI helpers
        function loadTrainJobs() {
            fetch('/api/echo/train_list').then(r => r.json()).then(j => {
                const jobs = j.jobs || [];
                const el = document.getElementById('trainingJobsList');
                if (!el) return;
                el.innerHTML = '';
                jobs.forEach(job => {
                    const div = document.createElement('div');
                    div.style.border = '1px solid #444'; div.style.padding = '8px'; div.style.margin = '6px 0';
                    div.innerHTML = `<b>${job.id}</b> - ${job.status} - <button onclick="viewLog('${job.id}')">Log</button> <button onclick="cancelJob('${job.id}')">Cancel</button>`;
                    el.appendChild(div);
                });
            }).catch(console.error);
        }
        function startTrain(event) {
            event.preventDefault();
            const form = document.getElementById('trainForm');
            const fd = new FormData(form);
            const body = {};
            form.querySelectorAll('input,select').forEach(i => { if (i.name) body[i.name] = i.value });
            fetch('/api/echo/train_model', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then(r => r.json()).then(j => {
                alert(JSON.stringify(j));
                loadTrainJobs();
            }).catch(e => { console.error(e); alert('Start failed') });
        }
        function viewLog(id) {
            fetch('/api/echo/train_status?job_id=' + encodeURIComponent(id)).then(r => r.json()).then(j => {
                const modal = document.getElementById('trainLogModal');
                document.getElementById('trainLogContent').textContent = j.log_tail || 'No log';
                modal.style.display = 'block';
            }).catch(console.error);
        }
        function cancelJob(id) {
            fetch('/api/echo/train_cancel', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ job_id: id }) }).then(r => r.json()).then(j => { alert(JSON.stringify(j)); loadTrainJobs(); }).catch(console.error);
        }
        setInterval(loadTrainJobs, 5000);
        if(r.status===401){
            // server requires admin token
            let token = prompt('Admin token required to refresh index:');
            if(!token) return alert('Cancelled');
            try{
                const r2 = await fetch('/scripts/refresh_index',{method:'POST',headers:{'X-ADMIN-TOKEN':token}});
                const j2 = await r2.json();
                if(j2.ok) location.reload(); else alert('Refresh failed: '+(j2.error||'unknown'));
            }catch(e){ alert('Refresh error: '+e); }
        } else {
            const j = await r.json();
            if(j.ok){ location.reload(); } else { alert('Refresh failed: '+(j.error||'unknown')); }
        }
    }).catch(e=>{ alert('Refresh error: '+e); });
}
</script>
</body>
</html>"""
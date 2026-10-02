"""MasterChief Ops Center Template"""

OPS_CENTER_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MasterChief Ops Center</title>
<style>
:root{
  --bg:#0f172a;
  --panel:#111827;
  --panel2:#1f2937;
  --text:#e5e7eb;
  --muted:#9ca3af;
  --good:#22c55e;
  --warn:#f59e0b;
  --bad:#ef4444;
  --accent:#38bdf8;
  --border:#334155;
}
*{box-sizing:border-box}
body{margin:0;font-family:"Segoe UI",Tahoma,sans-serif;background:radial-gradient(circle at top right,#0b2239 0%,#0f172a 55%);color:var(--text)}
header{padding:14px 18px;border-bottom:1px solid var(--border);background:rgba(17,24,39,.75);backdrop-filter:blur(8px);position:sticky;top:0;z-index:5;display:flex;align-items:center;gap:12px;flex-wrap:wrap}
header h1{margin:0;font-size:18px;color:#7dd3fc}
header .meta{font-size:12px;color:var(--muted)}
header .btn{background:var(--panel2);border:1px solid var(--border);color:var(--text);text-decoration:none;border-radius:8px;padding:6px 10px;font-size:12px}
header .btn:hover{border-color:var(--accent);color:var(--accent)}
main{padding:14px;display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:12px}
.card{background:linear-gradient(180deg,var(--panel) 0%,#0b1220 100%);border:1px solid var(--border);border-radius:12px;padding:12px;min-height:120px}
.card h2{font-size:13px;margin:0 0 8px 0;color:#7dd3fc;letter-spacing:.02em}
.kv{display:flex;justify-content:space-between;gap:10px;padding:3px 0;font-size:12px}
.kv .k{color:var(--muted)}
.tag{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;border:1px solid var(--border);margin:2px 4px 2px 0}
.tag.good{color:var(--good);border-color:#14532d;background:#14532d33}
.tag.warn{color:var(--warn);border-color:#78350f;background:#78350f33}
.tag.bad{color:var(--bad);border-color:#7f1d1d;background:#7f1d1d33}
.list{max-height:220px;overflow:auto;border:1px solid #1e293b;border-radius:8px;padding:8px;background:#02061755}
.item{font-size:12px;line-height:1.35;padding:5px 0;border-bottom:1px solid #1e293b}
.item:last-child{border-bottom:none}
.path{color:#93c5fd;word-break:break-all}
.controls a{margin-right:6px}
.mono{font-family:Consolas,monospace}
.btn{background:var(--panel2);border:1px solid var(--border);color:var(--text);text-decoration:none;border-radius:8px;padding:5px 9px;font-size:12px;cursor:pointer}
.btn:hover{border-color:var(--accent);color:var(--accent)}
.row{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.text{width:100%;background:#02061799;border:1px solid #1e293b;color:var(--text);border-radius:8px;padding:8px;font-size:12px}
.status{margin-top:8px;font-size:12px;color:var(--muted)}
</style>
</head>
<body>
<header>
  <h1>MasterChief Ops Center</h1>
  <span class="meta" id="generated">Loading summary...</span>
  <a class="btn" href="/sys/diagnostics">Diagnostics</a>
  <a class="btn" href="/sys/scm">SCM</a>
  <a class="btn" href="/services">Services</a>
  <a class="btn" href="/processes">Processes</a>
  <a class="btn" href="/modules">Modules</a>
  <a class="btn" href="/web_tf_wizard">TF Wizard</a>
</header>
<main id="grid"></main>
<script>
function esc(v){return String(v ?? '').replace(/[&<>"']/g,s=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[s]));}
function sevClass(sev){if(sev==='error')return 'bad'; if(sev==='warning')return 'warn'; return 'good';}

async function runAction(action, payload){
  const r = await fetch('/sys/api/ops-action', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify(Object.assign({action}, payload || {}))
  });
  const j = await r.json();
  if(!j.ok){ throw new Error(j.error || 'Action failed'); }
  return j;
}

async function killPid(pid){
  if(!confirm('Terminate process ' + pid + '?')) return;
  try{
    await runAction('kill_process', {pid});
    await boot();
  }catch(err){
    alert('Kill failed: ' + err.message);
  }
}

async function serviceAction(action, name){
  try{
    await runAction(action, {service_name:name});
    await boot();
  }catch(err){
    alert('Service action failed: ' + err.message);
  }
}

async function suggestModule(){
  const ideaEl = document.getElementById('moduleIdea');
  const outEl = document.getElementById('moduleSuggestOut');
  const idea = (ideaEl && ideaEl.value || '').trim();
  if(!idea){ outEl.textContent = 'Enter an idea first.'; return; }
  outEl.textContent = 'Analyzing idea...';
  try{
    const r = await fetch('/sys/api/modules/from-idea', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({idea})
    });
    const j = await r.json();
    if(!j.ok){ throw new Error(j.error || 'Suggestion failed'); }
    window.__lastCreatePayload = j.create_payload || null;
    outEl.textContent = 'Suggested name: ' + (j.suggestion.name || 'n/a') + ' | type: ' + (j.suggestion.type || 'n/a') + ' | capabilities: ' + ((j.suggestion.capabilities || []).join(', ') || 'none');
  }catch(err){
    outEl.textContent = 'Suggestion failed: ' + err.message;
  }
}

async function createModuleFromIdea(){
  const outEl = document.getElementById('moduleSuggestOut');
  if(!window.__lastCreatePayload){ outEl.textContent = 'Run Suggest first.'; return; }
  outEl.textContent = 'Creating module...';
  try{
    const r = await fetch('/addons/create_blank_module', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify(window.__lastCreatePayload)
    });
    const j = await r.json();
    if(!j.success){ throw new Error(j.error || 'Create failed'); }
    outEl.textContent = 'Module created: ' + (j.module_name || 'unknown');
    await boot();
  }catch(err){
    outEl.textContent = 'Create failed: ' + err.message;
  }
}

function render(data){
  document.getElementById('generated').textContent = 'Updated: ' + (data.generated_at || 'n/a');
  const d = data.diagnostics || {};
  const git = data.git || {};
  const rbac = data.rbac || {};
  const secrets = data.secrets || {};
  const cloud = data.cloud || {};
  const sessions = data.echo_sessions || {};
  const tf = data.terraform_wizard || {};
  const uiLinks = data.ui_links || {};
  const addons = (data.addons || {}).installed || [];
  const services = data.services || [];
  const procs = data.processes_top || [];

  const issuesHtml = (d.issues || []).slice(0,10).map(i =>
    `<div class="item"><span class="tag ${sevClass(i.severity)}">${esc(i.severity||'info')}</span> ${esc(i.message)}<br><span class="path">${esc(i.file || 'unknown')}:${esc(i.line || 0)}</span><br><span class="mono">${esc(i.suggestion || '')}</span></div>`
  ).join('') || '<div class="item">No issues reported.</div>';

  const orphansHtml = (d.orphans || []).slice(0,15).map(p => `<div class="item path">${esc(p)}</div>`).join('') || '<div class="item">No orphan files found.</div>';
  const commitsHtml = (git.recent_commits || []).slice(0,8).map(c => `<div class="item mono">${esc(c.hash)} ${esc(c.message)}</div>`).join('') || '<div class="item">No commit data.</div>';
  const branchesHtml = (git.branches || []).slice(0,10).map(b => `<span class="tag">${esc(b)}</span>`).join('');
  const addHtml = addons.slice(0,16).map(a => `<span class="tag">${esc(a)}</span>`).join('') || '<span class="tag">None</span>';
  const svcHtml = services.slice(0,10).map(s => `<div class="item"><div class="row">${esc(s.name)} <span class="tag ${s.status==='running'?'good':'warn'}">${esc(s.status)}</span> ${s.port?`port ${esc(s.port)}`:''} <button class="btn" onclick="serviceAction('service_start','${esc(s.name)}')">Start</button> <button class="btn" onclick="serviceAction('service_stop','${esc(s.name)}')">Stop</button> <button class="btn" onclick="serviceAction('service_restart','${esc(s.name)}')">Restart</button></div></div>`).join('') || '<div class="item">No tracked services.</div>';
  const procHtml = procs.slice(0,10).map(p => `<div class="item"><div class="row">PID ${esc(p.pid)} · ${esc(p.name)} · CPU ${esc(p.cpu_percent||0)}% <button class="btn" onclick="killPid(${esc(p.pid)})">Kill</button></div></div>`).join('') || '<div class="item">No process data.</div>';

  const uiKeys = Object.keys(uiLinks);
  const uiHtml = uiKeys.slice(0,16).map(k => `<div class="item"><span class="path">${esc(k)}</span> -> ${esc((uiLinks[k]||{}).path || 'n/a')}</div>`).join('') || '<div class="item">No dynamic UI links found.</div>';

  document.getElementById('grid').innerHTML = `
    <section class="card">
      <h2>Diagnostics Snapshot</h2>
      <div class="kv"><span class="k">Issues</span><b>${esc(d.issues_count || 0)}</b></div>
      <div class="kv"><span class="k">Orphan Files</span><b>${esc(d.orphans_count || 0)}</b></div>
      <div class="list">${issuesHtml}</div>
    </section>

    <section class="card">
      <h2>Orphan Files</h2>
      <div class="list">${orphansHtml}</div>
    </section>

    <section class="card">
      <h2>Git Status</h2>
      <div class="kv"><span class="k">Current Branch</span><b>${esc(git.branch || 'n/a')}</b></div>
      <div>${branchesHtml || '<span class="tag">n/a</span>'}</div>
      <div class="list">${commitsHtml}</div>
    </section>

    <section class="card">
      <h2>RBAC and Sessions</h2>
      <div class="kv"><span class="k">Users</span><b>${esc(rbac.users || 0)}</b></div>
      <div class="kv"><span class="k">Roles</span><b>${esc(rbac.roles || 0)}</b></div>
      <div class="kv"><span class="k">RBAC Sessions</span><b>${esc(rbac.sessions || 0)}</b></div>
      <div class="kv"><span class="k">Echo Sessions</span><b>${esc(sessions.count || 0)}</b></div>
      <div class="kv"><span class="k">MOTD</span><span>${esc(data.motd || '(not set)')}</span></div>
    </section>

    <section class="card">
      <h2>Secrets, Cloud, Terraform</h2>
      <div class="kv"><span class="k">Secrets</span><b>${esc(secrets.count || 0)}</b></div>
      <div class="kv"><span class="k">Rotation Due</span><b>${esc(secrets.rotation_due || 0)}</b></div>
      <div class="kv"><span class="k">Cloud Accounts</span><b>${esc(cloud.accounts || 0)}</b></div>
      <div class="kv"><span class="k">Providers</span><span>${esc((cloud.providers || []).join(', ') || 'n/a')}</span></div>
      <div class="kv"><span class="k">Estimated Monthly</span><b>$${esc((cloud.costs || {}).total || 0)}</b></div>
      <div class="controls" style="margin-top:8px">
        <a class="btn" href="${esc(tf.route || '/web_tf_wizard')}">Open TF Wizard</a>
      </div>
    </section>

    <section class="card">
      <h2>Addons, Modules, Dynamic GUI Links</h2>
      <div class="kv"><span class="k">Installed Addons</span><b>${esc((data.addons || {}).count || 0)}</b></div>
      <div>${addHtml}</div>
      <div style="margin-top:8px" class="list">${uiHtml}</div>
      <div style="margin-top:8px">
        <textarea id="moduleIdea" class="text" rows="3" placeholder="Describe your module idea, for example: incident timeline dashboard with RBAC and cloud cost drilldown"></textarea>
        <div class="row" style="margin-top:6px">
          <button class="btn" onclick="suggestModule()">Suggest Scaffold</button>
          <button class="btn" onclick="createModuleFromIdea()">Create Module</button>
        </div>
        <div class="status" id="moduleSuggestOut">No idea analyzed yet.</div>
      </div>
      <div class="controls" style="margin-top:8px">
        <a class="btn" href="/addons">Addon Manager</a>
        <a class="btn" href="/module-manager">Module Builder</a>
      </div>
    </section>

    <section class="card">
      <h2>Service and Process Controls</h2>
      <div class="list">${svcHtml}</div>
      <div style="height:8px"></div>
      <div class="list">${procHtml}</div>
      <div class="controls" style="margin-top:8px">
        <a class="btn" href="/services">Start/Stop Services</a>
        <a class="btn" href="/processes">Kill Processes</a>
      </div>
    </section>
  `;
}

async function boot(){
  const r = await fetch('/sys/api/ops-summary', {cache:'no-store'});
  const data = await r.json();
  render(data);
}
boot().catch(err => {
  document.getElementById('generated').textContent = 'Failed to load summary: ' + err;
});
</script>
</body>
</html>
"""

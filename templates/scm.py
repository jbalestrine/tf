"""MasterChief Source Control Manager — HTML Template"""

SCM_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MasterChief · Source Control</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg0:#0d1117;--bg1:#161b22;--bg2:#21262d;--bg3:#2d333b;
  --border:#30363d;--text:#e6edf3;--muted:#8b949e;--accent:#7c3aed;
  --green:#3fb950;--yellow:#d29922;--red:#f85149;--blue:#58a6ff;
}
body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg0);color:var(--text);
  height:100vh;display:flex;flex-direction:column;overflow:hidden;font-size:13px}

/* Header */
#header{background:var(--bg1);border-bottom:1px solid var(--border);
  padding:0 16px;height:48px;display:flex;align-items:center;gap:12px;flex-shrink:0}
#header .title{font-weight:600;font-size:14px;display:flex;align-items:center;gap:8px}
#branch-badge{background:var(--bg3);border:1px solid var(--border);border-radius:12px;
  padding:2px 10px;font-size:12px;color:var(--blue);font-weight:600}
.spacer{flex:1}
.hbtn{padding:6px 14px;border-radius:6px;border:1px solid var(--border);background:var(--bg2);
  color:var(--text);cursor:pointer;font-size:12px;font-weight:500;text-decoration:none;display:inline-flex;align-items:center;gap:6px}
.hbtn:hover{background:var(--bg3)}
.hbtn.primary{background:var(--accent);border-color:var(--accent);color:#fff}
.hbtn.primary:hover{opacity:.9}
.hbtn.green{background:#238636;border-color:#2ea043;color:#fff}
.hbtn.green:hover{background:#2ea043}
#git-help-dialog{width:min(760px,calc(100vw - 32px));max-height:calc(100vh - 32px);
  margin:auto;padding:0;border:1px solid var(--border);border-radius:12px;
  background:var(--bg1);color:var(--text);box-shadow:0 20px 60px #000a}
#git-help-dialog::backdrop{background:#000b}
#git-help-dialog .help-content{padding:20px;overflow:auto;max-height:calc(100vh - 96px);
  font-size:13px;line-height:1.65}
#git-help-dialog h2{font-size:20px;margin:0 0 8px}
#git-help-dialog h3{font-size:14px;margin:18px 0 6px;color:var(--blue)}
#git-help-dialog p{margin:8px 0}
#git-help-dialog code{font-family:Consolas,monospace;background:var(--bg2);padding:1px 4px;border-radius:3px}
#git-help-dialog pre{background:var(--bg2);border:1px solid var(--border);padding:10px 12px;
  border-radius:6px;overflow:auto;white-space:pre}
#git-help-dialog .help-actions{position:sticky;bottom:0;display:flex;justify-content:flex-end;
  background:var(--bg1);padding:10px 20px;border-top:1px solid var(--border)}

/* Body */
#body{display:grid;grid-template-columns:320px 1fr;grid-template-rows:1fr auto;flex:1;overflow:hidden}

/* Left panel — working tree */
#left{grid-row:1/3;border-right:1px solid var(--border);display:flex;flex-direction:column;overflow:hidden}
#left-header{padding:10px 14px;font-weight:600;font-size:12px;text-transform:uppercase;
  letter-spacing:.05em;color:var(--muted);border-bottom:1px solid var(--border);
  display:flex;align-items:center;gap:8px}
#stage-actions{padding:8px 12px;border-bottom:1px solid var(--border);display:flex;gap:6px}
#file-list{flex:1;overflow-y:auto;padding:4px 0}
.file-row{display:flex;align-items:center;gap:8px;padding:5px 12px;cursor:pointer;
  border-radius:4px;margin:1px 4px}
.file-row:hover{background:var(--bg2)}
.file-row.selected{background:var(--bg3)}
.file-row input[type=checkbox]{accent-color:var(--accent);cursor:pointer;width:14px;height:14px}
.file-status{font-size:11px;font-weight:700;width:16px;text-align:center;border-radius:3px;padding:1px 2px}
.s-M{color:var(--yellow)}
.s-A{color:var(--green)}
.s-D{color:var(--red)}
.s-?{color:var(--muted)}
.s-R{color:var(--blue)}
.file-name{flex:1;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.file-area{font-size:10px;color:var(--muted);white-space:nowrap}
#no-changes{padding:24px;text-align:center;color:var(--muted);font-size:12px}

/* Right — commit history */
#right{overflow:hidden;display:flex;flex-direction:column;border-bottom:1px solid var(--border)}
#right-header{padding:10px 14px;font-weight:600;font-size:12px;text-transform:uppercase;
  letter-spacing:.05em;color:var(--muted);border-bottom:1px solid var(--border);
  display:flex;align-items:center;gap:8px}
#commit-list{flex:1;overflow-y:auto;padding:4px 0}
.commit-row{padding:8px 16px;border-bottom:1px solid var(--border);cursor:pointer}
.commit-row:hover{background:var(--bg2)}
.commit-hash{font-family:monospace;font-size:11px;color:var(--blue);margin-right:8px}
.commit-msg{font-size:12px;color:var(--text)}
.commit-date{font-size:11px;color:var(--muted)}

/* Bottom — commit panel */
#commit-panel{padding:12px 16px;background:var(--bg1);border-top:1px solid var(--border);
  display:flex;flex-direction:column;gap:8px}
#commit-row-1{display:flex;gap:8px;align-items:center}
#commit-msg-input{flex:1;background:var(--bg2);border:1px solid var(--border);color:var(--text);
  border-radius:6px;padding:8px 12px;font-size:13px;outline:none;font-family:inherit}
#commit-msg-input:focus{border-color:var(--accent)}
#commit-row-2{display:flex;gap:8px;align-items:center}
#commit-scope{font-size:12px;color:var(--muted)}
#output-box{background:var(--bg2);border:1px solid var(--border);border-radius:6px;
  padding:8px 12px;font-family:monospace;font-size:12px;color:var(--green);
  max-height:80px;overflow-y:auto;white-space:pre-wrap;display:none}
#status-bar{font-size:12px;color:var(--muted);padding:4px 0}

/* Loading spinner */
.spin{display:inline-block;animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}

/* Scrollbars */
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
</style>
</head>
<body>

<div id="header">
  <div class="title">
    <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
      <circle cx="6" cy="18" r="3"/><circle cx="18" cy="6" r="3"/><circle cx="18" cy="18" r="3"/>
      <path d="M6 15V9m12 9V9M6 9a6 6 0 0 0 12 0"/>
    </svg>
    Source Control
  </div>
  <span id="branch-badge">⟳ loading…</span>
  <div class="spacer"></div>
  <button class="hbtn" onclick="loadStatus()" title="Refresh git status">↻ Refresh</button>
  <a class="hbtn" href="/sys/api/export-active" title="Download active app files as ZIP">📦 Export Source ZIP</a>
  <a class="hbtn" href="/sys/diagnostics">🔬 Diagnostics</a>
  <button class="hbtn" type="button" onclick="document.getElementById('git-help-dialog').showModal()">Beginner guide</button>
</div>

<dialog id="git-help-dialog" aria-labelledby="git-help-title">
  <div class="help-content">
    <h2 id="git-help-title">Keep Source Control tidy</h2>
    <p>Git lists files it sees as changed. A noisy list often includes generated builds, caches, logs, or local app data. You do not need to delete those files to hide future generated changes.</p>

    <h3>1. Check what a file is before changing anything</h3>
    <p>Look at its path and status in this page. Ask: “Is this source my app needs, or output that the app/build process recreates?” File age alone does not answer that.</p>
    <pre><code>git status --short
git check-ignore -v -- path/to/file</code></pre>

    <h3>2. Tell Git to ignore generated or private files</h3>
    <p>Open the repository's <code>.gitignore</code> file and add a specific pattern. Examples—only use paths you have confirmed are generated or local:</p>
    <pre><code># Reproducible build output
build/
data/roku_builds/

# Local logs and private settings
*.log
.env
# Keep the shareable example configuration
!.env.example</code></pre>
    <p>Never use broad patterns such as <code>*.py</code>, <code>*.json</code>, or <code>data/</code>: they can hide real app source and useful project data.</p>

    <h3>3. Verify the rule before committing</h3>
    <pre><code>git check-ignore -v -- path/to/generated-file
git status --short
git add .gitignore
git diff --cached -- .gitignore</code></pre>
    <p>If <code>git check-ignore</code> names the rule you added, Git is ignoring that untracked path. If it does not, check the spelling and directory level of your pattern.</p>

    <h3>4. Commit and push just the cleanup rule</h3>
    <p>In Source Control, select only <code>.gitignore</code>, enter a message like “Ignore generated build files,” then commit. Push after reviewing the commit. This records the rule; it does not delete your local files.</p>

    <h3>If the file is already tracked</h3>
    <p><code>.gitignore</code> does not hide a file Git already tracks. Removing a tracked file from Git changes what is in the repository for everyone, even if a local-only command keeps a copy on your computer. Stop and review it with someone before changing tracking; databases, RBAC, sessions, and configuration may contain important local state.</p>
    <p><strong>For this project:</strong> generated Roku builds and selected local runtime outputs are already ignored. Diagnostics can help find disconnected scripts; the Chaos Monkey Area is where you inspect and run useful CLI tools and sanity tests. “Orphaned” does not mean “safe to delete.”</p>
  </div>
  <div class="help-actions">
    <button class="hbtn primary" type="button" onclick="document.getElementById('git-help-dialog').close()">Got it</button>
  </div>
</dialog>

<div id="body">

  <!-- Left: working tree -->
  <div id="left">
    <div id="left-header">
      <span>Changes</span>
      <span id="change-count" style="background:var(--accent);color:#fff;border-radius:10px;padding:1px 7px;font-size:11px">0</span>
    </div>
    <div id="stage-actions">
      <button class="hbtn" onclick="selectAll(true)" style="font-size:11px;padding:4px 10px">Select All</button>
      <button class="hbtn" onclick="selectAll(false)" style="font-size:11px;padding:4px 10px">Deselect</button>
      <button class="hbtn" onclick="refreshDiscard()" style="font-size:11px;padding:4px 10px;color:var(--muted)" title="Refresh status">↻</button>
    </div>
    <div id="file-list">
      <div id="no-changes" style="display:none">✓ Nothing to commit</div>
    </div>
  </div>

  <!-- Right: commit history -->
  <div id="right">
    <div id="right-header">
      <span>Commit History</span>
      <span id="commit-count" style="color:var(--muted);font-weight:400"></span>
    </div>
    <div id="commit-list"></div>
  </div>

  <!-- Bottom: commit panel -->
  <div id="commit-panel">
    <div id="commit-row-1">
      <input id="commit-msg-input" type="text" placeholder="Commit message…" onkeydown="if(event.key==='Enter')commitSelected()">
      <button class="hbtn green" onclick="commitSelected()">✓ Commit</button>
      <button class="hbtn green" onclick="commitAndPush()" title="Commit then push to remote">✓ Commit &amp; Push</button>
    </div>
    <div id="commit-row-2">
      <span id="commit-scope">No files selected</span>
      <div class="spacer"></div>
      <button class="hbtn" onclick="gitPull()" title="git pull">⬇ Pull</button>
      <button class="hbtn" onclick="gitPush()" title="git push">⬆ Push</button>
    </div>
    <div id="status-bar"></div>
    <div id="output-box"></div>
  </div>

</div>

<details open style="margin:12px 16px;background:var(--bg1);border:1px solid var(--border);border-radius:8px;padding:10px 14px;color:var(--text);">
  <summary style="cursor:pointer;font-weight:700;color:var(--blue);">Keep Source Control focused: ignore generated files safely</summary>
  <div style="padding:10px 4px;max-width:1100px;font-size:12px;line-height:1.7;">
    <p>
      A long Changes list often comes from generated build output, caches, logs, or local runtime data.
      Use <code>.gitignore</code> for files Git should leave out of future changes. Ignoring files does not delete them.
    </p>
    <p><strong>1. Identify the source before changing anything</strong></p>
    <pre><code>git status --short
git status --short --untracked-files=all
git check-ignore -v -- path/to/suspected-generated-file</code></pre>
    <p><strong>2. Add narrow patterns to the repository's <code>.gitignore</code></strong></p>
    <pre><code># Examples only — add paths that are generated in your project
build/
*.log
.env
data/generated-output/
data/local-cache.sqlite3</code></pre>
    <p>
      Ignore generated bundles, caches, local databases, logs, and private environment files—not source code.
      Keep example configuration such as <code>.env.example</code>. Avoid broad patterns like <code>*.py</code>,
      <code>*.json</code>, or <code>data/</code>; they can hide real application files and data.
    </p>
    <p><strong>3. Verify, then commit only the ignore rules</strong></p>
    <pre><code>git check-ignore -v -- path/to/generated-file
git status --short
git add .gitignore
git diff --cached -- .gitignore
git commit -m "Ignore generated files"
git push</code></pre>
    <p>
      <strong>Important:</strong> <code>.gitignore</code> only affects untracked files. If a file is already tracked,
      adding a pattern will not remove it from Changes or GitHub. Do not use <code>git rm --cached</code> or delete
      files just to hide them; first confirm they are generated, not needed at runtime, and backed up if they contain
      important local data. This repository's generated Roku bundles and runtime artifacts are already ignored.
    </p>
  </div>
</details>

<script>
let _files = [];    // {status, file, checked}
let _pushAfterCommit = false;

// ── Status codes → label ─────────────────────────────────
const STATUS_LABEL = {M:'Modified',A:'Added',D:'Deleted','?':'Untracked',R:'Renamed',' ':'Clean'};

// ── Load git status ──────────────────────────────────────
async function loadStatus() {
  setStatus('<span class="spin">⟳</span> Refreshing…');
  try {
    const r = await fetch('/sys/api/scm/status');
    const d = await r.json();

    // Branch badge
    document.getElementById('branch-badge').textContent = '⎇ ' + (d.branch || 'unknown');

    // Build file list — merge staged + unstaged, dedupe by filename
    const seen = new Map();
    for (const f of (d.staged   || [])) seen.set(f.file, {status: f.status, file: f.file, area:'staged'});
    for (const f of (d.unstaged || [])) {
      if (!seen.has(f.file)) seen.set(f.file, {status: f.status, file: f.file, area:'unstaged'});
    }
    _files = [...seen.values()].map(f => ({...f, checked: true}));

    renderFileList();
    renderCommitHistory(d.commits || []);
    setStatus('Last refreshed: ' + new Date().toLocaleTimeString());
  } catch(e) {
    setStatus('Error: ' + e.message);
  }
}

// ── Render file list ─────────────────────────────────────
function renderFileList() {
  const el = document.getElementById('file-list');
  const nc = document.getElementById('no-changes');
  document.getElementById('change-count').textContent = _files.length;

  if (!_files.length) {
    el.innerHTML = '';
    nc.style.display = '';
    updateScope();
    return;
  }
  nc.style.display = 'none';

  el.innerHTML = _files.map((f, i) => {
    const sc = f.status === '?' ? '?' : f.status;
    return `<div class="file-row" onclick="toggleRow(${i})">
      <input type="checkbox" ${f.checked ? 'checked' : ''} onclick="event.stopPropagation();toggleCheck(${i})">
      <span class="file-status s-${sc}" title="${STATUS_LABEL[sc]||sc}">${sc === '?' ? '?' : sc}</span>
      <span class="file-name" title="${f.file}">${f.file}</span>
      <span class="file-area">${f.area||''}</span>
    </div>`;
  }).join('');
  updateScope();
}

function toggleRow(i) {
  _files[i].checked = !_files[i].checked;
  renderFileList();
}
function toggleCheck(i) {
  _files[i].checked = !_files[i].checked;
  updateScope();
}
function selectAll(val) {
  _files.forEach(f => f.checked = val);
  renderFileList();
}
function updateScope() {
  const sel = _files.filter(f => f.checked);
  const el = document.getElementById('commit-scope');
  if (!sel.length) { el.textContent = 'No files selected'; return; }
  if (sel.length === _files.length) { el.textContent = 'All ' + _files.length + ' changed files'; return; }
  el.textContent = sel.length + ' of ' + _files.length + ' files';
}

// ── Render commit history ────────────────────────────────
function renderCommitHistory(commits) {
  const el = document.getElementById('commit-list');
  document.getElementById('commit-count').textContent = commits.length ? '(last ' + commits.length + ')' : '';
  if (!commits.length) { el.innerHTML = '<div style="padding:20px;text-align:center;color:var(--muted)">No commits found</div>'; return; }
  el.innerHTML = commits.map(c => `
    <div class="commit-row" title="${c.hash}">
      <span class="commit-hash">${c.hash}</span>
      <span class="commit-msg">${escHtml(c.message)}</span>
    </div>`).join('');
}

// ── Commit ───────────────────────────────────────────────
async function commitSelected() {
  _pushAfterCommit = false;
  await _doCommit();
}
async function commitAndPush() {
  _pushAfterCommit = true;
  await _doCommit();
}
async function _doCommit() {
  const msg = document.getElementById('commit-msg-input').value.trim();
  if (!msg) { setStatus('⚠ Enter a commit message first'); return; }
  const selected = _files.filter(f => f.checked).map(f => f.file);
  if (!selected.length) { setStatus('⚠ No files selected'); return; }

  setStatus('<span class="spin">⟳</span> Committing…');
  showOutput('');
  try {
    const r = await fetch('/sys/api/scm/commit', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({message: msg, files: selected}),
    });
    const d = await r.json();
    if (d.ok) {
      showOutput(d.output || 'Committed.');
      document.getElementById('commit-msg-input').value = '';
      setStatus('✓ Committed');
      if (_pushAfterCommit) await gitPush();
      else loadStatus();
    } else {
      showOutput(d.error || 'Unknown error');
      setStatus('✗ Commit failed');
    }
  } catch(e) {
    setStatus('Error: ' + e.message);
  }
}

// ── Push / Pull ──────────────────────────────────────────
async function gitPush() {
  setStatus('<span class="spin">⟳</span> Pushing…');
  try {
    const r = await fetch('/sys/api/scm/push', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
    const d = await r.json();
    showOutput(d.output || (d.ok ? 'Pushed.' : 'Push failed'));
    setStatus(d.ok ? '✓ Pushed' : '✗ Push failed — see output');
    if (d.ok) loadStatus();
  } catch(e) { setStatus('Error: ' + e.message); }
}
async function gitPull() {
  setStatus('<span class="spin">⟳</span> Pulling…');
  try {
    const r = await fetch('/sys/api/scm/pull', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
    const d = await r.json();
    showOutput(d.output || (d.ok ? 'Up to date.' : 'Pull failed'));
    setStatus(d.ok ? '✓ Pulled' : '✗ Pull failed — see output');
    if (d.ok) loadStatus();
  } catch(e) { setStatus('Error: ' + e.message); }
}

function refreshDiscard() { loadStatus(); }

// ── Helpers ──────────────────────────────────────────────
function setStatus(html) { document.getElementById('status-bar').innerHTML = html; }
function showOutput(text) {
  const el = document.getElementById('output-box');
  el.textContent = text;
  el.style.display = text ? '' : 'none';
}
function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ── Init ─────────────────────────────────────────────────
loadStatus();
</script>
</body>
</html>
"""

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
</div>

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

<details style="margin:12px 16px;background:var(--bg1);border:1px solid var(--border);border-radius:8px;padding:10px 14px;color:var(--text);">
  <summary style="cursor:pointer;font-weight:700;color:var(--blue);">Git command and recovery reference</summary>
  <div style="padding:10px 4px;max-width:1100px;font-size:12px;line-height:1.7;">
    <p><strong>Inspect first</strong></p>
    <pre><code>git status --short
git diff
git diff --staged
git log --oneline --decorate -10
git branch -vv</code></pre>
    <p><strong>Everyday workflow</strong></p>
    <pre><code>git switch -c feature/my-change
git add -- path/to/file
git restore --staged -- path/to/file
git commit -m "Describe the change"
git fetch origin
git pull --ff-only
git push -u origin feature/my-change</code></pre>
    <p><strong>Recovery: preserve work before changing anything</strong></p>
    <pre><code>git diff &gt; working-tree-backup.patch
git diff --staged &gt; staged-backup.patch
git stash push -u -m "backup before recovery"
git stash list
git stash apply "stash@{0}"</code></pre>
    <p><strong>Undo choices</strong></p>
    <pre><code>git restore --worktree -- path/to/file
git restore --source=&lt;commit&gt; -- path/to/file
git revert &lt;commit&gt;
git reflog
git branch rescue/keep-before-recovery &lt;commit&gt;</code></pre>
    <p style="color:var(--muted);">
      <code>git restore --worktree</code> discards uncommitted edits to the named file. Prefer <code>git revert</code>
      for undoing a commit already shared with others. Before recovery, inspect status and make a backup/stash.
      Avoid <code>git reset --hard</code> and <code>git clean</code> unless you have verified what will be lost.
      Never share remote URLs if they contain embedded credentials.
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

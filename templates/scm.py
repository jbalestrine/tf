"""Git Command Center template."""

SCM_TEMPLATE = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>MasterChief · Git Command Center</title>
<link rel="stylesheet" href="/static/git-command-center.css">
<link rel="stylesheet" href="/static/source-control-navigation.css">
<script src="/static/git-file-editor-link.js" defer></script>
<script src="/static/git-quick-workflow.js" defer></script>
<script src="/static/git-action-receipts.js" defer></script>
<script src="/static/git-command-center.js" defer></script>
<script src="/static/git-pull-requests.js" defer></script>
<script src="/static/pypi-release.js" defer></script>
</head><body>
<header class="header">
  <a href="/" class="brand">MasterChief</a>
  <div><p class="eyebrow">SOURCE CONTROL</p><h1>Git Command Center</h1></div>
  <nav aria-label="Page links"><a href="/">Dashboard</a><a href="/sys/diagnostics">Diagnostics</a><a href="/sys/api/export-active">Export source</a></nav>
</header>
<main>
  <nav class="source-control-navigation" aria-label="Source Control workspaces">
    <h2>Source Control</h2>
    <p>Two specialized workspaces. Choosing a repository in GitHub Integration does not change the Git Command Center repository.</p>
    <div class="source-control-links">
      <a href="/sys/scm" aria-current="page"><strong>Git Command Center</strong><span>Manage the local MasterChief repository, Git workflow and pull requests.</span></a>
      <a href="/github"><strong>GitHub Integration</strong><span>Browse and clone repositories, explore files and save scripts.</span></a>
      <a href="/static/git-workflow-guide.html#activity-status"><strong>File Ecosystem</strong><span>Explore, edit, stage and review changed files.</span></a>
    </div>
  </nav>
  <p><a href="/static/git-workflow-guide.html">Git workflow diagram and field guide</a> · <a href="/static/git-workflow-guide.html#activity-status">Recent file activity &amp; 3D ecosystem</a> · <a href="/masterchief_code_ui">Code UI</a></p>
  <section class="intro"><div><h2>Your workflow, in one place</h2>
    <p>Inspect, prepare, save and publish. Review output and confirm every change before it runs.</p></div>
    <button id="refresh" type="button">Refresh repository</button></section>
  <div class="summary"><span id="branch">Branch: loading...</span><span id="changes">Loading changes...</span></div>
  <div id="pypi-deploy"><noscript><section class="panel"><h2>PYPI DEPLOY</h2><p>Publishing to PyPI is separate from Git merge. Enable JavaScript for the release checklist, or consult the release section of the project README.</p></section></noscript></div>
  <div id="quick-workflow"></div>
  <div id="pull-request-overview"></div>
  <section class="panel" id="update-and-push"><h2>Update and push your app: essentials</h2>
    <p>Save your edits first. Each button selects an action below; review its preview, click <strong>Run command</strong>, confirm when prompted, and check the output before continuing.</p>
    <ol>
      <li><strong>Check:</strong> <code>git status</code> shows your branch and uncommitted changes. “Up to date” compares commits, not uncommitted edits. <button type="button" data-guide-command="status">1. Check status</button></li>
      <li><strong>Stage:</strong> <code>git add -A</code> stages all tracked edits and deletions and non-ignored new files. Alternatively, stage selected paths. <button type="button" data-guide-command="stage_all">2. Stage all changes</button> <button type="button" data-guide-command="stage">Stage one path instead</button></li>
      <li><strong>Review:</strong> run <code>git status</code> and <code>git diff --staged</code>; check all staged files for private data or credentials. <button type="button" data-guide-command="status">3. Check staged files</button> <button type="button" data-guide-command="staged_diff">Review staged diff</button></li>
      <li><strong>Commit:</strong> enter a message for <code>git commit -m "Describe your changes"</code>. It includes all staged changes. <button type="button" data-guide-command="commit">4. Commit staged files</button></li>
      <li><strong>Push:</strong> use <code>git push</code> for a branch with an upstream, or set the upstream on its first push. Only commits are pushed. <button type="button" data-guide-command="push">5. Push current upstream</button> <button type="button" data-guide-command="push_upstream">Set upstream and push</button></li>
    </ol>
    <p class="warning"><strong>Important:</strong> Stage all includes changes across the entire repository, including deletions, and keeps previously staged changes. Ignored untracked files are not included. Review the complete staged set before committing; stage selected paths instead if you do not want everything. A commit is local until pushed, and pushing does not merge a pull request.</p>
    <p><a href="/static/git-workflow-guide.html#update-and-push">Open the full step-by-step guide and caveats</a></p>
  </section>
  <details class="panel"><summary>Working tree and recent commits</summary>
    <div class="workspace"><div><h2>Changes</h2><div id="file-list">Loading...</div></div>
    <div><h2>Recent commits</h2><pre id="commit-list">Loading...</pre></div></div>
    <p>Select a file to prepare its staging command, or open it in Code UI. Deleted or non-text files may not be readable. Already-staged changes are included in a commit.</p>
  </details>
  <section class="workflow"><h2>Everyday workflow</h2><ol>
    <li><b>Inspect</b><span>Check status, branches and changes.</span></li>
    <li><b>Prepare</b><span>Fetch, then create a feature branch.</span></li>
    <li><b>Save</b><span>Stage selected files, review and commit.</span></li>
    <li><b>Publish</b><span>Push, create a PR and review it. <a href="/github">Browse GitHub repositories</a>.</span></li>
    <li><b>Repeat</b><span>After merge, fetch and start fresh.</span></li>
  </ol></section>
  <div class="workspace">
    <section class="panel"><div class="section-title"><h2>Command library</h2><span>Choose an action to see its command</span></div>
      <label for="command-search">Find a command</label><input id="command-search" type="search" placeholder="Search commands">
      <div id="command-list"></div></section>
    <div class="side">
      <section class="panel"><h2 id="action-title">Select a command</h2><p id="action-hint">Commands run in the MasterChief repository.</p>
        <p><a href="#quick-workflow">Return to quick guided workflow</a></p>
        <form id="command-form"><div id="fields"></div><label>Command preview</label><pre id="preview"></pre>
          <p id="risk" class="warning" hidden>Confirm carefully. This changes files, Git history, or remote state. High-risk actions can permanently discard work.</p>
          <button type="submit" id="run" disabled>Run command</button></form></section>
      <section class="panel"><div class="section-title"><h2>Output</h2><span id="result-status" role="status" aria-live="polite">Ready</span></div>
        <p id="pr-result-link" hidden><a target="_blank" rel="noopener noreferrer">Open pull request on GitHub</a></p>
        <pre id="output">Command output will appear here.</pre></section>
    </div>
  </div>
  <details class="panel"><summary>Safety &amp; recovery notes</summary>
    <p>A clean status does not mean other branches or ignored files are safe to delete. Review staged content and private data before committing or pushing.</p>
    <p>Reset, force-delete, abort and force-push may discard work or rewrite history. Inspect status and reflog, verify backups, and confirm the exact target first. Reverting does not remove secrets from history.</p>
    <p>Reflog is local and not a backup. Merge commits require special revert handling. For conflicts, inspect status, resolve and stage files before continuing.</p>
  </details>
</main></body></html>"""

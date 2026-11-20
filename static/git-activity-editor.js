(() => {
  const $ = id => document.getElementById(id);
  const content = $('editor-content'), output = $('editor-output');
  let path = '', version = '', saved = '', busy = false, pendingReview = null;

  function dirty() { return !!path && content.value !== saved; }
  function controls() {
    content.disabled = busy || !path;
    $('editor-save').disabled = busy || !dirty();
    $('editor-stage').disabled = busy || !path || dirty();
    $('editor-review').disabled = busy;
    $('editor-commit').disabled = busy;
  }
  function setBusy(value) { busy = value; controls(); }
  function status(message) { $('editor-status').textContent = message; }
  function clearReview() {
    pendingReview = null;
    $('editor-commit').textContent = 'Review staged files for commit';
  }
  async function api(url, options) {
    const response = await fetch(url, options);
    let data;
    try { data = await response.json(); }
    catch { throw new Error(`Unexpected server response (HTTP ${response.status}). Restart MasterChief to load the latest API.`); }
    if (!response.ok || data.ok === false) throw new Error(data.error || data.stderr || `HTTP ${response.status}`);
    return data;
  }
  function post(url, data) {
    return api(url, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)});
  }
  async function command(action, values) {
    return post('/sys/api/scm/commands', {action, values, confirmation: action});
  }
  function refreshViews() {
    $('activity-refresh').click();
    $('refresh').click();
  }
  async function open(next) {
    if (busy) { status('Wait for the current operation to finish.'); return; }
    if (next === path) { $('activity-editor').scrollIntoView({behavior: 'smooth', block: 'start'}); return; }
    if (dirty() && !window.confirm(`Discard unsaved edits to ${path} and open ${next}?`)) {
      status(`Still editing ${path}; unsaved edits were kept.`);
      return;
    }
    setBusy(true); status(`Opening ${next}...`);
    try {
      const data = await api(`/sys/api/scm/activity-file?path=${encodeURIComponent(next)}`);
      path = next; version = data.version; content.value = data.content; saved = content.value;
      $('editor-path').textContent = path;
      status('Loaded. Edit the file, then save before staging.');
      $('activity-editor').scrollIntoView({behavior: 'smooth', block: 'start'});
    } catch (error) { status(`Could not open ${next}: ${error.message}`); }
    finally { setBusy(false); }
  }
  content.addEventListener('input', () => { clearReview(); status(dirty() ? 'Unsaved edits.' : 'No unsaved edits.'); controls(); });
  $('editor-message').addEventListener('input', clearReview);
  window.addEventListener('beforeunload', event => { if (dirty()) { event.preventDefault(); event.returnValue = ''; } });
  $('editor-save').addEventListener('click', async () => {
    if (busy || !dirty()) return;
    setBusy(true); status(`Saving ${path}...`);
    try {
      const data = await post('/sys/api/scm/activity-file', {path, content: content.value, version});
      version = data.version; saved = content.value;
      status('Saved to disk. Stage the file when ready.'); refreshViews();
    } catch (error) { status(`Save failed: ${error.message}`); }
    finally { setBusy(false); }
  });
  $('editor-stage').addEventListener('click', async () => {
    if (busy || !path || dirty()) return;
    if (!window.confirm(`Stage the entire saved file?\n\n${path}\n\nExisting staged files will remain staged.`)) return;
    setBusy(true); status(`Staging ${path}...`);
    try {
      const result = await command('stage', {path});
      clearReview();
      output.textContent = [result.stdout, result.stderr].filter(Boolean).join('\n') || 'File staged.';
      status('File staged. Review all staged changes before committing.'); refreshViews();
    } catch (error) { status(`Stage failed: ${error.message}`); }
    finally { setBusy(false); }
  });
  async function review() {
    const state = await api('/sys/api/scm/status');
    const names = state.staged.map(item => item.file);
    const result = await post('/sys/api/scm/commands', {action: 'staged_diff', values: {}});
    output.textContent = `Branch: ${state.branch || '(detached HEAD)'}\nStaged files:\n${names.join('\n') || '(none)'}\n\n${result.stdout || '(No staged diff)'}${result.stderr ? `\n${result.stderr}` : ''}`;
    return names;
  }
  $('editor-review').addEventListener('click', async () => {
    if (busy) return;
    clearReview();
    setBusy(true); status('Loading staged changes...');
    try { const names = await review(); status(`${names.length} staged file(s). Review the output below.`); }
    catch (error) { status(`Review failed: ${error.message}`); }
    finally { setBusy(false); }
  });
  $('editor-commit').addEventListener('click', async () => {
    if (busy) return;
    if (dirty()) { status('Save or discard unsaved editor changes before committing.'); return; }
    const message = $('editor-message').value.trim();
    if (!message) { status('Enter a commit message first.'); return; }
    setBusy(true); status('Reviewing staged changes...');
    try {
      const names = await review();
      if (!names.length) { clearReview(); status('No staged files to commit.'); return; }
      if (!pendingReview || pendingReview.message !== message || pendingReview.output !== output.textContent) {
        pendingReview = {message, output: output.textContent};
        $('editor-commit').textContent = 'Confirm commit';
        status('Review the staged files and diff below, then select Confirm commit.');
        return;
      }
      if (!window.confirm(`Commit ALL ${names.length} staged file(s)?\n\n${names.join('\n')}\n\nMessage: ${message}\n\nReview the staged diff on the page before confirming.`)) {
        status('Commit cancelled. Review the staged diff below.'); return;
      }
      const result = await command('commit', {message});
      clearReview();
      output.textContent = [result.stdout, result.stderr].filter(Boolean).join('\n') || 'Commit completed.';
      $('editor-message').value = '';
      status('Commit completed. Changes have not been pushed.'); refreshViews();
    } catch (error) { status(`Commit failed: ${error.message}`); }
    finally { setBusy(false); }
  });
  controls();
  window.GitActivityEditor = {open};
})();

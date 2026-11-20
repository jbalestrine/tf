(() => {
  const $ = id => document.getElementById(id);
  let commands = [], selected = null;
  async function api(url, options) {
    const response = await fetch(url, options);
    let data;
    try { data = await response.json(); }
    catch { throw new Error(`Unexpected server response (HTTP ${response.status}). Restart MasterChief to load the latest Source Control API.`); }
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    return data;
  }
  function renderList() {
    const search = $('command-search').value.toLowerCase(), list = $('command-list');
    list.replaceChildren();
    for (const group of [...new Set(commands.map(c => c.group))]) {
      const entries = commands.filter(c => c.group === group && `${c.label} ${c.command.join(' ')}`.toLowerCase().includes(search));
      if (!entries.length) continue;
      const box = document.createElement('div'), heading = document.createElement('h3');
      box.className = 'command-group'; heading.textContent = group; box.append(heading);
      for (const command of entries) {
        const button = document.createElement('button');
        button.type = 'button'; button.className = 'command-item';
        button.setAttribute('aria-pressed', String(selected?.id === command.id));
        const label = document.createElement('span'), example = document.createElement('small');
        label.textContent = command.label;
        example.textContent = command.command.join(' ');
        button.append(label, example); button.onclick = () => select(command);
        box.append(button);
      }
      list.append(box);
    }
  }
  function values() {
    return Object.fromEntries([...$('fields').querySelectorAll('input,textarea')].map(input => [input.name, input.value]));
  }
  function updatePreview() {
    const inputs = values();
    $('preview').textContent = selected.command.map(arg => {
      const match = /^\{(.+)\}$/.exec(arg);
      if (!match) return arg;
      const value = inputs[match[1]];
      return value ? JSON.stringify(value) : `<${match[1]}>`;
    }).join(' ');
  }
  function select(command) {
    selected = command; $('action-title').textContent = command.label;
    $('fields').replaceChildren(); $('risk').hidden = !command.confirm;
    const warnings = {
      stage_all: 'Stages all tracked changes, including deletions, and all non-ignored new files in the repository. Review files and private data first.',
      stage: 'Stages the whole selected path. Review its contents and any already-staged files before committing.',
      commit: 'Creates a local commit containing all staged changes. Review staged files and their contents first.',
      push: 'Publishes committed changes to the current upstream. Uncommitted changes are not pushed.',
      push_upstream: 'Publishes the specified branch to origin and sets its upstream. Uncommitted changes are not pushed.'
    };
    $('risk').textContent = warnings[command.id] || (command.group === 'High risk'
      ? 'High-risk action: this can permanently discard work or rewrite history. Verify the target and backups first.'
      : 'This action changes files, Git history, or remote state. Review the command and target before confirming.');
    for (const field of command.fields) {
      const label = document.createElement('label'), input = document.createElement(field === 'body' ? 'textarea' : 'input');
      label.textContent = field; input.name = field; input.required = true;
      input.placeholder = field === 'ref' ? 'e.g. origin/Masterchief4' : field;
      label.append(input); $('fields').append(label); input.addEventListener('input', updatePreview);
    }
    $('run').disabled = false; updatePreview(); renderList();
  }
  async function refresh() {
    try {
      const data = await api('/sys/api/scm/status');
      $('branch').textContent = `Branch: ${data.branch || '(detached HEAD)'}`;
      const names = new Set([...data.staged, ...data.unstaged].map(item => item.file));
      $('changes').textContent = `${names.size} changed file(s)`;
      const list = $('file-list'); list.replaceChildren();
      if (!names.size) list.textContent = 'No changes reported.';
      for (const name of names) {
        const row = document.createElement('button');
        row.type = 'button'; row.className = 'command-item';
        const areas = [data.staged.some(item => item.file === name) ? 'staged' : '',
          data.unstaged.some(item => item.file === name) ? 'unstaged' : ''].filter(Boolean).join(', ');
        row.textContent = `${name} (${areas})`;
        row.onclick = () => {
          select(commands.find(command => command.id === 'stage'));
          const input = $('fields').querySelector('[name="path"]');
          input.value = name; updatePreview(); input.focus();
        };
        const entry = document.createElement('div');
        entry.append(row, window.gitFileEditorLink(name));
        list.append(entry);
      }
      $('commit-list').textContent = data.commits.map(item => `${item.hash} ${item.message}`).join('\n') || 'No commits found.';
    } catch (error) { $('changes').textContent = `Status unavailable: ${error.message}`; }
  }
  $('refresh').onclick = refresh;
  $('command-search').oninput = renderList;
  for (const button of document.querySelectorAll('[data-guide-command]')) {
    button.addEventListener('click', () => {
      const command = commands.find(entry => entry.id === button.dataset.guideCommand);
      if (!command) { $('result-status').textContent = 'This command is unavailable. Restart MasterChief to load the latest commands, then sign in as an RBAC admin and refresh.'; return; }
      select(command);
      $('command-form').scrollIntoView({behavior: 'smooth', block: 'center'});
    });
  }
  $('command-form').onsubmit = async event => {
    event.preventDefault();
    if (!selected) return;
    const command = selected, args = values();
    if (command.confirm && !window.confirm(`Run this operation in the MasterChief repository?\n\n${$('preview').textContent}\n\nReview the target and any risk before continuing.`)) return;
    $('run').disabled = true; $('result-status').textContent = 'Running...';
    try {
      const data = await api('/sys/api/scm/commands', {method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({action:command.id, values:args, confirmation:command.confirm ? command.id : null})});
      $('output').textContent = [data.stdout, data.stderr].filter(Boolean).join('\n') || '(No output)';
      $('result-status').textContent = data.ok ? 'Completed' : `Failed (exit ${data.returncode})`;
      await refresh();
    } catch (error) { $('result-status').textContent = 'Failed'; $('output').textContent = error.message; }
    finally { $('run').disabled = false; }
  };
  api('/sys/api/scm/commands').then(data => { commands = data.commands; renderList(); refresh(); })
    .catch(error => { $('result-status').textContent = 'Unable to load commands'; $('output').textContent = error.message; });
})();

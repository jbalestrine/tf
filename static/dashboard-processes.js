(() => {
  const rows = document.getElementById('mc-process-rows');
  if (!rows) return;
  const status = document.getElementById('mc-process-status');
  const summary = document.getElementById('mc-process-summary');
  const filter = document.getElementById('mc-process-filter');
  const refresh = document.getElementById('mc-process-refresh');
  const end = document.getElementById('mc-process-end');
  let processes = [], selected = null, loading = false;

  function displayMemory(bytes) { return `${(bytes / 1024 / 1024).toFixed(1)} MB`; }
  function cpu(value) { return value === null ? 'Sampling...' : `${value.toFixed(1)}%`; }
  function cell(row, text) {
    const td = document.createElement('td');
    td.textContent = text;
    row.append(td);
    return td;
  }
  function render() {
    rows.replaceChildren();
    summary.replaceChildren();
    const query = filter.value.trim().toLowerCase();
    const visible = processes.filter(proc => `${proc.name} ${proc.pid}`.toLowerCase().includes(query));
    for (const proc of visible) {
      const tr = document.createElement('tr');
      const radio = document.createElement('input');
      radio.type = 'radio'; radio.name = 'mc-process'; radio.disabled = !proc.can_end;
      radio.setAttribute('aria-label', `Select ${proc.name}, PID ${proc.pid}`);
      radio.checked = Boolean(selected && selected.pid === proc.pid && selected.created === proc.created);
      radio.addEventListener('change', () => { selected = proc; end.disabled = false; });
      cell(tr, '').append(radio);
      cell(tr, proc.name); cell(tr, String(proc.pid)); cell(tr, proc.status);
      cell(tr, cpu(proc.cpu)); cell(tr, displayMemory(proc.memory_bytes));
      rows.append(tr);
    }
    if (!visible.length) {
      const tr = document.createElement('tr');
      const td = cell(tr, query ? 'No matching processes.' : 'No processes available.');
      td.colSpan = 6; rows.append(tr);
    }
    for (const proc of processes.slice(0, 5)) {
      const line = document.createElement('div'); line.className = 'mc-process-summary-row';
      const name = document.createElement('span'); name.textContent = `${proc.name} (PID ${proc.pid})`;
      const usage = document.createElement('span'); usage.textContent = `${cpu(proc.cpu)} CPU · ${displayMemory(proc.memory_bytes)}`;
      line.append(name, usage); summary.append(line);
    }
  }
  async function load() {
    if (loading) return;
    loading = true; refresh.disabled = true;
    try {
      const response = await fetch('/api/dashboard/processes', {credentials: 'same-origin', cache: 'no-store'});
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || `HTTP ${response.status}`);
      processes = data.processes;
      if (selected && !processes.some(proc => proc.pid === selected.pid && proc.created === selected.created && proc.can_end)) selected = null;
      end.disabled = !selected;
      render();
      status.textContent = `${processes.length} accessible processes · updated ${new Date().toLocaleTimeString()}${data.skipped ? ` · ${data.skipped} unavailable or exited during sampling` : ''}. CPU needs two samples.`;
    } catch (error) {
      selected = null; end.disabled = true;
      status.textContent = `Process readings unavailable: ${error.message}. Requires an authenticated RBAC admin. Previously displayed readings may be stale.`;
    } finally { loading = false; refresh.disabled = false; }
  }
  filter.addEventListener('input', () => {
    const query = filter.value.trim().toLowerCase();
    if (selected && !`${selected.name} ${selected.pid}`.toLowerCase().includes(query)) {
      selected = null; end.disabled = true;
    }
    render();
  });
  refresh.addEventListener('click', load);
  end.addEventListener('click', async () => {
    if (!selected || loading) return;
    const target = selected;
    if (!window.confirm(`End ${target.name} (PID ${target.pid}) on the MasterChief server?\n\nUnsaved work may be lost. This requests termination and cannot be undone.`)) return;
    loading = true; end.disabled = true; refresh.disabled = true;
    try {
      const response = await fetch(`/api/dashboard/processes/${target.pid}/terminate`, {
        method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({created: target.created, confirmation: target.pid})
      });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || `HTTP ${response.status}`);
      selected = null;
      status.textContent = data.message;
    } catch (error) {
      selected = null;
      status.textContent = `Could not end process: ${error.message}`;
    } finally { loading = false; refresh.disabled = false; end.disabled = true; render(); }
  });
  load();
  setInterval(() => { if (!document.hidden) load(); }, 5000);
})();

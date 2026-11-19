(() => {
  const host = document.getElementById('management-inventory');
  if (!host) return;
  const title = document.createElement('h2');
  title.textContent = 'Platform inventory';
  const description = document.createElement('p');
  description.textContent = 'Read-only overview across management systems. Configured state and runtime state are separate; an add-on folder is not necessarily a runnable service.';
  const search = document.createElement('input');
  search.type = 'search';
  search.placeholder = 'Search inventory';
  search.setAttribute('aria-label', 'Search platform inventory');
  const filter = document.createElement('select');
  filter.setAttribute('aria-label', 'Filter inventory by category');
  const all = document.createElement('option');
  all.value = '';
  all.textContent = 'All categories';
  filter.append(all);
  const status = document.createElement('p');
  status.setAttribute('role', 'status');
  const list = document.createElement('div');
  const refresh = document.createElement('button');
  refresh.type = 'button';
  refresh.textContent = 'Refresh inventory';
  refresh.addEventListener('click', load);
  const header = document.createElement('div');
  header.append(search, filter, refresh);
  header.style.cssText = 'display:flex;gap:8px;flex-wrap:wrap';
  host.style.cssText = 'margin:24px 0;padding:16px;border:1px solid #475569;border-radius:8px';
  host.append(title, description, header, status, list);
  let items = [];
  window.managementInventoryReady = false;

  function render() {
    const query = search.value.trim().toLocaleLowerCase();
    const visible = items.filter(item => (!filter.value || item.kind === filter.value) &&
      [item.name, item.key, item.kind, item.configured, item.runtime, item.detail]
        .some(value => String(value || '').toLocaleLowerCase().includes(query)));
    status.textContent = `Showing ${visible.length} of ${items.length} items.`;
    list.replaceChildren();
    for (const item of visible) {
      const card = document.createElement('div');
      card.style.cssText = 'padding:10px 0;border-top:1px solid #475569';
      const heading = document.createElement('strong');
      heading.textContent = `${item.name} — ${item.kind}`;
      const state = document.createElement('div');
      state.textContent = `Configured: ${item.configured} | Runtime: ${item.runtime}`;
      const detail = document.createElement('div');
      detail.textContent = item.detail;
      const link = document.createElement('a');
      link.href = item.url;
      link.textContent = 'Open management page';
      card.append(heading, state, detail, link);
      list.append(card);
    }
  }

  async function load() {
    refresh.disabled = true;
    status.textContent = 'Loading inventory...';
    try {
      const response = await fetch('/api/management/inventory', {cache: 'no-store'});
      if (!(response.headers.get('content-type') || '').toLowerCase().includes('application/json')) {
        throw new Error(`Unexpected server response (HTTP ${response.status}). Restart MasterChief to load the inventory, then sign in as an administrator.`);
      }
      const result = await response.json();
      if (!response.ok || !result.ok) throw new Error(result.error || `HTTP ${response.status}`);
      if (!Array.isArray(result.items)) throw new Error('Invalid inventory response.');
      items = result.items;
      window.managementInventoryReady = true;
      const previous = filter.value;
      filter.replaceChildren(all);
      for (const kind of [...new Set(items.map(item => item.kind))].sort()) {
        const option = document.createElement('option');
        option.value = kind;
        option.textContent = kind;
        filter.append(option);
      }
      filter.value = [...filter.options].some(option => option.value === previous) ? previous : '';
      render();
    } catch (error) {
      window.managementInventoryReady = false;
      items = [];
      list.replaceChildren();
      status.textContent = `Inventory unavailable: ${error.message}`;
    } finally {
      refresh.disabled = false;
      window.dispatchEvent(new Event('management-inventory-ready'));
    }
  }
  search.addEventListener('input', render);
  filter.addEventListener('change', render);
  window.refreshManagementInventory = load;
  load();
})();

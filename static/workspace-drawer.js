(() => {
  const el = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text) node.textContent = text;
    return node;
  };
  const button = el('button', 'mc-drawer-launch', '☰ Workspaces');
  button.type = 'button';
  button.setAttribute('aria-haspopup', 'dialog');
  button.setAttribute('aria-expanded', 'false');
  const overlay = el('div', 'mc-drawer-overlay');
  overlay.hidden = true;
  const panel = el('section', 'mc-drawer');
  panel.setAttribute('role', 'dialog');
  panel.setAttribute('aria-modal', 'true');
  panel.setAttribute('aria-labelledby', 'mc-drawer-title');
  const head = el('div', 'mc-drawer-head');
  const title = el('h2', '', 'Workspaces'); title.id = 'mc-drawer-title';
  const close = el('button', 'mc-drawer-close', 'Close');
  close.type = 'button';
  head.append(title, close);
  const description = el('p', 'mc-drawer-intro', 'Find a workspace by task. Existing navigation stays in place. The Unified Site Map lists technical routes.');
  const label = el('label', 'mc-drawer-label', 'Search workspaces');
  const search = el('input', 'mc-drawer-search'); search.type = 'search';
  search.placeholder = 'Search tools and add-ons'; label.append(search);
  const status = el('p', 'mc-drawer-status'); status.setAttribute('role', 'status');
  const list = el('div', 'mc-drawer-list');
  panel.append(head, description, label, status, list);
  overlay.append(panel);
  document.body.append(button, overlay);
  let items = [], loaded = false, previousFocus = null, closeTimer = null, openingFrame = null;
  const groups = ['Home', 'Develop', 'Source Control', 'Build & Deploy', 'Operate', 'Manage', 'More tools', 'Installed add-ons'];

  function render() {
    list.replaceChildren();
    const query = search.value.trim().toLocaleLowerCase();
    let count = 0;
    for (const group of groups) {
      const entries = items.filter(item => item.group === group &&
        `${item.title} ${item.description} ${group}`.toLocaleLowerCase().includes(query));
      if (!entries.length) continue;
      count += entries.length;
      const section = el('section', 'mc-drawer-group');
      section.append(el('h3', '', group));
      const primary = entries.filter(item => !item.extra);
      const extra = entries.filter(item => item.extra);
      function link(item) {
        const anchor = el('a', 'mc-drawer-link');
        anchor.href = item.url;
        if (item.url === location.pathname + location.search + location.hash ||
            (!location.hash && item.url === location.pathname)) anchor.setAttribute('aria-current', 'page');
        anchor.append(el('strong', '', item.title));
        if (item.description || item.disabled) {
          anchor.append(el('span', '', [item.description, item.disabled ? 'Feature disabled' : ''].filter(Boolean).join(' · ')));
        }
        return anchor;
      }
      primary.forEach(item => section.append(link(item)));
      if (extra.length) {
        const details = el('details', 'mc-drawer-more');
        details.open = Boolean(query) || !primary.length;
        details.append(el('summary', '', `More ${group.toLowerCase()} (${extra.length})`));
        extra.forEach(item => details.append(link(item)));
        section.append(details);
      }
      list.append(section);
    }
    status.textContent = count ? `${count} workspace${count === 1 ? '' : 's'}${query ? ' found' : ''}. Access depends on your permissions.` : 'No workspaces found.';
  }
  async function load() {
    status.textContent = 'Loading workspaces...';
    try {
      const response = await fetch('/api/workspace-drawer', {credentials: 'same-origin'});
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || `HTTP ${response.status}`);
      items = data.items; loaded = true; render();
    } catch (error) {
      status.textContent = `Unable to load workspaces: ${error.message}. Close and reopen to retry.`;
    }
  }
  function open() {
    clearTimeout(closeTimer);
    if (openingFrame !== null) cancelAnimationFrame(openingFrame);
    previousFocus = document.activeElement;
    overlay.hidden = false; overlay.inert = false; button.setAttribute('aria-expanded', 'true');
    openingFrame = requestAnimationFrame(() => {
      openingFrame = requestAnimationFrame(() => { overlay.classList.add('mc-drawer-visible'); openingFrame = null; });
    });
    search.focus();
    if (!loaded) load();
  }
  function dismiss() {
    if (openingFrame !== null) { cancelAnimationFrame(openingFrame); openingFrame = null; }
    overlay.classList.remove('mc-drawer-visible'); overlay.inert = true;
    button.setAttribute('aria-expanded', 'false');
    clearTimeout(closeTimer);
    closeTimer = setTimeout(() => { overlay.hidden = true; }, 250);
    if (previousFocus && previousFocus.isConnected) previousFocus.focus();
  }
  button.addEventListener('click', open);
  close.addEventListener('click', dismiss);
  overlay.addEventListener('click', event => { if (event.target === overlay) dismiss(); });
  list.addEventListener('click', event => { if (event.target.closest('a[href]')) dismiss(); });
  search.addEventListener('input', render);
  panel.addEventListener('keydown', event => {
    if (event.key === 'Escape') { event.preventDefault(); dismiss(); return; }
    if (event.key !== 'Tab') return;
    const focusable = Array.from(panel.querySelectorAll('button, input, a[href], summary'))
      .filter(node => node.getClientRects().length);
    if (!focusable.length) return;
    if (event.shiftKey && document.activeElement === focusable[0]) { event.preventDefault(); focusable[focusable.length - 1].focus(); }
    else if (!event.shiftKey && document.activeElement === focusable[focusable.length - 1]) { event.preventDefault(); focusable[0].focus(); }
  });
})();

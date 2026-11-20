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
  const groups = ['Home', 'Develop', 'Source Control', 'Build & Deploy', 'Operate', 'Automate & AI', 'Manage', 'More tools', 'Installed add-ons'];
  const favoritesKey = 'masterchief.workspace.favorites.v1', recentKey = 'masterchief.workspace.recent.v1';
  const homeGrid = document.getElementById('mc-start-grid');
  const homeContinue = document.getElementById('mc-continue');
  const startPoints = [
    ['/masterchief_code_ui', 'Work on code', 'Edit MasterChief project files.'],
    ['/static/git-workflow-guide.html#release-journey', 'Complete an update', 'Follow changes through commit, review, and merge.'],
    ['/iac_manager', 'Build infrastructure', 'Manage infrastructure as code.'],
    ['/scripts', 'Run or automate', 'Manage scripts and automation.'],
    ['/sys/diagnostics', 'Check system health', 'Inspect diagnostics and application status.']
  ];
  let storageWarning = false;
  function readStored(key) {
    try {
      const value = JSON.parse(localStorage.getItem(key) || '[]');
      if (!Array.isArray(value)) throw new TypeError('Invalid saved workspace list');
      return value.filter(item => typeof item === 'string');
    } catch { storageWarning = true; return []; }
  }
  function writeStored(key, values) {
    try { localStorage.setItem(key, JSON.stringify(values)); return true; }
    catch { storageWarning = true; status.textContent = 'Browser storage is unavailable; favorites and recent work cannot be saved.'; return false; }
  }
  function visit(item) {
    if (item.url.includes('?')) return;
    const known = new Set(items.map(entry => entry.url));
    writeStored(recentKey, [item.url, ...readStored(recentKey).filter(url => url !== item.url && !url.includes('?') && known.has(url))].slice(0, 8));
  }
  function makeLink(item) {
    const row = el('div', 'mc-drawer-row');
    const anchor = el('a', 'mc-drawer-link');
    anchor.href = item.url;
    if (item.url === location.pathname + location.search + location.hash ||
        (!location.hash && item.url === location.pathname)) anchor.setAttribute('aria-current', 'page');
    anchor.append(el('strong', '', item.title));
    if (item.description || item.disabled) anchor.append(el('span', '', [item.description, item.disabled ? 'Feature disabled' : ''].filter(Boolean).join(' · ')));
    anchor.addEventListener('click', () => visit(item));
    const pinned = readStored(favoritesKey).includes(item.url);
    const pin = el('button', 'mc-drawer-favorite', pinned ? '★' : '☆');
    pin.type = 'button';
    if (item.url.includes('?')) {
      pin.disabled = true;
      pin.title = 'Favorites are unavailable for links with query parameters.';
      pin.setAttribute('aria-label', `Favorites unavailable for ${item.title}: link contains query parameters`);
      row.append(anchor, pin);
      return row;
    }
    pin.setAttribute('aria-label', `${pinned ? 'Remove' : 'Add'} ${item.title} ${pinned ? 'from' : 'to'} favorites`);
    pin.setAttribute('aria-pressed', String(pinned));
    pin.addEventListener('click', () => {
      const known = new Set(items.map(entry => entry.url));
      const selected = readStored(favoritesKey).filter(url => url !== item.url && !url.includes('?') && known.has(url));
      if (!pinned) selected.push(item.url);
      if (!writeStored(favoritesKey, selected)) { renderHome(); return; }
      render();
      renderHome();
      const next = [...list.querySelectorAll('.mc-drawer-favorite')].find(node => node.getAttribute('aria-label') === `${pinned ? 'Add' : 'Remove'} ${item.title} ${pinned ? 'to' : 'from'} favorites`);
      if (next) next.focus();
    });
    row.append(anchor, pin);
    return row;
  }

  function render() {
    const expanded = new Set([...list.querySelectorAll('details[open] > summary')].map(node => node.textContent));
    list.replaceChildren();
    const query = search.value.trim().toLocaleLowerCase();
    let count = 0;
    if (!query) {
      for (const [heading, key] of [['Favorites', favoritesKey], ['Recently opened', recentKey]]) {
        const urls = readStored(key);
        const found = urls.filter(url => !url.includes('?')).map(url => items.find(item => item.url === url)).filter(Boolean);
        if (!found.length) continue;
        const section = el('section', 'mc-drawer-group');
        section.append(el('h3', '', heading));
        found.forEach(item => section.append(makeLink(item)));
        list.append(section);
      }
    }
    for (const group of groups) {
      const entries = items.filter(item => item.group === group &&
        `${item.title} ${item.description} ${group}`.toLocaleLowerCase().includes(query));
      if (!entries.length) continue;
      count += entries.length;
      const section = el('section', 'mc-drawer-group');
      section.append(el('h3', '', group));
      const primary = entries.filter(item => !item.extra);
      const extra = entries.filter(item => item.extra);
      primary.forEach(item => section.append(makeLink(item)));
      if (extra.length) {
        const details = el('details', 'mc-drawer-more');
        const summary = el('summary', '', `More ${group.toLowerCase()} (${extra.length})`);
        details.open = Boolean(query) || !primary.length || expanded.has(summary.textContent);
        details.append(summary);
        extra.forEach(item => details.append(makeLink(item)));
        section.append(details);
      }
      list.append(section);
    }
    status.textContent = count ? `${count} workspace${count === 1 ? '' : 's'}${query ? ' found' : ''}. Access depends on your permissions.` : 'No workspaces found.';
    if (storageWarning) status.textContent += ' Browser storage is unavailable; favorites and recent work may not be saved.';
  }
  function renderHome() {
      if (!homeGrid) return;
      homeGrid.replaceChildren();
      for (const [url, title, description] of startPoints) {
        const item = items.find(entry => entry.url === url);
        if (!item) continue;
        const anchor = el('a');
        anchor.href = item.url;
        anchor.append(el('strong', '', title), el('span', '', description + (item.disabled ? ' Feature disabled.' : '')));
        anchor.addEventListener('click', () => visit(item));
        homeGrid.append(anchor);
      }
      if (!homeGrid.children.length) homeGrid.textContent = 'No starting points are available. Use the existing navigation.';
      homeContinue.replaceChildren();
      const recent = readStored(recentKey).filter(url => !url.includes('?')).map(url => items.find(item => item.url === url)).filter(Boolean).slice(0, 3);
      if (recent.length) {
        const heading = el('h3', '', 'Continue to recently opened');
        const links = el('div', 'mc-start-grid');
        recent.forEach(item => {
          const anchor = el('a');
          anchor.href = item.url;
          anchor.append(el('strong', '', item.title), el('span', '', item.disabled ? 'Feature disabled' : item.description));
          anchor.addEventListener('click', () => visit(item));
          links.append(anchor);
        });
        const clear = el('button', 'mc-clear-recent', 'Clear recent workspaces');
        clear.type = 'button';
        clear.addEventListener('click', () => {
          if (writeStored(recentKey, [])) {
            renderHome(); render();
            const heading = document.getElementById('mc-start-title');
            if (heading) { heading.tabIndex = -1; heading.focus(); }
          } else { renderHome(); render(); }
        });
        homeContinue.append(heading, links, clear);
      }
      if (storageWarning) homeContinue.append(el('p', 'mc-start-note', 'Browser storage is unavailable; favorites and recent work may not be saved.'));
  }
  async function load() {
    status.textContent = 'Loading workspaces...';
    try {
      const response = await fetch('/api/workspace-drawer', {credentials: 'same-origin'});
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || `HTTP ${response.status}`);
      items = data.items; loaded = true; render(); renderHome();
    } catch (error) {
      status.textContent = `Unable to load workspaces: ${error.message}. Close and reopen to retry.`;
      if (homeGrid) homeGrid.textContent = `Unable to load starting points: ${error.message}. Use the existing navigation or open Workspaces to retry.`;
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
  if (homeGrid) load();
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

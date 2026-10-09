(() => {
  const nav = document.querySelector('nav[aria-label="Main navigation"]');
  if (!nav) return;

  const search = nav.querySelector('#nav-search');
  const status = nav.querySelector('#nav-search-status');
  const groups = Array.from(nav.querySelectorAll('details.nav-group'));
  const links = Array.from(nav.querySelectorAll('a[href]'));
  const groupLinks = new Map(groups.map(group => [
    group,
    Array.from(group.querySelectorAll('a[href]'))
  ]));

  function closeGroups(except = null) {
    groups.forEach(group => {
      if (group !== except) group.open = false;
    });
  }

  function filterPages() {
    const query = (search?.value || '').trim().toLocaleLowerCase();
    let matchCount = 0;
    if (query) {
      nav.classList.add('searching');
      links.forEach(link => {
        const matches = link.textContent.toLocaleLowerCase().includes(query);
        link.hidden = !matches;
        if (matches) matchCount += 1;
      });
      groups.forEach(group => {
        const hasMatch = groupLinks.get(group).some(link => !link.hidden);
        group.hidden = !hasMatch;
        group.open = hasMatch;
      });
      if (status) status.textContent = matchCount ? `${matchCount} match${matchCount === 1 ? '' : 'es'}` : 'No pages found';
      return;
    }

    nav.classList.remove('searching');
    links.forEach(link => { link.hidden = false; });
    groups.forEach(group => {
      group.hidden = false;
      group.open = false;
    });
    if (status) status.textContent = '';
  }

  groups.forEach(group => {
    const summary = group.querySelector('summary');
    if (summary) summary.setAttribute('aria-expanded', String(group.open));
    group.addEventListener('toggle', () => {
      const groupSummary = group.querySelector('summary');
      if (groupSummary) groupSummary.setAttribute('aria-expanded', String(group.open));
      if (group.open && !nav.classList.contains('searching')) closeGroups(group);
    });
    group.addEventListener('keydown', event => {
      if (event.key === 'Escape') {
        group.open = false;
        group.querySelector('summary')?.focus();
      }
    });
  });

  search?.addEventListener('input', filterPages);
  search?.addEventListener('keydown', event => {
    if (event.key === 'Enter') {
      const firstMatch = search.value.trim() ? links.find(link => !link.hidden) : null;
      if (firstMatch) window.location.assign(firstMatch.href);
    } else if (event.key === 'Escape') {
      search.value = '';
      filterPages();
      search.blur();
    }
  });

  nav.addEventListener('click', event => {
    const anchor = event.target instanceof Element ? event.target.closest('a[href]') : null;
    if (anchor) closeGroups();
  });

  document.addEventListener('click', event => {
    if (!nav.contains(event.target) && !search?.value) closeGroups();
  });

  document.addEventListener('keydown', event => {
    const target = event.target;
    const typing = target instanceof HTMLElement && (
      target.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName)
    );
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      search?.focus();
      search?.select();
    } else if (event.key === '/' && !typing) {
      event.preventDefault();
      search?.focus();
    } else if (event.key === 'Escape' && !search?.value) {
      closeGroups();
    }
  });

  filterPages();
})();

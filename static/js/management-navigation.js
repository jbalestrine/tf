(() => {
  const nav = document.querySelector('[data-management-page]');
  if (!nav) return;
  const pages = [
    {key: 'master-menu', title: 'Master Menu', url: '/master-menu',
      description: 'Page and feature flags, plus navigation by focus.'},
    {key: 'features', title: 'Feature Management', url: '/features',
      description: 'Configured feature handlers and their settings.'},
    {key: 'modules', title: 'Module Management', url: '/modules',
      description: 'Built-in manager module configuration.'},
    {key: 'addons', title: 'Add-on Modules', url: '/addons/modules',
      description: 'Installed add-on files and services.'},
    {key: 'code', title: 'Code Manager', url: '/ext/code_manager/',
      description: 'Isolated app features and linked blueprints.'}
  ];
  const heading = document.createElement('h2');
  heading.className = 'management-nav-title';
  heading.textContent = 'Management Center';
  const intro = document.createElement('p');
  intro.className = 'management-nav-intro';
  intro.textContent = 'Choose a specialized workspace. Similar controls can affect different parts of the platform.';
  const list = document.createElement('ul');
  list.className = 'management-nav-list';
  for (const page of pages) {
    const item = document.createElement('li');
    const link = document.createElement('a');
    link.href = page.url;
    link.textContent = page.title;
    if (nav.dataset.managementPage === page.key) link.setAttribute('aria-current', 'page');
    const description = document.createElement('span');
    description.textContent = page.description;
    item.append(link, description);
    list.append(item);
  }
  nav.replaceChildren(heading, intro, list);
})();

(() => {
  window.gitFileEditorLink = path => {
    const link = document.createElement('a');
    link.href = `/masterchief_code_ui?open=${encodeURIComponent(path)}`;
    link.textContent = 'Open in Code UI';
    link.setAttribute('aria-label', `Open ${path} in Code UI`);
    link.target = '_blank';
    link.rel = 'noopener';
    return link;
  };
})();

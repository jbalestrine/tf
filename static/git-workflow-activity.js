(() => {
  const $ = id => document.getElementById(id);
  async function loadActivity() {
    $('activity-status').textContent = 'Loading activity...';
    try {
      const response = await fetch('/sys/api/scm/activity');
      let data;
      try { data = await response.json(); }
      catch { throw new Error(`Unexpected server response (HTTP ${response.status}). Restart MasterChief to load file activity.`); }
      if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
      const groups = new Map();
      for (const file of data.files) {
        const area = file.path.includes('/') ? file.path.split('/')[0] : '(repository root)';
        if (!groups.has(area)) groups.set(area, []);
        groups.get(area).push(file);
      }
      const container = $('activity-groups'); container.replaceChildren();
      for (const [area, files] of groups) {
        const group = document.createElement('details'), title = document.createElement('summary'), list = document.createElement('ul');
        title.textContent = `${area} (${files.length})`; group.append(title);
        for (const file of files) {
          const item = document.createElement('li');
          const button = document.createElement('button');
          button.type = 'button'; button.className = 'activity-file';
          button.textContent = file.path;
          button.addEventListener('click', () => window.GitActivityEditor.open(file.path));
          item.append(button, ` — ${file.sources.join(', ')} `, window.gitFileEditorLink(file.path));
          list.append(item);
        }
        group.append(list); container.append(group);
      }
      if (!groups.size) container.textContent = 'No changed files in the working tree or latest commit.';
      window.GitActivity3D.load(data);
      const graph = $('activity-graph'); graph.replaceChildren();
      if (!data.edges.length) graph.textContent = 'No statically resolved Python imports involving these files were found.';
      else {
        const list = document.createElement('div'); list.className = 'dependency-graph';
        for (const edge of data.edges) {
          const item = document.createElement('div'), source = document.createElement('span'),
            arrow = document.createElement('span'), target = document.createElement('span');
          item.className = 'dependency-edge'; source.className = target.className = 'dependency-node';
          source.textContent = edge.from; arrow.textContent = 'imports →'; target.textContent = edge.to;
          item.append(source, arrow, target);
          list.append(item);
        }
        graph.append(list);
      }
      const c = data.coverage;
      $('activity-status').textContent = `Showing ${c.changed_shown} of ${c.changed_total} files, ${Math.min(data.edges.length, c.edges_total)} of ${c.edges_total} relationships. Python files considered: ${c.python_scanned} of ${c.python_total}; ${c.warning_count} inspection warning(s).`;
      if (c.warnings.length) {
        const details = document.createElement('details'), title = document.createElement('summary'), list = document.createElement('ul');
        title.textContent = 'Inspection warnings'; details.append(title);
        for (const warning of c.warnings) { const item = document.createElement('li'); item.textContent = warning; list.append(item); }
        details.append(list); graph.append(details);
      }
    } catch (error) { $('activity-status').textContent = `Activity unavailable: ${error.message} Any previously displayed activity may be out of date.`; }
  }
  $('activity-refresh').addEventListener('click', loadActivity);
  loadActivity();
})();

((root) => {
  const stages = ['Workshop', 'Checkpoint', 'Launch', 'Review Gate', 'Merge', 'Arrival'];
  function decide(update, status) {
    if (!update.branch) return {stage: 0, reason: 'Detached HEAD: select a branch before starting this journey.'};
    if (update.branch !== status.branch || (update.worktree === 'clean') !== (!status.staged.length && !status.unstaged.length))
      return {stage: 0, reason: 'The repository changed during the check. Refresh before continuing.'};
    if (status.unstaged.length) return {stage: 0, reason: 'Review your changed files, then stage the ones you want.'};
    if (status.staged.length) return {stage: 1, reason: 'Review all staged changes and create your commit.'};
    const pr = update.pull_request;
    if (pr.state === 'merged' && pr.head_matches && pr.merged_head_matches && pr.merged_at && pr.merge_commit)
      return {stage: 5, reason: 'GitHub reports this commit in a merged pull request.'};
    if (update.upstream.state === 'not_configured') return {stage: 2, reason: 'This branch has no upstream. Set one when you push.'};
    if (update.upstream.state !== 'matches') return {stage: 2, reason: 'The remote needs attention. Inspect its state before pushing.'};
    if (pr.state === 'unknown') return {stage: 3, reason: 'The PR could not be verified. Resolve the error and refresh before creating or merging.'};
    if (pr.state === 'none' || pr.state === 'closed' || pr.state === 'merged')
      return {stage: 3, reason: 'Check the target and create a new pull request if this branch has new work.'};
    if (!pr.head_matches) return {stage: 3, reason: 'The PR head differs from your local commit. Verify the branch before merging.'};
    if (pr.details_error || pr.draft === undefined) return {stage: 3, reason: 'PR details could not be verified. Review the PR on GitHub.'};
    if (pr.draft) return {stage: 3, reason: 'This PR is a draft. Mark it ready on GitHub after reviewing it.'};
    return {stage: 4, reason: 'Review the PR, approvals, and required checks before confirming a merge.'};
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = {decide};
  if (!root.document) return;
  const document = root.document;
  const $ = id => document.getElementById(id);
  if (!$('journey-toggle')) return;
  let update, status, active = 0, suggested = 0, loading = false;
  const el = (tag, text, cls) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (cls) node.className = cls;
    return node;
  };
  function action(parent, label, actionId, values) {
    const button = el('button', label);
    button.type = 'button';
    button.addEventListener('click', () => document.dispatchEvent(
      new CustomEvent('scm-journey-select', {detail: {action: actionId, values: values || {}}})));
    parent.append(button);
  }
  function githubLink(parent, pr) {
    try {
      const url = new URL(pr.url);
      if (url.protocol !== 'https:' || url.hostname !== 'github.com') throw new Error('Invalid URL');
      const link = el('a', `Review PR #${pr.number} on GitHub`);
      link.href = url.href; link.target = '_blank'; link.rel = 'noopener noreferrer';
      parent.append(link);
    } catch { parent.append(el('p', 'PR link unavailable: invalid GitHub URL.')); }
  }
  function render() {
    const map = $('journey-map');
    map.replaceChildren();
    stages.forEach((name, index) => {
      const button = el('button', undefined, `journey-node${index === active ? ' is-selected' : ''}${index === suggested ? ' is-next' : ''}`);
      button.type = 'button';
      button.setAttribute('aria-pressed', String(index === active));
      button.append(el('span', String(index + 1).padStart(2, '0'), 'journey-number'), el('strong', name),
        el('small', index === suggested ? 'Current focus' : 'Explore stage'));
      button.addEventListener('click', () => { active = index; render(); });
      map.append(button);
    });
    const detail = $('journey-detail');
    detail.replaceChildren();
    detail.classList.toggle('is-arrival', active === 5 && suggested === 5);
    detail.append(el('p', `STAGE ${active + 1} / ${stages.length}`, 'journey-kicker'),
      el('h3', stages[active]));
    const actions = el('div', undefined, 'journey-actions');
    const pr = update.pull_request, upstream = update.upstream;
    if (active === 0) {
      detail.append(el('p', 'Your workshop: review changed paths and stage only what belongs in this update. Stage all includes deletions and non-ignored new files across the repository.'));
      const files = new Map();
      for (const entry of status.staged) files.set(entry.file, ['staged']);
      for (const entry of status.unstaged) {
        const areas = files.get(entry.file) || [];
        areas.push('unstaged'); files.set(entry.file, areas);
      }
      if (!files.size) detail.append(el('p', 'No uncommitted changes reported.'));
      else {
        const list = el('ul', undefined, 'journey-files');
        for (const [path, areas] of files) {
          const item = el('li');
          item.append(el('span', `${path} (${areas.join(', ')})`));
          if (areas.includes('unstaged')) action(item, 'Stage path', 'stage', {path});
          list.append(item);
        }
        detail.append(list);
      }
      action(actions, 'Inspect status', 'status');
      action(actions, 'Stage all changes', 'stage_all');
      const ecosystem = el('a', 'Open file ecosystem and editor');
      ecosystem.href = '#activity-status'; actions.append(ecosystem);
    } else if (active === 1) {
      detail.append(el('p', `${status.staged.length} staged path(s). A commit includes every staged change. Review the staged diff, including private data, before committing.`));
      action(actions, 'Review staged diff', 'staged_diff');
      action(actions, 'Review staged list', 'status');
      action(actions, 'Prepare commit', 'commit');
    } else if (active === 2) {
      const descriptions = {
        matches: 'Your current commit matches its live upstream branch.',
        different: 'Your current commit differs from the remote. This check cannot tell whether it is ahead, behind, or diverged. Inspect before pushing or pulling.',
        not_configured: 'No upstream is configured. Set one on the first push.',
        missing: 'The configured remote branch no longer exists. Inspect the remote before proceeding.',
        unknown: `Remote status is unavailable: ${upstream.message || 'unknown error'}.`
      };
      detail.append(el('p', descriptions[upstream.state] || 'Remote status unavailable.'));
      action(actions, 'Inspect status', 'status');
      action(actions, 'Inspect branches', 'branches');
      if (upstream.state === 'different') {
        action(actions, 'Fetch origin before inspecting', 'fetch');
        action(actions, 'Prepare push after review', 'push');
      }
      if (upstream.state === 'matches') action(actions, 'Prepare push', 'push');
      if (upstream.state === 'not_configured' && update.branch) action(actions, 'Set origin upstream and push', 'push_upstream', {branch: update.branch});
    } else if (active === 3 || active === 4) {
      detail.append(el('p', pr.state === 'none' ? 'No same-repository PR was found for this branch. Fork-based PRs are not included.'
        : pr.state === 'unknown' ? `PR status unavailable: ${pr.message || 'unknown error'}.`
        : `PR #${pr.number}: ${pr.state.toUpperCase()}${pr.draft ? ' (DRAFT)' : ''} → ${pr.base}. ${pr.head_matches ? 'Reported PR head matches your commit.' : 'Reported PR head differs from your commit.'}`));
      if (pr.details_error) detail.append(el('p', `Review details unavailable: ${pr.details_error}`));
      if (pr.review_decision !== undefined) {
        const checks = pr.checks;
        detail.append(el('p', `Review decision: ${pr.review_decision || 'not reported'}. Checks: ${Array.isArray(checks) ? `${checks.length} reported; inspect their results on GitHub` : 'not reported'}.`));
        if (Array.isArray(checks) && checks.length) {
          const list = el('ul', undefined, 'journey-checks');
          for (const check of checks) {
            const name = check.name || check.context || 'Unnamed check';
            const result = check.conclusion || check.state || check.status || 'unknown';
            list.append(el('li', `${name}: ${result}`));
          }
          detail.append(list);
        }
      }
      if (pr.number) githubLink(actions, pr);
      if (active === 3 && ['none', 'closed', 'merged'].includes(pr.state) && update.branch)
        action(actions, 'Prepare new pull request', 'pr', {branch: update.branch});
      if (active === 4 && pr.state === 'open' && pr.head_matches && !pr.draft && !pr.details_error)
        action(actions, 'Prepare merge commit', 'pr_merge', {pr_number: String(pr.number)});
      detail.append(el('p', 'Review changes, approvals, and check results on GitHub. GitHub enforces repository rules and may block or queue a merge.'));
    } else {
      if (suggested === 5) {
        const title = el('h3', 'Update complete!', 'journey-celebration');
        detail.append(title, el('p', 'GitHub reports this pull request merged with your current commit. This does not verify deployment.'));
        const receipt = el('ul', undefined, 'journey-receipt');
        for (const line of [`Branch: ${update.branch}`, `Commit: ${update.head}`, `Destination: ${pr.repository} / ${pr.base}`,
          `PR: #${pr.number}`, `Merged: ${pr.merged_at}`, `Merge commit: ${pr.merge_commit}`]) receipt.append(el('li', line));
        detail.append(receipt);
        githubLink(actions, pr);
        detail.append(el('p', 'Start the next update: fetch origin, then create a new branch from the verified base. The existing branches are not deleted.'));
        action(actions, 'Fetch origin', 'fetch');
        action(actions, 'Create next branch', 'new_branch');
      } else {
        detail.append(el('p', 'The arrival receipt appears only after GitHub reports a merged PR for the current commit and the working tree is clean. Refresh after completing the merge.'));
      }
    }
    detail.append(actions);
  }
  async function get(url) {
    const response = await fetch(url);
    let data;
    try { data = await response.json(); }
    catch { throw new Error(`Unexpected server response (HTTP ${response.status}). Restart MasterChief and sign in as an RBAC admin.`); }
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    return data;
  }
  async function refresh() {
    if (loading) return;
    loading = true;
    $('journey-refresh').disabled = true;
    $('journey-status').textContent = 'Checking the local repository, upstream, and GitHub...';
    try {
      [update, status] = await Promise.all([get('/sys/api/scm/update-check'), get('/sys/api/scm/status')]);
      const choice = decide(update, status);
      active = suggested = choice.stage;
      $('journey-branch').textContent = `${update.branch || 'Detached HEAD'} · ${update.head.slice(0, 12)}`;
      $('journey-status').textContent = `Next focus: ${stages[suggested]}. ${choice.reason}`;
      render();
    } catch (error) {
      update = status = null;
      $('journey-branch').textContent = 'Journey unavailable';
      $('journey-map').replaceChildren(); $('journey-detail').replaceChildren();
      $('journey-status').textContent = `Unable to verify the journey: ${error.message}`;
    } finally { loading = false; $('journey-refresh').disabled = false; }
  }
  $('journey-toggle').addEventListener('click', () => {
    const panel = $('journey-panel');
    panel.hidden = !panel.hidden;
    $('journey-toggle').setAttribute('aria-expanded', String(!panel.hidden));
    $('journey-toggle').textContent = panel.hidden ? 'Open Release Journey' : 'Close Release Journey';
    if (!panel.hidden) refresh();
  });
  $('journey-refresh').addEventListener('click', refresh);
  document.addEventListener('scm-command-completed', () => { if (!$('journey-panel').hidden) refresh(); });
})(typeof window !== 'undefined' ? window : globalThis);

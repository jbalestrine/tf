(() => {
  const button = document.getElementById('update-check-button');
  const result = document.getElementById('update-check-result');
  if (!button || !result) return;
  button.addEventListener('click', async () => {
    button.disabled = true;
    result.textContent = 'Checking local changes, remote branch, and GitHub pull request...';
    try {
      const response = await fetch('/sys/api/scm/update-check');
      let data;
      try { data = await response.json(); }
      catch { throw new Error(`Unexpected server response (HTTP ${response.status}). Restart MasterChief and sign in as an RBAC admin.`); }
      if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
      result.replaceChildren();
      const heading = document.createElement('h3');
      heading.textContent = 'Update check';
      const list = document.createElement('ul');
      const add = text => { const li = document.createElement('li'); li.textContent = text; list.appendChild(li); return li; };
      add(`Branch: ${data.branch || 'detached HEAD'} · commit ${data.head.slice(0, 12)}`);
      add(data.worktree === 'clean' ? 'Working tree: clean; no uncommitted changes (ignored files are not checked).'
        : 'Working tree: uncommitted changes exist, including staged or untracked files. Review status.');
      const upstream = data.upstream;
      if (upstream.state === 'matches') add(`Push: HEAD matches ${upstream.remote}/${upstream.ref.replace(/^refs\/heads\//, '')} on the remote.`);
      else if (upstream.state === 'different') add(`Push: HEAD differs from ${upstream.remote}/${upstream.ref.replace(/^refs\/heads\//, '')} on the remote. Inspect divergence before pushing or pulling.`);
      else if (upstream.state === 'missing') add('Push: the configured remote branch no longer exists.');
      else add(`Push: ${upstream.message || 'Unable to verify upstream.'}`);
      const pr = data.pull_request;
      if (pr.state === 'none') add(`Pull request: no PR found in ${pr.repository} with a head branch from that same repository. Fork-based PRs are not included.`);
      else if (pr.state === 'unknown') add(`Pull request: unable to verify. ${pr.message || ''}`);
      else {
        const li = add(`Latest created same-repository PR for this branch in ${pr.repository}: #${pr.number} is ${pr.state.toUpperCase()}, targeting ${pr.base}. ${pr.head_matches ? 'Its reported head matches your commit.' : 'Its reported head differs from your current commit; this does not confirm that your current commit was merged.'} `);
        try {
          const url = new URL(pr.url);
          if (url.protocol !== 'https:' || url.hostname !== 'github.com') throw new Error('Unexpected URL');
          const link = document.createElement('a');
          link.href = url.href; link.target = '_blank'; link.rel = 'noopener noreferrer'; link.textContent = 'View PR';
          li.appendChild(link);
        } catch { li.append('PR link unavailable: unexpected URL.'); }
      }
      result.append(heading, list);
    } catch (error) {
      result.textContent = `Unable to check update: ${error.message}`;
    } finally { button.disabled = false; }
  });
})();

(() => {
  const container = document.getElementById('pull-request-overview');
  if (!container) return;
  container.innerHTML = `
    <section class="panel" aria-labelledby="pr-overview-title">
      <h2 id="pr-overview-title">Pull requests</h2>
      <p>All pull requests for the GitHub repository resolved from this local repository, newest GitHub update first. Updates include activity outside the app; this is not an app action history. Review checks and approvals on GitHub before merging.</p>
      <div class="pr-controls"><button type="button" id="pr-refresh">Refresh pull requests</button>
        <button type="button" id="pr-previous" disabled>Previous</button><button type="button" id="pr-next" disabled>Next</button></div>
      <p id="pr-status" role="status" aria-live="polite">Loading pull requests...</p>
      <div id="pr-list"></div>
    </section>`;
  const $ = id => document.getElementById(id);
  let page = 1, loading = false;
  async function load(requestedPage) {
    if (loading) return;
    loading = true;
    $('pr-refresh').disabled = $('pr-previous').disabled = $('pr-next').disabled = true;
    $('pr-status').textContent = 'Loading pull requests from GitHub...';
    try {
      const response = await fetch(`/sys/api/scm/pull-requests?page=${requestedPage}`);
      let data;
      try { data = await response.json(); }
      catch { throw new Error(`Unexpected server response (HTTP ${response.status}). Restart MasterChief and sign in as an RBAC admin.`); }
      if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
      page = data.page;
      const list = $('pr-list');
      list.replaceChildren();
      $('pr-status').textContent = data.pull_requests.length
        ? `Page ${page} · ${data.pull_requests.length} pull request(s), sorted by latest GitHub update.`
        : `Page ${page} · No pull requests found.`;
      for (const pr of data.pull_requests) {
        const card = document.createElement('article');
        card.className = 'pr-card';
        const heading = document.createElement('h3');
        heading.textContent = `#${pr.number} · ${pr.title}`;
        const info = document.createElement('p');
        const date = new Date(pr.updated_at);
        const updated = Number.isNaN(date.getTime()) ? pr.updated_at : date.toLocaleString();
        info.textContent = `${pr.state.toUpperCase()}${pr.draft ? ' · DRAFT' : ''} · ${pr.repository} · ${pr.head} → ${pr.base} · ${pr.author} · Updated ${updated}`;
        const link = document.createElement('a');
        try {
          const url = new URL(pr.url);
          if (url.protocol !== 'https:' || url.hostname !== 'github.com') throw new Error('Unexpected PR URL');
          link.href = url.href;
          link.target = '_blank';
          link.rel = 'noopener noreferrer';
          link.textContent = 'Review on GitHub';
          card.append(heading, info, link);
        } catch {
          card.append(heading, info);
          const error = document.createElement('p');
          error.textContent = 'Cannot display the GitHub link: unexpected URL.';
          card.append(error);
        }
        if (pr.state === 'open' && !pr.draft) {
          const merge = document.createElement('button');
          merge.type = 'button';
          merge.textContent = `Select PR #${pr.number} to merge`;
          merge.addEventListener('click', () => document.dispatchEvent(
            new CustomEvent('scm-select-pr-merge', {detail: {number: pr.number}})));
          card.append(merge);
        }
        list.append(card);
      }
      $('pr-previous').disabled = page <= 1;
      $('pr-next').disabled = !data.has_next || page >= 10000;
    } catch (error) {
      $('pr-list').replaceChildren();
      $('pr-status').textContent = `Unable to load pull requests: ${error.message}`;
      $('pr-previous').disabled = page <= 1;
    } finally {
      loading = false;
      $('pr-refresh').disabled = false;
    }
  }
  $('pr-refresh').addEventListener('click', () => load(1));
  $('pr-previous').addEventListener('click', () => load(page - 1));
  $('pr-next').addEventListener('click', () => load(page + 1));
  document.addEventListener('scm-pr-changed', () => load(1));
  load(1);
})();

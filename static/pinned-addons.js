(() => {
  const nav = document.querySelector('nav[aria-label="Main navigation"]');
  if (!nav) return;

  async function request(url, options) {
    const response = await fetch(url, options);
    let data;
    try {
      data = await response.json();
    } catch {
      throw new Error(`Unexpected server response (HTTP ${response.status}).`);
    }
    if (!response.ok || data.error) {
      throw new Error(data.error || `Request failed (HTTP ${response.status}).`);
    }
    return data;
  }

  for (const row of nav.querySelectorAll('.pinned-addon')) {
    const button = row.querySelector('.pinned-addon-start');
    const status = row.querySelector('.pinned-addon-status');
    const base = `/addons/modules/${encodeURIComponent(row.dataset.addonName)}`;
    button.addEventListener('click', async () => {
      button.disabled = true;
      status.textContent = 'Checking status...';
      try {
        const current = await request(`${base}/status`);
        if (current.status === 'running' || current.status === 'blueprint') {
          status.textContent = 'Already running. Use the link to open it.';
          return;
        }
        if (current.status !== 'stopped') {
          throw new Error(`Unexpected service status: ${current.status}`);
        }
        status.textContent = 'Starting...';
        const result = await request(`${base}/start`, {method: 'POST'});
        if (result.status === 'starting') {
          status.textContent = 'Starting. It may take a few seconds to be ready.';
        } else if (result.status === 'running' || result.status === 'blueprint') {
          status.textContent = 'Running. Use the link to open it.';
        } else if (result.status === 'html') {
          status.textContent = 'Static add-on is available. Use the link to open it.';
        } else {
          throw new Error(`Unexpected start response: ${result.status}`);
        }
      } catch (error) {
        status.textContent = `Could not start: ${error.message}`;
      } finally {
        button.disabled = false;
      }
    });
  }
})();

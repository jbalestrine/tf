((root) => {
  const key = 'masterchief.git.receipts.v1';
  function read() {
    const records = JSON.parse(root.sessionStorage.getItem(key) || '[]');
    if (!Array.isArray(records)) throw new Error('Invalid receipt storage.');
    return records;
  }
  function record(receipt) {
    const records = read();
    records.unshift(receipt);
    root.sessionStorage.setItem(key, JSON.stringify(records.slice(0, 30)));
  }
  function render(container) {
    container.replaceChildren();
    const title = document.createElement('h3');
    title.textContent = 'Command receipts (this browser tab)';
    const note = document.createElement('p');
    note.textContent = 'Only confirmed commands run from this command panel are recorded here. This is not a complete audit log or GitHub activity history. Branch is observed immediately before the command. Receipts are lost when this tab closes.';
    container.append(title, note);
    try {
      const records = read();
      if (!records.length) { container.append('No command receipts in this tab yet.'); return; }
      const list = document.createElement('ol');
      for (const entry of records) {
        const row = document.createElement('li');
        row.textContent = `${entry.time} · ${entry.action} · ${entry.result} · MasterChief local repository · branch before action: ${entry.branch || 'unavailable or detached'}`;
        if (entry.prUrl) {
          try {
            const url = new URL(entry.prUrl);
            if (url.protocol === 'https:' && url.hostname === 'github.com') {
              const link = document.createElement('a');
              link.href = url.href; link.target = '_blank'; link.rel = 'noopener noreferrer'; link.textContent = ' · Open PR';
              row.append(link);
            }
          } catch { row.append(' · PR link unavailable'); }
        }
        list.append(row);
      }
      container.append(list);
    } catch (error) {
      const warning = document.createElement('p');
      warning.textContent = `Receipts unavailable: ${error.message}`;
      container.append(warning);
    }
  }
  root.gitActionReceipts = {record, render};
})(window);

(() => {
  'use strict';
  const page = document.getElementById('visualPage');
  const status = document.getElementById('visualStatus');
  let dirty = false;
  const message = value => { status.textContent = value; };
  function canReplace() {
    return !dirty || window.confirm('Replace the current visual document? Download it first if you need to keep your changes.');
  }
  page.addEventListener('input', () => { dirty = true; });
  page.addEventListener('paste', event => {
    event.preventDefault();
    document.execCommand('insertText', false, event.clipboardData.getData('text/plain'));
    dirty = true;
  });
  page.addEventListener('drop', event => {
    event.preventDefault();
    message('Use Import DOCX / PDF to open a file; paste inserts plain text.');
  });
  window.addEventListener('beforeunload', event => {
    if (dirty) { event.preventDefault(); event.returnValue = ''; }
  });
  document.querySelectorAll('#visualFormatting button').forEach(button => {
    button.addEventListener('mousedown', event => event.preventDefault());
    button.addEventListener('click', () => {
      page.focus();
      document.execCommand(button.dataset.command, false, button.dataset.value || null);
      dirty = true;
    });
  });
  document.getElementById('visualNew').addEventListener('click', () => {
    if (!canReplace()) return;
    page.replaceChildren();
    const paragraph = document.createElement('p');
    paragraph.append(document.createElement('br'));
    page.append(paragraph);
    dirty = false;
    page.focus();
    message('Blank document ready. Add your content and download a copy.');
  });
  async function importFile(file, confirmed = false) {
    if (!file || (!confirmed && !canReplace())) return;
    const form = new FormData();
    form.append('file', file, file.name);
    message('Importing a copy...');
    try {
      const response = await fetch('/api/visual-resume/import', {method: 'POST', body: form});
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || 'Import failed.');
      page.innerHTML = result.html;
      dirty = true;
      message(result.warning);
    } catch (error) {
      message(`Import failed: ${error.message}`);
    }
  }
  document.getElementById('visualImport').addEventListener('change', async event => {
    await importFile(event.target.files[0]);
    event.target.value = '';
  });
  window.openVisualArtifact = async filename => {
    if (!canReplace()) return;
    try {
      const response = await fetch(`/api/download/${encodeURIComponent(filename)}`);
      if (!response.ok) throw new Error('Could not read the generated file.');
      const blob = await response.blob();
      const tab = document.querySelector('.tab[onclick*="visualTab"]');
      switchTab('visualTab', tab);
      await importFile(new File([blob], filename, {type: blob.type}), true);
    } catch (error) {
      message(`Import failed: ${error.message}`);
    }
  };
  async function exportFile(format) {
    message(`Preparing ${format.toUpperCase()}...`);
    try {
      const response = await fetch(`/api/visual-resume/export/${format}`, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({html: page.innerHTML})
      });
      if (!response.ok) {
        const result = await response.json();
        throw new Error(result.detail || 'Export failed.');
      }
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement('a');
      link.href = url; link.download = `resume-edited.${format}`; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      message(`${format.toUpperCase()} download started. Check the file before closing this editor.`);
    } catch (error) {
      message(`Export failed: ${error.message}`);
    }
  }
  document.getElementById('visualDocx').addEventListener('click', () => exportFile('docx'));
  document.getElementById('visualPdf').addEventListener('click', () => exportFile('pdf'));
})();

(() => {
  'use strict';

  const pendingKey = 'masterchief.pendingArchetype';

  function installLauncher() {
    if (document.getElementById('mc-archetype-launcher')) return;
    const button = document.createElement('a');
    button.id = 'mc-archetype-launcher';
    button.href = `/archetypes?return=${encodeURIComponent(location.pathname)}`;
    button.textContent = '🧭 Architecture + Code';
    button.title = 'Design an architecture, preview its diagram and generated code, and export SVG or Visio';
    button.style.cssText = [
      'position:fixed', 'right:18px', 'bottom:18px', 'z-index:9999',
      'padding:10px 14px', 'border-radius:22px', 'background:#245037',
      'border:1px solid #72c98c', 'color:#f0fff4', 'font:600 14px/1.2 Segoe UI,Arial,sans-serif',
      'text-decoration:none', 'box-shadow:0 4px 16px rgba(0,0,0,.35)'
    ].join(';');
    document.body.append(button);
  }

  function locateEditor() {
    const knownSelector = '#code-editor, #editor, #codeEditor, textarea[data-code-editor]';
    const textarea = document.querySelector(knownSelector);
    if (textarea instanceof HTMLTextAreaElement || textarea instanceof HTMLInputElement) {
      return {
        value: textarea.value,
        set(code) {
          textarea.value = code;
          textarea.dispatchEvent(new Event('input', {bubbles: true}));
          textarea.dispatchEvent(new Event('change', {bubbles: true}));
          textarea.focus();
        }
      };
    }
    if (window.monaco?.editor?.getEditors) {
      const editor = window.monaco.editor.getEditors().find(candidate => candidate.getDomNode()?.offsetParent);
      if (editor) {
        return {
          value: editor.getValue(),
          set(code) {
            editor.setValue(code);
            editor.focus();
          }
        };
      }
    }
    const preview = document.querySelector('#preview-code');
    if (preview) {
      return {
        value: preview.textContent || '',
        set(code) {
          preview.textContent = code;
        }
      };
    }
    return null;
  }

  function loadIntoPage(archetype) {
    if (!archetype || typeof archetype.code !== 'string') return;
    const editor = locateEditor();
    if (!editor) {
      if (location.pathname !== '/masterchief_code_ui') {
        localStorage.setItem(pendingKey, JSON.stringify(archetype));
        location.href = '/masterchief_code_ui';
      } else {
        window.alert('No code editor was found on this page.');
      }
      return;
    }
    if (editor.value.trim() && !window.confirm(`Replace the current editor contents with “${archetype.title}”?`)) {
      return;
    }
    editor.set(archetype.code);
    localStorage.removeItem(pendingKey);
    window.alert(`Loaded “${archetype.title}” into this page. Review it before running or saving.`);
  }

  function consumePending() {
    const raw = localStorage.getItem(pendingKey);
    if (!raw) return;
    let archetype;
    try {
      archetype = JSON.parse(raw);
    } catch (error) {
      localStorage.removeItem(pendingKey);
      console.error('Invalid pending code archetype:', error);
      return;
    }
    loadIntoPage(archetype);
  }

  function initialize() {
    installLauncher();
    consumePending();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize, {once: true});
  } else {
    initialize();
  }
})();

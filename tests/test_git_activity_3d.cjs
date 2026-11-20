const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

test('3D ecosystem preserves changed and related files and describes both import directions', () => {
  class Element {
    constructor() { this.children = []; this.handlers = {}; this.value = ''; this.disabled = false; this.textContent = ''; }
    addEventListener(name, fn) { this.handlers[name] = fn; }
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this.children = children; this.textContent = ''; }
    add(option) { this.children.push(option); }
    setAttribute(name, value) { this[name] = value; }
  }
  class Option { constructor(text, value) { this.textContent = text; this.value = value; } }
  const elements = Object.fromEntries(['ecosystem-canvas', 'ecosystem-file', 'ecosystem-detail', 'ecosystem-reset'].map(id => [id, new Element()]));
  const canvas = elements['ecosystem-canvas'];
  canvas.clientWidth = 600; canvas.clientHeight = 400;
  canvas.getContext = () => ({
    setTransform() {}, beginPath() {}, moveTo() {}, lineTo() {}, stroke() {}, arc() {}, fill() {}, fillText() {}
  });
  const opened = [];
  const window = { devicePixelRatio: 1, addEventListener() {}, GitActivityEditor: { open: name => opened.push(name) } };
  const document = { getElementById: id => elements[id], createElement: () => new Element() };
  const context = { window, document, Option };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '..', 'static', 'git-file-editor-link.js'), 'utf8'), context);
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '..', 'static', 'git-activity-3d.js'), 'utf8'), context);
  const data = {
    files: [{ path: 'a.py' }, { path: 'note.txt' }],
    edges: [{ from: 'a.py', to: 'b.py' }, { from: 'c.py', to: 'a.py' }]
  };
  window.GitActivity3D.load(data);
  const selector = elements['ecosystem-file'];
  assert.deepEqual(selector.children.map(option => option.value), ['', 'a.py', 'b.py', 'c.py', 'note.txt']);
  selector.value = 'a.py';
  selector.handlers.change();
  assert.equal(opened[0], 'a.py');
  assert.equal(elements['ecosystem-detail'].children[2].href, '/masterchief_code_ui?open=a.py');
  const list = elements['ecosystem-detail'].children[3];
  assert.deepEqual(list.children.map(item => item.textContent), ['Imports: b.py', 'Imported by: c.py']);
  window.GitActivity3D.load(data);
  assert.equal(selector.value, 'a.py');
  elements['ecosystem-reset'].handlers.click();
  assert.equal(selector.value, '');
  window.GitActivity3D.load({ files: [], edges: [] });
  assert.equal(selector.disabled, true);
  assert.equal(elements['ecosystem-detail'].textContent, 'No files to display.');
  assert.equal(window.gitFileEditorLink('dir/a #?.py').href, '/masterchief_code_ui?open=dir%2Fa%20%23%3F.py');
});

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const script = fs.readFileSync(path.join(__dirname, '..', 'static', 'workspace-drawer.js'), 'utf8');

function setup(items, saved = {}, blocked = false) {
  class Element {
    constructor(tag) {
      this.tag = tag;
      this.children = [];
      this.listeners = {};
      this.attributes = {};
      this.value = '';
      this.textContent = '';
      this.classList = {add() {}, remove() {}};
    }
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this.children = children; }
    setAttribute(name, value) { this.attributes[name] = value; }
    addEventListener(name, callback) { this.listeners[name] = callback; }
    querySelectorAll() { return []; }
    focus() {}
  }
  const grid = new Element('div');
  const continuation = new Element('div');
  const document = {
    body: new Element('body'),
    createElement: tag => new Element(tag),
    getElementById: id => ({'mc-start-grid': grid, 'mc-continue': continuation}[id] || null),
  };
  const localStorage = {
    getItem: key => { if (blocked) throw new Error('blocked'); return saved[key] || null; },
    setItem: (key, value) => { if (blocked) throw new Error('blocked'); saved[key] = value; },
  };
  const fetch = async () => ({ok: true, json: async () => ({ok: true, items})});
  vm.runInNewContext(script, {
    document, localStorage, fetch, location: {pathname: '/', search: '', hash: ''},
    setTimeout, clearTimeout, requestAnimationFrame() {}, cancelAnimationFrame() {},
  });
  return {grid, continuation, saved, document};
}

const item = (title, url, group = 'Develop', disabled = false) =>
  ({title, url, group, description: title, extra: false, disabled});
const flush = () => new Promise(resolve => setImmediate(resolve));

test('home uses only catalog destinations and labels disabled features', async () => {
  const ui = setup([
    item('Code UI', '/masterchief_code_ui'),
    item('Scripts', '/scripts', 'Automate & AI', true),
  ]);
  await flush();
  assert.deepEqual(ui.grid.children.map(node => node.href), ['/masterchief_code_ui', '/scripts']);
  assert.match(ui.grid.children[1].children[1].textContent, /Feature disabled/);
});

test('recent destinations are canonical, ordered, and clearable', async () => {
  const key = 'masterchief.workspace.recent.v1';
  const ui = setup([item('Code UI', '/masterchief_code_ui')], {
    [key]: JSON.stringify(['/not-in-catalog', '/masterchief_code_ui']),
  });
  await flush();
  assert.equal(ui.continuation.children[1].children.length, 1);
  assert.equal(ui.continuation.children[1].children[0].href, '/masterchief_code_ui');
  ui.grid.children[0].listeners.click();
  assert.equal(ui.saved[key], '["/masterchief_code_ui"]');
  ui.continuation.children[2].listeners.click();
  assert.equal(ui.saved[key], '[]');
  assert.equal(ui.continuation.children.length, 0);
});

test('storage failures are reported without blocking starting points', async () => {
  const ui = setup([item('Code UI', '/masterchief_code_ui')], {}, true);
  await flush();
  assert.equal(ui.grid.children.length, 1);
  assert.match(ui.continuation.children[0].textContent, /storage is unavailable/);
});

test('links with query parameters are never recorded or favorited', async () => {
  const ui = setup([item('Parameterized tool', '/tool?secret=value')]);
  await flush();
  const panel = ui.document.body.children[1].children[0];
  const list = panel.children[4];
  const row = list.children[0].children[1];
  assert.equal(row.children[1].disabled, true);
  row.children[0].listeners.click();
  assert.equal(ui.saved['masterchief.workspace.recent.v1'], undefined);
});

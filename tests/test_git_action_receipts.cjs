const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function setup(blocked = false) {
  const saved = {};
  const window = {sessionStorage: {
    getItem: key => { if (blocked) throw new Error('blocked'); return saved[key] || null; },
    setItem: (key, value) => { if (blocked) throw new Error('blocked'); saved[key] = value; },
  }};
  class Element {
    constructor() { this.children = []; this.textContent = ''; }
    append(...children) { this.children.push(...children); }
    replaceChildren() { this.children = []; }
  }
  const document = {createElement: () => new Element()};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '..', 'static', 'git-action-receipts.js'), 'utf8'),
    {window, document, URL});
  return {api: window.gitActionReceipts, container: new Element()};
}
test('receipts remain capped and display verified GitHub links', () => {
  const {api, container} = setup();
  for (let i = 0; i < 32; i++) api.record({time: 'now', action: `action ${i}`, result: 'completed', branch: 'feature', prUrl: 'https://github.com/o/r/pull/2'});
  api.render(container);
  const list = container.children[2];
  assert.equal(list.children.length, 30);
  assert.match(list.children[0].textContent, /action 31/);
  assert.equal(list.children[0].children[0].href, 'https://github.com/o/r/pull/2');
});
test('storage failure is surfaced and invalid links are not rendered', () => {
  const blocked = setup(true);
  blocked.api.render(blocked.container);
  assert.match(blocked.container.children[2].textContent, /Receipts unavailable/);
  assert.throws(() => blocked.api.record({}), /blocked/);
  const ui = setup();
  ui.api.record({time: 'now', action: 'merge', result: 'unconfirmed', prUrl: 'https://example.com/'});
  ui.api.render(ui.container);
  assert.equal(ui.container.children[2].children[0].children.length, 0);
});

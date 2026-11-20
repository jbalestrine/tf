const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const script = fs.readFileSync(path.join(root, 'static', 'pinned-addons.js'), 'utf8');

function setup(responses) {
  const calls = [];
  let click;
  const button = {disabled: false, addEventListener: (_, fn) => { click = fn; }};
  const status = {textContent: ''};
  const row = {
    dataset: {addonName: 'Resume & Studio'},
    querySelector: selector => selector === '.pinned-addon-start' ? button : status,
  };
  const nav = {querySelectorAll: () => [row]};
  const document = {querySelector: () => nav};
  const fetch = async (url, options) => {
    calls.push({url, options});
    const response = responses.shift();
    if (response instanceof Error) throw response;
    return response;
  };
  vm.runInNewContext(script, {document, fetch, encodeURIComponent});
  return {click, button, status, calls};
}

const response = (data, status = 200) => ({ok: status >= 200 && status < 300, status, json: async () => data});

test('starts a stopped addon without navigating away', async () => {
  const ui = setup([response({status: 'stopped'}), response({status: 'starting'})]);
  await ui.click();
  assert.equal(ui.calls.length, 2);
  assert.equal(ui.calls[0].url, '/addons/modules/Resume%20%26%20Studio/status');
  assert.equal(ui.calls[1].url, '/addons/modules/Resume%20%26%20Studio/start');
  assert.equal(ui.calls[1].options.method, 'POST');
  assert.match(ui.status.textContent, /may take a few seconds/);
  assert.equal(ui.button.disabled, false);
});

test('does not start an already running service or blueprint', async () => {
  for (const status of ['running', 'blueprint']) {
    const ui = setup([response({status})]);
    await ui.click();
    assert.equal(ui.calls.length, 1);
    assert.match(ui.status.textContent, /Already running/);
  }
});

test('reports failures and restores the start button', async () => {
  for (const failure of [response({error: 'No entry point'}, 400), new Error('Network failed')]) {
    const ui = setup([response({status: 'stopped'}), failure]);
    await ui.click();
    assert.match(ui.status.textContent, /Could not start:/);
    assert.equal(ui.button.disabled, false);
  }
});

test('recognizes static add-ons and rejects unexpected service status', async () => {
  const staticUi = setup([response({status: 'stopped'}), response({status: 'html'})]);
  await staticUi.click();
  assert.match(staticUi.status.textContent, /Static add-on/);
  const unknown = setup([response({status: 'unknown'})]);
  await unknown.click();
  assert.equal(unknown.calls.length, 1);
  assert.match(unknown.status.textContent, /Unexpected service status/);
});

test('both main menu templates include separate links and start controls', () => {
  for (const file of ['templates/layout.html', 'templates/base.py']) {
    const template = fs.readFileSync(path.join(root, file), 'utf8');
    assert.match(template, /data-addon-name="{{ _mod_name }}"/);
    assert.match(template, /class="pinned-addon-start"/);
    assert.match(template, /href="{{ _mod.url }}"/);
    assert.match(template, /src="\/static\/pinned-addons\.js"/);
  }
});

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, 'index.html'), 'utf8');
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(match => match[1]);

async function openWrapper(pathname, hostname, response) {
  const elements = new Map();
  const classes = new Set();
  const calls = [];
  let destination;
  const document = {
    documentElement: {classList: {add: value => classes.add(value)}},
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, {hidden: false, textContent: '', addEventListener() {}});
      return elements.get(id);
    },
  };
  const location = {pathname, hostname, replace: value => { destination = value; }};
  const context = vm.createContext({
    document, location, fetch: async url => { calls.push(url); return response; },
  });
  vm.runInContext(scripts[0], context);
  vm.runInContext(scripts.at(-1), context);
  await new Promise(resolve => setImmediate(resolve));
  return {context, elements, classes, calls, destination};
}

function statusResponse(payload) {
  return {ok: true, headers: {get: () => 'application/json'}, json: async () => payload};
}

test('static and proxy entry points redirect to the running local service', async () => {
  for (const suffix of ['web/index.html', 'app/']) {
    const result = await openWrapper(`/addons/modules/MasterChief_Resume_Studio_UI/${suffix}`, 'localhost',
      statusResponse({status: 'running', port: 9100}));
    assert.ok(result.classes.has('installed-addon'));
    assert.equal(result.destination, 'http://127.0.0.1:9100/');
    assert.deepEqual(result.calls, ['/addons/modules/MasterChief_Resume_Studio_UI/status']);
  }
});

test('stopped service blocks the dashboard and offers retry', async () => {
  const result = await openWrapper('/addons/modules/Studio/web/index.html', 'localhost',
    statusResponse({status: 'stopped', port: null}));
  assert.ok(result.classes.has('installed-addon'));
  assert.equal(result.destination, undefined);
  assert.match(result.elements.get('addonRedirectMessage').textContent, /Start Resume Studio/);
  assert.equal(result.elements.get('addonRetry').hidden, false);
  assert.match(html, /\.installed-addon body > :not\(#addonRedirect\) \{ display: none !important; \}/);
});

test('HTML status responses and nonlocal access produce useful errors', async () => {
  const htmlResponse = {ok: true, headers: {get: () => 'text/html'}};
  const result = await openWrapper('/addons/modules/Studio/web/index.html', 'localhost', htmlResponse);
  assert.match(result.elements.get('addonRedirectMessage').textContent, /check the add-on service/);
  assert.equal(result.elements.get('addonRetry').hidden, false);
  const remote = await openWrapper('/addons/modules/Studio/web/index.html', 'example.com', htmlResponse);
  assert.match(remote.elements.get('addonRedirectMessage').textContent, /host machine only/);
  assert.equal(remote.calls.length, 0);
});

const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function setup({enabled = true, reject = false} = {}) {
  const handlers = {};
  const elements = {};
  for (const id of ['screen', 'status', 'connect', 'disconnect', 'start', 'viewer', 'fullscreen', 'source', 'switch', 'source-status']) {
    elements[id] = {
      textContent: '', disabled: false, attributes: {}, handlers: {},
      setAttribute(name, value) { this.attributes[name] = value; },
      addEventListener(name, callback) { this.handlers[name] = callback; },
      click() { return this.handlers.click(); },
    };
  }
  const document = {
    fullscreenEnabled: enabled,
    fullscreenElement: null,
    getElementById(id) { return elements[id.replace('mc-ubuntu-', '')]; },
    addEventListener(name, callback) { handlers[name] = callback; },
    async exitFullscreen() { this.fullscreenElement = null; handlers.fullscreenchange(); },
  };
  elements.viewer.requestFullscreen = async () => {
    if (reject) throw new Error('Permission denied');
    document.fullscreenElement = elements.viewer;
    handlers.fullscreenchange();
  };
  const clients = [];
  class RFB {
    constructor(screen, url) { this.screen = screen; this.url = url; clients.push(this); }
    addEventListener() {}
  }
  const source = fs.readFileSync(path.join(__dirname, '..', 'static-src', 'ubuntu-desktop.js'), 'utf8')
    .replace("import RFB from '@novnc/novnc';", '');
  vm.runInNewContext(source, {
    document, RFB, location: {protocol: 'http:', host: 'localhost'},
    fetch: async () => ({ok: true, json: async () => ({ok: true, state: 'poweroff'})}),
  });
  return {document, elements, clients, handlers};
}

test('full screen enters, exits, and reflects Escape', async () => {
  const {document, elements, handlers} = setup();
  await elements.fullscreen.click();
  assert.equal(document.fullscreenElement, elements.viewer);
  assert.equal(elements.fullscreen.textContent, 'Exit full screen');
  assert.equal(elements.fullscreen.attributes['aria-pressed'], 'true');
  await elements.fullscreen.click();
  assert.equal(document.fullscreenElement, null);
  assert.equal(elements.fullscreen.textContent, 'Full screen');
  await elements.fullscreen.click();
  document.fullscreenElement = null;
  handlers.fullscreenchange();
  assert.equal(elements.fullscreen.attributes['aria-pressed'], 'false');
});

test('unavailable and denied full screen are explicit', async () => {
  assert.equal(setup({enabled: false}).elements.fullscreen.disabled, true);
  const {elements} = setup({reject: true});
  await elements.fullscreen.click();
  assert.match(elements.status.textContent, /Unable to change full screen: Permission denied/);
});

test('desktop requests a resizable guest display', () => {
  const {elements, clients} = setup();
  elements.connect.click();
  assert.equal(clients[0].scaleViewport, true);
  assert.equal(clients[0].resizeSession, true);
});

test('dashboard includes the named full screen viewer and controls', () => {
  const template = fs.readFileSync(path.join(__dirname, '..', 'templates', 'pages.py'), 'utf8');
  assert.match(template, /UBUNTU MASTERCHIEF OS/);
  assert.match(template, /id="mc-ubuntu-viewer"[\s\S]*id="mc-ubuntu-fullscreen"[\s\S]*id="mc-ubuntu-screen"/);
  const css = fs.readFileSync(path.join(__dirname, '..', 'static', 'ubuntu-desktop.css'), 'utf8');
  assert.match(css, /#mc-ubuntu-viewer:fullscreen #mc-ubuntu-screen\{flex:1/);
});

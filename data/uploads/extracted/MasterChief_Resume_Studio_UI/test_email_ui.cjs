const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, 'index.html'), 'utf8');
const start = html.indexOf('    async function jsonRequest(');
const end = html.indexOf('    let emailAuto=', start);
assert.ok(start >= 0 && end > start);
const code = html.slice(start, end);

function requestWith(response) {
  const context = vm.createContext({fetch: async () => response});
  vm.runInContext(code, context);
  return context.jsonRequest('/api/example', 'POST', {});
}

test('validation errors describe fields without exposing submitted values', async () => {
  const response = {ok: false, status: 422, json: async () => ({
    detail: [{loc: ['body', 'company'], msg: 'String should have at least 1 character', input: 'private'}]
  })};
  await assert.rejects(requestWith(response), error =>
    error.message === 'company: String should have at least 1 character');
});

test('reports server errors and invalid responses', async () => {
  await assert.rejects(requestWith({ok: false, status: 400, json: async () => ({detail: 'Attachment is unavailable'})}),
    /Attachment is unavailable/);
  await assert.rejects(requestWith({ok: false, status: 500, json: async () => { throw new SyntaxError(); }}),
    /invalid response \(HTTP 500\)/);
});

test('identifies a reply body validation error', async () => {
  await assert.rejects(requestWith({ok: false, status: 422, json: async () => ({
    detail: [{loc: ['body', 'body'], msg: 'String should have at least 1 character'}]
  })}), /body: String should have at least 1 character/);
});

test('keeps generated and manual reply actions distinct', () => {
  assert.match(html, /Send Generated Recruiting Reply/);
  assert.match(html, /Review & Send Manual Reply/);
  assert.match(html, /Company and role are not required/);
});

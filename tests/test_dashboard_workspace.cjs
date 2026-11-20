const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {nextStep} = require('../static/dashboard-workspace.js');

test('system readings appear before the workspace guidance on the dashboard', () => {
  const template = fs.readFileSync(path.join(__dirname, '..', 'templates', 'pages.py'), 'utf8');
  const dashboard = template.slice(template.indexOf('DASHBOARD_TEMPLATE ='), template.indexOf('# Scripts templates'));
  const grid = dashboard.indexOf('<div class="dashboard-grid">');
  const start = dashboard.indexOf('<section class="mc-start"');
  assert.ok(grid >= 0 && start > grid);
  const readings = dashboard.slice(grid, start);
  for (const id of ['cpu-value', 'cpu-progress', 'mem-value', 'mem-progress', 'disk-value', 'disk-progress']) {
    assert.ok(readings.includes(`id="${id}"`), `${id} must be visible before the workspace guidance`);
  }
  assert.match(readings, /System Uptime/);
  assert.ok(dashboard.indexOf('mc-process-title') > grid);
  assert.match(readings, /id="mc-process-details"/);
  assert.match(readings, /id="mc-process-end"/);
  assert.match(readings, /dashboard-processes\.js/);
});

function state() {
  return {branch: 'feature', worktree: 'clean', upstream: {state: 'matches'}, pull_request: {state: 'none'}};
}
test('local edits and uncertain upstream never imply readiness to merge', () => {
  const update = state();
  update.worktree = 'changes';
  assert.match(nextStep(update), /uncommitted/);
  update.worktree = 'clean';
  update.upstream.state = 'different';
  assert.match(nextStep(update), /cannot determine/);
  update.upstream.state = 'unknown';
  assert.match(nextStep(update), /attention/);
});
test('pull request guidance requires matching heads and verified merge', () => {
  const update = state();
  update.pull_request = {state: 'open', number: 7, head_matches: false, draft: false};
  assert.match(nextStep(update), /different head/);
  update.pull_request.head_matches = true;
  assert.match(nextStep(update), /approvals/);
  update.pull_request = {state: 'merged', number: 7, head_matches: true};
  assert.doesNotMatch(nextStep(update), /verified merged commit/);
  Object.assign(update.pull_request, {merged_head_matches: true, merged_at: 'date', merge_commit: 'abc'});
  assert.match(nextStep(update), /verified merged commit/);
});

const {test} = require('node:test');
const assert = require('node:assert/strict');
const {decide} = require('../static/release-journey.js');

function state() {
  return {
    update: {branch: 'feature', worktree: 'clean', upstream: {state: 'matches'},
      pull_request: {state: 'none'}},
    status: {branch: 'feature', staged: [], unstaged: []}
  };
}
test('journey finds next actionable stage without treating uncommitted changes as complete', () => {
  const {update, status} = state();
  update.worktree = 'changes';
  status.unstaged.push({file: 'new'});
  assert.equal(decide(update, status).stage, 0);
  status.unstaged = [];
  status.staged.push({file: 'new'});
  assert.equal(decide(update, status).stage, 1);
});
test('journey handles no upstream, unknown PR and open PR safely', () => {
  const {update, status} = state();
  update.upstream.state = 'not_configured';
  assert.equal(decide(update, status).stage, 2);
  update.upstream.state = 'matches';
  update.pull_request = {state: 'unknown'};
  assert.equal(decide(update, status).stage, 3);
  update.pull_request = {state: 'open', head_matches: true, draft: true};
  assert.equal(decide(update, status).stage, 3);
  update.pull_request.draft = false;
  assert.equal(decide(update, status).stage, 4);
});
test('arrival needs matching verified merged commit and clean worktree', () => {
  const {update, status} = state();
  update.pull_request = {state: 'merged', head_matches: true, merged_head_matches: true,
    merged_at: '2026-01-01', merge_commit: 'abc'};
  assert.equal(decide(update, status).stage, 5);
  update.pull_request.merged_head_matches = false;
  assert.equal(decide(update, status).stage, 3);
  update.pull_request.merged_head_matches = true;
  update.worktree = 'changes';
  status.unstaged.push({file: 'new'});
  assert.equal(decide(update, status).stage, 0);
});
test('inconsistent snapshots do not claim completion', () => {
  const {update, status} = state();
  status.branch = 'other';
  assert.match(decide(update, status).reason, /changed during the check/);
});

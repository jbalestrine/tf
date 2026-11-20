const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const root = path.resolve(__dirname, '..');
for (const [file, current] of [
  ['templates/scm.py', '/sys/scm'],
  ['features/templates/github_integration.html', '/github'],
]) {
  test(`${file} links both Source Control workspaces and marks the current page`, () => {
    const text = fs.readFileSync(path.join(root, file), 'utf8');
    assert.match(text, /href="\/static\/source-control-navigation\.css"/);
    assert.match(text, /aria-label="Source Control workspaces"/);
    assert.match(text, /href="\/sys\/scm"/);
    assert.match(text, /href="\/github"/);
    assert.ok(text.includes(`href="${current}" aria-current="page"`));
    assert.match(text, /does not change the Git Command Center repository/);
    assert.match(text, /href="\/static\/git-workflow-guide\.html"/);
    assert.match(text, /<strong>File Ecosystem<\/strong>/);
  });
}

test('workflow guide exposes the preview and full editable file', () => {
  const text = fs.readFileSync(path.join(root, 'static', 'git-workflow-guide.html'), 'utf8');
  for (const name of ['git-workflow-everyday.png', 'git-workflow-guide.vsdx']) {
    assert.ok(text.includes(`/static/${name}`));
    assert.ok(fs.statSync(path.join(root, 'static', name)).size > 0);
  }
  assert.match(text, /Safety and branches/);
  assert.match(text, /Recovery and caveats/);
  assert.match(text, /Command reference/);
  assert.match(text, /id="activity-groups"/);
  assert.match(text, /id="activity-graph"/);
  assert.match(text, /id="ecosystem-canvas"/);
  assert.match(text, /id="ecosystem-file"/);
  assert.match(text, /src="\/static\/git-activity-3d\.js"/);
  assert.match(text, /src="\/static\/git-file-editor-link\.js"/);
  assert.match(text, /id="update-check-button"/);
  assert.match(text, /id="update-check-result"/);
  assert.match(text, /src="\/static\/git-update-check\.js"/);
});

test('both Git pages expose the executable everyday update steps and caveats', () => {
  for (const file of ['templates/scm.py', 'static/git-workflow-guide.html']) {
    const text = fs.readFileSync(path.join(root, file), 'utf8');
    assert.match(text, /id="update-and-push"/);
    for (const action of ['status', 'stage_all', 'stage', 'staged_diff', 'commit', 'push', 'push_upstream']) {
      assert.ok(text.includes(`data-guide-command="${action}"`), `${file} missing ${action}`);
    }
    for (const command of ['git add -A', 'git status', 'git diff --staged', 'git commit -m', 'git push']) {
      assert.ok(text.includes(command), `${file} missing ${command}`);
    }
    assert.match(text, /deletions/);
    assert.match(text, /private data|credentials/);
  }
});

test('quick guided workflow is shared by both Git pages and exposes each action', () => {
  for (const file of ['templates/scm.py', 'static/git-workflow-guide.html']) {
    const text = fs.readFileSync(path.join(root, file), 'utf8');
    assert.match(text, /id="quick-workflow"/);
    assert.ok(text.indexOf('git-quick-workflow.js') < text.indexOf('git-command-center.js'));
  }
  const guide = fs.readFileSync(path.join(root, 'static/git-quick-workflow.js'), 'utf8');
  for (const action of ['stage_all', 'status', 'staged_diff', 'commit', 'push', 'push_upstream',
    'pr_view', 'pr', 'pr_merge', 'fetch', 'new_branch', 'branches', 'switch_branch']) {
    assert.ok(guide.includes(`data-guide-command="${action}"`), `missing ${action}`);
  }
  assert.match(guide, /does not delete your local or remote branches/);
  assert.match(guide, /Nothing runs when you open this guide/);
});

test('both Git pages include the shared pull request overview', () => {
  for (const file of ['templates/scm.py', 'static/git-workflow-guide.html']) {
    const text = fs.readFileSync(path.join(root, file), 'utf8');
    assert.match(text, /id="pull-request-overview"/);
    assert.match(text, /src="\/static\/git-pull-requests\.js"/);
  }
});

test('development navigation links directly to the file ecosystem', () => {
  for (const file of ['templates/base.py', 'templates/layout.html', 'templates/master_menu.html',
    'templates/scm.py', 'features/templates/github_integration.html', 'templates/diagnostics.py',
    'templates/source_map.html', 'app_features/code_manager/templates/index.html', 'web_ide.html']) {
    const text = fs.readFileSync(path.join(root, file), 'utf8');
    assert.ok(text.includes('/static/git-workflow-guide.html#activity-status'), `${file} missing ecosystem link`);
  }
});

test('main navigation exposes ecosystem without opening a dropdown', () => {
  for (const file of ['templates/base.py', 'templates/layout.html']) {
    const text = fs.readFileSync(path.join(root, file), 'utf8');
    const nav = text.indexOf('aria-label="Main navigation"');
    const ecosystem = text.indexOf('href="/static/git-workflow-guide.html#activity-status"', nav);
    const dropdown = text.indexOf('<details class="nav-group', nav);
    assert.ok(nav >= 0 && ecosystem > nav && ecosystem < dropdown, file);
  }
});

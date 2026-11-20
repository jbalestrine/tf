const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const script = fs.readFileSync(path.join(root, 'static', 'js', 'management-navigation.js'), 'utf8');
const layout = fs.readFileSync(path.join(root, 'templates', 'layout.html'), 'utf8');
const navigationCss = fs.readFileSync(path.join(root, 'static', 'css', 'management-navigation.css'), 'utf8');
const pages = [
  ['master-menu', 'templates/master_menu.html', '/master-menu'],
  ['features', 'features/templates/feature_manager.html', '/features'],
  ['modules', 'templates/modules.html', '/modules'],
  ['addons', 'templates/pages.py', '/addons/modules'],
  ['code', 'app_features/code_manager/templates/index.html', '/ext/code_manager/']
];

test('main navigation styling is scoped away from the management navigation', () => {
  assert.match(layout, /<nav class="main-navigation" aria-label="Main navigation">/);
  assert.match(layout, /nav:where\(\.main-navigation\)\{position:sticky/);
  assert.match(layout, /@media\(max-width:720px\)\{nav:where\(\.main-navigation\)/);
  assert.doesNotMatch(layout, /(?:^|[},])\s*nav(?!:where\(\.main-navigation\))(?:\s*[>{,:]|\s+a\b)/m);
});

test('management navigation overrides legacy global navigation layout', () => {
  assert.match(navigationCss, /\.management-navigation\s*\{[^}]*display:\s*block;[^}]*position:\s*static;/s);
  assert.match(navigationCss, /grid-template-columns:\s*repeat\(auto-fit,\s*minmax\(180px,\s*1fr\)\)/);
});

function element(tag) {
  return {
    tag, children: [], attributes: {},
    append(...children) { this.children.push(...children); },
    replaceChildren(...children) { this.children = children; },
    setAttribute(name, value) { this.attributes[name] = value; }
  };
}

for (const [current, file, url] of pages) {
  test(`${current} includes navigation and highlights the current page`, () => {
    const markup = fs.readFileSync(path.join(root, file), 'utf8');
    assert.ok(markup.includes(`data-management-page="${current}"`));
    assert.ok(markup.includes('/static/js/management-navigation.js'));
    assert.ok(markup.includes('/static/css/management-navigation.css'));
    const nav = element('nav');
    nav.dataset = {managementPage: current};
    const document = {querySelector: () => nav, createElement: element};
    vm.runInNewContext(script, {document});
    const list = nav.children[2];
    assert.equal(list.children.length, 5);
    const links = list.children.map(item => item.children[0]);
    assert.equal(links.filter(link => link.attributes['aria-current'] === 'page').length, 1);
    assert.equal(links.find(link => link.attributes['aria-current'] === 'page').href, url);
    assert.ok(list.children.every(item => item.children[1].textContent));
  });
}

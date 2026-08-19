import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const sourceRoot = new URL('../dspace-angular/source/', import.meta.url);
const componentPath = new URL('src/themes/custom/app/search-page/search-page.component.ts', sourceRoot);
const templatePath = new URL('src/themes/custom/app/search-page/search-page.component.html', sourceRoot);
const stylePath = new URL('src/themes/custom/app/search-page/search-page.component.scss', sourceRoot);

const [component, template, styles] = await Promise.all([
  readFile(componentPath, 'utf8'),
  readFile(templatePath, 'utf8'),
  readFile(stylePath, 'utf8'),
]);

test('PCIRN search page enables its scoped visual stylesheet', () => {
  assert.match(component, /^\s*styleUrls:\s*\[['"]\.\/search-page\.component\.scss['"]\]/m);
  assert.match(component, /^\s*templateUrl:\s*['"]\.\/search-page\.component\.html['"]/m);
  assert.match(template, /class="pcirn-search-page"/);
  assert.doesNotMatch(component, /header|navbar/i);
  assert.doesNotMatch(template, /header|navbar/i);
});

test('PCIRN search stylesheet exposes the approved visual/icon contract', () => {
  for (const hook of [
    ':host ::ng-deep',
    '#search-form',
    '#search-sidebar',
    '#search-content',
    '.search-button',
    '.scope-button',
    '.fa-search',
    '.fa-filter',
    '.fa-list',
    '.fa-th-large',
    '.fa-file-export',
    '.fa-rss-square',
    '.fa-file-alt',
    '@media (max-width:',
  ]) {
    assert.match(styles, new RegExp(hook.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  }
  assert.doesNotMatch(styles, /header|navbar/i);
});

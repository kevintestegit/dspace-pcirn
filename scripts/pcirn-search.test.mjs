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
    '.row-with-sidebar > :not(#search-page-sidebar-content) > .row > .col-12:has(#search-form)',
    'padding-inline: clamp(1rem, 4vw, 3.75rem)',
    'ds-object-grid',
    '.card-element',
    'height: 33rem',
    '.card-body',
    'flex-direction: column',
    '.card-title',
    '.card-text',
    '.card-body > ds-truncatable',
    '-webkit-line-clamp: 2',
    '-webkit-line-clamp: 3',
    '.text-center:last-child',
    '.pagination-masked.top ds-rss',
    'float: none !important',
    'align-items: center',
    'width: min(12rem, 100%)',
    'min-height: 2.4rem',
    'width: 2.5rem',
    'height: 2.5rem',
    '@media (max-width:',
  ]) {
    assert.match(styles, new RegExp(hook.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  }
  assert.doesNotMatch(styles, /header|navbar/i);
});

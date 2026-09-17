import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const sourceRoot = new URL('../dspace-angular/source/', import.meta.url);
const componentPath = new URL('src/themes/custom/app/search-page/search-page.component.ts', sourceRoot);
const templatePath = new URL('src/themes/custom/app/search-page/search-page.component.html', sourceRoot);
const stylePath = new URL('src/themes/custom/styles/_pcirn-search.scss', sourceRoot);
const globalStylePath = new URL('src/themes/custom/styles/_global-styles.scss', sourceRoot);
const typographyPath = new URL('src/themes/custom/styles/_pcirn-typography.scss', sourceRoot);
const comcolTemplatePath = new URL('src/app/shared/comcol/sections/comcol-search-section/comcol-search-section.component.html', sourceRoot);
const mydspaceComponentPath = new URL('src/themes/custom/app/my-dspace-page/my-dspace-page.component.ts', sourceRoot);
const mydspaceTemplatePath = new URL('src/themes/custom/app/my-dspace-page/my-dspace-page.component.html', sourceRoot);
const workflowStylePath = new URL('src/themes/custom/styles/_pcirn-workflow.scss', sourceRoot);
const taskSummaryComponentPath = new URL('src/themes/custom/app/my-dspace-page/workflow-task-summary/pcirn-workflow-task-summary.component.ts', sourceRoot);
const taskSummaryTemplatePath = new URL('src/themes/custom/app/my-dspace-page/workflow-task-summary/pcirn-workflow-task-summary.component.html', sourceRoot);
const discoveryConfigurationPath = new URL('../dspace/config/spring/api/discovery.xml', import.meta.url);

const [component, template, styles, globalStyles, typography, comcolTemplate, mydspaceComponent, mydspaceTemplate,
  workflowStyles, taskSummaryComponent, taskSummaryTemplate, discoveryConfiguration] = await Promise.all([
  readFile(componentPath, 'utf8'),
  readFile(templatePath, 'utf8'),
  readFile(stylePath, 'utf8'),
  readFile(globalStylePath, 'utf8'),
  readFile(typographyPath, 'utf8'),
  readFile(comcolTemplatePath, 'utf8'),
  readFile(mydspaceComponentPath, 'utf8'),
  readFile(mydspaceTemplatePath, 'utf8'),
  readFile(workflowStylePath, 'utf8'),
  readFile(taskSummaryComponentPath, 'utf8'),
  readFile(taskSummaryTemplatePath, 'utf8'),
  readFile(discoveryConfigurationPath, 'utf8'),
]);

test('PCIRN search page enables its scoped visual stylesheet', () => {
  assert.match(component, /^\s*styleUrls:\s*\[['"]\.\/search-page\.component\.scss['"]\]/m);
  assert.match(component, /^\s*templateUrl:\s*['"]\.\/search-page\.component\.html['"]/m);
  assert.match(template, /class="pcirn-search-page"/);
  assert.match(template, /\[showRSS\]="false"/);
  assert.doesNotMatch(component, /header|navbar/i);
  assert.doesNotMatch(template, /header|navbar/i);
});

test('PCIRN search styles load globally for every search container', () => {
  assert.match(globalStyles, /@import '\.\/_pcirn-search\.scss';/);
  assert.match(styles, /^\.pcirn-search-page\s*\{/m);
});

test('PCIRN type scale drives page title and search headings', () => {
  assert.match(globalStyles, /@import '\.\/_pcirn-typography\.scss';/);
  for (const token of [
    '--pcirn-fs-page-title: 1.5rem',
    '--pcirn-fs-section: 1.25rem',
    '--pcirn-fs-label: 1.05rem',
    '--pcirn-fs-card-title: 1rem',
    '--pcirn-fs-meta: .85rem',
  ]) {
    assert.match(typography, new RegExp(token.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  }
  assert.match(typography, /ds-comcol-page-header h1/);
  assert.match(typography, /ds-comcol-page-handle/);
  assert.match(styles, /font-size: var\(--pcirn-fs-section\)/);
  assert.match(styles, /font-size: var\(--pcirn-fs-card-title\)/);
});

test('community and collection search reuse the PCIRN search shell', () => {
  assert.match(comcolTemplate, /class="pcirn-search-page"/);
  assert.match(comcolTemplate, /\[showRSS\]="false"/);
});

test('my dspace reuses the PCIRN search shell', () => {
  assert.match(mydspaceComponent, /templateUrl:\s*'\.\/my-dspace-page\.component\.html'/);
  assert.match(mydspaceTemplate, /class="pcirn-search-page pcirn-mydspace-page"/);
  assert.match(mydspaceTemplate, /\[configurationList\]="\(configurationList\$ \| async\)"/);
  assert.match(mydspaceTemplate, /\[showRSS\]="false"/);
});

test('the OpenSearch distribution feed is hidden everywhere', () => {
  assert.match(globalStyles, /ds-rss \{\s*display: none !important;\s*\}/);
});

test('PCIRN review task cards stay compact on MyDSpace', () => {
  assert.match(globalStyles, /@import '\.\/_pcirn-workflow\.scss';/);
  assert.match(workflowStyles, /^\.pcirn-mydspace-page\s*\{/m);
  assert.match(workflowStyles, /ds-thumbnail\s*\{[^}]*max-width: 4\.25rem/);
  assert.match(workflowStyles, /thumbnail-content\.outer::before\s*\{[^}]*padding-top: 100%/);
  assert.match(workflowStyles, /\.row > \[class\*='offset-'\]\s*\{[^}]*margin-left: 0/);
  assert.match(workflowStyles, /ds-claimed-task-actions-loader,[\s\S]*?ds-pool-task-actions-loader\s*\{[^}]*display: contents/);
  assert.match(workflowStyles, /ds-item-list-preview \.row > \.col-md-2/);
  assert.match(workflowStyles, /ds-item-list-preview \.row > \.col-3/);
  assert.match(workflowStyles, /font-size: var\(--pcirn-fs-card-title\)/);
  assert.match(workflowStyles, /font-size: var\(--pcirn-fs-meta\)/);
});

test('PCIRN sidebar chrome follows the system type scale', () => {
  assert.match(styles, /\.sidebar-content \.search-switch-configuration h3/);
  assert.match(styles, /\.sidebar-content ds-themed-search-filters h3/);
  assert.match(styles, /\.sidebar-content ds-themed-search-settings h3/);
  assert.match(styles, /ds-search-settings h4,[\s\S]*?font-size: \.9rem/);
  assert.match(styles, /ds-search-filters \.btn \{[\s\S]*?font-size: \.85rem/);
});

test('PCIRN list/detail switch is minimal and pinned to the right', () => {
  assert.match(styles, /ds-view-mode-switch \{[\s\S]*?\.btn \{[\s\S]*?width: 2rem/);
  assert.match(styles, /ds-view-mode-switch \{[\s\S]*?\.btn \{[\s\S]*?min-height: 1\.7rem/);
  assert.match(styles, /ds-view-mode-switch \{[\s\S]*?\.btn \{[\s\S]*?background: transparent/);
  const switchBlock = styles.match(/#search-page-sidebar-content ds-view-mode-switch \{[^}]*\}/)[0];
  assert.match(switchBlock, /position: absolute/);
  assert.match(switchBlock, /right: 0/);
});

test('MyDSpace announces pending workflow tasks to the reviewer', () => {
  assert.match(mydspaceTemplate, /<ds-pcirn-workflow-task-summary><\/ds-pcirn-workflow-task-summary>/);
  assert.match(mydspaceComponent, /PcirnWorkflowTaskSummaryComponent/);
  assert.match(taskSummaryComponent, /searchBy\('findByUser'/);
  assert.match(taskSummaryComponent, /ClaimedTaskDataService/);
  assert.match(taskSummaryComponent, /PoolTaskDataService/);
  assert.match(taskSummaryTemplate, /pcirn\.mydspace\.tasks\.title/);
  assert.match(taskSummaryTemplate, /pcirn\.mydspace\.tasks\.action/);
  assert.match(taskSummaryTemplate, /configuration: 'workflow'/);
});

test('list card thumbnail placeholder renders a real icon glyph', () => {
  assert.match(styles, /content: '\\f15b';/);
  assert.match(styles, /font-family: 'Font Awesome 6 Free';/);
  assert.doesNotMatch(styles, /content: '\\\\f15b';/);
});

test('PCIRN search sidebar hides type, has-files and access-status facets', () => {
  const sidebarFacets = discoveryConfiguration.match(/<property name="sidebarFacets">[\s\S]*?<\/property>/)[0];
  for (const filter of ['searchFilterAuthor', 'searchFilterSubject', 'searchFilterIssued']) {
    assert.match(sidebarFacets, new RegExp(`<ref bean="${filter}"`));
  }
  for (const filter of ['searchFilterType', 'searchFilterContentInOriginalBundle', 'searchFilterAccessStatus']) {
    assert.doesNotMatch(sidebarFacets, new RegExp(`<ref bean="${filter}"`));
  }
  const authorFilter = discoveryConfiguration.match(/<bean id="searchFilterAuthor"[\s\S]*?<\/bean>/)[0];
  assert.match(authorFilter, /<property name="isOpenByDefault" value="false"\/>/);
});

test('PCIRN search stylesheet exposes the approved visual/icon contract', () => {
  for (const hook of [
    '.pcirn-search-page',
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
    'top: 5.35rem',
    'min-height: 1.7rem',
    'width: 2.5rem',
    'height: 2.5rem',
    'padding: .5rem',
    'gap: .5rem',
    'min-height: 3rem',
    'flex: 0 1 15rem',
    'margin-right: .4rem',
    'color: #fff',
    '@media (max-width:',
  ]) {
    assert.match(styles, new RegExp(hook.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  }
  assert.doesNotMatch(styles, /header|navbar/i);
});

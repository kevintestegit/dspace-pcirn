import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import assert from 'node:assert/strict';

const template = readFileSync(
  new URL('../dspace-angular/source/src/themes/custom/app/navbar/navbar.component.html', import.meta.url),
  'utf8',
);

test('PCIRN header navigation labels use translated keys', () => {
  for (const key of [
    'home.breadcrumbs',
    'communityList.breadcrumbs',
    'item.page.collections',
    'item.page.publications',
  ]) {
    assert.match(template, new RegExp(`\\{\\{\\s*'${key}'\\s*\\|\\s*translate\\s*\\}\\}`));
  }

  for (const label of ['Início', 'Comunidades', 'Coleção', 'Publicações']) {
    assert.doesNotMatch(template, new RegExp(`>\\s*${label}\\s*<`));
  }
});

test('PCIRN footer navigation labels use plural collections key', () => {
  const footerTemplate = readFileSync(
    new URL('../dspace-angular/source/src/app/footer/footer.component.html', import.meta.url),
    'utf8',
  );
  assert.match(footerTemplate, /routerLink="\/collection-list">\{\{\s*'item\.page\.collections'\s*\|\s*translate\s*\}\}/);
  assert.doesNotMatch(footerTemplate, /routerLink="\/collection-list">\{\{\s*'collection\.listelement\.badge'/);
});

test('search scope and breadcrumbs do not mention DSpace and use Publicações', async () => {
  const JSON5 = (await import('../dspace-angular/source/node_modules/json5/lib/index.js')).default;
  const pt = JSON5.parse(readFileSync(new URL('../dspace-angular/source/src/assets/i18n/pt-BR.json5', import.meta.url), 'utf8'));
  const en = JSON5.parse(readFileSync(new URL('../dspace-angular/source/src/assets/i18n/en.json5', import.meta.url), 'utf8'));

  assert.equal(pt['search.form.scope.all'], 'Todo o Acervo');
  assert.equal(pt['search.breadcrumbs'], 'Publicações');
  assert.equal(en['search.form.scope.all'], 'All of Repository');
  assert.equal(en['search.breadcrumbs'], 'Publications');
});


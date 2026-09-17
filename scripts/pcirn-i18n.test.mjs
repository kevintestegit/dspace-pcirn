import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import assert from 'node:assert/strict';
import JSON5 from '../dspace-angular/source/node_modules/json5/lib/index.js';

const initServiceUrl = new URL('../dspace-angular/source/src/app/init.service.ts', import.meta.url);
const ptBrUrl = new URL('../dspace-angular/source/src/assets/i18n/pt-BR.json5', import.meta.url);
const enUrl = new URL('../dspace-angular/source/src/assets/i18n/en.json5', import.meta.url);

test('InitService sets default fallback language in TranslateService', () => {
  const initServiceSrc = readFileSync(initServiceUrl, 'utf8');
  assert.match(initServiceSrc, /this\.translate\.setDefaultLang\(/);
});

test('all pcirn, user-menu and publicacoes keys in pt-BR.json5 exist in en.json5', () => {
  const pt = JSON5.parse(readFileSync(ptBrUrl, 'utf8'));
  const en = JSON5.parse(readFileSync(enUrl, 'utf8'));
  const missingInEn = Object.keys(pt).filter(
    (k) => (k.startsWith('pcirn.') || k.startsWith('user-menu.') || k.startsWith('publicacoes.')) && !en[k],
  );
  assert.deepEqual(missingInEn, []);
});

const homePageUrl = new URL(
  '../dspace-angular/source/src/themes/custom/app/home-page/home-page.component.html',
  import.meta.url,
);

test('home-page template does not have hardcoded Portuguese text', () => {
  const tpl = readFileSync(homePageUrl, 'utf8');
  for (const str of [
    'Pesquise no acervo',
    'Normas e Portarias',
    'POPs e Procedimentos',
    'Produção Científica',
    'Relatórios Técnicos',
    'Acesso rápido',
    'Coleções em destaque',
    'Últimas publicações',
    'Ver todas as publicações',
  ]) {
    assert.doesNotMatch(tpl, new RegExp(`>\\s*${str}\\s*<`));
  }
});

const footerUrl = new URL(
  '../dspace-angular/source/src/app/footer/footer.component.html',
  import.meta.url,
);

test('footer template uses translated keys and no hardcoded column titles', () => {
  const tpl = readFileSync(footerUrl, 'utf8');
  for (const str of [
    'Ciência que identifica. Informação que transforma.',
    'Navegação',
    'Ajuda e informações',
    'Plataforma',
    'Desenvolvido por',
    'Polícia Científica do Rio Grande do Norte. Todos os direitos reservados.',
  ]) {
    assert.doesNotMatch(tpl, new RegExp(`>\\s*${str}\\s*<`));
  }
});

const pcirnItemUrl = new URL(
  '../dspace-angular/source/src/themes/custom/app/item-page/pcirn-document-item/pcirn-document-item.component.html',
  import.meta.url,
);

test('pcirn-document-item template translates document types and removes hardcoded aria-labels', () => {
  const tpl = readFileSync(pcirnItemUrl, 'utf8');
  assert.doesNotMatch(tpl, /aria-label="Visualizador do documento"/);
  assert.doesNotMatch(tpl, /aria-label="Informações do documento"/);
  assert.match(tpl, /'pcirn\.item\.viewer\.aria'\s*\|\s*translate/);
  assert.match(tpl, /'pcirn\.item\.info\.aria'\s*\|\s*translate/);
  assert.match(tpl, /type\s*\|\s*dsPcirnDocumentType/);
});

test('home-page template translates dc.type with dsPcirnDocumentType', () => {
  const tpl = readFileSync(homePageUrl, 'utf8');
  assert.match(tpl, /item\.metadata\['dc\.type'\]\?\.\[0\]\?\.value\s*\|\s*dsPcirnDocumentType/);
});

const typeBadgeUrl = new URL(
  '../dspace-angular/source/src/themes/custom/app/shared/object-collection/shared/badges/type-badge/type-badge.component.html',
  import.meta.url,
);

test('type-badge template translates documentType with dsPcirnDocumentType', () => {
  const tpl = readFileSync(typeBadgeUrl, 'utf8');
  assert.match(tpl, /documentType\s*\|\s*dsPcirnDocumentType/);
});

const pipeSrcUrl = new URL(
  '../dspace-angular/source/src/app/shared/utils/pcirn-document-type.pipe.ts',
  import.meta.url,
);

test('PcirnDocumentTypePipe handles normalization and fallbacks', () => {
  const pipeSrc = readFileSync(pipeSrcUrl, 'utf8');
  assert.match(pipeSrc, /@Pipe\({\s*name:\s*'dsPcirnDocumentType'/);
  assert.match(pipeSrc, /transform\(value/);
});

test('document type translations exist for standard PCIRN types in pt-BR and en', () => {
  const pt = JSON5.parse(readFileSync(ptBrUrl, 'utf8'));
  const en = JSON5.parse(readFileSync(enUrl, 'utf8'));

  const testCases = [
    { key: 'pcirn.document-type.PORTARIA', pt: 'Portaria', en: 'Ordinance' },
    { key: 'pcirn.document-type.DECRETO', pt: 'Decreto', en: 'Decree' },
    { key: 'pcirn.document-type.LEI', pt: 'Lei', en: 'Law' },
    { key: 'pcirn.document-type.POP', pt: 'Procedimento Operacional Padrão (POP)', en: 'Standard Operating Procedure (SOP)' },
    { key: 'pcirn.document-type.NOTA_TECNICA', pt: 'Nota Técnica', en: 'Technical Note' },
    { key: 'pcirn.document-type.TEXTO', pt: 'Texto', en: 'Text' },
    { key: 'pcirn.document-type.DOCUMENTO', pt: 'Documento', en: 'Document' },
    { key: 'pcirn.document-type.DEFAULT', pt: 'Documento', en: 'Document' },
  ];

  for (const tc of testCases) {
    assert.equal(pt[tc.key], tc.pt, `Missing or mismatched pt-BR key: ${tc.key}`);
    assert.equal(en[tc.key], tc.en, `Missing or mismatched en key: ${tc.key}`);
  }
});




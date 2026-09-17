# Plano: rótulos amigáveis na full item page

Spec: `docs/superpowers/specs/2026-09-17-full-item-page-labels-design.md`
Execução: direta nesta sessão (sem tool de subagentes disponível — gates de review aplicados inline).

## Task 1 — Template full page (1 edit)

Arquivo: `dspace-angular/source/src/app/item-page/full/full-item-page.component.html` (~linha 27).

Trocar:

```html
<td>{{mdEntry.key}}</td>
```

por (dentro do `@for` existente, `@let` é escopado por iteração — padrão já usado em `cc-license/item-page-cc-license-field.component.html`):

```html
@let labelKey = 'metadata.' + mdEntry.key;
@let label = (labelKey | translate);
<td>{{ label === labelKey ? mdEntry.key : label }}</td>
```

Fallback por igualdade exata: ngx-translate default (e `TranslateLoaderMock` nos specs) devolve a própria chave quando falta tradução → mostra `dc.*` cru. Nunca vazio, nunca esconde.

## Task 2 — Entradas i18n (2 edits)

`dspace-angular/source/src/assets/i18n/en.json5` + `pt-BR.json5`, chaves flat `metadata.<campo>`:

author→Author/Autor, coverage.temporal→Temporal Coverage/Cobertura Temporal, date.accessioned→Date Accessioned/Data de Ingestão, date.issued→Issue Date/Data de Publicação, description.abstract→Abstract/Resumo, format.extent→Extent/Extensão, identifier.other→Other Identifier/Outro Identificador, identifier.uri→URI/URI, language→Language/Idioma, publisher→Publisher/Editor, rights→Rights/Direitos, source→Source/Fonte, subject→Subject/Assunto, title→Title/Título, type→Type/Tipo.

Outros idiomas: sem entrada → fallback cru, sem quebra.

## Task 3 — Verificação

- Parse json5 dos 2 i18n (node) — sem vírgula/chave quebrada.
- ESLint nos arquivos alterados, se disponível.
- Spec existente `full-item-page.component.spec.ts` ("should display the item's metadata") continua válido: mock usa `TranslateLoaderMock` (dicionário vazio) → fallback cru, valores inalterados. `ng test` exige Chrome; se indisponível, validação é parse + review de template.
- Deploy (fora do código, operador): rebuild imagem Angular + restart + hard-refresh; confere fix anterior das divs `d-none` no inspector e rótulos pt-BR na full page.

# F1 — Correções de bugs funcionais visíveis (design)

## Objetivo

Fechar os seis itens da frente F1 do parecer de 2026-09-23: regressões visíveis na home e na página do item, validador de e-mail que falha aberto, suíte Maven quebrada, tabelas de administração cortadas no mobile e classes Bootstrap 4 no admin de governança.

Nenhuma mudança de arquitetura, rota, permissão ou backend além do teste de e-mail.

## Contexto e evidência

| Item | Local | Problema |
| --- | --- | --- |
| A2 | `themes/custom/app/home-page/pcirn-home-data.service.ts:139-157` | `combineLatest` emite no primeiro estado pendente; `failed` é `undefined` e `communities.payload.totalElements` lança `TypeError` — a grade de métricas nunca renderiza |
| A5 | `themes/custom/app/item-page/simple/field-components/file-section/file-section.component.html:6,17-23` | perdeu o tamanho do arquivo e usa `$first` como "primário"; o teste `scripts/pcirn-item-document.test.mjs` proíbe `dsFileSize` (trava o bug) |
| A6 | `app/access-control/epeople-registry/eperson-form/validators/email-taken.validator.ts:28-32` | `hasSucceeded && payload ? {emailTaken} : null` + `catchError(() => of(null))` → 403/5xx/rede viram "e-mail livre". O banco tem `eperson_email_key` UNIQUE e o REST não trata duplicidade com mensagem amigável |
| A1 | `dspace-api/src/test/java/org/dspace/core/EmailTest.java:135` | asserta `&#8599;`, mas `PcirnEmailTemplateRenderer.java:132` gera `&#8594;` — nenhum código produz `&#8599;`; `mvn test` quebra |
| Tabelas admin | `themes/custom/styles/_pcirn-admin.scss:99-105` (+ `:365,379`) | `.table-responsive { overflow: hidden }` com `min-width: 38rem/34rem` no mobile corta colunas sem scroll |
| BS4/BS5 | `app/admin/admin-governance/admin-governance.component.html:5,47,63,67,76,78,86,88` | `mr-2`, `ml-2`, `badge-warning`, `badge-success` não existem no Bootstrap 5.3 usado pelo app |

## Decisões

- **A6 (escolha do usuário)**: falha de verificação vira erro distinto e bloqueante (`emailCheckFailed`), com mensagem "Não foi possível verificar o e-mail. Tente novamente." — não salva até verificar.
- **A1**: remover a asserção do caractere decorativo; manter as asserções semânticas (rótulo, `href` e contagem de URL). Não acoplar teste a ornamento.
- **A5**: `$first` continua definindo a hierarquia visual do botão "Ver" e da extensão; "primário" volta a ser `primaryBitstreamId === file.id`, com badge traduzido e tamanho para todos os arquivos.

## Arquitetura

Arquivos alterados:

1. `dspace-angular/source/src/themes/custom/app/home-page/pcirn-home-data.service.ts` — guarda de estado pendente/falho antes de montar o payload.
2. `dspace-angular/source/src/themes/custom/app/home-page/pcirn-home-data.service.spec.ts` — 2 casos novos.
3. `dspace-angular/source/src/themes/custom/app/item-page/simple/field-components/file-section/file-section.component.html` — primário real, badge e tamanho.
4. `dspace-angular/source/src/themes/custom/app/item-page/simple/field-components/file-section/file-section.component.ts` — importa `FileSizePipe`.
5. `dspace-angular/source/src/themes/custom/app/item-page/simple/field-components/file-section/file-section.component.scss` — estilo do tamanho.
6. `dspace-angular/source/src/app/access-control/epeople-registry/eperson-form/validators/email-taken.validator.ts` — `emailCheckFailed`.
7. `dspace-angular/source/src/app/access-control/epeople-registry/eperson-form/eperson-form.component.ts` — `errorMessages.emailCheckFailed`.
8. `dspace-angular/source/src/assets/i18n/en.json5` e `pt-BR.json5` — chave `error.validation.emailCheckFailed`.
9. `dspace-angular/source/src/app/access-control/epeople-registry/eperson-form/validators/email-taken.validator.spec.ts` — 4 casos.
10. `dspace-angular/source/scripts/pcirn-item-document.test.mjs` — passa a exigir tamanho e primário real.
11. `dspace-api/src/test/java/org/dspace/core/EmailTest.java` — asserção semântica.
12. `dspace-angular/source/src/themes/custom/styles/_pcirn-admin.scss` — `overflow-x: auto`.
13. `dspace-angular/source/src/app/admin/admin-governance/admin-governance.component.html` — classes BS5.

## Comportamento por item

**A2** — no `map` das métricas: se algum estado falhou, devolver esse estado (comportamento atual); se algum não tem `hasSucceeded` ou `payload`, devolver o primeiro estado incompleto. O template (`home-page.component.html:60`) já só renderiza com `hasSucceeded && payload`, então a grade fica oculta até os três responderem, sem erro de runtime.

**A5** — cada arquivo mostra `({{ file?.sizeBytes | dsFileSize }})`; o arquivo cujo `id === primaryBitstreamId` recebe `pcirn-document-file-primary` e o badge `item.page.bitstreams.primary`. Quando não há primário definido, nenhum arquivo recebe o destaque, mas o botão "Ver" do primeiro continua com o estilo principal.

**A6** — `hasSucceeded && !payload` → `null` (livre); `hasSucceeded && payload` → `{ emailTaken: true }`; `!hasSucceeded` ou erro de stream → `{ emailCheckFailed: true }`. O formulário exibe a chave nova e bloqueia o salvamento.

**A1** — a asserção vira `containsString(">Abrir")`, mantendo `href="https://example.org/task"` e `countOccurrences(html, ">https://example.org/task</a>") == 1`.

**Tabelas admin** — `.table-responsive` passa a `overflow-x: auto`; os `min-width` permanecem e o conteúdo passa a rolar em vez de sumir.

**Governance** — `mr-2` → `me-2`, `ml-2` → `ms-2`, `badge-warning`/`badge-success` → `text-bg-warning`/`text-bg-success`.

## Verificação

1. `node --test dspace-angular/source/scripts/pcirn-*.test.mjs` (inclui o teste atualizado do file-section).
2. Karma focado: `pcirn-home-data.service.spec.ts`, `email-taken.validator.spec.ts` e `eperson-form.component.spec.ts`.
3. Maven: `EmailTest` em `dspace-api` (limpar `dspace-api/target/generated-sources`, artefato gerado com dono `root`, antes de rodar).
4. Validação viva: home (métricas), página de item (tamanho + badge de primário), formulário de e-person (e-mail duplicado e falha simulada), `/access-control/epeople` e `/admin/governance` em 390 px.

## Limites

Não entram nesta frente: reprodutibilidade/CI (F0), e-mail (F2), migrações (F3), governança (F4), design system (F5) e decisões de produto (F6). Sem commits: o working tree permanece como está até pedido explícito.

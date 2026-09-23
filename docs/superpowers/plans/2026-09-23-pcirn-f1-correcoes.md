# F1 — Correções de bugs funcionais visíveis — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fechar as seis correções da frente F1: métricas da home, seção de arquivos do item, validador de e-mail, teste de e-mail do Maven, tabelas admin no mobile e classes Bootstrap 4 no admin de governança.

**Architecture:** Mudanças localizadas em serviços/validadores/templates do tema custom e em um teste Java. Sem novas dependências, rotas ou abstrações.

**Tech Stack:** Angular 19 (standalone, RxJS), Jasmine/Karma, node:test, Maven (dspace-api), SCSS.

**Spec:** `docs/superpowers/specs/2026-09-23-pcirn-f1-correcoes-design.md`

> Neste ambiente, commits só acontecem se o usuário pedir explicitamente. Não há passos de commit neste plano.

---

### Task 1: A2 — guarda de estado nas métricas da home

**Files:**
- Modify: `dspace-angular/source/src/themes/custom/app/home-page/pcirn-home-data.service.ts:139-157`
- Test: `dspace-angular/source/src/themes/custom/app/home-page/pcirn-home-data.service.spec.ts`

- [ ] **Step 1: Escrever os testes que falham**

Adicionar ao `describe('PcirnHomeDataService', ...)`, depois do teste "keeps a featured-collection error isolated from latest publications":

```ts
  it('stays pending without payload until every source succeeds', done => {
    const emptyPage = buildPaginatedList(undefined, []);
    const service = new PcirnHomeDataService(
      { findTop: () => createPendingRemoteDataObject$() } as any,
      { findAll: () => createSuccessfulRemoteDataObject$(emptyPage) } as any,
      { search: () => createSuccessfulRemoteDataObject$(emptyPage) } as any,
    );

    service.metrics.subscribe(metrics => {
      expect(metrics.hasSucceeded).toBeFalse();
      expect(metrics.payload).toBeUndefined();
      done();
    });
  });

  it('passes the failure through when one source fails', done => {
    const emptyPage = buildPaginatedList(undefined, []);
    const service = new PcirnHomeDataService(
      { findTop: () => createFailedRemoteDataObject$('communities unavailable') } as any,
      { findAll: () => createSuccessfulRemoteDataObject$(emptyPage) } as any,
      { search: () => createSuccessfulRemoteDataObject$(emptyPage) } as any,
    );

    service.metrics.subscribe(metrics => {
      expect(metrics.hasFailed).toBeTrue();
      expect(metrics.payload).toBeUndefined();
      done();
    });
  });
```

Atualizar o import:

```ts
import {
  createFailedRemoteDataObject$,
  createPendingRemoteDataObject$,
  createSuccessfulRemoteDataObject$,
} from '../../../../app/shared/remote-data.utils';
```

- [ ] **Step 2: Rodar e ver o primeiro teste falhar**

Run (em `dspace-angular/source`):
`CHROME_BIN=/usr/bin/google-chrome npx ng test --source-map=true --watch=false --configuration test --include='src/themes/custom/app/home-page/pcirn-home-data.service.spec.ts'`
Expected: FAIL em "stays pending without payload until every source succeeds" (`TypeError` de `payload` indefinido vira erro do observable).

- [ ] **Step 3: Implementar a guarda**

Substituir o `map` de `buildMetrics` por:

```ts
      map(([communities, collections, items]) => {
        const states = [communities, collections, items] as RemoteData<unknown>[];
        const failed = states.find(data => data.hasFailed);
        if (failed) {
          return failed as unknown as RemoteData<PcirnHomeMetrics>;
        }
        if (!communities.hasSucceeded || !communities.payload ||
          !collections.hasSucceeded || !collections.payload ||
          !items.hasSucceeded || !items.payload) {
          const incomplete = states.find(data => !data.hasSucceeded || !data.payload);
          return incomplete as unknown as RemoteData<PcirnHomeMetrics>;
        }
        return new RemoteData(
          communities.timeCompleted,
          communities.msToLive,
          communities.lastUpdated,
          communities.state,
          undefined,
          {
            communities: communities.payload.totalElements,
            collections: collections.payload.totalElements,
            items: items.payload.totalElements,
          },
          communities.statusCode,
        );
      }),
```

- [ ] **Step 4: Rodar de novo**

Run: o mesmo comando do Step 2.
Expected: `TOTAL: 5 SUCCESS` (3 antigos + 2 novos).

---

### Task 2: A5 — tamanho e primário real na seção de arquivos

**Files:**
- Modify: `dspace-angular/source/src/themes/custom/app/item-page/simple/field-components/file-section/file-section.component.html`
- Modify: `dspace-angular/source/src/themes/custom/app/item-page/simple/field-components/file-section/file-section.component.ts`
- Modify: `dspace-angular/source/src/themes/custom/app/item-page/simple/field-components/file-section/file-section.component.scss`
- Test: `dspace-angular/source/scripts/pcirn-item-document.test.mjs`

- [ ] **Step 1: Atualizar o teste de contrato (falha primeiro)**

Em `scripts/pcirn-item-document.test.mjs`, no teste "file section opens documents in the browser viewer instead of forcing a download", trocar:

```js
  assert.doesNotMatch(fileSection, /dsFileSize|pcirn-document-download-size/);
```

por:

```js
  assert.match(fileSection, /dsFileSize/);
  assert.match(fileSection, /primaryBitstreamId/);
  assert.match(fileSection, /item\.page\.bitstreams\.primary/);
```

- [ ] **Step 2: Rodar e ver falhar**

Run (em `dspace-angular/source`): `node --test scripts/pcirn-item-document.test.mjs`
Expected: FAIL no teste do file section.

- [ ] **Step 3: Template**

No `@for` do template, trocar o bloco do arquivo por:

```html
      @for (file of bitstreams; track file; let first = $first) {
        <div class="pcirn-document-file" [class.pcirn-document-file-primary]="file.id === primaryBitstreamId">
          <ds-file-download-link
            [bitstream]="file"
            [item]="item"
            [showIcon]="false"
            [isBlank]="true"
            [cssClasses]="first ? 'pcirn-document-download' : 'pcirn-document-download pcirn-document-download-secondary'">
            <i class="fas fa-eye" aria-hidden="true"></i>
            <span class="pcirn-document-download-copy">
              <strong>
                {{ 'pcirn.item.view' | translate }}
                @if (first && fileExtension(file); as extension) {
                  ({{ extension }})
                }
              </strong>
            </span>
          </ds-file-download-link>
          <span class="pcirn-document-file-name">
            {{ dsoNameService.getName(file) }}
            <span class="pcirn-document-file-size">({{ file?.sizeBytes | dsFileSize }})</span>
            @if (file.id === primaryBitstreamId) {
              <span class="badge text-bg-primary ms-2">{{ 'item.page.bitstreams.primary' | translate }}</span>
            }
          </span>
        </div>
      }
```

- [ ] **Step 4: Importar o pipe**

Em `file-section.component.ts`, adicionar o import e registrá-lo:

```ts
import { FileSizePipe } from '../../../../../../../app/shared/utils/file-size-pipe';
```

```ts
  imports: [
    CommonModule,
    FileSizePipe,
    ThemedFileDownloadLinkComponent,
    ThemedLoadingComponent,
    TranslateModule,
    VarDirective,
  ],
```

- [ ] **Step 5: Estilo do tamanho**

Adicionar ao `file-section.component.scss`:

```scss
.pcirn-document-file-size {
  color: #5b7186;
  font-size: .78rem;
  font-weight: 400;
  margin-left: .25rem;
}
```

- [ ] **Step 6: Rodar de novo**

Run: `node --test scripts/pcirn-item-document.test.mjs`
Expected: PASS.

---

### Task 3: A6 — validador de e-mail não falha mais aberto

**Files:**
- Modify: `dspace-angular/source/src/app/access-control/epeople-registry/eperson-form/validators/email-taken.validator.ts:24-33`
- Modify: `dspace-angular/source/src/app/access-control/epeople-registry/eperson-form/eperson-form.component.ts:326-329`
- Modify: `dspace-angular/source/src/assets/i18n/en.json5:2086`
- Modify: `dspace-angular/source/src/assets/i18n/pt-BR.json5:3140`
- Test: `dspace-angular/source/src/app/access-control/epeople-registry/eperson-form/validators/email-taken.validator.spec.ts`

- [ ] **Step 1: Reescrever a spec**

Substituir os dois testes de `email-taken.validator.spec.ts` por quatro:

```ts
  it('returns no validation error when the email is free', async () => {
    const service = {
      getEPersonByEmail: () => of({ hasCompleted: true, hasSucceeded: true, payload: undefined } as RemoteData<EPerson>),
    } as unknown as EPersonDataService;
    const validator = ValidateEmailNotTaken.createValidator(service);

    const validationResult = validator(control) as Observable<ValidationErrors | null>;

    await expectAsync(firstValueFrom(validationResult)).toBeResolvedTo(null);
  });

  it('returns emailTaken when the email is taken', async () => {
    const service = {
      getEPersonByEmail: () => of({ hasCompleted: true, hasSucceeded: true, payload: { uuid: 'eperson-uuid' } } as RemoteData<EPerson>),
    } as unknown as EPersonDataService;
    const validator = ValidateEmailNotTaken.createValidator(service);

    const validationResult = validator(control) as Observable<ValidationErrors | null>;

    await expectAsync(firstValueFrom(validationResult)).toBeResolvedTo({ emailTaken: true });
  });

  it('returns emailCheckFailed when the email lookup fails', async () => {
    const service = {
      getEPersonByEmail: () => of({ hasCompleted: true, hasSucceeded: false } as RemoteData<EPerson>),
    } as unknown as EPersonDataService;
    const validator = ValidateEmailNotTaken.createValidator(service);

    const validationResult = validator(control) as Observable<ValidationErrors | null>;

    await expectAsync(firstValueFrom(validationResult)).toBeResolvedTo({ emailCheckFailed: true });
  });

  it('returns emailCheckFailed when the email lookup errors', async () => {
    const service = {
      getEPersonByEmail: () => throwError(() => new Error('lookup failed')),
    } as unknown as EPersonDataService;
    const validator = ValidateEmailNotTaken.createValidator(service);

    const validationResult = validator(control) as Observable<ValidationErrors | null>;

    await expectAsync(firstValueFrom(validationResult)).toBeResolvedTo({ emailCheckFailed: true });
  });
```

- [ ] **Step 2: Rodar e ver falhar**

Run (em `dspace-angular/source`):
`CHROME_BIN=/usr/bin/google-chrome npx ng test --source-map=true --watch=false --configuration test --include='src/app/access-control/epeople-registry/eperson-form/validators/email-taken.validator.spec.ts'`
Expected: FAIL nos dois testes de falha (retornam `null`).

- [ ] **Step 3: Implementar o validador**

```ts
          map(res => {
            if (!res.hasSucceeded) {
              return { emailCheckFailed: true };
            }
            return res.payload ? { emailTaken: true } : null;
          }),
          catchError(() => of({ emailCheckFailed: true })),
```

- [ ] **Step 4: Mensagem no formulário e i18n**

Em `eperson-form.component.ts`, no `errorMessages` do campo `email`:

```ts
      errorMessages: {
        emailTaken: 'error.validation.emailTaken',
        emailCheckFailed: 'error.validation.emailCheckFailed',
        email: 'error.validation.NotValidEmail',
      },
```

Em `en.json5`, depois de `"error.validation.emailTaken"`:

```json5
"error.validation.emailCheckFailed": "Unable to verify this email. Please try again",
```

Em `pt-BR.json5`, depois de `"error.validation.emailTaken"`:

```json5
"error.validation.emailCheckFailed": "Não foi possível verificar este e-mail. Tente novamente",
```

- [ ] **Step 5: Rodar de novo**

Run: o mesmo comando do Step 2.
Expected: `TOTAL: 4 SUCCESS`.

---

### Task 4: A1 — alinhar o EmailTest com o renderer

**Files:**
- Modify: `dspace-api/src/test/java/org/dspace/core/EmailTest.java:135`

- [ ] **Step 1: Trocar a asserção decorativa pela semântica**

```java
        assertThat(html, containsString(">Abrir"));
```

As asserções de `href` e de contagem de URL logo abaixo permanecem.

- [ ] **Step 2: Limpar artefato gerado com dono root**

```bash
docker run --rm -v /dados/apps/dspace:/app alpine sh -c "rm -rf /app/dspace-api/target/generated-sources"
```

(É saída gerada de build; sem isso o `javac` do usuário não consegue sobrescrever os arquivos.)

- [ ] **Step 3: Rodar o teste**

```bash
mkdir -p "$HOME/.cache/dspace-maven-repo"
docker run --rm -u "$(id -u):$(id -g)" -e HOME=/tmp -e MAVEN_OPTS="-Duser.home=/tmp" \
  -v /dados/apps/dspace:/app -v "$HOME/.cache/dspace-maven-repo:/m2" -w /app \
  maven:3-eclipse-temurin-17 \
  mvn --no-transfer-progress -Dmaven.repo.local=/m2 -DskipUnitTests=false \
  -Dtest=EmailTest -DfailIfNoTests=false -pl dspace-api test
```

Expected: `BUILD SUCCESS` com `Tests run: ... Failures: 0`. Se falhar resolvendo `dspace-services`, rodar antes `scripts/backend-dev.sh init` (caminho documentado) e repetir.

---

### Task 5: tabelas admin no mobile e classes Bootstrap 5

**Files:**
- Modify: `dspace-angular/source/src/themes/custom/styles/_pcirn-admin.scss:99-105`
- Modify: `dspace-angular/source/src/app/admin/admin-governance/admin-governance.component.html`

- [ ] **Step 1: Scroll horizontal nas tabelas**

Em `_pcirn-admin.scss`, no bloco `.table-responsive`:

```scss
  .table-responsive {
    overflow-x: auto;
    border: 1px solid $pcirn-admin-border;
    border-radius: .75rem;
    background: $pcirn-admin-surface;
    box-shadow: 0 8px 24px rgba(8, 47, 77, .05);
  }
```

- [ ] **Step 2: Classes BS5 no governance**

No `admin-governance.component.html`: `mr-2` → `me-2`, `ml-2` → `ms-2`, e na linha 47:

```html
[ngClass]="community.accessMode === 'restricted' ? 'text-bg-warning' : 'text-bg-success'"
```

- [ ] **Step 3: Conferir compilação**

Run: `docker logs dspace-angular --since 2m 2>&1 | grep -i "compiled successfully"`
Expected: `Compiled successfully` sem erro de template.

---

### Task 6: Verificação final

- [ ] **Step 1: Suíte de scripts**

Run (em `dspace-angular/source`): `node --test scripts/pcirn-*.test.mjs`
Expected: todos passando (109 anteriores + nenhum novo arquivo).

- [ ] **Step 2: Karma focado**

Run (em `dspace-angular/source`):
```bash
CHROME_BIN=/usr/bin/google-chrome npx ng test --source-map=true --watch=false --configuration test \
  --include='src/themes/custom/app/home-page/pcirn-home-data.service.spec.ts' \
  --include='src/app/access-control/epeople-registry/eperson-form/validators/email-taken.validator.spec.ts' \
  --include='src/app/access-control/epeople-registry/eperson-form/eperson-form.component.spec.ts'
```
Expected: todos SUCCESS. Se o CLI aceitar apenas um `--include` por vez, rodar o comando uma vez para cada spec.

- [ ] **Step 3: Validação viva**

Com conta administradora temporária (criada via `dspace create-administrator` e removida ao final):
1. `/home`: grade de métricas renderiza e não há erro no console.
2. Página de um item com múltiplos arquivos: tamanho aparece em cada arquivo e o badge "Primário" fica no bitstream primário real.
3. `/access-control/epeople`: criar e-person com e-mail já existente mostra "Este e-mail já está em uso"; com o backend inacessível (simular via devtools offline) mostra "Não foi possível verificar este e-mail".
4. `/access-control/epeople` e `/admin/governance` em 390 px: tabelas rolam na horizontal e badges de modo de acesso têm cor.

---

## Self-review

- **Cobertura do spec**: A2 (Task 1), A5 (Task 2), A6 (Task 3), A1 (Task 4), tabelas admin e BS4 (Task 5), verificação (Task 6). Limites respeitados: nada de F0/F2–F6.
- **Sem placeholders**: todos os passos têm código/comando completos.
- **Consistência de tipos/nomes**: `emailCheckFailed` usado igual em validador, formulário, i18n e spec; `primaryBitstreamId` e `dsFileSize` conforme o componente base; `states`/`incomplete` definidos e usados na mesma task.

# Análise de bugs e melhorias — fork PCIRN (DSpace 9.3)

Data: 2026-09-22 · HEAD analisado: `42fffa78d0` + working tree não commitada
Base de comparação (delta autoral): `73c9d1bf2e` (upstream `dspace-9_x` no momento do fork)
Escopo: 77 commits autorais, 96 arquivos no backend + submódulo Angular (~124 arquivos)

## Como a análise foi feita

- **Isolamento do delta autoral**: o fork contém dois "deltas" distintos. Comparar contra `e0fae432ff` (release 9.3) mistura ~2.400 arquivos de commits **upstream** (Tim Donohue, Sascha Szott e outros) que o fork mergeou depois. Toda conclusão deste relatório usa `git diff 73c9d1bf2e HEAD`, que contém **apenas** o trabalho do fork (autoria `kevintestegit`/`gecid-004`).
- **Verificação dinâmica** no ambiente em execução: backend `http://localhost:8501/server` (imagem de 2026-09-21, inclui o HEAD), Solr `:8984`, Postgres `:55432`, Angular dev server `:4000`.
- **Verificação em banco** (somente leitura) via `psql` no container `dspacedb`.
- **Execução de testes**: os 12 scripts `scripts/pcirn-*.test.mjs` rodados com Node 22 (todos passam). O `mvn test` do `dspace-api` **não pôde ser executado** (ver B1).

---

## A. Bugs confirmados

### A1 — [ALTO] `mvn test` do `dspace-api` falha: asserção de teste contradiz o renderer (working tree)

- **Local**: `dspace-api/src/test/java/org/dspace/core/EmailTest.java:135` × `dspace-api/src/main/java/org/dspace/core/PcirnEmailTemplateRenderer.java:132`
- **Evidência**:
  - Teste: `assertThat(html, containsString(">Abrir &nbsp;&#8599;</a>"));`
  - Renderer (working tree): `+ actionLabel + " &nbsp;&#8594;</a></td></tr>"` (o HEAD commitado ainda tem `&#8599;`)
  - `grep -rn "8599" dspace/config/emails/ dspace-api/src/main/java/org/dspace/core/` → **vazio**: nenhum caminho de código produz `&#8599;`, então a asserção é impossível de satisfazer.
- **Contexto**: a mudança não commitada ajustou o renderer (seta, cor, `border-radius`) e atualizou `PcirnEmailTemplateRendererTest.java`, mas **não** atualizou `EmailTest.java` (`git status` mostra só o primeiro como modificado).
- **Impacto**: `mvn test -DskipUnitTests=false` quebra em `EmailTest.buildAddsPlainTextActionFallback`. Como o commit anterior é justamente "test: align email assertions with PCIRN templates", o ajuste ficou pela metade.
- **Correção**: trocar a asserção para `&#8594;` ou, melhor, assertar semântica (`containsString("href=\"https://example.org/task\"")` + presença do rótulo), evitando acoplar o teste a um caractere decorativo.

### A2 — [ALTO] Métricas da home quebram no primeiro estado de *loading* (`payload` indefinido)

- **Local**: `dspace-angular/source/src/themes/custom/app/home-page/pcirn-home-data.service.ts:127-138`
- **Evidência**:
  - `const failed = [communities, collections, items].find(data => data.hasFailed); if (failed) { ... }` seguido de `communities.payload.totalElements`.
  - `request-entry-state.model.ts:67-73`: `hasFailed` retorna **`undefined`** quando o estado está carregando (não é `false`).
  - `remote-data-build.service.ts:318-327`: o filtro do `toRemoteDataObservable` descarta **apenas** "sucesso com payload indefinido" — ou seja, estados pendentes **com payload `undefined` são emitidos**.
- **Impacto**: `combineLatest` emite assim que as três fontes emitem o primeiro valor (todas pendentes) → `communities.payload.totalElements` lança `TypeError` → o observable de `metrics` entra em erro → a grade de métricas da home não renderiza.
- **Não verificado em runtime**: o container Angular roda `npm run serve` (dev server sem SSR), e a verificação com Chromium headless foi bloqueada pelo sandbox. A conclusão é por leitura de código com as linhas citadas.
- **Correção**: guardar o estado pendente antes de desreferenciar, ex.:
  ```ts
  const all = [communities, collections, items];
  const failed = all.find(d => d.hasFailed);
  if (failed) { return failed as unknown as RemoteData<PcirnHomeMetrics>; }
  if (!all.every(d => d.hasSucceeded && d.payload)) { /* devolver estado pendente */ }
  ```

### A3 — [ALTO] Ausência de um asset/layout derruba **todos** os e-mails do sistema

- **Local**: `PcirnEmailTemplateRenderer.java:94-95` (`Files.readString` do layout), `:156-163` (`inlineResource` lança `IOException` se o arquivo faltar), consumidos por `Email.java:446-450` sem `try/catch`.
- **Evidência**: `if (!file.isFile() || !file.canRead()) { throw new IOException("Unable to read PCIRN email asset: " + file); }` — e `Email.build()` chama `render(...)` no caminho crítico; `send()` só trata `mail.server.disabled`.
- **Impacto**: um rename/remoção de `pcirn-layout.html` ou de um dos 5 assets faz **nenhum** e-mail sair (registro, reset de senha, notificações de submissão), com exceção propagada ao chamador em vez de e-mail degradado. Também há NPE se `dspace.dir` não estiver definido (`Paths.get(null, ...)`). O layout é relido do disco em cada e-mail, sem cache.
- **Correção**: degradar com `LOG.warn` (omitir a imagem/CTA ausente e seguir), cachear o layout, e validar `dspace.dir` com mensagem explícita.

### A4 — [ALTO] O caminho de build documentado do backend está quebrado (permissões em `target/`)

- **Local**: `scripts/backend-dev.sh:14-31` (roda Maven como `uid` do usuário) × `dspace-api/target/generated-sources/annotations/` (dono `nobody:nogroup`, modo 644)
- **Evidência** (execução real):
  ```
  $ docker run ... maven:3-eclipse-temurin-17 mvn ... -pl dspace-api compile
  [ERROR] error: Problem opening file to write MetaModel for Handle:
          /app/dspace-api/target/generated-sources/annotations/org/dspace/handle/Handle_.java
  $ ls -l dspace-api/target/generated-sources/annotations/org/dspace/handle/Handle_.java
  -rw-r--r-- 1 nobody nogroup 1182 set 18 07:58 ...
  ```
  Os `.java` gerados (e o diretório) pertencem a `nobody`, de um build anterior rodado como root no container; o `javac` do usuário não consegue sobrescrevê-los.
- **Impacto**: `scripts/backend-dev.sh` falha no `mvn compile` de `dspace-api` até que os artefatos gerados sejam recriados. Nota relacionada: `dspace-api/target/classes` está **vazio** (0 `.class`), e o `docker-compose.yml` monta esse diretório como override — logo o container em execução usa as classes da imagem, não o código local.
- **Correção**: `rm -rf dspace-api/target/generated-sources` (é saída gerada) ou `chown -R "$(id -u):$(id -g)" dspace-api/target`; e no script, evitar builds como root no mesmo volume.

### A5 — [MÉDIO] Regressão de informação na seção de arquivos do item

- **Local**: `dspace-angular/source/src/themes/custom/app/item-page/simple/field-components/file-section/file-section.component.html:6,17`
- **Evidência** (comparação com o template base `src/app/item-page/simple/field-components/file-section/file-section.component.html:8-13`):
  - base: `@if (primaryBitstreamId === file.id) { <span class="badge bg-primary">{{ 'item.page.bitstreams.primary' | translate }}</span> }` + `<span> ({{(file?.sizeBytes) | dsFileSize }})</span>`
  - custom: `[class.pcirn-document-file-primary]="first"` e extensão só do primeiro arquivo; **sem tamanho** e **sem** o badge real de primário.
- **Impacto**: o usuário perde o tamanho do arquivo (informação que existia) e "primário" passa a significar "primeiro da lista", o que é falso quando o bitstream primário é outro.
- **Correção**: reintroduzir `dsFileSize` e usar `primaryBitstreamId === file.id` para o destaque, mantendo `$first` só como hierarquia visual.

### A6 — [MÉDIO] Validador de e-mail "falha aberto": duplicidade deixa de ser checada

- **Local**: `dspace-angular/source/src/app/access-control/epeople-registry/eperson-form/validators/email-taken.validator.ts:25-32`
- **Evidência**: `map(res => res.hasSucceeded && res.payload ? { emailTaken: true } : null)` + `catchError(() => of(null))`.
- **Impacto**: qualquer resposta não-sucedida — inclusive **403** (o endpoint `byEmail` exige `ADMIN`/`MANAGE_ACCESS_GROUP`), 5xx ou falha de rede — é tratada como "e-mail livre". A checagem de unicidade simplesmente deixa de existir, em silêncio. O spec novo (`email-taken.validator.spec.ts:20-40`) cristaliza apenas os caminhos de falha e não testa o caso positivo.
- **Correção**: distinguir "não encontrado" (`hasSucceeded && !payload` → `null`) de "não foi possível verificar" (`!hasSucceeded` → erro próprio), e cobrir os dois caminhos no spec.

### A7 — [MÉDIO] Migrações de acesso: idempotência alegada é falsa e não há asserção de estado final

- **Local**: `dspace-api/src/main/resources/org/dspace/storage/rdbms/sqlmigration/postgres/`
- **Evidência**:
  - `V9.4_2026.08.18__pcirn_public_portarias.sql:143-192` concede READ anônimo a itens/bundles/bitstreams **sem** filtrar `in_archive`/`withdrawn`/`deleted`; `V9.4_2026.09.17__pcirn_access_reconcile.sql:6-9` reconhece o problema e o §8 limpa. Como o Flyway não reaplica 09.17, **reexecutar 08.18 recria o vazamento** — e o cabeçalho do arquivo convida à reexecução ("safe to re-run").
  - `V9.4_2026.08.14__pcirn_mvp_access.sql:66-81` concede ADD em toda coleção; `V9.4_2026.08.24...sql:235-239` remove o ADD de `PCIRN_Depositantes`. Reexecutar 08.14 anula o endurecimento de 08.24.
  - `V9.4_2026.08.15...sql:70` / `08.17:77` / `08.24:62,111` usam `RAISE EXCEPTION` sobre títulos de comunidade/structure hardcoded → em instalação limpa (QA, upgrade) a migração **aborta e o DSpace não sobe**.
  - `08.15:40-42,51-55` e `08.17:70-74,85-91`: `SELECT ... INTO` sem guarda de múltiplas linhas (as proteções existem em 08.18/08.24 e não foram retroaplicadas).
- **Impacto**: estado final não garantido, correções desfeitas por reexecução manual, e migrações não portáveis para outra instância.
- **Correção**: remover as alegações de idempotência, transformar cada correção de dados em nova migração versionada, trocar `RAISE EXCEPTION` por no-op guardado nas partes dependentes de dados da instalação e adicionar bloco final de asserção de estado.

### A8 — [MÉDIO] Metadados canônicos apontando para `localhost`

- **Local**: `V9.4_2026.08.17__pcirn_portarias_collections.sql:115` e `V9.4_2026.08.24__pcirn_sector_submission_and_shared_read.sql:218` (`'http://localhost:4000/handle/'`)
- **Evidência**:
  ```
  SELECT count(*) FROM metadatavalue WHERE text_value LIKE '%localhost:4000%';  --> 28
  ```
  (enquanto `dspace/config/local.cfg:2` define `dspace.ui.url = http://10.9.233.96:4000`)
- **Impacto**: 28 valores de `dc.identifier.uri` (inclusive em coleções criadas pelas migrações) apontam para um host que não existe em produção — links canônicos quebrados que as migrações perpetuam.
- **Correção**: usar `${dspace.ui.url}` (ou handle puro) em vez do literal, e corrigir os 28 registros existentes via nova migração.

### A9 — [MÉDIO] Bootstrap de administrador silenciosamente inócuo (e-mail inexistente hardcoded)

- **Local**: `V9.4_2026.08.14__pcirn_mvp_access.sql:47` e `V9.4_2026.08.15__pcirn_sector_access.sql:170` (`'gesiele@localhost.com'`)
- **Evidência**: o e-mail não existe na base → `JOIN eperson` não retorna linhas → **0 inserções, sem erro e sem log**. O acesso da conta real veio de outra migração (`08.16`).
- **Impacto**: falha de provisionamento silenciosa; se a conta não existisse por outro caminho, o setor ficaria sem membro e sem sinal algum.
- **Correção**: usar variável/parâmetro de configuração e adicionar asserção (`IF NOT EXISTS ... RAISE NOTICE/EXCEPTION`).

### A10 — [MÉDIO] E-mails sem `emailTitle` recebem o shell PCIRN com `<h1>` vazio

- **Local**: `dspace/config/emails/pcirn-layout.html:38-41` × `Email.java:534-537` (`getContextValue` devolve `""`) — ex.: `DailyReportEmailer.java:75` (`email.setContent("Checker Report", ...)`)
- **Impacto**: e-mails legítimos (relatório do checker, entre outros que usam `setContent`) saem com título vazio e com aviso institucional ("se você não reconhece esta mensagem") fora de contexto.
- **Correção**: aplicar o shell somente quando houver `emailTitle`, ou cair num título padrão (`config.get('dspace.name')`).

### A11 — [MÉDIO] ~942 KB de imagens inline em cada mensagem

- **Local**: `dspace/config/emails/assets/` + `PcirnEmailTemplateRenderer.java:109-114`
- **Evidência** (`ls -la`): `desenho1.png` 466.290 · `brasao-policia-cientifica-rn.png` 248.267 · `brasao-estado-rn.png` 210.453 · `footer-bg-pcirn.webp` 14.246 · `dspace-logo-white.svg` 2.416 → **941.672 bytes** por e-mail (~1,25 MB em base64), sendo que os brasões são exibidos a 42 px.
- **Impacto**: envio lento, risco de clipping/limite de tamanho e de pontuação de spam.
- **Correção**: comprimir/redimensionar (PNG8/JPEG) para o tamanho real de exibição.
- **Relacionado (não verificado por cliente)**: o logo é inline em **SVG** e o fundo em **WebP**, formatos que não renderizam no Outlook (e SVG não renderiza no Gmail). Enviar PNG para o logo.

### A12 — [MÉDIO] Os scripts `pcirn-*.test.mjs` não testam comportamento

- **Local**: `scripts/pcirn-*.test.mjs` (12 arquivos) e `dspace-angular/source/scripts/pcirn-*.test.mjs`
- **Evidência**: todos passam (`node <arquivo>` → exit 0, verificado), mas são `readFile` + regex sobre TS/SCSS/JSON/SQL — nenhum importa código da aplicação. Exemplos de asserções frágeis: `assert.match(migration, /editor/)`, `assert.match(heroStyles, /height:\s*350px/)`.
- **Impacto**: travam valores literais de CSS (qualquer ajuste visual legítimo "quebra o teste") e **passam 100% verdes com os bugs A2 e A5 presentes**. O spec `pcirn-home-data.service.spec.ts:25-53` ("shares collection and search reads used by content and metrics") não assina nada, então passaria igual sem `shareReplay`; `buildMetrics` não tem teste.
- **Correção**: manter no máximo um smoke test de arquivos e migrar a cobertura para specs Jasmine reais (o `PcirnHomeDataService` é testável com stubs, inclusive o caso de loading do A2).

### A13 — [BAIXO] Higiene de repositório

- `.env.bak` (310 B), `docker-compose.yml.bak` (6.198 B) e `docker-compose-network-fix.yml` commitados.
- `dspace-angular/config/config.yml` commitado apontando para `sandbox.dspace.org` (`rest.host: sandbox.dspace.org`, `ssl: true`, `port: 443`), enquanto produção usa `PUBLIC_UI_URL`/`DSPACE_REST_HOST`. O `.gitignore` do submódulo (`config/.gitignore`: `config.*.yml`) **não cobre** `config.yml` — o padrão exige um segmento no meio.
- `.env` commitado com IP interno (`10.9.233.96`) — sem credenciais (verificado), mas deveria ser `.env.example`.
- **Correção**: remover os `.bak`, mover `config.yml` para `config.example.yml` e ampliar o padrão do `.gitignore`.

### A14 — [BAIXO] Documentação contraditória sobre o modelo de acesso

- `docs/pcirn-repository.md:28` afirma que "o sistema é interno" e que a migração `08.05` troca as leituras anônimas pelo grupo `Usuarios_Logados`; porém `docs/superpowers/plans/2026-08-17-public-permissions-nugecid.md` e `docs/pcirn-publicacao-analise.md:86` descrevem leitura pública, e o banco confirma o estado **público**:
  ```
  anon_policies_0_9_10       | 15624
  site_anon_read             |     1
  collections_with_anon_read | 23 / 23
  ```
- `docs/pcirn-publicacao-analise.md:21` já registra que `structure.xml` (22 coleções / 4 comunidades) ≠ banco (23 / 5, por criação via migração) — ou seja, `structure.xml` não é fonte única da hierarquia.
- **Correção**: decidir e documentar explicitamente o modelo (público ou interno), alinhar os docs e marcar as migrações "make private" como superadas.

---

## B. Riscos de projeto a revisar (não são bugs, mas exigem decisão)

1. **`submit_delete` apaga o item definitivamente, sem motivo registrado** — `AcceptEditRejectAction.processDelete` → `XmlWorkflowServiceImpl.deleteWorkflowByWorkflowItem:969-991` faz `turnOffAuthorisationSystem()` + `itemService.delete(...)`: exclusão física e irreversível, sem `provenance`/justificativa e sem e-mail ao depositante (diferente do `reject`). Para um repositório de **atos oficiais** (portarias), isso é risco de conformidade e de perda de acervo com um clique. O teste novo (`AcceptEditRejectActionTest`) só verifica as *strings* das opções. Sugestão: registrar motivo/autor no log estruturado (e no e-mail ao depositante) ou substituir por *withdraw* + política de descarte.
2. **`RETURN_TO_POOL` removido do revisor** — intencional (há teste que exige a ausência), mas elimina a única forma de devolver a tarefa ao pool; confirmar que é o desejado no fluxo NUGECID.
3. **OAI-PMH desabilitado** (`dspace/config/modules/oai.cfg`: `oai.enabled = false`) — é **decisão documentada** (`docs/pcirn-repository.md:28`, plano de 17/08), não bug. Vale reavaliar: sem OAI-PMH não há colheita por BDTD/Lattes/OpenAIRE, o que é incomum para repositório com leitura pública.
4. **`Email.java` (core do DSpace) passou a envolver *todo* e-mail no shell PCIRN** — mudança global em classe de núcleo, acoplada a um template e a 5 assets de um cliente específico (ver A3/A10). Alternativa: aplicar o shell por template/flag de configuração.
5. **`discovery.xml`**: a busca padrão passou a retornar **apenas itens** (`(search.resourcetype:Item AND latestVersion:true)`), removendo comunidades/coleções dos resultados, e a ordenação padrão deixou de ser por relevância (`sortScore` foi para o fim). Ambas são escolhas de produto — confirmar que a busca por nome de coleção/assunto não é um caso de uso esperado.
6. **`webui.browse.index.5 = type:metadata:dc.type:text`** funciona (verificado: `/api/discover/browses/type/entries` → 200, valores `DECRETO`, `LEI`…), mas coexiste com o vocabulário controlado `pcirn-document-types` para o mesmo campo — dois mecanismos paralelos para `dc.type`.

---

## C. Verificado e descartado (falsos positivos)

Registrado para dar confiança ao relatório — cada item foi checado e **não** é bug:

| Suspeita | Verificação | Veredito |
|---|---|---|
| Anexos inline quebram porque o `FileInputStream` é fechado antes do envio (`Email.java:471-478`) | `InputStreamDataSource` (`Email.java:743-752`) faz buffer completo em `ByteArrayOutputStream` no construtor | **Não é bug** |
| `@PreAuthorize` em `EPersonRestRepository.findByEmail` e validações de `RegistrationRestRepository` seriam do fork | `git log` mostra autoria de **Tim Donohue** e **Sascha Szott** (upstream mergeado após 9.3) | **Upstream, não fork** |
| Endurecimento de XXE em `XMLUtils` (`getTransformerFactory`) quebraria XSLT com `xsl:import` | Mesma origem upstream (`cc8a9268f4`, Tim Donohue), com `getTrustedTransformerFactory` para OAI | **Upstream, não fork** |
| `/api/discover/browses/type/items` → HTTP 500 | `author/items` (upstream) retorna o mesmo 500: browse `valueList` exige `filterValue`; o caminho correto (`/entries`) responde 200 | **Comportamento upstream** |
| `/api/discover/browses/pcirn-document-types/entries` → HTTP 400 ("Unknown browse index") | `srsc` (índice de vocabulário do upstream) retorna 400 idêntico | **Comportamento upstream** |
| `oai.enabled=false` seria regressão acidental de um commit em massa | Decisão documentada em 3 documentos do fork | **Intencional** |
| `user.registration=false`, LDAP/OIDC sem autocadastro, grupo `Usuarios_Logados` | Documentado em `docs/pcirn-repository.md:24`; o grupo existe no banco (`d2acb6bb-…`) | **Intencional** |
| Busca de coleção por título seria ambígua (4 coleções homônimas) | A migração escopa por `cc.community_id = resolved_uuid` (`08.17:85-91`) | **Não é bug** |
| Segredos commitados | `.env` sem credenciais; produção exige `POSTGRES_PASSWORD`/`PUBLIC_UI_URL` por variável; `smtp.env` está no `.gitignore` e fora do Git | **Não há vazamento** |
| Chaves de tradução PCIRN ausentes | Cruzamento das 1.230 chaves `\| translate` contra `en.json5`/`pt-BR.json5`: nenhuma ausente | **Não é bug** |

---

## D. Melhorias sugeridas (curto prazo, por ordem de retorno)

1. **Rodar `mvn test -DskipUnitTests=false` no CI do fork** — o A1 mostra que a suíte quebrou sem que ninguém percebesse; incluir também `checkstyle` (o PR precisa passá-lo).
2. **Fallback gracioso no renderer de e-mail** (A3) + cache do layout + assets otimizados (A11).
3. **Guardas de estado pendente nos serviços da home** (A2) e teste do caminho de loading.
4. **Asserções de estado final nas migrações** (A7) e proibição de reexecução manual das migrações de dados.
5. **Acessibilidade/i18n no Angular**: `[attr.aria-label]` em `<div>` genérico é ignorado por leitores de tela (`home-page.component.html:15-18,56,61`) — usar `role="group"` + `aria-labelledby`; os 4 chips do hero prometem categorias ("Normas e Portarias", "POPs"…) mas todos navegam para `/search` sem filtro; `fale-conosco.component.html` está 100% em PT (inclusive rótulos ARIA) com o e-mail institucional duplicado em 3 pontos do template + 1 no TS; `aria-label="Close"` fixo em inglês no modal de exclusão do workflow; `dsPcirnDocumentType` é pipe puro com `translate.instant`, então o rótulo não acompanha a troca de idioma.
6. **Heurísticas por nome de grupo/coleção**: `eperson-form.component.ts:548-550` identifica o grupo administrador por `group.name === 'Administrator'` e usa `page.find(...)` sobre busca paginada (pode conceder admin no grupo errado); `collection-list-page.component.ts:37` usa `n.includes('cin')` para escolher ícone, o que casa "Me**dicina** Legal". Preferir UUID/`Group.ADMIN` permanente e metadado em vez de heurística de texto.
7. **Higiene**: remover `.bak`, `config.yml` → `config.example.yml`, `.env` → `.env.example`, e ampliar o padrão do `.gitignore` do submódulo.

---

## E. Limitações desta análise

- **Não executei a suíte Maven** (bloqueada por A4); A1 é conclusivo por leitura (asserção literal de substring cuja cadeia produtora não existe em nenhum arquivo), mas não observado em execução.
- **Não executei testes de integração** (`dspace-server-webapp`, `*-IT`), nem fluxos de escrita ponta a ponta (submissão, workflow, edição de metadados) — portanto contratos de payload e efeitos colaterais de escrita não foram confirmados.
- **A2, A5, A6 e os itens de UI/i18n do Angular** são conclusões de leitura de código: o container Angular roda dev server sem SSR e a verificação com Chromium headless foi bloqueada pelo sandbox.
- **Renderização nos clientes de e-mail** (SVG/WebP/clipping) não foi testada em Gmail/Outlook.
- **Não revisado em detalhe**: ~2.000 linhas de SCSS novos do tema, contraste real de cores, e os componentes Angular custom não listados explicitamente (media-viewer, community-page, search-page, páginas de erro/info).
- A causa raiz da divergência entre a migração `08.05` ("make site private") e as políticas anônimas herdadas (15.540 `TYPE_INHERITED`) não é determinável apenas com leitura — exigiria reconstruir a ordem entre migração e carga do acervo.

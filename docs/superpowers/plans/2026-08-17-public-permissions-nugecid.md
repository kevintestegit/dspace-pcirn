# Acesso público e aprovação obrigatória pelo NUGECID Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir leitura pública somente de Portarias aprovadas, manter POPs e demais documentos restritos a usuários autenticados e obrigar toda nova publicação a passar pelo NUGECID.

**Architecture:** Usar `ResourcePolicy`, grupos, coleções e XML Workflow nativos do DSpace. O PostgreSQL será a fonte da verdade para visibilidade; o workflow `editor` do grupo `NUGECID` será a única transição para arquivo; REST, importação e protocolos externos não terão caminhos paralelos de publicação. A sidebar de setores continuará sendo uma preocupação exclusiva da Angular e permanecerá invisível para anônimos.

**Tech Stack:** DSpace 9.4, Java/Spring Security, PostgreSQL/Flyway, XML Workflow, REST, Angular standalone components, RxJS, testes JUnit/Jasmine/Node e Docker Compose.

---

## Fonte da verdade e mapa de arquivos

**Criar:**

- `dspace-api/src/main/resources/org/dspace/storage/rdbms/sqlmigration/postgres/V9.4_2026.08.17__pcirn_public_access_workflow.sql` — reconciliação idempotente das políticas públicas e autenticadas.

**Modificar:**

- `dspace-server-webapp/src/main/java/org/dspace/app/rest/repository/ItemRestRepository.java` — bloquear criação REST direta de item arquivado.
- `dspace-server-webapp/src/test/java/org/dspace/app/rest/ItemRestRepositoryIT.java` — substituir expectativas de publicação direta por negação.
- `dspace-api/src/main/java/org/dspace/app/itemimport/ItemImport.java` — forçar importação `add` para workflow e recusar `replace` direto.
- `dspace-api/src/test/java/org/dspace/app/itemimport/ItemImportCLIIT.java` — provar que importação não publica diretamente.
- `dspace-server-webapp/src/main/java/org/dspace/app/rest/security/WebSecurityConfiguration.java` — permitir que leituras anônimas cheguem às políticas por objeto.
- `dspace/config/modules/sword-server.cfg` e `dspace/config/modules/swordv2-server.cfg` — declarar SWORD desativado explicitamente.
- `dspace/config/pcirn/structure.xml`, `dspace/config/item-submission.xml` e `dspace/config/spring/api/workflow.xml` — somente se a verificação encontrar coleção sem o workflow padrão ou papel diferente de `NUGECID`.
- `dspace-angular/source/scripts/pcirn-home.test.mjs` — reforçar o contrato de sidebar anônima sem duplicar a implementação existente.
- `docs/pcirn-repository.md` — substituir a descrição de sistema interno pelo modelo público/interno aprovado.

**Preservar:** `.env`, Compose, volumes, mudanças Angular não relacionadas, migrações já registradas em `schema_version` e o grupo curatorial `NUGECID`.

**Caminho substituído:** `V9.4_2026.08.05__make_site_private.sql` e as políticas setoriais não serão reescritos; uma migração posterior fará o cutover. O plano setorial anterior deixa de ser a fonte de visibilidade, pois POPs devem ser legíveis por qualquer usuário autenticado.

## Task 1: Confirmar o estado real antes do cutover

**Files:** nenhum.

- [ ] **Step 1: Preservar o estado de trabalho.**

Executar:

```bash
git status --short --branch
git -C dspace-angular/source status --short --branch
```

Esperado: as alterações já existentes permanecem listadas; não executar `reset`, `checkout`, limpeza ou remoção.

- [ ] **Step 2: Confirmar migrações aplicadas.**

Executar:

```bash
docker compose exec -T dspacedb psql -U dspace -d dspace -c \
  "SELECT version, description FROM schema_version WHERE version LIKE '9.4.2026.%' ORDER BY installed_rank;"
```

Esperado: o resultado informa quais migrações `.14`, `.15` e `.16` estão registradas antes da nova versão.

- [ ] **Step 3: Medir grupos e políticas atuais.**

Executar:

```bash
docker compose exec -T dspacedb psql -U dspace -d dspace -c \
  "SELECT name FROM epersongroup WHERE name IN ('Anonymous','Usuarios_Logados','NUGECID') OR name LIKE 'PCIRN_Setor_%' ORDER BY name;"
```

Esperado: os grupos existentes são identificados; a migração não cria nomes alternativos.

- [ ] **Step 4: Inspecionar o serviço Angular existente.**

Executar:

```bash
rg -n "authenticated\\$|authenticated && !adminSidebarVisible|findTop|pcirn-sector-sidebar" \
  dspace-angular/source/src/app/shared/sector-sidebar \
  dspace-angular/source/src/app/root/root.component.html \
  dspace-angular/source/scripts/pcirn-home.test.mjs
```

Esperado: `SectorSidebarService.visible$` exige autenticação, a consulta de comunidades só ocorre autenticado e o template só renderiza o `<aside>` quando `visible$` é verdadeiro.

- [ ] **Step 5: Commitar somente a evidência, se houver atualização documental.**

Não criar snapshot ou arquivo temporário. Se nenhuma documentação for alterada nesta tarefa, não criar commit.

## Task 2: Reconciliar as políticas de leitura

**Files:**

- Create: `dspace-api/src/main/resources/org/dspace/storage/rdbms/sqlmigration/postgres/V9.4_2026.08.17__pcirn_public_access_workflow.sql`

- [ ] **Step 1: Criar a migração sem alterar versões anteriores.**

Usar `DO $$` e tabelas temporárias `ON COMMIT DROP`; para cada grupo novo, inserir primeiro em `dspaceobject` e depois em `epersongroup`. Resolver as coleções por nome exato, falhando se `Portarias e Atos Normativos Internos` não existir.

- [ ] **Step 2: Materializar os objetos PCIRN afetados.**

Preencher uma tabela temporária com a coleção de Portarias e todas as coleções das comunidades PCIRN existentes, incluindo seus itens, bundles e bitstreams. A consulta deve seguir `community2collection`, `item.owning_collection`, `item2bundle`, `bundle2bitstream` e não usar UUID fixo.

- [ ] **Step 3: Reconciliar a classe pública.**

Para a coleção `Portarias e Atos Normativos Internos`, substituir políticas de leitura de `Usuarios_Logados` e `PCIRN_Setor_*` por `Anonymous` nos objetos arquivados. Garantir na coleção os defaults `DEFAULT_ITEM_READ` (`action_id = 10`) e `DEFAULT_BITSTREAM_READ` (`action_id = 9`) para `Anonymous`, além de `READ` (`action_id = 0`) onde a navegação da coleção exigir.

- [ ] **Step 4: Reconciliar a classe autenticada.**

Para POPs e demais coleções internas, remover políticas de leitura setoriais e garantir `READ` para `Usuarios_Logados`. Garantir os defaults de item e bitstream para `Usuarios_Logados` nas coleções internas, para que itens aprovados futuros herdem a regra.

- [ ] **Step 5: Fechar pendências.**

Remover políticas `Anonymous` de itens ainda não arquivados e seus bitstreams. Não remover políticas de submissão do remetente nem do grupo `NUGECID`; essas políticas são necessárias para o acompanhamento do workflow.

- [ ] **Step 6: Validar a migração no ambiente Docker.**

Reconstruir o backend para incluir o novo recurso SQL e executar a migração pelo entrypoint oficial:

```bash
docker compose up -d --build dspace
docker compose exec dspace /dspace/bin/dspace database migrate
```

Esperado: execução sem erro e nova versão registrada em `schema_version`.

- [ ] **Step 7: Confirmar o resultado da migração.**

Consultar `resourcepolicy` e confirmar `Anonymous` somente na árvore de Portarias, `Usuarios_Logados` nos documentos internos e nenhuma política `Anonymous` em item não arquivado.

- [ ] **Step 8: Commitar a migração.**

```bash
git add dspace-api/src/main/resources/org/dspace/storage/rdbms/sqlmigration/postgres/V9.4_2026.08.17__pcirn_public_access_workflow.sql
git commit -m "feat: reconcile public repository access"
```

## Task 3: Tornar o workflow a única publicação

**Files:**

- Modify: `dspace/config/spring/api/workflow.xml`
- Modify: `dspace/config/item-submission.xml`
- Modify: `dspace-server-webapp/src/main/java/org/dspace/app/rest/repository/ItemRestRepository.java`
- Test: `dspace-server-webapp/src/test/java/org/dspace/app/rest/ItemRestRepositoryIT.java`

- [ ] **Step 1: Escrever a expectativa de bloqueio REST.**

No método `createAndReturn` de `ItemRestRepository`, a criação direta de item arquivado deve ser negada para o administrador e para qualquer outro usuário. Antes da alteração, acrescentar/ajustar um teste que faça `POST /api/core/items?owningCollection=123456789%2F1` com `inArchive=true` e espere `403`.

- [ ] **Step 2: Bloquear a rota direta.**

Trocar a autorização administrativa do método por uma negação permanente:

```java
@PreAuthorize("denyAll()")
protected ItemRest createAndReturn(Context context) throws AuthorizeException, SQLException {
```

Manter o corpo legado inacessível atrás de `denyAll()` para evitar refatoração não relacionada; a rota padrão de submissão continuará usando `WorkflowItemRestRepository`.

- [ ] **Step 3: Atualizar testes de legado da rota.**

Em `ItemRestRepositoryIT.java`, os testes `testCreateItem`, `testCreateItemInArchiveFalseBadRequestException`, `createItemFromExternalSources` e seus casos de origem externa devem testar a negação da rota, enquanto testes de `update` devem criar fixtures com `ItemBuilder` ou `WorkflowItemBuilder`, nunca por `POST /api/core/items`.

- [ ] **Step 4: Confirmar o workflow XML.**

O workflow padrão deve manter uma única primeira etapa `editstep`, com papel de escopo `REPOSITORY`, nome `NUGECID` e ação de edição que permita aprovar ou devolver. Todas as coleções submetidas pelo mapeamento `default` de `item-submission.xml` devem apontar para o processo PCIRN e nunca para uma instalação direta.

- [ ] **Step 5: Rodar o teste REST focado.**

```bash
mvn -pl dspace-server-webapp -am -Dtest=ItemRestRepositoryIT -DfailIfNoTests=false test
```

Esperado: os testes de criação direta falham com `403`; submissão por workspace/workflow permanece disponível.

- [ ] **Step 6: Commitar a trava de publicação.**

```bash
git add dspace/config/spring/api/workflow.xml \
  dspace/config/item-submission.xml \
  dspace-server-webapp/src/main/java/org/dspace/app/rest/repository/ItemRestRepository.java \
  dspace-server-webapp/src/test/java/org/dspace/app/rest/ItemRestRepositoryIT.java
git commit -m "feat: require workflow for item publication"
```

## Task 4: Fechar importações e protocolos alternativos

**Files:**

- Modify: `dspace-api/src/main/java/org/dspace/app/itemimport/ItemImport.java`
- Test: `dspace-api/src/test/java/org/dspace/app/itemimport/ItemImportCLIIT.java`
- Modify: `dspace/config/modules/sword-server.cfg`
- Modify: `dspace/config/modules/swordv2-server.cfg`

- [ ] **Step 1: Escrever a expectativa do importador.**

Adicionar testes que confirmem: `add` cria workspace/workflow e não item arquivado; `replace` é recusado; `delete` continua restrito à operação administrativa de remoção.

- [ ] **Step 2: Forçar o caminho seguro no importador.**

Em `ItemImport.setup()`/`validate()`, aplicar esta regra antes de executar `ItemImportService`:

```java
if ("replace".equals(command)) {
    throw new UnsupportedOperationException("SAF replacement is disabled; submit the file through the NUGECID workflow");
}
if ("add".equals(command)) {
    useWorkflow = true;
}
```

Manter `ItemImportServiceImpl.addItem()` como responsável por criar o workspace e iniciar o workflow; não instalar o item diretamente nem gerar Handle antes da aprovação.

- [ ] **Step 3: Atualizar os testes SAF.**

Os testes de `add` devem consultar o item pelo metadado e confirmar `isArchived() == false`; os testes de `replace` devem esperar `UnsupportedOperationException`; os testes de `delete` devem preservar a cobertura de remoção.

- [ ] **Step 4: Desativar SWORD explicitamente.**

Definir nas duas configurações:

```properties
sword-server.enabled = false
swordv2-server.enabled = false
```

Manter `oai.enabled = false` e `iiif.enabled = false`; não habilitar protocolos para compensar a leitura pública da Angular.

- [ ] **Step 5: Rodar os testes do importador.**

```bash
mvn -pl dspace-api -Dtest=ItemImportCLIIT -DfailIfNoTests=false test
```

Esperado: `add` permanece não arquivado, `replace` falha explicitamente e nenhum teste produz publicação sem workflow.

- [ ] **Step 6: Commitar o fechamento dos atalhos.**

```bash
git add dspace-api/src/main/java/org/dspace/app/itemimport/ItemImport.java \
  dspace-api/src/test/java/org/dspace/app/itemimport/ItemImportCLIIT.java \
  dspace/config/modules/sword-server.cfg \
  dspace/config/modules/swordv2-server.cfg
git commit -m "feat: route imports through approval workflow"
```

## Task 5: Permitir leitura pública sem abrir escrita

**Files:**

- Modify: `dspace-server-webapp/src/main/java/org/dspace/app/rest/security/WebSecurityConfiguration.java`
- Verify: `dspace/config/modules/authentication-password.cfg`

- [ ] **Step 1: Escrever a matriz HTTP mínima.**

Testar que GET anônimo chega ao avaliador de objeto e que POST/PATCH/DELETE sem autenticação continuam negados. Login, redefinição de senha e `GET /api/security/csrf` continuam públicos.

- [ ] **Step 2: Remover o bloqueio global de transporte para leitura.**

Restaurar o comportamento nativo do DSpace em que, após os matchers de administração e autenticação, a cadeia permite que as verificações `@PreAuthorize` de leitura apliquem as `ResourcePolicy`. Não criar filtro Java paralelo.

- [ ] **Step 3: Confirmar contas e e-mail.**

Manter:

```properties
user.registration = false
authentication-password.login.specialgroup = Usuarios_Logados
```

Não desativar `user.forgot-password`; validar a criação administrativa de EPerson e redefinição de senha sem habilitar autocadastro.

- [ ] **Step 4: Rodar a validação REST.**

Com uma Portaria e um POP aprovados:

```bash
curl -i http://localhost:8501/server/api/core/items/<PORTARIA_UUID>
curl -i http://localhost:8501/server/api/core/items/<POP_UUID>
curl -i http://localhost:8501/server/api/core/bitstreams/<PORTARIA_BITSTREAM_UUID>/content
```

Esperado: Portaria `200`; POP anônimo `401`/`403`; bitstream da Portaria `200`; POP com token autenticado `200`.

- [ ] **Step 5: Commitar a abertura somente de leitura.**

```bash
git add dspace-server-webapp/src/main/java/org/dspace/app/rest/security/WebSecurityConfiguration.java
git commit -m "feat: allow policy-controlled public reads"
```

## Task 6: Garantir a sidebar somente para usuários logados

**Files:**

- Verify: `dspace-angular/source/src/app/shared/sector-sidebar/sector-sidebar.service.ts`
- Verify: `dspace-angular/source/src/app/shared/sector-sidebar/sector-sidebar.component.html`
- Verify: `dspace-angular/source/src/app/root/root.component.html`
- Modify/Test: `dspace-angular/source/scripts/pcirn-home.test.mjs`

- [ ] **Step 1: Preservar a regra existente.**

Não adicionar guard ou store. `SectorSidebarService.visible$` deve continuar equivalente a:

```ts
map(([authenticated, adminSidebarVisible]) => authenticated && !adminSidebarVisible)
```

O `switchMap` deve retornar `of(undefined)` quando anônimo, evitando consulta REST de comunidades.

- [ ] **Step 2: Adicionar a prova source-level.**

Em `pcirn-home.test.mjs`, testar `authenticated && !adminSidebarVisible`, o ramo `of(undefined)` e `@if (sectorSidebarService.visible$ | async)` no template. Não criar nova implementação.

- [ ] **Step 3: Rodar o teste Angular.**

```bash
cd dspace-angular/source
node --test scripts/pcirn-home.test.mjs
```

Esperado: todos os testes passam; nenhum arquivo de produção Angular muda se a regra atual estiver intacta.

- [ ] **Step 4: Commitar somente a prova da sidebar.**

```bash
git -C dspace-angular/source add scripts/pcirn-home.test.mjs
git -C dspace-angular/source commit -m "test: hide sector sidebar from anonymous users"
```

Não incluir as demais alterações já existentes no sub-repositório Angular.

## Task 7: Provar o fluxo ponta a ponta e atualizar a documentação

**Files:**

- Modify: `docs/pcirn-repository.md`
- Verify: `docs/superpowers/specs/2026-08-17-public-permissions-nugecid-approval-design.md`

- [ ] **Step 1: Atualizar o fluxo documentado.**

Substituir “O sistema é interno” por: Portarias aprovadas são públicas; POPs e demais documentos aprovados exigem login; todo envio passa pelo NUGECID; contas são criadas pelo administrador e usam redefinição por e-mail.

- [ ] **Step 2: Provar Portaria.**

Enviar, devolver, reenviar e aprovar uma Portaria. Confirmar que pendente fica privado, que a aprovação gera Handle e busca, e que o público baixa o bitstream somente depois da aprovação.

- [ ] **Step 3: Provar POP.**

Enviar e aprovar um POP. Confirmar acesso para usuário logado e `401`/`403` para anônimo, inclusive na busca e no download.

- [ ] **Step 4: Provar ausência de bypass.**

Confirmar `403` na criação REST direta, falha no SAF `replace`, workflow no SAF `add`, SWORD desativado e ausência de sidebar/consulta de comunidades para anônimo.

- [ ] **Step 5: Rodar as verificações finais.**

```bash
cd dspace-angular/source
npm run build:lint
npm run build
node --test scripts/pcirn-home.test.mjs
cd ../..
mvn -pl dspace-server-webapp -am -DskipUnitTests=false -DskipIntegrationTests=false test
```

Esperado: build Angular, testes source-level e testes Maven passam; falha de infraestrutura deve ser registrada como “implementado, não provado”.

- [ ] **Step 6: Atualizar a documentação.**

```bash
git add docs/pcirn-repository.md
git commit -m "docs: describe public and internal access"
```

## Critérios de aceite

- Portaria aprovada: público consulta, busca e baixa.
- POP aprovado: somente usuário logado consulta, busca e baixa.
- Pendente/devolvido/rejeitado: somente remetente e NUGECID.
- Toda submissão chega ao NUGECID antes da instalação.
- Criação direta REST e importação sem workflow não publicam.
- Contas não podem ser criadas por autocadastro e redefinição usa e-mail.
- Usuário anônimo não vê `#pcirn-sector-sidebar` nem dispara a consulta de comunidades.
- Usuário autenticado mantém a sidebar conforme as políticas do backend.
- O checkout conserva alterações não relacionadas e não reescreve migrações aplicadas.

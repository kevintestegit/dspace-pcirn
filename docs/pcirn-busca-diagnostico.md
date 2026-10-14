# Motor de busca das publicações — diagnóstico de desempenho

**Data:** 2026-10-13
**Ambiente medido:** instância de homologação em containers (`dspace` REST em `:8501`, `dspacesolr` em `:8984`, `dspacedb` Postgres 15 em `:55432`, `dspace-angular` em `:4000`)
**Código:** DSpace `9.4-SNAPSHOT`, commit `4e6374d02e`

---

## 1. Resumo executivo

O Solr **não é o gargalo**. O tempo da busca é consumido por trabalho que o DSpace faz *em volta* da consulta.

Números-chave medidos:

| Medida | Valor |
|---|---|
| Tempo de resposta do Solr (`QTime`) | média **0,33 ms**, p99 **5,1 ms** |
| Latência de uma busca REST de 20 itens | mediana **41–44 ms** (até 67 ms sob carga) |
| Requisição com 0 resultados | ~**15 ms** (custo fixo) |
| Consultas Solr disparadas por **uma** busca | **14** — constante (mesmo com 0 resultados, size=1 ou size=100) |
| Linhas lidas do Postgres por busca de 20 itens | **3.637** — idêntico na 2ª requisição repetida |
| JSON devolvido para 20 itens | **190 KB** (101 KB sem indentação) |

Orçamento aproximado de uma busca de 20 itens (~44 ms no servidor):

```
~15 ms  custo FIXO por requisição  ── 14 idas ao Solr (ida/volta HTTP), das quais ~13 são redundantes
~29 ms  custo POR ITEM (~1,45 ms × 20) ── dominado por leitura no Postgres
 ~0 ms  trabalho real do Solr na consulta (0,33 ms)
```

E, no navegador, a página de busca faz **1 requisição** — o N+1 do frontend que este documento chegou a apontar **não existe** (ver a correção na seção 3.5).

---

## 2. Como a busca funciona hoje

### 2.1 Fluxo de uma requisição

`GET /server/api/discover/search/objects` (o que a UI usa na caixa de busca e nas listagens):

1. `DiscoveryRestController.getSearchObjects` (`dspace-server-webapp/.../DiscoveryRestController.java:133`)
2. `DiscoveryRestRepository.getSearchObjects` (`.../rest/repository/DiscoveryRestRepository.java:92`)
   - resolve o escopo (`ScopeResolver`)
   - carrega a `DiscoveryConfiguration` do `discovery.xml` (bean `defaultConfiguration`)
   - `RestDiscoverQueryBuilder.buildQuery` → `DiscoverQueryBuilder.buildQuery` monta `DiscoverQuery` (paginação, ordenação, facetas, filtros, highlight)
   - `searchService.search(context, scopeObject, discoverQuery)` — **uma** chamada
3. `SolrServiceImpl.retrieveResult` (`dspace-api/.../discovery/SolrServiceImpl.java:988`)
   - `solrSearchCore.getSolr().query(...)` — a consulta ao Solr
   - para cada documento: `findIndexableObject` → `itemService.find(context, uuid)` (**1 SELECT por resultado**)
   - `resolveFacetFields` / `resolveJsonFacetFields`
4. `DiscoverResultConverter.convert` → `SearchResultsResource` → HAL/JSON
5. `ItemConverter.convert` por item, que chama `getPermissionFilteredMetadata` (`ItemConverter.java:76`)

### 2.2 Parâmetros enviados ao Solr (config `default`, anônimo)

| Parâmetro | Valor |
|---|---|
| `q` | `*:*` sem termo; senão o texto |
| `fq` | `(search.resourcetype:Item AND latestVersion:true)`, `-withdrawn:true`, `-discoverable:false`, `(read:(g0) OR admin:(g0))` |
| `fq` extra | `location:(m<uuid> OR l<uuid>)` para permissões herdadas |
| `fl` | `search.resourcetype, search.resourceid, search.uniqueid, database_status` |
| `rows` | 20 (teto `rest.search.max.results` = 100) |
| `sort` | `dc.date.accessioned_dt desc` |
| `facet.field` | `author_filter`, `subject_tax_0_filter`, `dateIssued.year`, `entityType_filter`; `facet.limit=5`, `facet.mincount=1` |
| highlight | `hl=true`, `hl.fl=*_hl`, `fragsize=0` (ilimitado) exceto abstract (250), `snippets=5` |
| `spellcheck` | **não é enviado** |

### 2.3 Volume indexado

2.253 itens · 66.340 valores de metadados · índice Solr: 2.558 documentos, 24 MB, 6 segmentos.

O índice é pequeno e cabe em memória — por isso o Solr responde em microssegundos.

---

## 3. Onde o tempo é gasto (evidências)

### 3.1 As 14 consultas ao Solr por busca — medido

> **Resolvido** (2026-10-14): as 14 consultas viraram **2** (1 principal + 1 de localização) no caminho quente. O diagnóstico abaixo é o retrato de antes e continua válido como evidência; a solução e as alternativas descartadas estão em `pcirn-busca-plano-otimizacao.md`, seção P1.

Contagem exata via métrica do Solr (`/solr/admin/metrics?prefix=QUERY`), delta por requisição:

```
size=1                            14.00 selects/busca
size=20 (default)                 14.00 selects/busca
size=100                          14.00 selects/busca
query sem resultados              14.00 selects/busca
size=20 &embed=thumbnail          14.00 selects/busca
```

**14 não é aleatório.** A configuração `default`, para usuário não-admin, faz **7 buscas lógicas**:

| # | Origem |
|---|---|
| 1 | consulta principal (`SolrServiceImpl.retrieveResult`) |
| 2 | `FacetYearRange` do `dateIssued` (asc + desc) |
| 2 | `calculateExtremeValue` min/max do `author` (`DiscoverFacetsConverter.java:118-133`) |
| 2 | `calculateExtremeValue` min/max do `dateIssued` |

E **cada** busca lógica é **duplicada** por `SolrServiceResourceRestrictionPlugin.additionalSearchParameters` (`dspace-api/.../discovery/SolrServiceResourceRestrictionPlugin.java:175-183`), que chama `SolrServiceImpl.createLocationQueryForAdministrableDSOs` (`SolrServiceImpl.java:610`) — uma **consulta Solr completa e independente** (`SolrQuery` próprio, com `setRows(Integer.MAX_VALUE)`) para descobrir em quais comunidades/coleções o usuário é admin.

Para **anônimo** (`epersonAndGroupClause = "g0"`), `admin:(g0)` nunca retorna nada: a consulta é executada e descartada 14 vezes por página.

A decomposição das 7 buscas lógicas vem da configuração (`discovery.xml:2752` e `:2796` com `exposeMinAndMaxValue=true`) somada ao código — e fecha exatamente com as 14 medidas.

**Confirmação independente do padrão "×2":** o endpoint de uma única faceta, que faz **1** busca lógica, mede **2** selects no Solr:

```
GET /api/discover/facets/author?query=teste     → 2.00 selects Solr
GET /api/discover/browses/dateissued/items      → 4.00 selects Solr
```

Ou seja: o multiplicador por requisição de localização é real e mensurável em qualquer endpoint do Discovery.

Confirmado em thread dump durante carga — pilha real capturada:

```
org.dspace.discovery.SolrServiceImpl.createLocationQueryForAdministrableDSOs
  ← org.dspace.discovery.SolrServiceResourceRestrictionPlugin.additionalSearchParameters
```

Distribuição de threads de requisição paradas em I/O de rede: **20,8 % esperando Solr**, 15,0 % esperando Postgres.

### 3.2 O banco: 3.637 linhas por busca, e o cache não ajuda

Delta de `pg_stat_user_tables` para **uma** busca (`query=transparencia`, 20 itens), medido duas vezes seguidas:

| tabela | req. 1 | req. 2 (idêntica) | seq_scan | idx_scan |
|---|---|---|---|---|
| `metadatafieldregistry` | **3.069** | **3.069** | 11 / 11 | 0 / 0 |
| `metadataschemaregistry` | 210 | 210 | 0 / 0 | 210 / 210 |
| `metadatavalue` | 210 | 210 | 0 / 0 | 11 / 11 |
| `resourcepolicy` | 88 | 88 | 0 / 0 | 55 / 55 |
| `dspaceobject` | 24 | 24 | 0 / 0 | 38 / 38 |
| `epersongroup` | 20 | 20 | 2 / 2 | 0 / 0 |
| `item` | 16 | 16 | 0 / 0 | 16 / 16 |
| **total** | **3.637** | **3.637** | | |

Três conclusões:

1. **84 % das linhas lidas** (3.069 de 3.637) são varreduras sequenciais completas de `metadatafieldregistry` — uma tabela de **279 linhas que praticamente não muda** (11 varreduras por requisição).
2. Os 210 valores reais de metadados (`metadatavalue`) são só 6 % do tráfego.
3. A repetição idêntica lê **exatamente o mesmo** — ou seja, **o cache de 2º nível do Hibernate não traz ganho entre requisições**, apesar de estar configurado (`hibernate.cache.use_second_level_cache=true`, `MetadataField`/`MetadataSchema` com `@Cacheable` e regiões de 3600 s no `hibernate-ehcache-config.xml`).

   Motivo: os acessos são **queries HQL/Criteria** (`AbstractHibernateDAO.executeCriteriaQuery`), e não cargas por ID. O cache de entidades não cobre queries, e `hibernate.cache.use_query_cache=true` só vale para queries marcadas com `setCacheable(true)`.

Também aparecem como N+1 por item: `itemService.find` (1 SELECT por resultado, `SolrServiceImpl.java:1014`), `Collection.getCommunities` (lazy, por item) e `resourcepolicy` (checagem de permissão por item).

### 3.3 Exceções como fluxo de controle, por item

`ItemConverter.getPermissionFilteredMetadata` (`dspace-server-webapp/.../converter/ItemConverter.java:85`) chama `itemService.canEdit` → `authorizeService.authorizeActionBoolean` → `authorizeAction`, que **lança `AuthorizeException`** no caminho de negação (`AuthorizeServiceImpl.java:177`), capturada logo acima (`:185`).

Para usuário anônimo é sempre negação, então **cada item de cada página constrói e lança exceção** — com `Throwable.fillInStackTrace`. Pilha capturada:

```
java.lang.Throwable.fillInStackTrace
  ← org.dspace.authorize.AuthorizeException.<init>
  ← org.dspace.authorize.AuthorizeServiceImpl.authorizeAction(AuthorizeServiceImpl.java:177)
  ← org.dspace.content.ItemServiceImpl.canEdit(ItemServiceImpl.java:1240)
  ← org.dspace.app.rest.converter.ItemConverter.getPermissionFilteredMetadata(ItemConverter.java:85)
```

### 3.4 Auto-flush/dirty-check em requisição somente-leitura

Antes de cada query, o Hibernate dispara `DefaultAutoFlushEventListener` e faz *dirty check* de **todas** as entidades carregadas no `Context`:

```
org.hibernate.persister.entity.DirtyHelper.isDirty
  ← DefaultFlushEntityEventListener.performDirtyCheck
  ← DefaultFlushEntityEventListener.onFlushEntity
  ← AbstractFlushingEventListener.flushEverythingToExecutions
  ← SessionImpl.autoFlushIfRequired
  ← ConcreteSqmSelectQueryPlan
```

Somando `DirtyHelper.isDirty`, `AbstractEntityPersister.getPropertyValues`, `Cascade`, `CascadeStyles$MultipleCascadeStyle.hasOrphanDelete` e `getOrphans`, são **~9–10 % das amostras de thread** gastas checando se algo mudou — em um caminho que só lê.

### 3.5 ~~O N+1 do frontend~~ — CORRIGIDO: o N+1 **não** acontece

> **Correção (2026-10-13).** Esta seção afirmava que a UI descartava o `indexableObject` embutido e refazia a busca item a item, gerando ~21 requisições por página. **Isso está errado** — a afirmação foi inferida da leitura do código, sem medir. A medição contra os logs reais do servidor desmente:

| Origem | Requisições |
|---|---|
| Buscas vindas do navegador (`/home`, `/search`, `/collection-list`, `/community-list`, `/mydspace`) | ~**907** |
| `GET /server/api/core/items/{uuid}` vindas do navegador | **81** |
| `GET /server/api/discover/facets/{name}` (total, qualquer origem) | 220 |

Isso é ~**0,09 requisição de item por busca**. Se a UI refizesse os 20 itens de cada página, seriam ~18.000.

**Por que o código não gera requisições:** `directlyAttachIndexableObjects` (`search.service.ts:227-278`) realmente chama `findByHref` por resultado, mas `DspaceRestResponseParsingService` já registra cada `indexableObject` embutido no cache, indexado pelo seu próprio `self` href (`search-response-parsing.service.ts:42-47`, via `addToObjectCache`). Com `useCachedVersionIfAvailable=true`, o `findByHref` vira **cache hit** e o `RequestService.send` não faz HTTP.

O custo restante é de CPU no navegador (montar 20 Observables por página), não de rede — e não foi medido como problema. A ação P3 está **cancelada**.

### 3.6 Payload

190 KB para 20 itens, dos quais **46,8 % é indentação** de JSON (101 KB minificado). Não é gargalo de CPU no servidor (`com.fasterxml.jackson` aparece em apenas 0,9 % das amostras). O custo é de rede e de parse no navegador — pequeno, já que a página faz uma única requisição de busca (ver a correção na seção 3.5). Não foi encontrada a chave de configuração que liga a indentação.

---

## 4. Melhorias priorizadas

Ordenadas por (impacto ÷ esforço). Nenhuma alteração foi feita — este documento é diagnóstico.

### P1 — Eliminar as consultas Solr redundantes · backend · baixo esforço · alto impacto

1. **Cachear por requisição** `createLocationQueryForAdministrableDSOs` (`SolrServiceImpl.java:610-648`): o resultado depende só do conjunto de grupos do usuário, não da query. Guardar no `Context` derruba **14 → 7** chamadas. Para anônimo, pode ser resolvido sem ir ao Solr.
2. **Trazer min/max das facetas na consulta principal** com o `stats.component` / `facet.range` do Solr, em vez de `calculateExtremeValue` (2 selects por faceta) — `DiscoverFacetsConverter.java:118-133`.
3. **`FacetYearRange` (2 selects no `dateIssued`)** → `facet.range`, na mesma consulta.

**Ganho esperado:** 14 → 1–3 selects por busca, economizando ~10–13 ms dos ~44 ms (**~25–30 % do tempo de servidor**).

### P2 — Cachear o registro de metadados · backend · baixo/médio esforço · alto impacto

3.069 das 3.637 linhas lidas (84 %) vêm de varreduras de `metadatafieldregistry`.

Opções (a decidir na implementação):
- marcar as queries de `MetadataField`/`MetadataSchema` como `setCacheable(true)` e confirmar que a região de cache é populada; **ou**
- cache em memória do mapeamento `(schema, element, qualifier) → MetadataField`, invalidado na escrita do registro (é dado de referência, muda raríssimo).

**Ganho esperado:** −84 % de linhas lidas e −11 idas ao banco por busca.

### ~~P3 — Corrigir o N+1 do frontend~~ · CANCELADA

A premissa estava errada: a UI **não** refaz a busca item a item, e as facetas já vêm na resposta principal. Medição nos logs reais na seção 3.5 — ~0,09 requisição de item por busca. Não há o que corrigir aqui.

### P4 — Remover exceções e checagens repetidas por item · backend · baixo esforço

- Substituir o caminho de exceção de `authorizeActionBoolean` por uma checagem que retorne booleano (`AuthorizeServiceImpl.java:177/185/198`).
- Evitar `Collection.getCommunities` lazy por item (carregar em lote).
- Reaproveitar `isAdmin(context)` uma vez por requisição, não por item.

**Ganho esperado:** poucos ms por requisição e menos pressão de GC.

### P5 — Modo somente-leitura no caminho de busca · backend · médio esforço

`FlushMode.MANUAL` (ou `setDefaultReadOnly(true)`) no `Context` das requisições de busca elimina o auto-flush/dirty-check — **~9–10 %** das amostras de CPU.

### P6 — Reduzir o payload · baixo esforço

Desligar a indentação do JSON na serialização (46,8 % dos bytes). Ganho pequeno no servidor, relevante no navegador — e multiplicado pelo item P3.

---

## 5. O que *não* é o problema

Para evitar trabalho inútil:

- **Tuning do Solr / tamanho de heap / segmentos / merge.** A consulta custa 0,33 ms de média; o índice tem 24 MB e 6 segmentos.
- **Índices faltando no Postgres.** `metadatafieldregistry` *tem* índices (`metadatafield_schema_idx`, `metadatafieldregistry_idx_element_qualifier`); o planejador escolhe seq scan porque a tabela tem 279 linhas — e essa é a escolha correta. O problema é a **quantidade de idas**, não o plano.
- **Disco.** Durante os testes não houve leitura de disco: tudo veio de `shared_buffers` (`blks_read = 0`).
- **`numFound` exato.** Não há `numFoundExact`, mas com 2.253 documentos a contagem é irrelevante.
- **`spellcheck`.** Não é enviado ao Solr no caminho REST.
- **Serialização no servidor.** Jackson responde por 0,9 % das amostras.

---

## 6. Como reproduzir as medições

```bash
# custo fixo vs por item
for s in 1 5 10 20 50 100; do
  /usr/bin/time -f "size=$s %e s" curl -s -o /dev/null \
    "http://localhost:8501/server/api/discover/search/objects?size=$s"
done

# quantas consultas Solr por busca (delta do contador)
curl -s "http://localhost:8984/solr/admin/metrics?group=core&prefix=QUERY./select.requests&wt=json"
# ... rodar N buscas ...
curl -s "http://localhost:8984/solr/admin/metrics?group=core&prefix=QUERY./select.requests&wt=json"

# tempo do Solr (média/p99)
curl -s "http://localhost:8984/solr/admin/metrics?group=core&prefix=QUERY&wt=json"

# linhas lidas do banco por busca
docker exec dspacedb psql -U dspace -d dspace -tAF'|' -c \
  "select relname,seq_scan,seq_tup_read,idx_scan,coalesce(idx_tup_fetch,0) from pg_stat_user_tables;"
# ... rodar 1 busca, esperar ~2,5 s (flush das estatísticas), medir de novo ...

# perfil de CPU/bloqueio
docker exec dspace jcmd 1 Thread.print
```

### Como validar cada correção

Medir **antes e depois, com o mesmo comando e a mesma carga**:

- P1: contador `QUERY./select.requests` por busca deve cair de **14** para **1–3**.
- P2: `seq_tup_read` de `metadatafieldregistry` por busca deve cair de **3.069** para próximo de **0**.
- P3: uma página de busca deve gerar **1–2** requisições no DevTools (Network).
- P4/P5: contagem de `fillInStackTrace` e `DirtyHelper.isDirty` nas amostras de thread dump.

---

## 7. Observações

- As medições foram feitas na instância de **homologação**, que tem uso real concorrente (havia um usuário editando submissão durante os testes). Os números de latência variam ±20 % entre execuções; as contagens (14 selects, 3.637 linhas) são determinísticas e reprodutíveis.
- Os testes de carga (`xargs -P 12..16`) foram executados em janelas curtas (~4–8 s) e encerrados.
- A árvore principal está customizada (config `default` com `defaultFilterQueries` PCIRN, `defaultSortField=sortDateAccessioned`, 2 facetas com `exposeMinAndMaxValue=true`). Existem worktrees em `.worktrees/*` com cópias desses arquivos; todas as referências aqui são da árvore principal.

# Plano de otimização da busca — PCIRN

**Data:** 2026-10-13
**Base:** [pcirn-busca-diagnostico.md](pcirn-busca-diagnostico.md) (desempenho) + [pcirn-busca-sintaxe.md](pcirn-busca-sintaxe.md) (sintaxe e qualidade)

Este é o backlog executável. Os itens **P1–P6** vêm do diagnóstico de desempenho, os itens **O7–O12** da análise de sintaxe/qualidade, e os itens **R1–R2** da revisão de relevância. Cada um traz a evidência medida, o ganho esperado e como validar.

### Princípio de ordem

Três dos itens (**O7, O8, O9**) mudam o **analisador** e o **`copyField`** do Solr, e por isso exigem **reindexação completa**. Eles devem ir juntos, numa **única reindexação**. Todo o resto é feito sem reindexar e pode entrar antes — inclusive **R1**, que é a melhoria de maior impacto na qualidade da busca e já está aplicada.

---

## Fase 0 — Relevância da busca (R1) ✅ APLICADO

### R1 — Ordenar por relevância, e não por data

**O problema.** A configuração `default` do `discovery.xml` forçava a ordenação:

```xml
<!--PCIRN: por padrão, últimos itens adicionados primeiro-->
<property name="defaultSortField" ref="sortDateAccessioned" />
```

Consequência medida: buscar `portaria` devolvia em primeiro lugar o **documento adicionado mais recentemente**, independentemente de quão bem ele casava com o termo. Confirmei que os resultados vinham exatamente em ordem decrescente de `dc.date.accessioned`. Num motor de busca, esse é o defeito mais grave possível — a relevância simplesmente não era usada.

**A correção, em dois pontos:**

1. **`discovery.xml`:** removido o `defaultSortField` **e movido `sortScore` para o primeiro lugar da lista**. As duas coisas são necessárias, por causa de como o DSpace resolve o default em `DiscoverQueryBuilder.getDefaultSortField`: sem `defaultSortField`, ele olha o **primeiro item de `sortFields`** — se esse item tiver `metadataField` em branco, o default é `"score"`. Ou seja, com `sortScore` em primeiro lugar a busca ordena por relevância; se `sortDateAccessioned` ficasse em primeiro, o resultado seria a data de novo, só que por um caminho diferente. `getDefaultSortDirection` também usa o primeiro item, e `sortScore` declara `desc`, então a ordenação sai como `score desc`.
2. **`SolrServiceImpl.resolveToSolrQuery`:** quando a ordenação é `score`, acrescento `dc.date.accessioned_dt desc` como **critério secundário**. Isso importa porque uma busca vazia pontua todos os documentos igualmente: sem desempate, a navegação (a home, a lista de uma coleção) voltaria em ordem arbitrária. Com ele, a relevância manda quando há termo e "mais recente primeiro" continua valendo na navegação — preservando a intenção original da customização PCIRN.

**Verificado direto no Solr:** `sort=score desc,dc.date.accessioned_dt desc` devolve, para `portaria`, documentos com "PORTARIA" no título, e as datas vêm fora de ordem — o que comprova que o score domina e a data só desempata.

**Não exige reindexação:** ordenação é decidida em tempo de consulta. Exige apenas o deploy (o `discovery.xml` é lido na inicialização).

**Como validar depois:** buscar um termo e conferir que o topo tem o termo no título; e que a navegação sem termo continua trazendo os últimos adicionados.

### R2 — Remover os sinônimos de demonstração ✅ APLICADO

O `synonyms.txt` era a lista de exemplo do Solr — `GB,gib,gigabyte,gigabytes`, `Television, Televisions, TV, TVs`, `pixima => pixma`, `aaa => aaaa`, `bbb => bbbb1 bbbb2`, `ccc => cccc1,cccc2` — sem nenhuma relação com o acervo. Entradas assim só produzem casamentos espúrios e nunca foram uma escolha deliberada.

Substituído por um arquivo limpo, com o formato documentado e uma orientação para que se cadastrem ali apenas siglas e variantes que existam de fato no acervo.

**Efeito imediato, sem reindexação:** o `SynonymFilterFactory` está apenas no analisador de **consulta**; o de índice não usa o arquivo. Basta recarregar o core do Solr.

---

## Resumo

| ID | Problema | Evidência medida | Ganho | Esforço | Reindex? |
|---|---|---|---|---|---|
| **R1** | A busca **não usava relevância**: ordenava por data de entrada | Buscar "portaria" devolvia o mais recente, não o mais relevante; `defaultSortField` forçado para `sortDateAccessioned` | **Maior ganho de qualidade** — a busca passa a ranquear por relevância | Baixo | Não |
| **P1** | 14 consultas Solr por busca, 12 delas evitáveis | 14 selects/busca no contador do Solr; log de requisições mostra 7 buscas lógicas × 2 | **14 → 8 → 2** consultas por busca; ~2× de vazão sob carga ✅ concluído e medido em homologação | Baixo | Não |
| **P2** | 84 % das linhas lidas são o registro de metadados | 3.069 de 3.637 linhas/busca | −84 % de leitura no banco | Baixo/Médio | Não |
| **P3** | ~~Frontend refaz a busca item a item~~ **PREMISSA ERRADA** | Medido nos logs: ~907 buscas de navegador contra 81 requisições de item (~0,09/busca). Não é N+1 | **Nenhum — cancelada** | — | — |
| **P4** | ~60 consultas de política por página (várias por item) | `ResourcePolicyDAOImpl` é o call site de banco mais frequente; ~55 varreduras em `resourcepolicy` por página | **Prefetch em lote: ~60 → 3 consultas** ✅ aplicado | Médio | Não |
| **P5** | Auto-flush/dirty-check em requisição de leitura | ~9–10 % das amostras de CPU | ~9 % de CPU | Médio | Não |
| **P6** | JSON indentado | medido numa página de busca real: 162 KB → 94 KB compactado, **42 % são espaços** | rede + parse no navegador | Baixo | Não |
| **O7** | Stemming em **inglês** sobre texto português | `manuais`=15 vs `manual`=31 não unificavam; agora ambos devolvem **42** | unifica plurais regulares **sem** over-stemming ✅ **no ar** (reindexado) | Baixo | **Sim** |
| **O8** | Stopwords de **36 palavras em inglês**, aplicadas na indexação | Não continha `a`/`o`/`e`/`de`/`com` — as mais frequentes do português, indexadas em 1.291 a 2.562 documentos. Depois: **0** em todas ✅ **no ar** | precisão + menos tokens | Baixo | **Sim** |
| **O9** | Campos internos vazam para o `search_text` | `search_text:item`: 2.257 → **30** ✅ **no ar**; `handle` continua encontrável | precisão; menos ruído | Médio | **Sim** |
| **O10** | `**` sem efeito e 422 por aspas soltas | `"notas tecnicas` → HTTP 422; `operacao%%`=13 | fecha aspas e colapsa curingas ✅ aplicado e **no ar** | Baixo | Não |
| **O11** | ~~Página de busca sem tratamento de erro~~ **JÁ EXISTIA** — minha afirmação estava errada | `search-results.component` já trata 422 com mensagem dedicada | mensagem pt-BR reescrita ✅ **no ar** | Baixo | Não |
| **O12** | Curinga à esquerda/fuzzy não escalam | **hoje**: QTime ~0 ms (não é gargalo) | proteção futura | Baixo | Não |
| **R2** | Sinônimos eram a lista de demonstração do Solr | `Television, Televisions, TV, TVs`; `aaa => aaaa`; `pixima => pixma` | remove casamentos espúrios ✅ **no ar** (`Televisions`: 4 → 0) | Baixo | Não |

---

## Estado da publicação na homologação (2026-10-14)

**Tudo o que está no ar agora vem de imagem própria** — não há mais bind mount de host nem arquivo copiado à mão, então recriar um container não desfaz nada.

| Item | No ar? | Imagem | Como |
|---|---|---|---|
| P1, P4 (código) | ✅ | `itep/dspace:search-p1` | derivada de `itep/dspace:restored-20260930` com as classes do working tree em `/dspace/overrides` e `LOADER_PATH` (**vírgula**) gravado na própria imagem |
| R1 (config da busca) | ✅ | — | `discovery.xml` no volume `d9_config` |
| R2 (sinônimos) | ✅ | `itep/dspace-solr:search-o7o8o9` | imagem construída a partir de `dspace/src/main/docker/dspace-solr/Dockerfile`, com o configset do repositório embutido |
| O7, O8, O9 | ✅ | `itep/dspace-solr:search-o7o8o9` | reindexação completa: **2.562 documentos em 1 minuto** |
| O10, O11 (Angular) | ✅ | `itep/dspace-angular:search-o10` | derivada da imagem em uso com os três arquivos do working tree; o dev server recompila no start |

Receitas das imagens derivadas: `.estabilizacao-backup/runtime/Dockerfile.dspace-overlay` e `Dockerfile.angular-o10`. O `docker-compose.recovery.yml` já aponta para as três imagens novas.

**O que ainda não é definitivo:** as duas imagens derivadas dependem de imagens-base que só existem nesta máquina (`itep/dspace:restored-20260930` e `itep/dspace-angular:institutional-links-20261006`). A do Solr é reprodutível a partir do repositório; para backend e Angular o caminho definitivo é construir do repositório (o `Dockerfile` da raiz e o do submodule).

Reversão:

```bash
docker compose -f .estabilizacao-backup/docker-compose.recovery.yml down
# edite docker-compose.recovery.yml de volta para os tags originais:
#   itep/dspace:restored-20260930 | itep/dspace-angular:institutional-links-20261006 | docker.io/dspace/dspace-solr:dspace-9_x
docker compose -f .estabilizacao-backup/docker-compose.recovery.yml up -d
# ATENCAO: voltar o Solr ao schema antigo exige reindexar de novo (o indice atual esta no formato novo)
```

Cópias do estado anterior: `.estabilizacao-backup/angular-antes-o10/` (Angular) e `.estabilizacao-backup/discovery.xml.antes-do-deploy-search` (config da busca).

**Achado à parte, fora do escopo da busca:** o servidor do container do Angular responde `Cannot GET /search` (404 do Express) para qualquer rota que não seja `/`. Link direto, refresh e URL compartilhada de uma página interna não funcionam; a navegação a partir da home funciona. É da configuração do servidor SSR (imagem `itep/dspace-angular:institutional-links-20261006`, de outro fluxo) e é **pré-existente** — conferido antes de eu tocar no container.

---

## Fase 1 — Backend, sem reindexar

### P1 — Eliminar as consultas Solr redundantes

> **Status: CONCLUÍDO** (2026-10-14) — ações 1, 2 e 3 entregues **sem reindexação e sem mudança de schema**. O caminho que este plano previa para as ações 2 e 3 (schema + `stats` + reindexação) foi medido e **rejeitado**; a justificativa está logo abaixo.

Contagem medida ao vivo, pelo contador `QUERY./select.requests` do core `search`, numa busca anônima de uma página: **14 consultas**. O log de requisições do Solr mostra que são **7 buscas lógicas, cada uma precedida pela consulta de "location"**:

| # | Consulta enviada ao Solr | Vezes | Para quê |
|---|---|---|---|
| L | `(Community OR Collection)` + `admin:(e… OR g…)`, `rows=2147483647` | **7** | descobrir as comunidades e coleções que o usuário administra |
| 1 | busca principal (`q=portaria`, com facetas) | 1 | os resultados |
| 2 | `q=*:*`, `fq=dateIssued.year:[* TO *]`, `sort=dateIssued.year_sort asc`, `rows=1` | 1 | ano mais antigo do intervalo da faceta de data |
| 3 | idem, `sort=… desc` | 1 | ano mais recente |
| 4‑7 | `author_min_sort asc`, `author_max_sort desc`, `dateIssued_min_sort asc`, `dateIssued_max_sort desc` | 4 | mínimo e máximo das facetas com `exposeMinAndMaxValue` |

As consultas 2 a 7 são as **consultas de limite**: não dependem do texto pesquisado, só do índice e das permissões de quem pergunta. A consulta L, ao contrário, é a que mais custa — ela roda com `rows=2147483647` (todas as comunidades e coleções administráveis) e rodava **uma vez por busca lógica**.

#### Ação 1 — memoizar a consulta de "location" por `Context` ✅

Implementada como memoização por `Context` (`Context.cacheRequestValue` / `getCachedRequestValue`), com chave derivada da cláusula de eperson e grupos — portanto correta mesmo se o usuário mudar no meio do contexto.

- A assinatura passou a receber o `Context`; os 2 chamadores (`SolrServiceResourceRestrictionPlugin`, `EntityTypeServiceImpl`) foram atualizados.
- Coberta por `SolrServiceImplAdministrableLocationsTest` (3 testes: chamada única por Context, cláusulas distintas não compartilham cache, resultado vazio também é memoizado).
- **Ganho: 14 → 8 consultas.**

#### Ações 2 e 3 — as seis consultas de limite ✅ (por outro caminho)

O plano previa trocá-las por `stats.field` — 1 consulta para a faixa de ano e 1 para os mínimos e máximos —, o que exigia tornar o ano numérico, dar `docValues` aos campos de limite e **reindexar**. Medido contra o Solr da homologação, esse caminho não se sustenta:

| Tentativa | Resultado medido |
|---|---|
| `stats.field` em `dateIssued.year_sort`, `dateIssued.year`, `author_min_sort`, `author_max_sort`, `dateIssued_min_sort`, `dateIssued_max_sort` | **HTTP 400** em todos: *"Field type lowerCaseSort{class=org.apache.solr.schema.TextField…} does not support statistics"* |
| `docValues="true"` no tipo `lowerCaseSort` (faria o `stats` funcionar) | **Mudaria o valor que a API devolve hoje.** Os `docValues` são gravados **antes** do analisador, então `author_min_sort` guardaria a caixa original (`'DE DIREÇÃO'`) enquanto o termo indexado é minúsculo. Por `docValues`, o máximo do `author` seria `test2, test2` (maiúsculas ordenam antes de minúsculas) e não `Testing, Works` — exatamente o que o IT `DiscoveryRestControllerIT.discoverSearchObjectsTestForMinMaxValues` fixa. Além disso, `docValues` não se derivam de segmentos já escritos: exigiria reindexação. |
| `facet.offset=-1` (para obter o maior valor numa única requisição) | **HTTP 500** *"Exception during facet.field"* em todos os campos testados |
| `facet.limit=-1` em `dateIssued_min_sort` / `dateIssued_max_sort` | Funciona, mas devolve **1009** datas distintas — resposta maior do que as duas consultas que substituiria |
| `facet.field=dateIssued.year_sort&facet.limit=-1&facet.sort=index` para a faixa de ano | **Equivalente** ao par ordenado (1959 e 2026 conferidos dos dois lados), mas economiza **uma** consulta e teria de passar pelo encanamento de facetas do `DiscoverQuery` |

**O caminho adotado:** como as seis consultas de limite não dependem da busca, elas são **memorizadas entre requisições**.

- `BoundaryValueCache` — cache curto, por JVM, para valores que descrevem apenas os limites de um conjunto de resultados. Cada entrada guarda o instante em que foi criada, o cache é limitado a 1000 entradas e é **invalidado por inteiro** em toda operação de indexação (`update`, `unIndexContent`, `deleteIndex`, `atomicUpdate`).
- **Chave.** O valor é resolvido já com o filtro de permissão do usuário, então a chave começa pela identidade de quem pergunta (`SolrServiceImpl.permissionScope`: a eperson, ou `anonymous`, mais os grupos especiais do `Context`) e termina no que a consulta tem de específico:
  - mínimos e máximos: `campo | campo de ordenação | direção`;
  - faixa de ano: `faceta | escopo (comunidade/coleção ou repositório) | configuração de busca | filtros selecionados`.
- **Validade.** TTL de 60 s. Na mesma JVM a indexação invalida na hora; o TTL cobre apenas o que outro processo (uma reindexação por linha de comando, por exemplo) tenha mudado. O que pode ficar defasado por até 60 s são apenas os **limites**: as contagens das facetas continuam sendo calculadas a cada busca.
- O que **não** foi feito: nada de schema, nada de reindexação, e nenhuma mudança nos valores que a API devolve — as mesmas consultas continuam sendo feitas, só não a cada busca.

#### Resultado

| Cenário | Consultas Solr por busca |
|---|---|
| Antes | **14** |
| Só a ação 1 (localização memoizada) | 8 |
| Ações 1 a 3, primeira busca (cache frio) | 8 |
| Ações 1 a 3, buscas seguintes (cache quente) | **2** (1 principal + 1 de localização) |

O cenário quente vale para qualquer busca anônima sem filtros — o caso dominante. Uma busca com filtros tem uma faixa de ano por combinação de filtros, e um usuário autenticado tem os seus próprios limites; nos dois casos o custo cai para o mesmo par principal + localização depois da primeira busca daquela combinação.

**Como validar:** delta de `QUERY./select.requests` por busca — 14 antes, 8 na primeira, 2 nas seguintes.

**Verificado:**
- 12 testes novos (`BoundaryValueCacheTest`, `SolrServiceImplBoundaryValuesTest`), suíte unitária completa do `dspace-api` com **1427 testes, 0 falhas**, Checkstyle limpo.
- **Ponta a ponta, na homologação:** 14 antes, **8** na primeira busca e **2** nas seguintes, medidos no contador do Solr.

#### Medição ponta a ponta na homologação (2026-10-14)

As classes foram publicadas sem reconstruir a imagem: `dspace-api/target/classes` e `dspace-server-webapp/target/classes` montados como *overlay* de classpath (`-Dloader.path=...`) e o container `dspace` recriado. Reverter é subir de novo a partir de `.estabilizacao-backup/docker-compose.recovery.yml` sem o arquivo de overlay.

| Cenário | Consultas por busca | Mediana de 1 busca | 40 buscas, concorrência 10 |
|---|---|---|---|
| Código anterior | **14** | 114 ms | 1821 / 1103 / 1123 ms |
| Com o P1 | **2** | 100 ms | 592 / 497 / 511 ms |

Leitura honesta: **a latência de uma busca isolada quase não muda** (114 → 100 ms). As idas ao Solr custavam ~0,2 ms de `QTime` cada e a rede é local, então tirá-las de um caminho ocioso não se nota. O ganho aparece **sob carga**, quando o custo por requisição disputa CPU: as mesmas 40 buscas caíram de ~1,1 s para ~0,5 s — **cerca de 2× mais vazão**. É o cenário que importa para o repositório, e é o que confirma que o trabalho de eliminar 12 idas redundantes ao Solr por busca valeu a pena.

Confirmado também que os valores devolvidos não mudaram: o `author` continua voltando com a caixa original (`DE DIREÇÃO` / `Secretaria de Segurança Pública/RN`) e a faixa de `dateIssued` continua a mesma — exatamente o que a rota `stats`/`docValues` teria alterado.

> **Achado de infraestrutura:** o `LOADER_PATH` do `docker-compose.dev.yml` usava `:` como separador, mas o `PropertiesLauncher` do Spring Boot 3.5 divide `loader.path` por **vírgula** — conferido no bytecode (`parsePathsProperty`) e no log com `-Dloader.debug=true`: com `:` o Spring trata a string inteira como um único caminho (`Nested archive paths: [/dspace/overrides/additions:/dspace/overrides/server:…]`) e **não coloca nada no classpath**. O overlay de classes documentado no repositório, portanto, nunca funcionou. Corrigido.

> **Bug latente que continua aberto:** `<dynamicField name="*_year" type="sint"/>` **nunca casa** com `dateIssued.year`, porque o separador é ponto e não underscore. O campo cai em `<dynamicField name="*" type="text"/>` e os anos estão indexados como texto — o que funciona por acaso (4 dígitos ordenam lexicograficamente igual a numericamente). Só incomoda quem quiser `facet.range`/`stats` sobre anos, e a correção exige reindexação.

### P2 — Cachear o registro de metadados

> **Status: REAVALIADA — prioridade reduzida** (2026-10-13).

3.069 das 3.637 linhas lidas por busca são 11 varreduras completas de `metadatafieldregistry` (279 linhas). A 2ª requisição idêntica lê **exatamente o mesmo** — o cache de 2º nível do Hibernate não cobre esses acessos porque são *queries* (`AbstractHibernateDAO.executeCriteriaQuery`), não cargas por ID.

**Porém: contagem de linhas ≠ tempo.** Essas 3.069 linhas estão todas em `shared_buffers` (`blks_read = 0`) e **não aparecem nos thread dumps** como bloqueio. Os pontos onde as threads realmente esperam são outros (Solr, políticas de permissão por item, auto-flush do Hibernate). O ganho de latência desta ação é provavelmente pequeno, ainda que a redução de tráfego no banco seja real.

Opções, se for retomada: marcar as queries de `MetadataField`/`MetadataSchema` como `setCacheable(true)` — `find` e `findByElement` **já usam** `org.hibernate.cacheable` e um mapa `cachedFields` —, **ou** manter em memória o mapa `(schema, element, qualifier) → MetadataField`.

**Como validar:** `seq_tup_read` de `metadatafieldregistry` por busca deve ir de **3.069 → ~0**.

### P4 — Remover exceções e checagens repetidas por item

> **Status: prefetch de políticas APLICADO; parte das exceções revertida** (2026-10-13).

- ❌ **Caminho de exceção de `authorizeActionBoolean` — revertido.** O defeito é real: `authorizeActionBoolean` chamava `authorizeAction` (que lança `AuthorizeException` na negação) e capturava a exceção, construindo e preenchendo stack trace **por item, por página**. A correção era trocar por uma chamada direta a `authorize`, devolvendo o booleano.
  - A mudança **quebra 10 testes** (`CollectionTest`: 5 falhas + 5 erros; `CommunityTest`: 1 falha + 4 erros).
  - **Causa:** os testes fazem stub de `authorizeAction` e dependem de `authorizeActionBoolean` ser implementado *através dele*. Ao chamar `authorize` direto, os dois métodos deixam de estar acoplados — e `CollectionServiceImpl.canEdit` usa `authorizeActionBoolean` para decidir se uma comunidade concede WRITE/ADD, então o resultado muda sob mock.
  - **Linha de base medida:** com o código original, `CollectionTest` (83), `CommunityTest` (57) e `AuthorizeServiceTest` (4) passam **144/144, zero falhas**.
  - **Veredito:** é uma mudança de semântica entre dois métodos públicos de uma API sensível (autorização), não uma otimização livre. O ganho medido (`fillInStackTrace` em ~1–3 % das amostras) não justifica. Precisa de aval explícito da equipe e revisão dos testes que fazem stub de `authorizeAction`.
  - O mesmo defeito existe em `CollectionServiceImpl.canEditBoolean` e `CommunityServiceImpl.canEditBoolean`, e pelo mesmo motivo a inversão de delegação (`canEditBoolean` passar a conter a regra e `canEdit` delegar a ela) também foi **tentada e revertida**: muda o ponto de extensão da classe e quebra os mesmos testes.
- ✅ **Prefetch das políticas em lote — APLICADO.** Os thread dumps apontam `ResourcePolicyDAOImpl.findByDSoAndAction` como o **call site de banco mais frequente**: converter um item pergunta se o usuário pode editá-lo, e a checagem sobe até a coleção, custando várias idas ao banco **por item** (~55 varreduras de índice em `resourcepolicy` por página de 20 itens).
  - **O que faz:** antes de converter a página, `DiscoverResultConverter.prefetchPolicies` reúne **os itens da página, as suas coleções e as comunidades acima delas** (via `communityService.getAllParents`) e chama `resourcePolicyService.prefetch(context, objetos, …)` para **WRITE, ADMIN e ADD**. São **3 consultas em vez de ~60**.
    - As comunidades entraram na segunda rodada: a checagem de edição sobe do item para a coleção e desta para as comunidades, e cada uma dessas perguntas custava uma consulta **por item**.
  - **Por que continua seguro:** o prefetch só *antecipa a busca*. `ResourcePolicyServiceImpl.find` consulta o mapa e devolve o que foi prefetchado; se não houver nada para aquele objeto/ação, cai na consulta individual de sempre. O funil `AuthorizeServiceImpl.getPoliciesActionFilter` e **toda a lógica de decisão de autorização ficaram intactos** — nenhum resultado de autorização pode mudar por causa disso.
  - **Onde ficam os dados:** `Context.prefetchedPolicies`, com escopo no `Context` (uma requisição). Chave presente com lista vazia significa "não tem política para esta ação", distinto de chave ausente ("não prefetchado").
  - **Teste:** `ResourcePolicyPrefetchTest` compara, para **4 objetos** (item com política, item sem política, coleção e comunidade) × **3 ações** (WRITE, ADMIN, ADD), as respostas vindas do banco com as vindas do prefetch — têm de ser idênticas. Passa.
  - **Verificado:** build dos 15 módulos, Checkstyle limpo em `dspace-api` e `dspace-server-webapp`, **148 testes, 0 falhas**.
  - **Não verificado end-to-end:** a queda no número de consultas por busca precisa de deploy para ser medida.
  - ⬜ **O que ainda sobra aqui:** `communityService.getAllParents(collection)` continua sendo uma consulta **por item** (é uma tabela diferente, `community2collection`, e cacheá-la exigiria mexer em `CollectionServiceImpl.canEdit`, que os testes fazem mock — mesma armadilha já registrada). Numa página de 20 itens isso são ~20 consultas.
- ⬜ Reaproveitar `isAdmin(context)` uma vez por requisição — **ganho baixo**: para anônimo (a maioria das buscas) `isAdmin` já retorna `false` sem tocar no banco. Só ajudaria usuários logados.

### P5 — Modo somente-leitura no caminho de busca

`FlushMode.MANUAL` (ou `setDefaultReadOnly(true)`) no `Context` das requisições de busca elimina o auto-flush/dirty-check que hoje percorre todas as entidades carregadas antes de cada query.

**Como validar:** contagem de `DirtyHelper.isDirty` / `Cascade` em thread dump deve cair.

---

## Fase 2 — Frontend e superfície do usuário

### ~~P3 — Corrigir o N+1 do frontend~~ · CANCELADA (premissa errada)

> **Correção (2026-10-13).** A premissa desta ação estava errada. Ela afirmava que `directlyAttachIndexableObjects` (`search.service.ts:227-278`) gerava uma requisição HTTP por resultado. **Não gera.**

Medição nos logs reais do servidor:

| Origem | Requisições |
|---|---|
| Buscas do navegador (`/home`, `/search`, `/collection-list`, `/community-list`, `/mydspace`) | ~**907** |
| `GET /server/api/core/items/{uuid}` do navegador | **81** |
| `GET /server/api/discover/facets/{name}` (total) | 220 |

São ~**0,09 requisição de item por busca**; se houvesse N+1 seriam ~18.000.

**Por quê:** o `DspaceRestResponseParsingService` registra cada `indexableObject` embutido no cache, indexado pelo seu `self` href (`search-response-parsing.service.ts:42-47`, via `addToObjectCache`). Com `useCachedVersionIfAvailable=true`, `findByHref` é **cache hit** e o `RequestService.send` não faz HTTP.

O que sobra é CPU do navegador ao montar 20 Observables por página — não medido como problema. **Não há o que otimizar aqui.**

### P6 — Reduzir o payload

Desligar a indentação do JSON: medido numa página de busca real, 162 KB viram 94 KB — **42 % dos bytes são espaços**. Ganho só de rede/parse, já que a página faz uma única requisição de busca.

**BLOQUEADO na origem da indentação** (2026-10-14). O que já foi descartado, com a busca feita:

| Onde procurei | Resultado |
|---|---|
| `application.properties` do `dspace-server-webapp` | só tem `spring.jackson.serialization.fail-on-empty-beans=false` |
| `INDENT_OUTPUT`, `indent-output`, `indentOutput` em todo o repositório | **nenhuma ocorrência** fora deste documento |
| Classes de configuração Jackson do REST | nenhum `@Bean ObjectMapper`/`Jackson2ObjectMapperBuilder` — só injeções do mapper do Spring |
| `dspace/config/**` (incluindo `local.cfg` do volume vivo) | nada |
| Variáveis de ambiente do container | nada de Jackson |
| Propriedades de sistema da JVM (`jcmd VM.system_properties`) | nada |
| `/actuator/env` | 401, exige autenticação |

Como a indentação **não está em nada versionado** e o `/actuator/health` (Jackson do próprio Spring Boot) responde compacto enquanto a API do DSpace responde indentada, a configuração vem de **dentro da imagem** — provavelmente um patch local aplicado na construção, não presente no `working tree`. Recomendação: **não perseguir agora**; conferir se a indentação desaparece sozinha depois da próxima construção de imagem a partir do repositório. Se não desaparecer, o próximo passo é comparar o `ObjectMapper` efetivo em tempo de execução (`jcmd`/heap dump), não continuar procurando em arquivo.

### O10 — Normalizar a entrada do usuário ✅ APLICADO

Evidência: `operacao%%` = 13 resultados (**idêntico a `operacao`** — o `%` é ignorado); `"notas tecnicas` (aspas sem fechar) = **HTTP 422**.

**Aplicado** em `search-query.util.ts` (`normalizeSearchQuery`), ligado ao `onSubmit` do `search-form.component.ts` — ou seja, no ponto por onde passa toda busca digitada na caixa de pesquisa.

| Entrada | Antes | Depois |
|---|---|---|
| `operacao**` / `operacao***` | equivale a `*` | colapsado para `operacao*` |
| `"notas tecnicas` | **HTTP 422**, sem resultados | fechado para `"notas tecnicas"` — a busca por frase que o usuário queria |
| `"notas tecnicas"` (balanceado) | ok | inalterado |
| `100%` · `operacao%` | `%` ignorado | **inalterado** (ver abaixo) |
| `(abc` · `AND` solto · `campo:` | HTTP 422 | inalterado — tratado pelo O11 |

> **Reviravolta na decisão do `%`.** O plano previa traduzir `%` → `*`. **Não fiz, e de propósito.** O `%` realmente não é curinga no Solr, mas neste acervo ele é muito mais provavelmente **texto literal** — "100%", "50%" — do que um curinga no estilo SQL, já que a interface não dá nenhuma dica de que curingas existem. Traduzir transformaria `100%` na busca por prefixo `100*`, ampliando o resultado em silêncio. Está documentado no próprio código.

**Verificado:** a função é pura e a lógica foi exercitada com **11 asserções, 11 corretas**, compiladas em TypeScript `--strict`. Há também um spec Jasmine (`search-query.util.spec.ts`) seguindo a convenção do projeto.

### O11 — ~~Tratar o erro de sintaxe com mensagem~~ · JÁ EXISTIA (afirmação minha estava errada)

**Correção.** Eu havia escrito que a página de busca não tinha tratamento de erro. **Está errado** — olhei o `search-page.component` e não o `search-results.component`, que é quem renderiza os resultados. O tratamento existe e é específico por código:

```ts
// search-results.component.ts
showError(): boolean {
    return this.searchResults?.hasFailed && (!this.searchResults?.errorMessage || this.searchResults?.statusCode !== 400);
}
errorMessageLabel(): string {
    return (this.searchResults?.statusCode === 422) ? 'error.invalid-search-query' : 'error.search-results';
}
```

E a tradução pt-BR também existia. **O que fiz então:** a mensagem em pt-BR mandava o cidadão para a documentação de sintaxe do Solr **em inglês**. Troquei por uma orientação acionável em português:

> "A consulta de pesquisa não é válida. Verifique se as aspas estão fechadas e se operadores como AND, OR e NOT estão entre dois termos. Exemplos: *portaria AND identidade* ou *"cadeia de custódia"*."

O `ds-error` renderiza com `[innerHTML]`, então a marcação é suportada.

---

## Fase 3 — Uma única reindexação (O7 + O8 + O9)

> **Status: as três mudanças de configuração foram APLICADAS** (2026-10-13). Falta a reindexação para terem efeito.
>
> As três são **compatíveis com o índice atual**: alteram analisadores e `copyField`, o que não quebra o core nem exige parada. Os documentos antigos mantêm a análise com que foram indexados; a mudança passa a valer conforme forem reindexados. Para uniformidade, rodar `dspace index-discovery -b`.
>
> Faça os três juntos. Cada um exige reindexação completa; separá-los significa reindexar três vezes.

### O7 — Stemming em português ✅ APLICADO (escolha corrigida após verificação)

**Evidência inicial:** o analisador usava `SnowballPorterFilterFactory language="English"`, que remove plurais em "-s" mas não entende morfologia portuguesa:

| Par | Com o stemmer inglês |
|---|---|
| `contrato` / `contratos` | 342 / 342 ✅ |
| `documento` / `documentos` | 1191 / 1191 ✅ |
| `licitacao` / `licitacoes` | 58 / **13** ❌ |
| `manual` / `manuais` | 31 / **11** ❌ |

**Verificação feita num core Solr temporário.** Criei um core `searchtest` a partir do configset real, com os arquivos modificados, e comparei o **token final** que cada stemmer produz. O core temporário e seu configset foram removidos ao final; o core `search` **nunca foi tocado** (conferido: 2.562 documentos intactos).

| Par | Inglês (antes) | Snowball PT | LightStem | **Minimal** | PortugueseStem |
|---|---|---|---|---|---|
| `portaria` / `portarias` | unifica | **`port`** ⚠ | `portari` | **`portaria`** | **`port`** ⚠ |
| `manual` / `manuais` | **não unifica** | **não unifica** | unifica | **unifica** | `man` ⚠ |
| `documento` / `documentos` | unifica | `document` | `document` | **`documento`** | `document` |
| `servidor` / `servidores` | unifica | `servidor` | `servidor` | **`servidor`** | **`serv`** ⚠ |
| `identidade` / `identidades` | `identidad` | — | `identidad` | **`identidade`** | `ident` ⚠ |
| `licitacao` / `licitacoes` | **não unifica** | não unifica | não unifica | **não unifica** | não unifica |

**Ação aplicada:** `solr.PortugueseMinimalStemFilterFactory`, nos dois analisadores do tipo `text`.

**Por que o minimal, e não os candidatos que eu havia citado antes:**

- **`SnowballPorterFilterFactory language="Portuguese"`** — minha primeira escolha, chegou a ser aplicada — **estava errada**: produz `portaria` → **`port`**, o que faz "porto", "porta" e "portaria" colapsarem no mesmo termo. Neste acervo "portaria" é o tipo documental dominante (2.246 dos 2.255 itens), então seria uma perda séria de precisão. E também **não** unifica `licitacao`/`licitacoes`, que era o objetivo declarado.
- **`PortugueseLightStemFilterFactory`** é intermediário: unifica `manual`/`manuais` e evita o `port`, mas ainda reduz `documento`→`document` e `contrato`→`contrat`.
- **`PortugueseMinimalStemFilterFactory`** é o único que **unifica os plurais regulares sem destruir palavras**: `portaria`, `documento`, `servidor` e `identidade` permanecem íntegros, e `manuais` passa a casar com `manual` — coisa que o stemmer inglês não fazia.

**O que o O7 NÃO resolve — correção da minha afirmação anterior.** Os pares em "-ção"/"-ções" **continuam sem unificar**: `licitacao` → `licitacao` vs `licitacoes` → `licitacoe`. Nenhum dos quatro stemmers unifica; é uma limitação dos algoritmos para esse sufixo, não um erro de configuração. A afirmação de que o O7 "recupera dezenas de documentos" para `licitacoes` **estava errada**. O contorno segue sendo buscar `licita*`, como documentado em [pcirn-busca-sintaxe.md](pcirn-busca-sintaxe.md).

**Risco:** baixo agora — o minimal não funde palavras distintas. Ainda assim muda o índice, portanto exige a reindexação da Fase 3.

#### Ensaio da reindexação (2026-10-14) — o que muda de fato

Antes de propor a janela, refiz a reindexação **numa cópia**: core `searchtest` criado a partir do configset real, os 2.562 documentos do índice vivo relidos com todos os campos armazenados e **reenviados** ao core de ensaio, para que o Solr os analisasse outra vez com o schema novo. O índice real não foi tocado (2.562 documentos conferidos ao final) e o core de ensaio foi removido.

| Consulta | Índice vivo | Com O7+O8+O9 | Leitura |
|---|---|---|---|
| `manuais` | 15 | **42** | O7: passa a unificar com `manual` |
| `manual` | 31 | **42** | os dois chegam ao **mesmo** conjunto |
| `relatorio` / `relatorios` | 66 / 66 | 66 / 66 | o stemmer inglês já unificava |
| `licitacao` / `licitacoes` | 58 / 13 | 58 / 13 | limitação conhecida, não é regressão |
| `a` · `o` · `e` · `de` · `com` | 2562 · 1951 · 2283 · 2256 · 1291 | **0** em todas | O8: deixam de casar com o acervo inteiro |
| `portaria` · `custodia` · `cadeia de custodia` | 2250 · 50 · 33 | 2250 · 50 · 33 | buscas reais estáveis |
| `identidade funcional` | 15 | 16 | +1 documento |
| `search_text:item` | 2257 | **30** | O9: o vazamento de campos internos some |
| `search_text:collection` | 21 | **0** | idem |
| `handle:123456789*` | 2276 | 2276 | o `handle` continua buscável |
| Tamanho do índice | 24,6 MB | 32,8 MB | +33 % (ver ressalva) |

**O que isso quer dizer:**

- **O7 vale a pena:** `manuais` sai de 15 para 42 documentos e passa a devolver o mesmo conjunto que `manual`. Hoje uma busca no plural **não encontra** 27 documentos que a busca no singular encontra.
- **O8 é pior do que eu havia escrito, e a correção importa.** A lista viva tem **36 palavras em inglês** e é aplicada **na indexação**: descarta `no` e `as`, que são palavras portuguesas legítimas — hoje uma busca por `as` devolve **zero** — e **não** contém `a`, `o`, `e`, `de`, `com`, que são as mais frequentes do português e estão indexadas em 1.291 a 2.562 documentos, sem nenhum poder de discriminação. Com a lista pt-BR, uma consulta formada só por palavra vazia devolve 0 em vez do acervo inteiro, e o índice perde esse ruído.
- **O9 é cirúrgico:** o vazamento cai de 2.257 para 30 documentos e o `handle` continua encontrável.
- **Ressalva sobre o tamanho:** a comparação de tamanho não é perfeitamente justa — o core de ensaio acabou de receber 2.562 documentos e tem segmentos não mesclados, enquanto o índice vivo acumulou merges. A diferença de termos é real (o stemmer minimal produz mais termos distintos que o inglês), mas a porcentagem exata deve ser lida com essa reserva.

**Custo da janela:** uma reindexação completa (`dspace index-discovery -b`) sobre 2.562 documentos. Como o tipo de campo e os analisadores mudam, ela é obrigatória e não há meio-termo.

### O8 — Stopwords em português ✅ APLICADO

**Evidência:** o `stopwords.txt` é a **lista de demonstração do Lucene** (contém literalmente `stopworda` e `stopwordb`). Isso produz dois defeitos opostos:

| Consulta | Hoje | Por quê |
|---|---|---|
| `no` | **0 resultados** | "no" está na lista inglesa — palavra legítima em português |
| `as` | **0 resultados** | idem |
| `no andamento` | 25 | sobra só "andamento" |
| `a` | **2.250** (tudo) | não é stopword na lista inglesa |
| `o` | 1.948 | idem |
| `e` | **2.250** (tudo) | idem |
| `de` / `da` / `do` / `para` / `com` | 2.240 / 1.957 / 2.083 / 1.656 / 1.291 | não removidas, incham o índice |

**Ação:** substituir por uma lista pt-BR (`a, o, e, de, da, do, em, um, para, com, no, na, por, ...`), mantendo o cuidado de que a remoção ocorre **dos dois lados** (índice e consulta) — o que é consistente.

**Efeito esperado:** buscar por palavra vazia deixa de devolver o repositório inteiro; índice menor; frases mais flexíveis.

**Verificado no core temporário** (`searchtest`, depois removido) comparando o token final do analisador antes e depois:

| termo | antes | depois |
|---|---|---|
| `a`, `o`, `e` | `a`, `o`, `e` (indexados!) | **(removidos)** ✅ |
| `de`, `da`, `do` | indexados | **(removidos)** ✅ |
| `para`, `com`, `em` | indexados | **(removidos)** ✅ |
| `no`, `as` | removidos | removidos ✅ (não regride) |
| `portaria`, `documento` | preservados | preservados ✅ (não come palavra útil) |

O O8 entrega exatamente o que prometia.

### O9 — Impedir que campos internos vazem para o `search_text` ✅ APLICADO

**Evidência decisiva:** o `schema.xml:364` tem `<copyField source="*" dest="search_text"/>` — copia **todos** os campos, inclusive os de controle:

| Consulta | Resultado | Comentário |
|---|---|---|
| `search_text:item` | **2.254** | vem de `search.resourcetype:Item` |
| `dc.title:item` | **0** | não é conteúdo |
| `search_text:g0` | **2.272** | vem de identificadores de grupo/ACL |
| `dc.title:g0` | **0** | — |
| `true` | **2.250** | vem de `archived`/`discoverable`/`latestVersion` |

Campos internos confirmados: `search.resourcetype`, `archived`, `discoverable`, `withdrawn`, `latestVersion`, `handle`, `location`, `read`, `edit`, `admin`, `submit`.

**Impacto:** buscar "item" — palavra comum em português — devolve o repositório **inteiro**. Além do ruído, expõe identificadores internos (UUIDs de grupos/usuários) ao índice de busca.

**Ação:** substituir o `copyField source="*"` por uma lista explícita de campos de conteúdo (`dc.*` e os campos de exibição), excluindo os internos.

**Como validar depois:** `search_text:item` e `g0` devem cair para ~0.

**Verificado no core temporário.** Indexei um documento de prova com os campos internos (`search.resourcetype:Item`, `archived:true`, `read:[g0]`, `latestVersion:true`, `discoverable:true`) e conteúdo (`dc.title`, `local.campo`, `fulltext`). Resultado — **9 de 9 asserções corretas**:

| consulta | resultado | esperado |
|---|---|---|
| `search_text:item` | **0** | interno, não deve entrar ✅ |
| `search_text:true` | **0** | interno ✅ |
| `search_text:g0` | **0** | interno (ACL) ✅ |
| `search_text:latestversion` / `discoverable` | **0** | interno ✅ |
| `search_text:documento` | **1** | `dc.title` ✅ |
| `search_text:licitacoes` | **1** | dobra de acento/caixa funciona ✅ |
| `search_text:valorxyz` | **1** | schema `local.*` ✅ |
| `search_text:palavraintegral` | **1** | `fulltext` ✅ |

Buscar "item" — palavra comum em português — deixa de devolver o repositório inteiro, e identificadores internos de grupo/usuário deixam de ser pesquisáveis.

> Observação: `<copyField source="*" dest="search_text"/>` é o padrão do DSpace upstream — é uma melhoria local, não a correção de um erro de configuração nosso.
>
> **O que foi aplicado:** o `source="*"` foi trocado por um `copyField` por schema de metadados, usando a lista real de `metadataschemaregistry` (dc, dcterms, dspace, eperson, local, relation, person, project, organization, periodical, creativework, creativeworkseries, publicationissue, publicationvolume, oaire, iiif, datacite, coar, journal, journalvolume, workflow), mais os campos de conteúdo que não são metadados e continuam pesquisáveis: `fulltext`, `handle` e `original_bundle_filenames`. Ficaram de fora `read`, `edit`, `admin`, `submit`, `location*`, `search.*`, `archived`, `discoverable`, `latestVersion`, `withdrawn` e demais campos de controle. Base da decisão: dos 66.353 valores de metadados, 66.317 (99,97 %) são do schema `dc`; os demais schemas somam 36.

---

## Fase 4 — Gatilho futuro (não fazer agora)

### O12 — Proteção contra consultas caras

**Medido hoje: não é problema.** QTime do Solr para `*racao` (curinga à esquerda), `*cao`, `operacao~` (fuzzy) e `operacao` são **todos ~0 ms** — o índice tem 2.558 documentos e o dicionário de termos é pequeno. Sem esta medição, seria fácil "otimizar" algo que não está lento.

**O risco é de escala.** Curinga à esquerda força varredura do dicionário de termos, e fuzzy com distância 2 expande para muitos termos — nenhum dos dois usa busca direta no índice. E hoje isso era multiplicado por **14 consultas por busca** — 2 depois do P1.

**Gatilho para agir:** monitorar o p99 de `QUERY./select.requestTimes` em `/solr/admin/metrics`. Se passar de **100 ms**, aplicar:

- `allowLeadingWildcard=false` (rejeitar `*termo`) ou exigir prefixo mínimo de 3 caracteres;
- limitar fuzzy a distância 1 (`~1`);
- `numFoundExact=false` / `minExactCount` para não contar exato em consultas caras.

Enquanto o gatilho não disparar, **não implementar** — seria complexidade sem ganho.

---

## Ordem de execução sugerida

```
0. R1 + R2  (relevância + sinônimos)         ← JÁ APLICADOS, só dependem de deploy. Não exigem reindexação
1. P1 ações 1 a 3 (cache da localização + cache dos limites)  ← maior ganho de servidor, baixo risco. Não exige reindexação
2. O7 + O8 + O9  ← UMA reindexação, validada em cópia antes  ← JÁ APLICADOS, aguardam a janela
3. O10 + O11 (normalização de entrada + mensagem de erro)    ← barato, melhora a UX já
4. P6 + P5  (payload, read-only)
5. Correção do campo de ano (`*_year`) ← exige a MESMA janela de reindexação do passo 2; hoje é só um bug latente
6. P4 batching de políticas  ← precisa de deploy para validar
7. O12      ← só quando o p99 do /select passar de 100 ms
```

~~P3~~ está cancelada: a premissa não se confirmou nos logs.

Ordem de deploy sugerida:
- **Deploy 1 (sem reindexação):** R1, R2, P1 (ações 1 a 3), O10, O11. Efeito imediato.
- **Deploy 2 (com reindexação):** O7, O8, O9. Uma única janela.

## Riscos

| Item | Risco | Mitigação |
|---|---|---|
| O7, O8 | Mudam ranking e recall; efeito só visível após reindexar | Validar tokens com a API `/analysis/field`; reindexar cópia e comparar resultados antes da produção |
| O9 | Remover campos do `search_text` pode derrubar buscas que hoje dependem deles | Medir quais campos são realmente usados; manter `dc.*` e campos de exibição |
| O10 | Traduzir `%`→`*` assume intenção do usuário | Decisão de produto; alternativa é avisar na interface |
| P1, P2 | Cache com invalidação errada serve dado velho | Consulta de localização: escopo por requisição. Limites: invalidação a cada indexação **mais** TTL de 60 s e a identidade do usuário na chave (P2: dado de referência que muda raríssimo) |

## Registro de tentativas

Conforme a prática de medir antes de otimizar, ficam registradas as hipóteses **descartadas por falta de evidência**:

| Hipótese | Medição | Veredito |
|---|---|---|
| "O Solr está lento" | QTime médio 0,33 ms, p99 5,1 ms | Descartada |
| "Faltam índices no Postgres" | Índices existem; seq scan é a escolha correta para 279 linhas | Descartada |
| "O disco é o gargalo" | `blks_read = 0` — tudo em `shared_buffers` | Descartada |
| "Curinga à esquerda é caro" | QTime ~0 ms em `*racao` e `*cao` | Descartada **nesta escala** (revisar via gatilho O12) |
| "Fuzzy `~` é caro" | QTime ~0 ms | Descartada **nesta escala** |
| "O payload grande é gargalo de CPU" | Jackson em 0,9 % das amostras | Descartada como CPU; mantida como rede/parse (P6) |
| "O cache de 2º nível está desligado" | Está ligado e configurado (3600 s), mas não cobre *queries* | Parcialmente descartada — a ação certa é P2 |
| "Unificar as 6 consultas auxiliares com `stats.component`" | `stats.field` devolve **HTTP 400** nos **6** campos candidatos, inclusive nos de valor único: o StatsComponent rejeita `TextField`; todos são `text` ou `lowerCaseSort` | **Descartada** |
| "Dar `docValues` ao tipo `lowerCaseSort` para o `stats` funcionar" | `docValues` são gravados **antes** do analisador: o maior `author` passaria a ser `test2, test2` (maiúscula ordena antes de minúscula) e não `Testing, Works`, que é o que o IT `discoverSearchObjectsTestForMinMaxValues` fixa. Também exigiria reindexação, porque `docValues` não se derivam de segmentos já escritos | **Descartada** — mudaria o valor devolvido pela API, não só o custo |
| "Usar `facet.range` para a faixa de ano" | `dateIssued.year_sort` → "Unable to range facet on field" (TextField) | **Descartada** — exige campo numérico/date |
| "Pegar o máximo com `facet.offset=-1` numa única requisição" | "Exception during facet.field" em todos os campos testados | **Descartada** |
| "Pegar os dois extremos com `facet.limit=-1` sobre `dateIssued_min_sort`/`_max_sort`" | Funciona, mas devolve **1009** datas distintas — resposta maior que as duas consultas que substituiria | **Descartada** |
| "Trocar o par ordenado da faixa de ano por um `facet.field=dateIssued.year_sort&facet.limit=-1&facet.sort=index`" | **Equivalente** ao par (1959/2026 conferidos dos dois lados), mas economiza **1** consulta das 14 e teria de passar pelo encanamento de facetas do `DiscoverQuery` | **Não aplicada** — o cache de limites já elimina as duas, e sem tocar no encanamento |
| "Trazer min/max das facetas para a consulta principal" | `calculateExtremeValue` monta um `DiscoverQuery` sem query nem filtros do usuário — os limites são **globais** | **Descartada** — mudaria a semântica do slider (passaria a variar com a busca) |
| "Eliminar a exceção de `authorizeActionBoolean` chamando `authorize` direto" | Quebra **10 testes**. Os testes fazem stub de `authorizeAction` e dependem de `authorizeActionBoolean` passar por ele; a mudança desacopla os dois métodos, e `CollectionServiceImpl.canEdit` depende desse acoplamento. Linha de base pura: **144/144 testes passam** | **Revertida** — não é otimização livre, é mudança de semântica em API de autorização |
| "Inverter a delegação de `canEditBoolean` para conter a regra e `canEdit` delegar a ela" | Mesmo efeito: altera o ponto de extensão da classe e quebra `CollectionTest`/`CommunityTest` | **Revertida** |
| "O frontend faz N+1: 1 requisição por resultado da busca" | Logs reais do servidor: ~907 buscas de navegador contra **81** requisições de item (~0,09/busca). O `indexableObject` embutido já é registrado no cache pelo seu `self` href, então `findByHref` é cache hit | **Descartada** — a premissa não se confirmou; P3 cancelada |
| "Trocar o parser de consulta para `edismax` com peso por campo (`qf=dc.title^6 dc.subject^3 ...`)" | Testado direto no Solr com 8 formatos de consulta (vazio, termo, multi-termo, frase, campo, curinga, acento, operadores): **todos** funcionam, mas o 1º resultado muda em **5 de 8** casos — e para `"identidade funcional"` o edismax põe no topo um documento pior que o parser atual, que acerta em cheio | **Não aplicada** — exige avaliação de relevância com conjunto de referência; sem isso seria troca às cegas |
| "As facetas são buscadas uma a uma pela UI" | `discover/facets/{name}`: **220** requisições no total, contra 7.959 buscas | **Descartada** |
| "Stemmer `SnowballPorterFilterFactory language=\"Portuguese\"`" (minha primeira escolha para O7; chegou a ser aplicada) | Verificado em core temporário: produz `portaria` → **`port`**, fundindo "porto"/"porta"/"portaria" — e "portaria" é 2.246 dos 2.255 itens. Também **não** unifica `licitacao`/`licitacoes`, que era o objetivo declarado | **Substituído** por `PortugueseMinimalStemFilterFactory` |
| "Stemmer `PortugueseLightStemFilterFactory`" | Intermediário: unifica `manual`/`manuais` e evita o `port`, mas reduz `documento`→`document` e `contrato`→`contrat` | **Não escolhido** — o minimal preserva melhor a precisão |
| "Aplicar O7, O8 e O9 e confiar na leitura do código" | Verificação em core Solr temporário (`searchtest`, removido ao final; core real intacto) mostrou que **O7 estava errado** e O8/O9 corretos | **A verificação evitou uma regressão de precisão em produção** |

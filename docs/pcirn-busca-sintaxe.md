# Sintaxe de busca do PCIRN — o que funciona (verificado na instância)

**Data:** 2026-10-13 · **Instância:** homologação (`:8501` REST / `:8984` Solr)
**Método:** todos os resultados abaixo foram obtidos por teste real contra a API, não por documentação genérica.

---

## 1. Resposta curta

A busca usa o **parser Lucene clássico** do Solr, e o DSpace **não escapa nem reescreve** o que o usuário digita (`SolrServiceImpl.resolveToSolrQuery` faz `solrQuery.setQuery(query)` direto). A verificação é direta: a API REST devolve exatamente o mesmo número de resultados que o Solr puro **com o filtro `search.resourcetype:Item` aplicado**.

Consequência prática: **a sintaxe funciona na caixa de busca da interface**. O frontend (`search-form.component.ts:149-165`) só repassa o texto para a URL, sem sanitizar.

- Operador padrão é **AND** (`q.op=AND` no `solrconfig.xml:122`).
- Campo padrão é **`search_text`** (`df=search_text`, linha 121) — e `search_text` recebe **todos** os campos via `<copyField source="*" dest="search_text"/>`. Ou seja, buscar sem campo procura em tudo (título, autor, resumo, etc.).

### Sobre `%%` e `**`

| Você escreveu | O que acontece | Veredito |
|---|---|---|
| `operacao%%` | 13 resultados — **igual a `operacao`** | **`%%` NÃO é curinga.** É ignorado |
| `operacao%` | 13 resultados | `%` é ignorado (só separa) |
| `operac%` | 0 resultados | `%` não amplia nada |
| `operacao**` | 13 resultados — igual a `operacao*` | `**` é só um `*` redundante |
| `operac*` | **110 resultados** | `*` é o curinga de verdade |
| `operaca?` | 13 resultados | `?` = exatamente 1 caractere |

**Não existe `%%` nem `**` no DSpace.** Isso é convenção de SQL/`LIKE`. Aqui os únicos curingas são `*` e `?`.

---

## 2. Para achar o documento exato

**Use frase entre aspas, com campo de título:**

```
dc.title:"modelo de identidade funcional dos servidores"
```

Resultado: **1 documento** — o exato.

### Como a frase se comporta (testado com um título real que contém `—`, `nº`, `/`)

| Consulta | Resultado | Regra |
|---|---|---|
| `dc.title:"PORTARIA nº 760/2026-GDG/PCIRN — Institui o modelo"` | **1** | título completo, colado da página |
| `dc.title:"PORTARIA nº 760/2026-GDG/PCIRN Institui o modelo"` | **1** | pode **remover a pontuação** (`—`) — ela é transparente |
| `dc.title:"modelo de identidade funcional dos servidores"` | **1** | **fragmento contíguo do meio** também funciona |
| `dc.title:"PORTARIA 760 2026 GDG PCIRN Institui o modelo"` | 0 | **não remova palavras** (`nº`) — quebra a adjacência |
| `dc.title:"servidores identidade funcional"` | 0 | **a ordem importa** |

**Receita prática:** copie um trecho contíguo de 3 a 6 palavras do título, na ordem, e coloque entre aspas. Não precisa acertar a pontuação.

---

## 3. Sintaxe verificada (tabela completa)

| Recurso | Exemplo | Resultado |
|---|---|---|
| Termo simples | `operacao` | 13 |
| Acento ignorado | `Operação` · `OPERACAO` · `operacao` | 13 (os três iguais) |
| Frase exata | `"notas tecnicas"` | 3 |
| Proximidade | `"notas tecnicas"~3` | 3 |
| Curinga (qualquer coisa) | `operac*` | 110 |
| Curinga no meio | `op*cao` | 21 |
| **Curinga no início** | `*racao` | 424 |
| Curinga de 1 caractere | `operaca?` | 13 |
| Fuzzy (tolera erro de digitação) | `operacao~` | 114 |
| E (implícito) | `manuais operacao` | 6 |
| E (explícito) | `manuais AND operacao` | 6 |
| OU | `manuais OR protocolos` | 688 |
| NÃO | `manuais NOT protocolos` · `manuais -protocolos` | 1 |
| Obrigatório | `+manuais +operacao` | 6 |
| Campo específico | `dc.title:Portaria` | 2195 |
| Campo + frase | `dc.title:"..."` | ver seção 2 |
| Data | `dc.date.issued:2026` | 655 |
| Autor | `dc.contributor.author:"Silva"` | 1 |
| Combinação | `dc.title:Portaria AND dc.date.issued:2026` | — |

Campo errado devolve 0, não erro: `title:Portaria` também funciona (2195), mas `xyzabc:operacao` → 0.

---

## 4. Concatenação de palavras — como funciona de verdade

Existe, mas **no momento da indexação**, não na consulta. O `WordDelimiterFilterFactory` do Solr está configurado com `catenateWords=1` e `catenateNumbers=1` (`schema.xml`, tipo `text`): ao indexar, ele cria **tanto as partes separadas quanto a versão colada**.

Exemplo real — `ABIS/CIN` está indexado como `abis`, `cin` **e** `abiscin`:

| Consulta | Resultado |
|---|---|
| `abis/cin` | 1 |
| `abiscin` (colado) | 1 |
| `abis cin` (separado) | 1 |

O mesmo vale para números: `42/2026` → indexado como `42`, `2026` e `422026`.

**Mas atenção — o efeito é assimétrico.** Colar as palavras só acha os documentos onde *aquela* justaposição existia:

| Consulta | Resultado |
|---|---|
| `medico-legais` | 112 |
| `medico legais` (separado) | 112 |
| `medicolegais` (colado) | **26** |

Ou seja: **o separado acha tudo; o colado acha um subconjunto.** Para não perder documento, prefira a forma separada ou use `medico* legais`.

---

## 5. Pegadinhas que valem conhecer

### 5.1 Singular e plural — funciona só em parte

O stemming configurado é **Snowball *English***, aplicado a texto em português (`schema.xml`, filtro `SnowballPorterFilterFactory language="English"`). Por isso plurais regulares em "-s" casam, mas "-ção"/"-ções" e irregulares **não**:

| Par | Resultado |
|---|---|
| `contrato` / `contratos` | 342 / 342 ✅ iguais |
| `documento` / `documentos` | 1191 / 1191 ✅ |
| `servidor` / `servidores` | 1218 / 1218 ✅ |
| `analise` / `analises` | 74 / 74 ✅ |
| `licitacao` / `licitacoes` | 58 / **13** ❌ |
| `manual` / `manuais` | 31 / **11** ❌ |

**Contorno:** para "licitação", busque `licita*` (cobre as duas formas) ou faça as duas buscas.

### 5.2 Erro de sintaxe devolve HTTP 422

Estes casos **falham** com `422 Unprocessable Entity` em vez de retornar vazio:

| Consulta | Resultado |
|---|---|
| `"notas tecnicas` (aspas sem fechar) | HTTP 422 |
| `(manuais` (parêntese aberto) | HTTP 422 |
| `AND` (operador solto) | HTTP 422 |
| `dc.title:` (campo sem valor) | HTTP 422 |

Vale garantir que a interface mostre uma mensagem amigável em vez de erro genérico quando o usuário digitar aspas soltas.

### 5.3 Acento e maiúscula são irrelevantes — inclusive com `*`

O filtro `ICUFoldingFilterFactory` dobra acentos e caixa, e é aplicado também em consultas com curinga:

| Consulta | Resultado |
|---|---|
| `dc.title:memoria*` · `memória*` · `MEMORIA*` · `Memória*` | 2 (todas iguais) |
| `dc.title:medico*` · `médico*` | 30 (iguais) |

Não é preciso digitar acento — e digitar não atrapalha.

### 5.4 Busca por campo só acha **Itens**

O DSpace sempre acrescenta o filtro `search.resourcetype:Item`. Se a consulta casar apenas com Coleções ou Comunidades, o resultado é **0** — mesmo o Solr puro achando documento.

Exemplo: `dc.title:"Notas Técnicas"` → **6** no Solr puro, **0** pela API, porque as 6 são **coleções** com esse nome, não itens.

### 5.5 Aspas, `*` e `?` não são afetados por acento, mas curinga não "corrige" a palavra

`operac*` funciona como prefixo a partir de "operac" (110 resultados). Já `operacao*` dentro de `dc.title` dá 0 simplesmente porque nenhum **item** tem essa palavra no título — os 13 resultados de `operacao` vêm de outros campos via `search_text`.

---

## 6. Campos que podem ser usados na busca por campo

O índice tem 61 campos base. Os úteis:

```
dc.title                    dc.title.alternative        dc.title.pt_BR
dc.contributor.author       dc.creator                  dc.publisher
dc.date.issued              dc.date.accessioned         dc.date.accessioned_dt
dc.description.abstract     dc.description.abstract.pt_BR
dc.subject                  dc.subject.pt_BR            dc.type
dc.identifier.uri           dc.identifier.other         dc.language
dc.relation.hasversion      dc.rights                   dc.source
dc.format.extent            dc.coverage.temporal        dspace.entity.type
handle                      author  subject  dateIssued  entityType
```

Internos (existem, mas são para uso do sistema): `search_text`, `search.resourcetype`, `search.resourceid`, `read`, `admin`, `withdrawn`, `location.*`, `latestVersion`.

---

## 7. Receitas rápidas

```
Achar um documento específico pelo título
    dc.title:"trecho contíguo do título"

Achar tudo sobre um assunto, cobrindo singular e plural
    licita*                        (em vez de licitacao)

Documentos de um autor com tolerância a digitação
    dc.contributor.author:silva~

Documentos de um ano
    dc.date.issued:2026

Título E autor
    dc.title:portaria AND dc.contributor.author:silva

Refinar sem trocar o termo principal
    operacao -protocolos
```

---

## 8. Referências de código

| Assunto | Local |
|---|---|
| Query repassada sem escape | `dspace-api/.../discovery/SolrServiceImpl.java:839-846` (`solrQuery.setQuery(query)`) |
| Operador padrão e campo padrão | `dspace/solr/search/conf/solrconfig.xml:117-127` (`df=search_text`, `q.op=AND`) |
| Cadeia de análise (folding, stemming, WordDelimiter) | `dspace/solr/search/conf/schema.xml:68-107` (tipo `text`) |
| `copyField source="*"` → `search_text` | `dspace/solr/search/conf/schema.xml:364` |
| Frontend repassa a query sem sanitizar | `dspace-angular/source/src/app/shared/search-form/search-form.component.ts:149-165` |

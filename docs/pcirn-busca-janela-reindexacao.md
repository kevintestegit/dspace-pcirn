# Janela de reindexação da busca — O7 + O8 + O9

> **Status: EXECUTADO em 2026-10-14.** Reindexação completa em **1 minuto** (11:06:31 → 11:07:31), 2.562 documentos, sem erro. O schema/stopwords/sinônimos foram publicados numa imagem construída a partir de `dspace/src/main/docker/dspace-solr/Dockerfile` (`itep/dspace-solr:search-o7o8o9`), então **sobrevivem a recriação do container** — que era a armadilha nº 1.
>
> Conferência pós-janela, medida no índice real:

| Consulta | Antes | Depois | Esperado |
|---|---|---|---|
| documentos | 2562 | **2562** | 2562 |
| `manuais` / `manual` | 15 / 31 | **42 / 42** | 42 / 42 |
| `search_text:item` | 2257 | **30** | ~30 |
| `handle:123456789*` | 2276 | **2276** | 2276 |
| `a` · `o` · `e` · `de` · `com` | 2562 · 1951 · 2283 · 2256 · 1291 | **0** em todas | 0 |
| `portaria` · `custodia` · `"cadeia de custódia"` | 2250 · 50 · 33 | **2250 · 50 · 33** | iguais |
| API `/discover/search/objects?query=portaria` | 2246 | **2246** | 2246 |

Este documento continua valendo como o procedimento, para uma próxima vez (outro acervo, outro schema) — inclusive as armadilhas, que foram **medidas**, não supostas.

## O que muda e por quê

| Item | Arquivo | Efeito |
|---|---|---|
| **O7** | `dspace/solr/search/conf/schema.xml` — tipo `text` | stemmer inglês → `PortugueseMinimalStemFilterFactory`. `manuais` passa a casar com `manual`. |
| **O8** | `dspace/solr/search/conf/stopwords.txt` | lista de 36 palavras **inglesas** → ~204 palavras **pt-BR** |
| **O9** | `dspace/solr/search/conf/schema.xml` — `copyField` | `source="*"` → 21 `copyField` por schema (mais `fulltext`, `handle`, `original_bundle_filenames`); campos internos param de vazar para o `search_text` |

Os três mudam a **indexação**. Não há meio-termo: ou se reindexa tudo, ou o índice fica meio velho e meio novo.

## Resultado esperado (medido no ensaio de 2026-10-14, em cópia do índice real)

O ensaio releu os 2.562 documentos do índice vivo e os reenviou a um core temporário com o schema novo. O índice real não foi tocado e o core temporário foi removido. Números de antes → depois:

| Consulta | Antes | Depois |
|---|---|---|
| `manuais` / `manual` | 15 / 31 | **42 / 42** (mesmo conjunto) |
| `relatorio` / `relatorios` | 66 / 66 | 66 / 66 |
| `licitacao` / `licitacoes` | 58 / 13 | 58 / 13 (limitação conhecida) |
| `a` · `o` · `e` · `de` · `com` | 2562 · 1951 · 2283 · 2256 · 1291 | **0** em todas |
| `portaria` · `custodia` · `cadeia de custodia` | 2250 · 50 · 33 | 2250 · 50 · 33 |
| `search_text:item` | 2257 | **30** |
| `handle:123456789*` | 2276 | 2276 |
| Documentos no índice | 2562 | 2562 |

Se algum desses números não bater no fim da janela, algo saiu do previsto — não siga adiante sem entender.

## As três armadilhas (todas verificadas)

1. **O configset mora na imagem, e o entrypoint o recopia a cada start.** O comando do container é:
   ```
   precreate-core search /opt/solr/server/solr/configsets/search
   cp -r /opt/solr/server/solr/configsets/search/* search
   ```
   Consequência: mexer só em `/var/solr/data/search/conf/` **não sobrevive a um `docker restart`**. É preciso atualizar também `/opt/solr/server/solr/configsets/search/conf/` — e, para sobreviver a um `docker rm` + `up`, o configset tem de estar **na imagem** (hoje a imagem é a `dspace/dspace-solr:dspace-9_x`, de estoque: o schema novo não está nela).
2. **Reindexar com o schema novo e depois recriar o container com o schema velho deixa o índice ilegível**, porque os termos já estão gravados no formato novo. A ordem importa: imagem/configset novo **antes ou junto** da reindexação.
3. **`dspace/solr/search/conf/` não é o que o container usa hoje.** O caminho vivo é o configset dentro do container; o repositório é a fonte da verdade que ainda **não** foi publicada.

Também vale saber: se o banco for revertido de um dump sem o índice correspondente, o mesmo problema aparece do outro lado — índice e banco andam juntos.

## Pré-condições

- [ ] Janela combinada (o REST fica indisponível para busca; a UI mostra erro).
- [ ] Configset com os três arquivos do repositório publicado na imagem do Solr **ou** montado do host.
- [ ] Backup do índice atual e do banco (`dspace backup`/dump), ou consciência de que a reindexação é reconstruível a partir do banco — ela é, desde que o schema esteja correto.
- [ ] Ninguém submetendo/ editando itens durante a janela (a reindexação lê o banco; escrita concorrente pode gerar índice inconsistente).

## Passos

```bash
# 1. Publicar o schema/stopwords no configset do container (e, idealmente, na imagem)
for f in schema.xml stopwords.txt synonyms.txt; do
  docker cp dspace/solr/search/conf/$f dspacesolr:/opt/solr/server/solr/configsets/search/conf/$f
done
docker restart dspacesolr      # o entrypoint recopia o configset para o core
# conferir que o core vivo pegou o schema novo:
docker exec dspacesolr grep -c PortugueseMinimalStemFilterFactory /var/solr/data/search/conf/schema.xml   # esperado: 2

# 2. Reindexar (2.562 documentos; a duração depende do banco)
docker exec dspace /dspace/bin/dspace index-discovery -b

# 3. Conferir (ver a tabela acima)
```

## Verificação

```bash
q() { curl -s "http://localhost:8984/solr/search/select?q=$1&df=search_text&q.op=AND&rows=0&wt=json" \
      | python3 -c "import sys,json;print(json.load(sys.stdin)['response']['numFound'])"; }
echo "manuais=$(q manuais) manual=$(q manual)   # ambos 42"
echo "search_text:item=$(q search_text:item)   # ~30, era 2257"
echo "handle=$(q 'handle:123456789*')          # 2276, inalterado"
curl -s "http://localhost:8984/solr/search/select?q=*:*&rows=0&wt=json" | python3 -c "import sys,json;print('docs',json.load(sys.stdin)['response']['numFound'])"
```

E do lado da aplicação, uma busca de verdade:

```bash
curl -s "http://localhost:8501/server/api/discover/search/objects?query=portaria&dsoType=item&size=20" \
  | python3 -c "import sys,json;d=json.load(sys.stdin);print('total',d['_embedded']['searchResult']['page']['totalElements'])"
```

## Reversão

Não há reversão parcial: o caminho de volta é **restaurar o configset antigo e reindexar de novo** (~mesmo custo), ou restaurar o índice do backup. Por isso a janela precisa de backup antes.

## Custo conhecido

- Reindexação completa de 2.562 documentos (o gargalo é o banco, não o Solr).
- Índice cresce: 24,6 MB → 32,8 MB no ensaio (+33 %, com a ressalva de que o core de ensaio tinha segmentos não mesclados). Em absoluto, +8 MB.

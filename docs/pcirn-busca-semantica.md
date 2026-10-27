# Busca semântica — PCIRN

**Data:** 2026-10-27

## Como funciona

1. Na indexação, o plugin `SolrServiceSemanticIndexPlugin` monta um texto com título, resumo,
   assuntos e o texto extraído do documento (OCR incluído) e envia esse texto a um serviço de
   embeddings.
2. O vetor resultante é gravado no core Solr dedicado `semantic` (campo `semantic_vector`).
   O core principal de busca não muda, então o schema continua compatível com o Solr 8.x
   embarcado usado nos testes.
3. Quando a busca é feita com `semantic=true`, o backend gera o vetor da consulta, busca os
   identificadores mais próximos no core `semantic` e monta a consulta principal com esses IDs
   ordenados por similaridade. Os filtros de permissão, coleção e `latestVersion` continuam
   valendo no core principal.
4. Os resultados voltam normalmente pela API/UI. Se o serviço de embeddings falhar, a busca cai
   automaticamente para a busca lexical (por palavras).

A busca semântica continua mostrando o trecho do documento (`hitHighlights.fulltext`) quando o
termo digitado aparece no texto. Ela não substitui a busca lexical: é um modo adicional.

## Modelo e dimensão

O padrão é o `bge-m3` (multilíngue, 1024 dimensões), servido pelo Ollama. O campo do core
semântico está definido com `vectorDimension="1024"` em
`dspace/solr/semantic/conf/schema.xml`.

Se trocar o modelo, ajuste **os dois** para a mesma dimensão:

- `semantic.embedding.dimension` em `dspace/config/modules/discovery.cfg`;
- `vectorDimension` do field type `knn_vector` no schema do core semântico.

Depois é obrigatório reindexar. Dimensões comuns: `bge-m3` = 1024, `nomic-embed-text` = 768,
`text-embedding-3-small` = 1536.

## Configuração

Em `dspace/config/modules/discovery.cfg` (ou no `local.cfg`):

```properties
semantic.enabled = true
semantic.embedding.url = http://ollama:11434/v1/embeddings
semantic.embedding.model = bge-m3
semantic.embedding.dimension = 1024
semantic.solr.server = ${solr.server}/${solr.multicorePrefix}semantic
# semantic.embedding.api-key =
# semantic.embedding.max-chars = 4000
# semantic.embedding.timeout-ms = 15000
# semantic.top-k = 100
```

O endpoint precisa ser compatível com a API de embeddings da OpenAI. O Ollama expõe
`/v1/embeddings`; um serviço externo (OpenAI, Azure, vLLM etc.) também pode ser usado — nesse caso,
configure `api-key` e a dimensão correspondente. **Atenção:** com serviço externo, o texto dos
documentos sai da infraestrutura local. Para conteúdo institucional, prefira um serviço local.

### Ollama no Docker Compose

Em produção, o `docker-compose.yml` sobe o `ollama` junto com a stack e o serviço de bootstrap
`ollama-init` baixa o modelo no primeiro start:

```bash
docker compose -f docker-compose.yml --env-file .env.production up -d
docker compose -f docker-compose.yml --env-file .env.production logs -f ollama-init
docker compose -f docker-compose.yml --env-file .env.production exec ollama ollama list
```

O modelo fica no volume `ollama_data`, não no repositório Git: são cerca de 1,2 GB baixados uma
única vez por volume. O servidor precisa de espaço em disco e de memória suficiente para o
`bge-m3` (aproximadamente 2 GB de RAM); em CPU, a geração dos vetores durante a reindexação é
lenta. Se o servidor não tiver saída para a internet, copie o volume `ollama_data` de uma máquina
que já tenha o modelo.

No ambiente de desenvolvimento o perfil continua opcional:

```bash
docker compose -f docker-compose.dev.yml --profile semantic up -d ollama
docker compose -f docker-compose.dev.yml exec ollama ollama pull bge-m3
```

As variáveis já têm os valores padrão no Compose; o `.env.production.example` as repete para
deixar explícito o que pode ser ajustado:

```dotenv
SEMANTIC_ENABLED=true
SEMANTIC_EMBEDDING_URL=http://ollama:11434/v1/embeddings
SEMANTIC_EMBEDDING_MODEL=bge-m3
SEMANTIC_EMBEDDING_DIMENSION=1024
SEMANTIC_SOLR_URL=http://dspacesolr:8983/solr/semantic
```

A imagem do Solr também precisa ser reconstruída a partir de
`dspace/src/main/docker/dspace-solr/Dockerfile`: ela inclui o configset `semantic`, e o entrypoint
do Compose cria o core `semantic` no primeiro start.

## Reindexação

O vetor só existe para itens indexados depois que o plugin entrou em operação. Se houver PDFs
digitalizados sem texto extraído, gere o OCR primeiro com `filter-media` (veja
[pcirn-busca-contexto-ocr.md](pcirn-busca-contexto-ocr.md)). Depois rode uma reindexação completa:

```bash
docker compose -f docker-compose.yml --env-file .env.production \
  run --rm dspace /dspace/bin/dspace index-discovery -b
```

A reindexação faz uma chamada de embeddings por item. Em caso de falha do serviço, o plugin
registra o erro e a indexação continua; a busca semântica simplesmente não encontra aquele item.
O cliente tem backoff de 60 segundos para não repetir o timeout em todos os itens.

## Uso

API:

```text
GET /server/api/discover/search/objects?query=porte+de+arma&semantic=true
```

UI: a busca por significado já vem habilitada em todas as buscas. O parâmetro `semantic=true` é
enviado automaticamente e preserva os filtros e a paginação. Para desativar numa consulta
específica, use `?semantic=false`.

## Limites

- É busca vetorial pura (KNN). Códigos exatos, números de portaria e nomes pouco frequentes podem
  funcionar melhor na busca lexical; o modo semântico é para consultas por assunto/sentido.
- O `top-k` é limitado por `semantic.top-k` (padrão 100) ou pelo necessário para a página atual.
  Os filtros de permissão/coleção são aplicados depois, no core principal; por isso, uma busca
  muito filtrada pode devolver menos itens que o `top-k`.
- A paginação e os filtros continuam funcionando; a contagem de facetas reflete os itens do
  `top-k` que sobreviveram aos filtros.
- Itens em workspace/workflow não recebem vetor; a busca semântica é para itens arquivados.
- O destaque de trechos usa o termo digitado (`hl.q`). Documentos encontrados apenas por
  similaridade, sem o termo literal, aparecem sem trecho destacado.

# Busca por contexto e OCR — PCIRN

**Data:** 2026-10-27

## O que muda

A busca já indexava o texto extraído dos arquivos no campo `fulltext` do Solr, mas:

- PDFs digitalizados (sem camada de texto) não geravam texto;
- o resultado da busca não exibia trechos do documento, apenas título/abstract.

Agora:

1. O `TikaTextExtractionFilter` configura OCR do Tika. Em PDFs, páginas com pouco ou nenhum texto
   são renderizadas e passam pelo Tesseract (`AUTO`).
2. O `discovery.xml` da busca padrão destaca o campo `fulltext`.
3. A lista de resultados do tema PCIRN mostra o trecho destacado do documento quando a busca casou
   dentro do arquivo; sem trecho, continua mostrando o abstract.

## Configuração

As propriedades têm padrão no código e estão documentadas em `dspace/config/dspace.cfg`:

```properties
textextractor.ocr.enabled = true
textextractor.ocr.language = por+eng
textextractor.ocr.strategy = AUTO
textextractor.ocr.dpi = 300
textextractor.ocr.timeout = 120
```

A imagem Docker instala `tesseract-ocr`, `tesseract-ocr-por` e `tesseract-ocr-eng`. Sem o binário
`tesseract`, o Tika ignora o OCR e a extração normal continua funcionando.

Para desativar o OCR: `textextractor.ocr.enabled = false`.

## Processar o acervo existente

O OCR vale para novos depósitos e para o que for reprocessado. Para gerar texto dos PDFs
digitalizados já existentes:

```bash
docker compose -f docker-compose.yml --env-file .env.production \
  run --rm dspace /dspace/bin/dspace filter-media -p "Text Extractor"
```

O `filter-media` processa somente bitstreams que ainda não têm um `.txt` no bundle `TEXT`; portanto,
PDFs que já tinham texto extraído são ignorados. Se o índice não for atualizado pelos eventos,
rode também:

```bash
docker compose -f docker-compose.yml --env-file .env.production \
  run --rm dspace /dspace/bin/dspace index-discovery -b
```

## Como validar

1. Busque uma palavra que exista apenas no corpo de um PDF digitalizado.
2. Confira no resultado que o item aparece e que o trecho do documento é exibido.
3. Na API, o campo `hitHighlights.fulltext` deve trazer o trecho com `<em>` ao redor do termo.

## Limites e segurança

- **Isto é busca textual por contexto.** A busca semântica por embeddings está implementada em
  [pcirn-busca-semantica.md](pcirn-busca-semantica.md) e usa o texto extraído (inclusive OCR) como
  parte da representação do documento.
- O snippet de `fulltext` é habilitado porque, na política atual do PCIRN, itens arquivados e seus
  bitstreams são públicos. O DSpace tem o alerta DS-3498: se houver bitstream restrito dentro de
  item público, o trecho pode expor conteúdo restrito. Antes de introduzir restrição por bitstream,
  desabilite o highlight de `fulltext` em `discovery.xml` ou implemente a correção do DS-3498.
- OCR é caro. `textextractor.ocr.timeout` é por página e o processamento de um PDF grande pode
  demorar. Acompanhe o `filter-media` e ajuste `textextractor.ocr.dpi` apenas se necessário.
- O filtro cobre PDFs. Imagens soltas (JPEG/PNG/TIFF) não são enviadas ao OCR; se o acervo tiver
  documentos digitalizados nesses formatos, isso precisa de um filtro próprio.

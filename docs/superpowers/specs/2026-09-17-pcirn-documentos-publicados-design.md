# Análise documento a documento — Itens publicados PCIRN

Data: 2026-09-17
Status: aprovado pelo solicitante (Piloto + lote)
Escopo: itens DSpace publicados (in_archive=true, withdrawn=false)

## 1. Contexto validado

- Banco `dspace` com 2221 itens arquivados, todos em `owning_collection=22c264e5-cd12-4906-9636-1924cd5048b2`, handle `123456789/2` (Portarias DG).
- Tipos: PORTARIA 2188, DECRETO 17, LEI 14, outros 4 (Nota Técnica, POP, Texto, Portaria).
- Títulos amostrais 2003-2007 indicam portarias administrativas (licença-prêmio, adicional noturno, lotação, designação) com ruído de OCR em parte dos títulos 2006.
- DSpace rodando: dspace, angular, db, solr up há ~51min.
- Pedido: ficha detalhada por documento, fonte PDF + metadados, documento a documento, melhor resumo possível.

## 2. Decisões

- Abordagem: Piloto + lote (validar ficha em 20 itens, depois escalar em lotes de ~200 com checkpoint).
- Ficha padrão por item: handle, UUID, coleção, título, autor/relator, data emissão/aprovação, identificador oficial, versão, idioma, tipo, assunto/palavras-chave, ementa original, resumo extraído do PDF (5-8 linhas), pontos-chave (3-5 bullets), observações de qualidade (OCR, bitstream ausente, metadado faltante).
- Saída: `docs/pcirn-publicados/inventario.csv` + `docs/pcirn-publicados/lote-*/<handle>.md` + `RESUMO-EXECUTIVO.md` por lote.
- Fontes: PostgreSQL como verdade para metadados/handles; assetstore/bundle ORIGINAL para PDFs; REST/Solr só conferência.

## 3. Arquitetura e arquivos

- Ler: `item`, `metadatavalue` (field 73 title + demais), `handle`, `collection`, `bundle/bitstream`, assetstore em volume docker.
- Gerar: inventário CSV completo, depois fichas markdown.
- Não criar: camada paralela de autorização, workflow novo, tabela nova, dependência nova. Usar `psql`, `pdftotext`/`pypdf` já disponíveis, REST nativo.
- Evitar: 2221 fichas de uma vez sem validação; leitura só de metadados sem PDF (rejeitado pelo solicitante).

## 4. Data flow

1. SQL inventário 2221 (handle, título, data, tipo).
2. Top-20 piloto (ordenado por handle): resolve bitstream ORIGINAL, baixa PDF, extrai texto, gera ficha.
3. Solicitante valida piloto.
4. Lotes ~200 itens com checkpoint e coluna observações; retoma de onde parou.
5. Consolidado executivo por lote + inventário final.

## 5. Erros e limites conhecidos

- PDF escaneado sem camada texto → marcar `sem-texto-extraível`, resumir só por metadados + título.
- OCR ruidoso (ex.: títulos 2006 com caracteres trocados) → transcrever melhor esforço e sinalizar.
- Bitstream ausente / múltiplos bitstreams → registrar, usar primeiro ORIGINAL.
- Metadado ausente (data, tipo, assunto) → campo `não informado`, não bloquear.
- Handles placeholder `123456789/*` e `localhost:4000` → manter como está, só referenciar.

## 6. Aceite

- Piloto: 20/20 fichas com handle válido + PDF localizado ou ausência justificada.
- Lote: cada ficha tem todos os campos do padrão ou `não informado` justificado; inventário cobre 2221.
- Nenhum segredo no git; PDFs não commitados, só fichas e CSV.

## 7. Próximo passo

- Invocar skill writing-plans para plano de execução do piloto e dos lotes.

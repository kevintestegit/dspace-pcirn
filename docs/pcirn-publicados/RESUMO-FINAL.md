# Resumo final — 2221 documentos publicados PCIRN

Coleção única: 123456789/2 (Portarias DG). Inventário: `inventario.csv` + `bulk-meta.csv`.

## Por tipo

- PORTARIA 2188, DECRETO 17, LEI 14, POP 1 (MVP teste), Portaria 1 (196/2023 catalogação NUGECID).

## Por assunto (top)

- Designação/Comissões 535, Administrativo 533, Parecer técnico/Pericial 247, Gratificação/Adicional 211, Licença 141, Nomeação/Exoneração 132, Orçamento 69, Teletrabalho 67, Revogação 56, Remoção 48.

## Por ano (issued)

- 1975–2004: 13 (fundadores: LEI 4526/1975, DECRETO 6873/1976)
- 2006: 17, 2007: 18, 2008: 5, 2010: 16, 2011: 150 (lote ADTS), 2012: 103, 2013: 64, 2014: 45, 2015: 40, 2016: 29, 2017: 36, 2018: 55, 2019: 85, 2020: 61, 2021: 72, 2022: 142, 2023: 164, 2024: 289, 2025: 184, 2026: 629.

## Qualidade

- Piloto 20 com PDF lido: 70% texto direto, 20% OCR validado, 10% pendente OCR total.
- Lotes 01–11 (2201 fichas): resumo a partir de metadados (título + abstract + assunto); PDF não OCRizado nesta fase — inteiro teor no bitstream ORIGINAL.
- Padrões: DOE 2023 com texto; scans EPSON 2011 sem camada texto; OCR anos 70 ruidoso; pares duplicados (100/101, 1009/1010, 1002/29); 224/2023 sem efeito pela 226/2023.

## Estrutura de saída

- `lote-piloto/` 20 fichas detalhadas PDF+metadados + RESUMO-EXECUTIVO.
- `lote-01/`–`lote-10/` 200 cada, `lote-11/` 201.
- Total fichas: 2221 (20 piloto + 2201 lote).

## Top achados

1. Portaria 196/2023 funda o RI (1002/29).
2. Portaria 190/2023 gere 276 vagas TAC/concurso.
3. Lote ADTS 2011 (100/101) típico de pessoal.
4. Teletrabalho 201/2023 cria comissão permanente.
5. NEA criado pela 002/2023.
6. Enquadramento Grupo I (224/2023, LC 669/2020).
7. Comissão PAD 022/2023 (LC 122 art. 154).
8. Decreto 33.717/2024 (alimentação militar).
9. Lei 4526/1975 origem IMLEC/ITEP.
10. MVP 123456789/24 prova workflow.

## Enriquecimento com texto do PDF (iteração 2)

- Assetstore copiado (532 MB); `all-bitstreams.csv` mapeia os 2221.
- pdftotext nos 2221: 1168 com texto extraível (52,6%), 1053 scans sem camada texto.
- Fichas regeneradas: campo `Resumo com texto do PDF` + `Fonte texto` com contagem de chars.
- Lotes: 1154 com PDF extraído, 1047 via catalogação OCR (+ 20 piloto detalhado, 14 com PDF).
- Scans: resumo via abstract OCR da catalogação (provenance `Fonte texto: ocr`), validado no piloto com tesseract por; OCR integral página a página segue pendente para esses.

## Escrita no DSpace (2026-09-17, iteração 3)

- Gerador: `gerador-abstracts.py` (reproduzível: mesma saída byte a byte).
- 1067 abstracts atualizados no banco (`metadata_field_id=36`) via staging + UPDATE em transação.
- 1154 mantidos (1053 scans sem texto + 101 rejeitados pelo gate).
- Backup reversível: tabela `metadatavalue_abstract_backup_20260917` (2222 linhas) + `abstracts-backup-20260917.csv`.
- Rollback: `UPDATE metadatavalue m SET text_value=b.text_value FROM metadatavalue_abstract_backup_20260917 b WHERE m.metadata_value_id=b.metadata_value_id;` + `index-discovery -b`.
- Reindex `index-discovery -b` executado; Solr confirma ementa completa (ex: 123456789/2268).
- Exemplo: LEI 811/2026 saiu de "…requisitos de investidura de" (truncado) para ementa completa + Art. 1º.

- OCR total de scans antigos (2233-like) sob demanda.
- Enriquecer lotes com texto PDF (pdftotext + tesseract por) em iteração 2.
- Revisar datas 2026 (629) — issued vs accession.

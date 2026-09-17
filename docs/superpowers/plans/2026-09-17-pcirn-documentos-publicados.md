# Pcirn Documentos Publicados Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extrair ficha detalhada PDF+metadados para os 2221 itens publicados, validando em piloto de 20 antes da escala.

**Architecture:** SQL no PostgreSQL como verdade para inventário/metadados, leitura de bitstreams ORIGINAL via REST/assetstore, extração texto com pdftotext/pypdf, fichas markdown em docs/pcirn-publicados/.

**Tech Stack:** PostgreSQL psql, DSpace REST (porta 8500), Python3 + pypdf, bash, markdown.

---

### Task 1: Inventário completo 2221 itens

**Files:**
- Create: `docs/pcirn-publicados/inventario.csv`
- Test: `docs/pcirn-publicados/inventario.csv` tem 2222 linhas (header + 2221)

- [ ] **Step 1: Gerar CSV via SQL**

Run:
```bash
docker compose exec -T dspacedb psql -U dspace -d dspace -c "\COPY (SELECT h.handle, i.uuid, (SELECT text_value FROM metadatavalue WHERE dspace_object_id=i.uuid AND metadata_field_id=73 LIMIT 1) AS title, (SELECT text_value FROM metadatavalue WHERE dspace_object_id=i.uuid AND metadata_field_id IN (SELECT metadata_field_id FROM metadatafieldregistry WHERE element='date' AND qualifier='issued') LIMIT 1) AS date_issued, (SELECT text_value FROM metadatavalue WHERE dspace_object_id=i.uuid AND metadata_field_id IN (SELECT metadata_field_id FROM metadatafieldregistry WHERE element='type') LIMIT 1) AS dtype FROM item i JOIN handle h ON h.resource_id=i.uuid WHERE i.in_archive=true AND i.withdrawn=false ORDER BY h.handle) TO '/tmp/inventario.csv' CSV HEADER" && docker compose cp dspacedb:/tmp/inventario.csv docs/pcirn-publicados/inventario.csv
```
Expected: arquivo criado com handle 123456789/*

- [ ] **Step 2: Conferir contagem**

Run: `wc -l docs/pcirn-publicados/inventario.csv && head -n 5 docs/pcirn-publicados/inventario.csv`
Expected: 2222 linhas, primeira linha header handle,uuid,title,date_issued,dtype

- [ ] **Step 3: Commit**

```bash
git add docs/pcirn-publicados/inventario.csv
git commit -m "docs: add pcirn published inventory"
```

### Task 2: Piloto 20 fichas detalhadas

**Files:**
- Create: `docs/pcirn-publicados/lote-piloto/*.md` (20 arquivos)
- Create: `docs/pcirn-publicados/lote-piloto/RESUMO-EXECUTIVO.md`

- [ ] **Step 1: Selecionar 20 handles piloto**

Run:
```bash
head -n 21 docs/pcirn-publicados/inventario.csv | tail -n 20 | cut -d, -f1
```
Expected: lista 20 handles, inclui 123456789/24 (MVP teste)

- [ ] **Step 2: Extrair metadados completos por item piloto**

Run para cada UUID:
```bash
docker compose exec -T dspacedb psql -U dspace -d dspace -c "SELECT f.element||'.'||COALESCE(f.qualifier,'') AS campo, m.text_value FROM metadatavalue m JOIN metadatafieldregistry f ON f.metadata_field_id=m.metadata_field_id WHERE m.dspace_object_id='<UUID>' ORDER BY campo;"
```
Expected: retorna title, contributor, date.issued, type, subject, description.abstract, identifier etc.

- [ ] **Step 3: Localizar bitstream ORIGINAL**

Run:
```bash
docker compose exec -T dspacedb psql -U dspace -d dspace -c "SELECT b.uuid, b.internal_id, b.size_bytes FROM item2bundle ib JOIN bundle2bitstream bb ON bb.bundle_id=ib.bundle_id JOIN bitstream b ON b.uuid=bb.bitstream_id JOIN bundle bun ON bun.uuid=ib.bundle_id JOIN metadatavalue mv ON mv.dspace_object_id=bun.uuid WHERE ib.item_id='<UUID>' AND mv.text_value='ORIGINAL' LIMIT 5;"
```
Expected: 1 linha por item com internal_id e size_bytes > 0

- [ ] **Step 4: Baixar PDF e extrair texto**

Run:
```bash
docker compose exec -T dspace ls /dspace/assetstore/<2-char-prefix>/<internal_id_prefix> 2>&1 | head
# alternativa via REST público:
curl -s http://localhost:8500/server/api/core/items/<UUID>/bundles -H "Accept: application/json" | head -c 2000
```
Expected: PDF localizado; texto extraído com `pdftotext doc.pdf - | head -n 100`

- [ ] **Step 5: Escrever 20 fichas markdown**

Formato por ficha `docs/pcirn-publicados/lote-piloto/<handle-sanitizado>.md`:
```markdown
# <titulo>
- Handle: <handle>
- UUID: <uuid>
- Coleção: 123456789/2
- Autor/relator:
- Data emissão:
- Tipo:
- Assunto:
- Ementa original:
- Resumo PDF (5-8 linhas):
- Pontos-chave:
- Observações:
```
Expected: 20 arquivos criados

- [ ] **Step 6: Commit piloto**

```bash
git add docs/pcirn-publicados/lote-piloto/
git commit -m "docs: add pcirn pilot 20 fichas"
```

### Task 3: Validação piloto + escala em lotes

**Files:**
- Modify: `docs/pcirn-publicados/lote-piloto/RESUMO-EXECUTIVO.md`

- [ ] **Step 1: Consolidar executivo piloto**

Escrever `RESUMO-EXECUTIVO.md` com: total 20, distribuição por tipo/ano, % PDFs legíveis vs OCR ruim vs ausentes, exemplos 3 melhores resumos.
Expected: arquivo existe com tabela

- [ ] **Step 2: Pedir aprovação para escala**

Perguntar ao usuário via question tool se piloto ok para escalar em lotes de 200.
Expected: aprovação explícita antes de Task 4

### Task 4: Lotes 200 itens até 2221

**Files:**
- Create: `docs/pcirn-publicados/lote-01/` ... `lote-11/`

- [ ] **Step 1: Processar lote-01 (linhas 22-221 do CSV)**

Repetir Steps 2-5 da Task 2 em script batch, com checkpoint a cada 50 itens, coluna observações para falhas.
Run: `wc -l docs/pcirn-publicados/lote-01/*.md`
Expected: 200 fichas

- [ ] **Step 2: Commit por lote**

```bash
git add docs/pcirn-publicados/lote-01/
git commit -m "docs: add pcirn lote-01 200 fichas"
```
Expected: commit ok, repetir até lote-11 (último com 21 itens)

### Task 5: Consolidado final

**Files:**
- Create: `docs/pcirn-publicados/RESUMO-FINAL.md`

- [ ] **Step 1: Gerar resumo final**

Consolidar: total fichas, % por tipo (PORTARIA/DECRETO/LEI), cobertura temporal, top assuntos, % qualidade PDF, pendências.
Expected: arquivo com tabelas + top 10 achados

- [ ] **Step 2: Commit final**

```bash
git add docs/pcirn-publicados/RESUMO-FINAL.md
git commit -m "docs: add pcirn final summary"
```

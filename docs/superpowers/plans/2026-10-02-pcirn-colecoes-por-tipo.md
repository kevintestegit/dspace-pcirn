# PCIRN Collections by Document Type Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the collection directory with seven global document-type searches, including new PAP and Memória Institucional types.

**Architecture:** Reuse DSpace configured search pages and discovery filters. Add two controlled item types, configure global searches without a collection/community scope, and make the collection page link to those searches.

**Tech Stack:** DSpace Spring XML and controlled vocabulary; Angular 20, RouterLink, ngx-translate.

**Spec:** `docs/superpowers/specs/2026-10-02-pcirn-colecoes-por-tipo-design.md`

## Global Constraints

- Show only the seven categories in the order specified by the spec.
- Category searches must have no community or collection scope.
- Searches must retain the current-item, not-withdrawn, discoverable filters.
- Existing items are not automatically reclassified.
- Do not change item or collection permissions.

## Review Focus

- Portaria category includes `PORTARIA`, `PORTARIA_E_ATO_NORMATIVO_INTERNO`, `DECRETO`, and `LEI`.
- PAP and Memória Institucional are selectable vocabulary values and match their search filters exactly.
- Guides include both `MANUAL_GUIA` and `MANUAL_GESTAO`.
- Category links open the right configured search page, including existing POP and report configurations.
- Collection directory no longer fetches communities, item counts, or individual collections.

---

### Task 1: Add global discovery configurations and document types

**Files:**
- Modify: `dspace/config/spring/api/discovery.xml`
- Modify: `dspace/config/controlled-vocabularies/pcirn-document-types.xml`
- Modify: `dspace-angular/source/src/assets/i18n/pt-BR.json5`
- Modify: `dspace-angular/source/src/assets/i18n/en.json5`

**Interfaces:**
- Produces search configuration IDs: `pcirnNormas`, `pcirnPops`, `pcirnPap`, `pcirnGuiasManuais`, `pcirnNotasTecnicas`, `pcirnRelatorios`, `pcirnMemoriaInstitucional`.
- Produces vocabulary values: `PAP` and `MEMORIA_INSTITUCIONAL`.

- [x] Extend `pcirnNormasConfiguration` to filter `itemtype:(PORTARIA OR PORTARIA_E_ATO_NORMATIVO_INTERNO OR DECRETO OR LEI)`.
- [x] Register all seven category IDs in `DiscoveryConfigurationService`'s map, reusing existing beans where available.
- [x] Add global configurations `pcirnPap`, `pcirnGuiasManuais`, `pcirnNotasTecnicas`, and `pcirnMemoriaInstitucional`; each includes the shared item/latest-version and visibility filters from the spec.
- [x] Add `PAP` and `MEMORIA_INSTITUCIONAL` controlled-vocabulary nodes and their `pt-BR`/`en` labels.
- [x] Add translated category headings for all seven search configuration IDs, following the existing `{configuration}.search.results.head` keys.
- [x] Run XML validation for `discovery.xml` and `pcirn-document-types.xml`.

### Task 2: Replace the collection directory with the seven category links

**Files:**
- Modify: `dspace-angular/source/src/themes/custom/app/collection-list-page/collection-list-page.component.ts`
- Modify: `dspace-angular/source/src/themes/custom/app/collection-list-page/collection-list-page.component.html`
- Modify: `dspace-angular/source/src/assets/i18n/pt-BR.json5`
- Modify: `dspace-angular/source/src/assets/i18n/en.json5`

**Interfaces:**
- Consumes the seven search configuration IDs and translated search headings from Task 1.
- Produces links to `/search` with query parameter `configuration` set to the matching ID, following `PCIRN_SEARCH_CONFIGURATIONS` in `home-page/pcirn-home-data.service.ts`.

- [x] Replace runtime collection loading, community lookups, counts, filtering, and failure states with the seven ordered category links.
- [x] Reuse the existing PCIRN list card styles and add translated category titles and page subtitle in Portuguese and English.
- [x] From `dspace-angular/source`, run `npm run build`; confirm it completes. Run `git diff --check` from the repository root.

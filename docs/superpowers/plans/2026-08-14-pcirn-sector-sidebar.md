# PCIRN Sector Sidebar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make authenticated users see only the PCIRN sectors and collections authorized by their DSpace group memberships, with support for membership in multiple sectors.

**Architecture:** Reuse DSpace communities, collections, `ResourcePolicy`, and `epersongroup2eperson` as the source of truth. A PostgreSQL migration will create sector membership groups and replace the current global `Usuarios_Logados` read grant on PCIRN objects with sector-specific read policies while preserving the existing `NUGECID` workflow group. Angular will add a regular-user sector sidebar that consumes the existing authorized community endpoint; the administrative sidebar remains unchanged.

**Tech Stack:** DSpace 9.4 Java/PostgreSQL migrations, DSpace REST, Angular 20 standalone components, RxJS, existing Portuguese i18n and Docker Compose development runtime.

---

## Scope and file map

**Create:**

- `dspace-api/src/main/resources/org/dspace/storage/rdbms/sqlmigration/postgres/V9.4_2026.08.15__pcirn_sector_access.sql` — idempotent sector groups and object read policies.
- `dspace-angular/source/src/app/shared/sector-sidebar/sector-sidebar.component.ts` — authorized sector query and rendering state.
- `dspace-angular/source/src/app/shared/sector-sidebar/sector-sidebar.component.html` — accessible sector links.
- `dspace-angular/source/src/app/shared/sector-sidebar/sector-sidebar.component.scss` — sidebar layout aligned with the PCIRN header/admin sidebar.
- `dspace-angular/source/src/app/shared/sector-sidebar/themed-sector-sidebar.component.ts` — theme wrapper with unthemed fallback.
- `dspace-angular/source/src/app/shared/sector-sidebar/sector-sidebar.component.spec.ts` — component behavior tests.

**Modify:**

- `dspace-angular/source/src/app/root/root.component.html` — render the sector sidebar alongside the existing admin sidebar.
- `dspace-angular/source/src/app/root/root.component.ts` — expose sector sidebar width/visibility state without changing admin menu rules.
- `dspace-angular/source/src/themes/custom/app/root/root.component.ts` — import the new themed sector sidebar in the custom root.
- `dspace-angular/source/src/app/root/root.component.scss` — reserve/animate layout space for the regular-user sidebar.
- `dspace-angular/source/src/assets/i18n/pt-BR.json5` — add sector-sidebar labels and empty state.
- `dspace-angular/source/scripts/pcirn-home.test.mjs` — add source-level assertions for the sector sidebar contract.

**Avoid:** `AdminSidebarComponent`, `app.menus.ts`, the existing workflow `NUGECID` group, and unrelated access migrations. No new sector table or Angular-only sector registry.

## Task 1: Add sector groups and policy migration

**Files:**

- Create `dspace-api/src/main/resources/org/dspace/storage/rdbms/sqlmigration/postgres/V9.4_2026.08.15__pcirn_sector_access.sql`.
- Test with the running PostgreSQL container and a disposable user membership.

- [ ] **Step 1: Write the migration header and group creation.**

Create the five membership groups with `INSERT ... WHERE NOT EXISTS`, using these exact names:

```sql
PCIRN_Setor_DG
PCIRN_Setor_IC
PCIRN_Setor_II
PCIRN_Setor_IML
PCIRN_Setor_NUGECID
```

Do not rename or delete the existing `NUGECID`, `PCIRN_Depositantes`, `Usuarios_Logados`, or `Administrator` groups.

- [ ] **Step 2: Resolve sector communities by `dc.title`.**

Map the groups to the existing top-level communities exactly:

```text
PCIRN_Setor_DG      -> Gestão Estratégica e Administrativa (DG)
PCIRN_Setor_IC      -> Instituto de Criminalística (IC)
PCIRN_Setor_II      -> Instituto de Identificação (II)
PCIRN_Setor_IML     -> Instituto de Medicina Legal (IML)
PCIRN_Setor_NUGECID -> Núcleo de Gestão do Conhecimento, Informação, Documentação e Memória (NUGECID)
```

The migration must fail loudly when a mapped community is missing instead of silently granting a policy to the wrong object.

- [ ] **Step 3: Grant sector `READ` policies to community trees.**

For every mapped top-level community, add a `READ` policy for its sector group to:

- the community UUID;
- every direct collection in `community2collection`;
- every existing item in those collections;
- every bundle belonging to those items;
- every bitstream belonging to those bundles.

Use `action_id = 0` for `READ` and `WHERE NOT EXISTS` guards on `(dspace_object, action_id, epersongroup_id)`.

- [ ] **Step 4: Remove only the global PCIRN read grant.**

Delete `READ` policies for `Usuarios_Logados` from the mapped community/collection/item/bundle/bitstream trees. Preserve policies for `Administrator`, explicit eperson grants, workflow grants, `ADD` policies, and all non-PCIRN objects.

- [ ] **Step 5: Preserve NUGECID workflow behavior.**

Leave the existing `NUGECID` group and its collection `editor` workflow role untouched. Sector visibility uses `PCIRN_Setor_NUGECID`; curatorial authority continues using `NUGECID`.

- [ ] **Step 6: Run the migration against the current DB without rebuilding.**

Run:

```bash
docker exec -i dspacedb psql -U dspace -d dspace \
  < dspace-api/src/main/resources/org/dspace/storage/rdbms/sqlmigration/postgres/V9.4_2026.08.15__pcirn_sector_access.sql
```

Expected: exit code `0`; five sector groups exist; each sector tree has a sector-group `READ` policy; no `Usuarios_Logados` `READ` remains on those trees.

## Task 2: Prove multiple sector memberships and authorization boundaries

**Files:** Database state only; no application source changes.

- [ ] **Step 1: Assign Kevin to one disposable sector group.**

Add `kevin.borges.700@ufrn.edu.br` to `PCIRN_Setor_IC` using the existing group membership path. Do not remove `Usuarios_Logados` or alter his email/password.

- [ ] **Step 2: Authenticate and query top-level communities.**

Use the existing CSRF + password login flow, then request `/server/api/core/communities/search/top`. Expected: only Instituto de Criminalística (IC) is returned for Kevin.

- [ ] **Step 3: Add a second sector membership.**

Add Kevin to `PCIRN_Setor_II` without removing IC. Repeat the query. Expected: IC and II are returned; DG and IML are absent.

- [ ] **Step 4: Test an unauthorized object.**

Request a DG community/collection URL with Kevin's bearer token. Expected: `401` or `403` according to the existing REST authorization response, never the protected metadata/content.

- [ ] **Step 5: Test admin and NUGECID preservation.**

Verify `admin@localhost` can still list all four operational communities and the NUGECID sector, and that the previously validated NUGECID workflow can still approve/devolve an item.

## Task 3: Implement the regular-user sector sidebar

**Files:**

- Create the five `sector-sidebar` files listed above.
- Modify both root components and root stylesheet.

- [ ] **Step 1: Add the component contract.**

The component exposes an observable of `Community` objects from `CommunityDataService.findTop(...)`, renders only when the user is authenticated and at least one authorized community exists, and links each object to `/communities/<uuid>`. It must not call an admin authorization endpoint or maintain a local sector list.

- [ ] **Step 2: Avoid duplicate admin navigation.**

Hide the regular-user sector sidebar whenever the existing admin sidebar has visible sections. Regular users get the sector sidebar; administrators retain their existing admin sidebar and can still use sectors through authorized community navigation.

- [ ] **Step 3: Add responsive markup.**

Use semantic `<aside aria-label="Setores">`, a compact PCIRN logo/header, one link per authorized community, loading state, and an explicit empty state that does not expose unauthorized sector names.

- [ ] **Step 4: Integrate root layout.**

Render `<ds-sector-sidebar>` before the existing `<ds-admin-sidebar>`. Extend the root's visibility/width observables only for the regular sidebar; do not change `MenuID.ADMIN`, admin menu providers, or admin permissions. Preserve the existing mobile collapse behavior and the PCIRN logo/header alignment.

- [ ] **Step 5: Add Portuguese translations.**

Add:

```json5
"sector-sidebar.title": "Setores",
"sector-sidebar.loading": "Carregando setores...",
"sector-sidebar.empty": "Nenhum setor foi atribuído ao seu usuário."
```

- [ ] **Step 6: Add component/source tests.**

The component test must assert: one authorized community renders one link; two memberships render two links; an empty authorized response renders the empty state; admin sidebar visibility suppresses the sector sidebar. Extend `scripts/pcirn-home.test.mjs` with source assertions for the selector, `findTop`, and sector translation keys.

## Task 4: Validate the user-visible flow

**Files:** No additional source files.

- [ ] **Step 1: Run focused Angular tests.**

Run:

```bash
cd dspace-angular/source
node --test scripts/pcirn-home.test.mjs
```

Expected: all existing tests plus sector-sidebar assertions pass.

- [ ] **Step 2: Restart only the development Angular service.**

Run:

```bash
docker compose up -d --no-build --force-recreate dspace-angular
```

Expected: the existing Node 22 development container returns to `Up`; no image rebuild occurs.

- [ ] **Step 3: Validate Kevin in the browser.**

After login, Kevin sees the sector sidebar with IC; after the second membership is added and the session is refreshed, he sees IC and II. Direct navigation to DG is rejected/forbidden.

- [ ] **Step 4: Validate the administrative regression path.**

Admin still sees the existing administrative sidebar and all expected access-control items. NUGECID curators still see and process workflow tasks.

## Task 5: Document membership operations

**Files:**

- Modify `docs/goals/pcirn-mvp/RESULTS.md` with the implemented sector groups and acceptance evidence.
- Add `docs/goals/pcirn-sector-sidebar/GOAL.md` as the execution handoff.

- [ ] **Step 1: Document exact group names and multi-sector operation.**

State that administrators add/remove users from any combination of `PCIRN_Setor_*` groups through the existing group-management UI; no Angular code change is required for membership editing.

- [ ] **Step 2: Record evidence.**

Include the API results for Kevin with one and two sector memberships, the denied DG request, the admin all-sector result, and the NUGECID workflow regression result.

## Acceptance gate

The feature is complete only when all of the following are true:

- a user with one sector sees exactly one sector;
- a user with two sector memberships sees exactly two sectors;
- a user cannot read another sector's protected objects;
- NUGECID is a visible sector without replacing its workflow group;
- admin and NUGECID curation behavior remains intact;
- focused Angular tests pass;
- no Docker image rebuild is needed for source iteration.


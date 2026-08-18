# PCIRN Reference Home Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Rebuild the public PCIRN home to match the approved reference while loading real DSpace data and exposing only public Portarias to anonymous users.

**Architecture:** Keep the existing custom Angular theme and DSpace data services. Add one small home data facade that combines real communities, collections, items and counts; add one idempotent SQL migration that grants anonymous read only to the Portarias tree; keep protected cards visible but guarded. The existing Docker development runtime is used for validation.

**Tech Stack:** DSpace 9.4 REST, PostgreSQL/Flyway SQL migrations, Angular standalone components, RxJS, NgRx auth selector, Bootstrap layout utilities, Node node:test, Docker Compose.

---

## File map

- Create: dspace-api/src/main/resources/org/dspace/storage/rdbms/sqlmigration/postgres/V9.4_2026.08.18__pcirn_public_portarias.sql — grants Anonymous read to the four Portarias collections and all existing descendants.
- Create: dspace-angular/source/src/themes/custom/app/home-page/pcirn-home-data.service.ts — combines existing DSpace data services into independent home blocks.
- Create: dspace-angular/source/src/themes/custom/app/home-page/pcirn-home-data.service.spec.ts — verifies public filtering and independent block failures.
- Modify: dspace-angular/source/src/themes/custom/app/home-page/home-page.component.ts — exposes real home observables and auth-aware card destinations.
- Modify: dspace-angular/source/src/themes/custom/app/home-page/home-page.component.html — implements the approved header-compatible home sections.
- Modify: dspace-angular/source/src/themes/custom/app/home-page/home-page.component.scss — implements the reference visual system and responsive states.
- Modify: dspace-angular/source/src/app/navbar/navbar.component.html — adds the approved public navigation labels without restoring anonymous statistics.
- Modify: dspace-angular/source/src/app/navbar/navbar.component.scss — styles the light institutional navigation.
- Modify: dspace-angular/source/src/app/header/header.component.scss — aligns search, language and login controls with the light header.
- Modify: dspace-angular/source/src/app/footer/footer.component.html — replaces placeholder footer copy with PCIRN institutional navigation.
- Modify: dspace-angular/source/src/app/footer/footer.component.scss — styles the dark institutional footer.
- Modify: dspace-angular/source/scripts/pcirn-home.test.mjs — extends static contract checks for real-data bindings, access labels and reference sections.

## Task 1: Open only the public Portarias tree

**Files:**
- Create: dspace-api/src/main/resources/org/dspace/storage/rdbms/sqlmigration/postgres/V9.4_2026.08.18__pcirn_public_portarias.sql
- Test: SQL queries and anonymous REST requests

- [ ] Step 1: Write the failing public-access probe.

Run:

~~~bash
for endpoint in \
  'http://localhost:8501/server/api/core/communities/search/top?size=1' \
  'http://localhost:8501/server/api/core/collections?size=1' \
  'http://localhost:8501/server/api/discover/search/objects?size=1'; do
  curl -sS -o /tmp/pcirn-public-probe.json -w "%{http_code} $endpoint\n" "$endpoint"
done
~~~

Expected before the migration: protected endpoints return 401, while /server/api/core/sites remains public.

- [ ] Step 2: Add the idempotent migration.

Resolve the Anonymous group and the collections titled Portarias e Atos Normativos Internos under these communities:

~~~text
Gestão Estratégica e Administrativa (DG)
Instituto de Criminalística (IC)
Instituto de Identificação (II)
Instituto de Medicina Legal (IML)
~~~

For each resolved UUID, insert missing Anonymous policies for actions READ (0), DEFAULT_BITSTREAM_READ (9) and DEFAULT_ITEM_READ (10). Insert Anonymous READ (0) for each owning community. For existing items, bundles and bitstreams below those collections, copy the existing sector read policy as an additional Anonymous policy; do not remove sector membership policies. Use WHERE NOT EXISTS for every insert.

- [ ] Step 3: Apply and verify the migration.

Run:

~~~bash
docker compose up -d dspace
docker compose logs --tail=120 dspace | rg 'Started ServerBootApplication|Flyway|2026.08.18|ERROR'
~~~

Expected: Flyway records 9.4.2026.08.18 in schema_version and DSpace reaches Started ServerBootApplication without migration errors.

- [ ] Step 4: Verify the access boundary.

Run:

~~~bash
curl -fsS 'http://localhost:8501/server/api/core/communities/search/top?size=10' >/tmp/pcirn-public-communities.json
curl -fsS 'http://localhost:8501/server/api/core/collections?size=10' >/tmp/pcirn-public-collections.json
curl -fsS 'http://localhost:8501/server/api/discover/search/objects?size=3' >/tmp/pcirn-public-search.json
docker compose exec -T dspacedb psql -U dspace -d dspace -Atc "SELECT version FROM schema_version WHERE version='9.4.2026.08.18';"
~~~

Expected: public collection/community/search requests return 200; only the four Portarias collections and their public descendants are discoverable. A direct request to a protected POP/production/report resource remains 401 or 403.

- [ ] Step 5: Commit the migration.

~~~bash
git add dspace-api/src/main/resources/org/dspace/storage/rdbms/sqlmigration/postgres/V9.4_2026.08.18__pcirn_public_portarias.sql
git commit -m "feat: publish PCIRN portarias anonymously"
~~~

## Task 2: Build the real-data home facade

**Files:**
- Create: dspace-angular/source/src/themes/custom/app/home-page/pcirn-home-data.service.ts
- Create: dspace-angular/source/src/themes/custom/app/home-page/pcirn-home-data.service.spec.ts

- [ ] Step 1: Write the failing service tests.

Construct the facade with spies for CommunityDataService, CollectionDataService, ItemDataService/SearchService and the auth selector. Assert these behaviors:

~~~ts
it('uses only public portaria data for anonymous users', () => {
  expect(buildQuickAccess(false)[0].route).toBe('/community-list');
  expect(buildQuickAccess(false).filter(card => card.requiresLogin)).toHaveSize(3);
});

it('keeps a failed block isolated from successful blocks', () => {
  expect(result.collections.error).toBeTrue();
  expect(result.metrics.loading).toBeFalse();
  expect(result.latest.loading).toBeFalse();
});
~~~

Export `buildQuickAccess(isAuthenticated: boolean)` from the facade file for this pure mapping test. The service contract is a PcirnHomeData object with quickAccess, featuredCommunities, metrics, latestPublications, and per-block loading/error state. No method may return placeholder titles or hard-coded counts.

- [ ] Step 2: Run the focused Angular test and verify failure.

Run from dspace-angular/source:

~~~bash
npm test -- --include='src/themes/custom/app/home-page/pcirn-home-data.service.spec.ts' --watch=false
~~~

Expected: FAIL because the facade and its public-only mapping do not exist.

- [ ] Step 3: Implement the minimal facade.

Use the existing services and operators:

~~~ts
this.communityDataService.findTop({ elementsPerPage: 4, currentPage: 1 });
this.collectionDataService.findByParent(community.id, { elementsPerPage: 4, currentPage: 1 });
this.searchService.search<Item>(publicPublicationSearchOptions, undefined, true, true);
~~~

Map RemoteData payloads into view models, use combineLatest/forkJoin only where the blocks are independent, and convert each block failure into its own error state. Anonymous requests use only the public Portarias scope; authenticated requests may use the authorized scope returned by the same services. Do not add a second HTTP client or a custom REST endpoint.

- [ ] Step 4: Run the focused service test and verify success.

Run the same command. Expected: all facade tests pass.

- [ ] Step 5: Commit the facade.

~~~bash
git add dspace-angular/source/src/themes/custom/app/home-page/pcirn-home-data.service.ts dspace-angular/source/src/themes/custom/app/home-page/pcirn-home-data.service.spec.ts
git commit -m "feat: load real data for PCIRN home"
~~~

## Task 3: Rebuild the home content and responsive layout

**Files:**
- Modify: dspace-angular/source/src/themes/custom/app/home-page/home-page.component.ts
- Modify: dspace-angular/source/src/themes/custom/app/home-page/home-page.component.html
- Modify: dspace-angular/source/src/themes/custom/app/home-page/home-page.component.scss
- Modify: dspace-angular/source/scripts/pcirn-home.test.mjs

- [ ] Step 1: Extend the static contract test before changing the template.

Add assertions to pcirn-home.test.mjs:

~~~js
assert.match(homeTemplate, /pcirn-home-hero/);
assert.match(homeTemplate, /pcirn-home-search/);
assert.match(homeTemplate, /pcirn-home-quick-access/);
assert.match(homeTemplate, /pcirn-home-featured/);
assert.match(homeTemplate, /pcirn-home-metrics/);
assert.match(homeTemplate, /pcirn-home-latest/);
assert.match(homeTemplate, /pcirnHomeData/);
assert.doesNotMatch(homeTemplate, /Relatório Anual de Atividades 2023/);
~~~

- [ ] Step 2: Run the contract test and verify failure.

~~~bash
node dspace-angular/source/scripts/pcirn-home.test.mjs
~~~

Expected: FAIL on the new reference-section assertions.

- [ ] Step 3: Implement the Angular bindings.

Inject the facade into HomePageComponent, expose its PcirnHomeData observable as pcirnHomeData$, and use async/@if/@for in the template. Keep only the four quick-access labels as institutional taxonomy; every collection, metric and publication title/value must come from the facade.

Use routes with the existing authentication behavior:

~~~html
<a [routerLink]="card.route" [queryParams]="card.queryParams" [class.pcirn-home-card-locked]="card.requiresLogin">
  <span>{{ card.title }}</span>
</a>
~~~

The template must contain the approved order: hero, search overlay, quick access, featured collections, metrics, latest publications, footer boundary. Include loading skeletons and a compact block-level error state.

- [ ] Step 4: Implement the visual system.

Use the existing hero-pcirn.webp, brasao-policia-cientifica-rn.png and footer-bg-pcirn.webp. Define the reference tokens in .pcirn-home: dark navy #062753, accent yellow #eab52c, paper background #f7f9fc, and blue action #08498f. Keep the header in normal flow so the hero cannot be clipped. Match the approved desktop layout and add media queries at 900px and 600px to stack cards and search controls.

- [ ] Step 5: Run contract and style checks.

~~~bash
node dspace-angular/source/scripts/pcirn-home.test.mjs
git diff --check
~~~

Expected: all static tests pass and git diff --check is clean.

- [ ] Step 6: Commit the home.

~~~bash
git add dspace-angular/source/src/themes/custom/app/home-page/home-page.component.ts dspace-angular/source/src/themes/custom/app/home-page/home-page.component.html dspace-angular/source/src/themes/custom/app/home-page/home-page.component.scss dspace-angular/source/scripts/pcirn-home.test.mjs
git commit -m "feat: redesign PCIRN institutional home"
~~~

## Task 4: Match the approved header and footer chrome

**Files:**
- Modify: dspace-angular/source/src/app/navbar/navbar.component.html
- Modify: dspace-angular/source/src/app/navbar/navbar.component.scss
- Modify: dspace-angular/source/src/app/header/header.component.scss
- Modify: dspace-angular/source/src/app/footer/footer.component.html
- Modify: dspace-angular/source/src/app/footer/footer.component.scss
- Modify: dspace-angular/source/scripts/pcirn-home.test.mjs

- [ ] Step 1: Write the failing chrome assertions.

Extend pcirn-home.test.mjs:

~~~js
assert.match(navbarTemplate, /Comunidades/);
assert.match(navbarTemplate, /Coleções/);
assert.match(navbarTemplate, /Publicações/);
assert.match(footerTemplate, /POLÍCIA CIENTÍFICA/);
assert.match(footerTemplate, /NUGECID/);
assert.doesNotMatch(statisticsMenu, /visible:\s*true/);
~~~

- [ ] Step 2: Run the test and verify failure.

~~~bash
node dspace-angular/source/scripts/pcirn-home.test.mjs
~~~

Expected: FAIL because the base navbar/footer still contain generic DSpace content.

- [ ] Step 3: Implement the chrome without changing auth behavior.

Render the institutional links through RouterLink, keep ds-search-navbar, ds-lang-switch and ds-auth-nav-menu, and preserve the existing anonymous statistics visibility guard. Use the existing custom theme component indirection; do not create a second header component.

- [ ] Step 4: Run the chrome test and verify success.

~~~bash
node dspace-angular/source/scripts/pcirn-home.test.mjs
~~~

Expected: all static checks pass.

- [ ] Step 5: Commit the chrome.

~~~bash
git add dspace-angular/source/src/app/navbar/navbar.component.html dspace-angular/source/src/app/navbar/navbar.component.scss dspace-angular/source/src/app/header/header.component.scss dspace-angular/source/src/app/footer/footer.component.html dspace-angular/source/src/app/footer/footer.component.scss dspace-angular/source/scripts/pcirn-home.test.mjs
git commit -m "feat: style PCIRN institutional chrome"
~~~

## Task 5: Validate public and authenticated flows

**Files:**
- Test: dspace-angular/source/scripts/pcirn-home.test.mjs
- Test: live REST/Angular containers

- [ ] Step 1: Verify anonymous REST visibility.

~~~bash
curl -fsS -o /tmp/pcirn-home-public.json -w '%{http_code}\n' 'http://localhost:8501/server/api/discover/search/objects?size=3'
curl -fsS -o /tmp/pcirn-home-public-collections.json -w '%{http_code}\n' 'http://localhost:8501/server/api/core/collections?size=10'
~~~

Expected: 200 for public Portarias data.

- [ ] Step 2: Verify protected REST visibility.

Resolve one protected item directly from the database, excluding the four public Portarias collections, and request it without credentials:

~~~bash
protected_uuid=$(docker compose exec -T dspacedb psql -U dspace -d dspace -Atc "SELECT i.uuid FROM item i WHERE NOT EXISTS (SELECT 1 FROM collection c JOIN metadatavalue mv ON mv.dspace_object_id=c.uuid JOIN metadatafieldregistry mf ON mf.metadata_field_id=mv.metadata_field_id WHERE c.uuid=i.owning_collection AND mf.element='title' AND mf.qualifier IS NULL AND mv.text_value='Portarias e Atos Normativos Internos') LIMIT 1;")
curl -sS -o /tmp/pcirn-protected-item.json -w '%{http_code}\n' "http://localhost:8501/server/api/core/items/$protected_uuid"
~~~

Expected: 401 or 403; never 200.

- [ ] Step 3: Rebuild the development Angular container.

~~~bash
docker compose restart dspace-angular
docker compose logs -f --tail=20 dspace-angular
~~~

Expected: Browser application bundle generation complete and Compiled successfully on port 4000.

- [ ] Step 4: Run the focused checks.

~~~bash
node dspace-angular/source/scripts/pcirn-home.test.mjs
git diff --check
~~~

Expected: all tests pass and no whitespace errors are reported.

- [ ] Step 5: Verify the browser flows.

Open http://10.9.233.96:4000/home anonymously and confirm the approved visual order, real counts/titles, no sidebar, and accessible Portarias. Authenticate with a provisioned account and confirm protected cards resolve only after login and the sidebar appears only after authentication.

- [ ] Step 6: Keep unrelated worktree changes untouched.

Only commit code/test changes from the tasks. Do not stage .env, generated .buildx, .playwright-mcp, .superpowers, or unrelated existing worktree changes.

## Final self-review

- Public home and header requirements are covered by Tasks 3 and 4.
- Real communities, collections, items and metrics are covered by Task 2.
- Anonymous Portarias access and protected POP/production/report access are covered by Tasks 1 and 5.
- Responsive and accessible behavior is covered by Task 3.
- NUGECID approval workflow is explicitly untouched.
- No static sample publication or hard-coded metric is allowed by the facade contract and contract test.

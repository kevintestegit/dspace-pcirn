# PCIRN Governance Admin Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver `/admin/governance` and the three PCIRN REST endpoints that back it, with the policy rewrite rules from `docs/superpowers/specs/2026-09-22-pcirn-governanca-design.md`.

**Architecture:** One Spring `@RestController` in `dspace-server-webapp` using native DSpace services for the matrix and the policy rewrite; one Angular lazy admin page in the `dspace-angular/source` submodule using raw REST through `DspaceRestService` for everything except membership, which reuses the native group/e-person endpoints.

**Tech Stack:** Java 17, Spring Boot (DSpace 9 REST), JUnit 4 + MockMvc integration tests, Angular 20 (standalone components), Jasmine/Karma.

---

## File map

- Create `dspace-server-webapp/src/main/java/org/dspace/app/rest/PcirnGovernanceRestController.java` — endpoints and policy rewrite.
- Create `dspace-server-webapp/src/main/java/org/dspace/app/rest/model/PcirnGovernanceRest.java` — DTO records.
- Create `dspace-server-webapp/src/test/java/org/dspace/app/rest/PcirnGovernanceRestControllerIT.java` — integration tests.
- Create `dspace-angular/source/src/app/admin/admin-governance/pcirn-governance-data.service.ts`.
- Create `dspace-angular/source/src/app/admin/admin-governance/admin-governance.component.ts|html|scss|spec.ts`.
- Create `dspace-angular/source/src/app/shared/menu/providers/governance.menu.ts`.
- Modify `dspace-angular/source/src/app/admin/admin-routes.ts`, `dspace-angular/source/src/app/app.menus.ts`.
- Modify `dspace-angular/source/src/assets/i18n/pt-BR.json5`, `en.json5`.
- No new database migration.

---

### Task 1: Matrix endpoint

**Files:** create controller, DTOs; test file.

- [ ] **Step 1: Write the failing IT for the matrix**

```java
@Test
public void governanceListsCommunityModeAndCollections() throws Exception {
    context.turnOffAuthorisationSystem();
    parentCommunity = CommunityBuilder.createCommunity(context);
    parentCommunity.setName("Instituto de Criminalística");
    Collection collection = CollectionBuilder.createCollection(context, parentCommunity);
    collection.setName("Portarias");
    context.restoreAuthSystemState();

    getClient().perform(get("/api/pcirn/governance").header("Authorization", getAuthToken(admin)))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.communities[0].name").value("Instituto de Criminalística"))
        .andExpect(jsonPath("$.communities[0].accessMode").value("public"))
        .andExpect(jsonPath("$.communities[0].collections[0].name").value("Portarias"))
        .andExpect(jsonPath("$.curationGroup.name").value("NUGECID"));
}
```

- [ ] **Step 2: Run it and confirm it fails**

Run from repository root after `mvn install -DskipTests`:
`mvn -pl dspace-server-webapp verify -DskipUnitTests=true -DskipIntegrationTests=false -Dit.test=PcirnGovernanceRestControllerIT`
Expected: 404 on `/api/pcirn/governance`.

- [ ] **Step 3: Implement the DTOs**

`PcirnGovernanceRest.java`:

```java
public final class PcirnGovernanceRest {
    private PcirnGovernanceRest() { }

    public record GroupSummary(UUID uuid, String name, int memberCount) { }

    public record CollectionGovernance(UUID uuid, String name, String handle,
                                       GroupSummary publishGroup) { }

    public record CommunityGovernance(UUID uuid, String name, String handle, String accessMode,
                                      GroupSummary sectorGroup,
                                      List<CollectionGovernance> collections) { }

    public record Governance(List<CommunityGovernance> communities, GroupSummary curationGroup) { }

    public record AccessModeRequest(String mode, UUID sectorGroup) { }

    public record SectorRequest(UUID sectorGroup) { }
}
```

- [ ] **Step 4: Implement the controller GET**

Constructor-inject `CommunityService`, `CollectionService`, `ItemService`, `BitstreamService`,
`ResourcePolicyService`, `GroupService`, `AuthorizeService`.

```java
public static final String CURATION_GROUP_NAME = "NUGECID";
public static final String MODE_PUBLIC = "public";
public static final String MODE_RESTRICTED = "restricted";

@GetMapping
@PreAuthorize("hasAuthority('ADMIN')")
public Governance getGovernance() throws SQLException {
    Context context = ContextUtil.obtainCurrentRequestContext();
    Group anonymous = groupService.findByName(context, Group.ANONYMOUS);
    Group administrator = groupService.findByName(context, Group.ADMIN);
    List<CommunityGovernance> communities = new ArrayList<>();
    for (Community community : communityService.findAll(context)) {
        communities.add(toCommunity(context, community, anonymous, administrator));
    }
    Governance result = new Governance(communities,
        toGroupSummary(context, groupService.findByName(context, CURATION_GROUP_NAME)));
    context.complete();
    return result;
}
```

`toCommunity` reads `READ` policies with `resourcePolicyService.find(context, community, Constants.READ)`:
`anonymousRead` when the group is Anonymous, otherwise the first non-Administrator group is the
sector group (stable order by group name). `accessMode` = restricted when a sector group exists and
Anonymous does not hold READ. Collections from `communityService.getAllCollections(context, community)`;
`publishGroup` = first non-Administrator group among `resourcePolicyService.find(context, collection, Constants.ADD)`
sorted by name. `toGroupSummary` returns `null` for a null group, otherwise the group with
`memberCount = groupService.allMembers(context, group).size()`.

- [ ] **Step 5: Run the IT again**

Expected: PASS.

- [ ] **Step 6: Commit**

```
git add dspace-server-webapp/src/main/java/org/dspace/app/rest/PcirnGovernanceRestController.java \
        dspace-server-webapp/src/main/java/org/dspace/app/rest/model/PcirnGovernanceRest.java \
        dspace-server-webapp/src/test/java/org/dspace/app/rest/PcirnGovernanceRestControllerIT.java
git commit -m "feat: add PCIRN governance matrix endpoint"
```

---

### Task 2: Community access mode endpoint

- [ ] **Step 1: Write failing ITs**

```java
@Test
public void restrictReplacesAnonymousReadAndKeepsSectorAdd() throws Exception {
    // community + collection + item + bitstream created with turnOffAuthorisationSystem
    // PUT /api/pcirn/governance/communities/{uuid}/access {"mode":"restricted","sectorGroup":<uuid>}
    getClient().perform(put("/api/pcirn/governance/communities/{uuid}/access", community.getID())
            .contentType(MediaType.APPLICATION_JSON)
            .content("{\"mode\":\"restricted\",\"sectorGroup\":\"" + sectorGroup.getID() + "\"}")
            .header("Authorization", getAuthToken(admin)))
        .andExpect(status().isOk());

    // anonymous read fails
    getClient().perform(get("/api/core/communities/{uuid}", community.getID()))
        .andExpect(status().isUnauthorized());
    // default policies now point to the sector group
    // (query repository through a second GET of the matrix and assert accessMode/memberCount)
}

@Test
public void restrictWithoutGroupIsRejected() throws Exception {
    // expect 422
}
```

- [ ] **Step 2: Run and confirm failure** (405/404).

- [ ] **Step 3: Implement PUT**

```java
@PutMapping("/communities/{uuid}/access")
@PreAuthorize("hasAuthority('ADMIN')")
public ResponseEntity<Void> setCommunityAccess(@PathVariable UUID uuid, @RequestBody AccessModeRequest body)
    throws SQLException, AuthorizeException {
    Context context = ContextUtil.obtainCurrentRequestContext();
    Community community = communityService.find(context, uuid);
    if (community == null) {
        throw new ResourceNotFoundException("No such community: " + uuid);
    }
    Group anonymous = groupService.findByName(context, Group.ANONYMOUS);
    Group administrator = groupService.findByName(context, Group.ADMIN);
    if (MODE_RESTRICTED.equals(body.mode())) {
        Group sector = body.sectorGroup() == null ? null : groupService.find(context, body.sectorGroup());
        if (sector == null || sector.equals(anonymous) || sector.equals(administrator)) {
            throw new UnprocessableEntityException("A valid sector group is required to restrict access");
        }
        applyCommunityAccess(context, community, anonymous, sector, true);
    } else if (MODE_PUBLIC.equals(body.mode())) {
        Group sector = existingSectorGroup(context, community, anonymous, administrator);
        applyCommunityAccess(context, community, sector, anonymous, false);
    } else {
        throw new UnprocessableEntityException("Unsupported access mode: " + body.mode());
    }
    context.complete();
    return ResponseEntity.ok().build();
}
```

`applyCommunityAccess`:

```java
private void applyCommunityAccess(Context context, Community community, Group from, Group to, boolean restricted)
    throws SQLException, AuthorizeException {
    replaceReadPolicy(context, community, from, to);
    for (Collection collection : communityService.getAllCollections(context, community)) {
        replaceReadPolicy(context, collection, from, to);
        replaceDefaultPolicy(context, collection, Constants.DEFAULT_ITEM_READ, from, to);
        replaceDefaultPolicy(context, collection, Constants.DEFAULT_BITSTREAM_READ, from, to);
        if (restricted) {
            ensurePolicy(context, collection, to, Constants.ADD);
        }
        itemService.findAllByCollection(context, collection)
            .forEachRemaining(item -> replaceReadPolicyUnchecked(context, item, from, to));
        bitstreamService.getCollectionBitstreams(context, collection)
            .forEachRemaining(bitstream -> replaceReadPolicyUnchecked(context, bitstream, from, to));
    }
}
```

Helpers: `replaceReadPolicy` updates only policies whose group id equals `from`; when none match
and `to` is a real group, `ensurePolicy` creates it. `ensurePolicy` checks
`authorizeService.findByTypeGroupAction(context, dso, group, action)` first, so repeated calls are
idempotent. Wrap checked exceptions from `forEachRemaining` in a small private
`replaceReadPolicyUnchecked` that rethrows as `UncheckedSQLException`-style runtime and unwrap in the
endpoint, aborting the context in the catch before rethrowing.

- [ ] **Step 4: Run the ITs** — all pass, including anonymous 401 after restriction and anonymous 200 after restoring public.

- [ ] **Step 5: Commit** `feat: add PCIRN community access mode endpoint`.

---

### Task 3: Collection sector binding endpoint

- [ ] **Step 1: Failing IT**: `PUT /collections/{uuid}/sector` on a collection without an `ADD` policy creates it and, when the owning community is public, sets collection READ/defaults to Anonymous; second call is a no-op (same policy count).
- [ ] **Step 2: Implement** — validate collection and group as in Task 2; when any owning community is restricted to a sector group different from the requested group, return 422; ensure `ADD`; reconcile collection READ + defaults + items/bitstreams to the community's read group (sector when restricted, Anonymous otherwise).
- [ ] **Step 3: Run ITs**, **Step 4: Commit** `feat: add PCIRN collection sector binding endpoint`.

---

### Task 4: Angular data service

**File:** `dspace-angular/source/src/app/admin/admin-governance/pcirn-governance-data.service.ts`

```ts
@Injectable({ providedIn: 'root' })
export class PcirnGovernanceDataService {
  private readonly restUrl: string;

  constructor(@Inject(APP_CONFIG) appConfig: AppConfig, private restService: DspaceRestService) {
    this.restUrl = `${appConfig.rest.baseUrl}`;
  }

  getGovernance(): Observable<RawRestResponse> {
    return this.restService.get(`${this.restUrl}/pcirn/governance`);
  }

  setCommunityAccess(communityUuid: string, mode: string, sectorGroup?: string): Observable<RawRestResponse> {
    return this.restService.request(RestRequestMethod.PUT,
      `${this.restUrl}/pcirn/governance/communities/${communityUuid}/access`, { mode, sectorGroup });
  }

  bindCollectionSector(collectionUuid: string, sectorGroup: string): Observable<RawRestResponse> {
    return this.restService.request(RestRequestMethod.PUT,
      `${this.restUrl}/pcirn/governance/collections/${collectionUuid}/sector`, { sectorGroup });
  }

  getGroupMembers(groupUuid: string): Observable<RawRestResponse> {
    return this.restService.get(`${this.restUrl}/core/groups/${groupUuid}/epersons?size=100`);
  }

  searchEPersons(query: string): Observable<RawRestResponse> {
    return this.restService.get(`${this.restUrl}/core/epersons/search/byMetadata?query=${encodeURIComponent(query)}`);
  }

  addGroupMember(groupUuid: string, epersonUuid: string): Observable<RawRestResponse> {
    return this.restService.request(RestRequestMethod.POST,
      `${this.restUrl}/core/groups/${groupUuid}/epersons`,
      `${this.restUrl}/core/epersons/${epersonUuid}`,
      { headers: new HttpHeaders({ 'Content-Type': 'text/uri-list' }) });
  }

  removeGroupMember(groupUuid: string, epersonUuid: string): Observable<RawRestResponse> {
    return this.restService.request(RestRequestMethod.DELETE,
      `${this.restUrl}/core/groups/${groupUuid}/epersons/${epersonUuid}`);
  }
}
```

Spec covers `getGovernance`, `setCommunityAccess`, and `addGroupMember` URLs.

---

### Task 5: Angular page, route, menu, i18n

- Component `AdminGovernanceComponent` (standalone, `CommonModule` + `TranslateModule` +
  `RouterLink`): `ngOnInit` calls `getGovernance()`; renders one card per community with mode
  badge, sector group, `Membros` toggle (lazy `getGroupMembers`), e-person search box, remove
  buttons, `Restringir`/`Publicar` button with confirm, `Editar comunidade` link to
  `/communities/${uuid}/edit/metadata`; a collection table with `Editar coleção` link
  (`/collections/${uuid}/edit/metadata`) and `Vincular grupo` when `publishGroup` is null;
  a `Curadoria NUGECID` block reusing the same member editor; `Nova comunidade`/`Nova coleção`
  buttons opening `ThemedCreateCommunityParentSelectorComponent` /
  `ThemedCreateCollectionParentSelectorComponent` through `NgbModal`.
- Route: add `{ path: 'governance', ... Themed? AdminGovernanceComponent }` to `admin-routes.ts`.
- Menu: new `GovernanceMenuProvider` (pattern of `BrevoEmailLogsMenuProvider`, `FeatureID.AdministratorOf`,
  link `/admin/governance`, icon `sitemap`) added to `MenuID.ADMIN` in `app.menus.ts`.
- i18n keys under `admin.governance.*` and `menu.section.governance` in `pt-BR.json5` and `en.json5`.

Spec (`admin-governance.component.spec.ts`) with a `PcirnGovernanceDataService` spy:

1. renders community name, mode, and collection names from a stubbed GET payload;
2. `setCommunityAccess` called with the chosen mode when toggling;
3. `addGroupMember` called when adding a selected e-person;
4. error state renders when `getGovernance` errors.

---

### Task 6: Verification

- [ ] Backend: `mvn -pl dspace-server-webapp verify -DskipUnitTests=true -DskipIntegrationTests=false -Dit.test=PcirnGovernanceRestControllerIT`
- [ ] Backend checkstyle: `mvn -pl dspace-server-webapp checkstyle:check` (or the project's `mvn install` check).
- [ ] Frontend: `npx ng test --watch=false --include=src/app/admin/admin-governance/admin-governance.component.spec.ts`
- [ ] Frontend lint on new files: `npx eslint src/app/admin/admin-governance src/app/shared/menu/providers/governance.menu.ts`
- [ ] Commit frontend: `feat: add PCIRN governance admin page`.
- [ ] Commit submodule pointer in the root repository.

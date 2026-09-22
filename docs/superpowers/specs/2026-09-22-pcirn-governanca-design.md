# PCIRN Governance Admin Page Design

## Decision

Add one administrative Angular page, "Governança" (`/admin/governance`), backed by three
PCIRN REST endpoints, so a site administrator can see and operate the PCIRN access model
from one place:

- which communities exist, which are public or restricted, and which sector group reads them;
- who belongs to each sector group (read + publish);
- who can publish into each collection;
- who receives submissions, receives `submit_task` e-mails, and authorizes publication
  (the repository-wide `NUGECID` workflow group).

Communities, collections, people, and groups keep DSpace as the single source of truth.
No parallel registry table, no duplicated membership store, no new workflow step.

Community and collection CRUD stays on the native screens; the page links to them.

## Current behavior

- Communities and collections are public: `Anonymous` holds `READ` on all of them.
- Publication (`ADD` on each collection) is granted to the matching sector group
  (`PCIRN_Setor_DG`, `PCIRN_Setor_IC`, `PCIRN_Setor_II`, `PCIRN_Setor_IML`,
  `PCIRN_Setor_NUGECID`), installed by
  `V9.4_2026.08.24__pcirn_sector_submission_and_shared_read.sql`.
- The workflow role `editor` is repository-scoped and resolves to the `NUGECID` group.
  Every member gets a pool task and the `submit_task` e-mail and can approve, return,
  or discard (`dspace/config/spring/api/workflow.xml`, `ClaimAction.java`).
- Groups and members are edited on the native Access Control screens.

## Model

| Concept | Native representation |
| --- | --- |
| Community access mode | `public` = `Anonymous` has `READ` on the community; `restricted` = the sector group has `READ`. Derived from `ResourcePolicy`, never persisted elsewhere. |
| Sector group of a community | The non-privileged group holding `READ` on the community (for example `PCIRN_Setor_DG`). |
| Members of a community | Members of its sector group. |
| Who can publish | Same sector group, via `ADD` policies on the community's collections. |
| Who receives and authorizes | Repository-wide `NUGECID` group. Members receive the pool task and `submit_task` e-mail. |
| Curation e-mail recipients | Same `NUGECID` members (`ClaimAction.alertUsersOnActivation`). |

## Backend contract

Namespace `/api/pcirn/governance`. Site administrators only (`hasAuthority('ADMIN')`).
Responses use short DTO records; no repository/projection machinery.

### GET `/api/pcirn/governance`

Returns the whole matrix in one payload:

```json
{
  "communities": [
    {
      "uuid": "...",
      "name": "Instituto de Criminalística",
      "handle": "123456789/4",
      "accessMode": "public",
      "sectorGroup": { "uuid": "...", "name": "PCIRN_Setor_IC", "memberCount": 3 },
      "collections": [
        {
          "uuid": "...",
          "name": "Portarias e Atos Normativos Internos",
          "handle": "123456789/7",
          "publishGroup": { "uuid": "...", "name": "PCIRN_Setor_IC" }
        }
      ]
    }
  ],
  "curationGroup": { "uuid": "...", "name": "NUGECID", "memberCount": 2 }
}
```

- `accessMode` is `restricted` when a non-`Anonymous`, non-`Administrator` group holds
  `READ` on the community; otherwise `public`.
- `sectorGroup`/`publishGroup` are `null` when no matching group policy exists.
- `memberCount` uses the group's direct e-person members.

### PUT `/api/pcirn/communities/{uuid}/access`

Body: `{ "mode": "public" | "restricted", "sectorGroup": "<group uuid>" }`
(`sectorGroup` required for `restricted`, ignored for `public`).

Transactional and idempotent. For `restricted`:

1. On the community, its collections, every item of those collections, and every
   bitstream of those items: replace `READ` policies held by `Anonymous` with the
   sector group. Create the group policy when missing.
2. On each collection: set the `DEFAULT_ITEM_READ` and `DEFAULT_BITSTREAM_READ`
   policies to the sector group so new items inherit the restriction.
3. On each collection: ensure an `ADD` policy for the sector group (publication).

For `public`, the reverse: replace the sector group's `READ` and default policies with
`Anonymous`; leave `ADD` untouched.

Rules:

- Policies for other groups or e-persons (embargo, lease, private items, administrators)
  are never touched.
- The sector group must exist, must not be `Anonymous`, and must not be the
  `Administrator` group; otherwise `422`.
- Missing community or group: `404`. Non-admin: `403`.
- Any failure aborts the context, so no partial rewrite is committed.

### PUT `/api/pcirn/collections/{uuid}/sector`

Body: `{ "sectorGroup": "<group uuid>" }`. Binds a collection created on the native
screen to a sector group without toggling the community mode: ensures the `ADD` policy
for the group and, when the community is `restricted`, reconciles the collection's
`READ` and default policies. Same validation and transaction rules.

## Frontend

- New lazy admin route `/admin/governance` guarded by `siteAdministratorGuard`, plus a
  sidebar entry (new menu provider, icon `sitemap`, visible to site administrators only),
  following `BrevoEmailLogsMenuProvider`.
- `PcirnGovernanceDataService` calls the two endpoints through `DspaceRestService`;
  member editing reuses the native `GroupDataService`/`EPersonDataService` endpoints.
- Page layout:
  - community rows: name, handle, access-mode badge, sector group name and member count,
    **Membros** button (search e-person, add/remove inline), **Alternar modo** button with
    a confirmation dialog and group picker when restricting, link **Editar comunidade**;
  - per-collection rows: name, handle, publish group, link **Editar coleção**, action
    **Vincular grupo** when the collection has no sector group;
  - global block: **Curadoria NUGECID** with member editing and a note that these members
    receive the submission e-mails and authorize publication;
  - shortcuts **Nova comunidade** / **Nova coleção** opening the native create flows.
- States: loading, empty, error; success notification after each mutation; the page
  reloads the matrix from the server after mutations (no client-side guesswork).
- i18n keys added to `pt-BR.json5` and `en.json5` with the commented-English pattern
  already used by this fork.

## Security and edge cases

- Every endpoint and every mutation re-checks site administrator authority on the server.
- Community listing uses the community service; policies are read through
  `ResourcePolicyService`, not raw SQL.
- A community with no sector group can stay public; restricting it without a group is
  rejected.
- Repeated toggles produce no duplicate policies.
- `ponytail:` one transaction per request; if the repository grows enough that a toggle
  times out, move the rewrite to an asynchronous process.

## Testing

Backend integration tests (`AbstractControllerIntegrationTest`):

1. Matrix lists a community with mode, sector group, and collections.
2. Restrict a public community with an existing item and bitstream: anonymous read
   fails, sector member read succeeds, defaults point to the group, `ADD` preserved.
3. Restore public: anonymous read succeeds again.
4. Restricted without group: `422`. Non-admin: `403`. Unknown community: `404`.
5. Local policies (for example an embargo for another group) survive both toggles.
6. `PUT /collections/{uuid}/sector` binds a collection without a group and is idempotent.

Frontend specs:

1. Component renders communities, modes, groups, and the NUGECID block.
2. Toggle calls the endpoint with the chosen mode/group and reloads.
3. Adding and removing a member calls the group endpoints.
4. Error state renders when the GET fails.

## Acceptance

1. Admin opens `/admin/governance` and sees every community, its mode, sector group, and
   members.
2. Admin restricts a community: anonymous users lose access to the community, its
   collections, items, and bitstreams; sector members keep access; new items inherit the
   restriction.
3. Admin returns the community to public and anonymous access works again.
4. Admin adds/removes a member of a sector group and of `NUGECID` from the page.
5. A member added to `NUGECID` sees the task queue and receives `submit_task`.
6. Community and collection creation/edition/deletion continue on the native screens,
   reachable from the page.

## Out of scope

- Per-collection workflow groups (curation remains repository-wide `NUGECID`).
- Separate e-mail recipient lists (e-mail follows the `NUGECID` group).
- Rebuilding native community/collection/people CRUD screens.
- New database tables or a parallel sector registry.

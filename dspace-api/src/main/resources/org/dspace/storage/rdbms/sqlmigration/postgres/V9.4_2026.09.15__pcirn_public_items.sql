-- PCIRN public read reconciliation: every published document is public.
--
-- Submission authorization is unchanged: it still requires an authenticated
-- user plus the sector ADD policy on the collection. This migration only
-- touches visibility (READ / DEFAULT_ITEM_READ / DEFAULT_BITSTREAM_READ):
--   * READ (0) for the special "Anonymous" group on every community and
--     collection (browse and item pages for anonymous visitors);
--   * READ (0) for Anonymous on every archived, non-withdrawn item and its
--     bundles and bitstreams;
--   * DEFAULT_ITEM_READ (10) and DEFAULT_BITSTREAM_READ (9) for Anonymous on
--     every collection, so newly approved items inherit public access at
--     install time (in-progress items stay private).
-- The now redundant authenticated/sector READ policies are removed.
--
-- Idempotent: safe to re-run manually.

-- 1. Fail fast when the expected groups are missing.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM epersongroup WHERE name = 'Anonymous') THEN
        RAISE EXCEPTION 'PCIRN public read migration: Anonymous group not found';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM epersongroup WHERE name = 'Usuarios_Logados') THEN
        RAISE EXCEPTION 'PCIRN public read migration: Usuarios_Logados group not found';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM epersongroup WHERE name = 'NUGECID') THEN
        RAISE EXCEPTION 'PCIRN public read migration: NUGECID group not found';
    END IF;
END $$;

-- 2. Anonymous READ on every community.
INSERT INTO resourcepolicy (
    policy_id, resource_type_id, action_id, rpname, rptype,
    epersongroup_id, dspace_object
)
SELECT nextval('resourcepolicy_seq'), 4, 0, 'PCIRN public read', 'CUSTOM',
       anon.uuid, c.uuid
FROM community c
CROSS JOIN epersongroup anon
WHERE anon.name = 'Anonymous'
  AND NOT EXISTS (
      SELECT 1
      FROM resourcepolicy rp
      WHERE rp.dspace_object = c.uuid
        AND rp.action_id = 0
        AND rp.epersongroup_id = anon.uuid
  );

-- 3. Anonymous READ on every collection, plus the defaults used when an item
--    is installed (approved) into the collection.
INSERT INTO resourcepolicy (
    policy_id, resource_type_id, action_id, rpname, rptype,
    epersongroup_id, dspace_object
)
SELECT nextval('resourcepolicy_seq'), 3, actions.action_id,
       'PCIRN public read', 'CUSTOM', anon.uuid, c.uuid
FROM collection c
CROSS JOIN epersongroup anon
CROSS JOIN (VALUES (0), (9), (10)) AS actions(action_id)
WHERE anon.name = 'Anonymous'
  AND NOT EXISTS (
      SELECT 1
      FROM resourcepolicy rp
      WHERE rp.dspace_object = c.uuid
        AND rp.action_id = actions.action_id
        AND rp.epersongroup_id = anon.uuid
  );

-- 4. Anonymous READ on every archived item that is not withdrawn.
INSERT INTO resourcepolicy (
    policy_id, resource_type_id, action_id, rpname, rptype,
    epersongroup_id, dspace_object
)
SELECT nextval('resourcepolicy_seq'), 2, 0, 'PCIRN public read', 'CUSTOM',
       anon.uuid, i.uuid
FROM item i
CROSS JOIN epersongroup anon
WHERE anon.name = 'Anonymous'
  AND i.in_archive = true
  AND i.withdrawn = false
  AND NOT EXISTS (
      SELECT 1
      FROM resourcepolicy rp
      WHERE rp.dspace_object = i.uuid
        AND rp.action_id = 0
        AND rp.epersongroup_id = anon.uuid
  );

-- 5. Anonymous READ on the bundles of every archived item.
INSERT INTO resourcepolicy (
    policy_id, resource_type_id, action_id, rpname, rptype,
    epersongroup_id, dspace_object
)
SELECT nextval('resourcepolicy_seq'), 1, 0, 'PCIRN public read', 'CUSTOM',
       anon.uuid, b.uuid
FROM item i
JOIN item2bundle i2b ON i2b.item_id = i.uuid
JOIN bundle b ON b.uuid = i2b.bundle_id
CROSS JOIN epersongroup anon
WHERE anon.name = 'Anonymous'
  AND i.in_archive = true
  AND i.withdrawn = false
  AND NOT EXISTS (
      SELECT 1
      FROM resourcepolicy rp
      WHERE rp.dspace_object = b.uuid
        AND rp.action_id = 0
        AND rp.epersongroup_id = anon.uuid
  );

-- 6. Anonymous READ on the bitstreams of every archived item.
INSERT INTO resourcepolicy (
    policy_id, resource_type_id, action_id, rpname, rptype,
    epersongroup_id, dspace_object
)
SELECT nextval('resourcepolicy_seq'), 0, 0, 'PCIRN public read', 'CUSTOM',
       anon.uuid, bs.uuid
FROM item i
JOIN item2bundle i2b ON i2b.item_id = i.uuid
JOIN bundle2bitstream b2s ON b2s.bundle_id = i2b.bundle_id
JOIN bitstream bs ON bs.uuid = b2s.bitstream_id
CROSS JOIN epersongroup anon
WHERE anon.name = 'Anonymous'
  AND i.in_archive = true
  AND i.withdrawn = false
  AND bs.deleted = false
  AND NOT EXISTS (
      SELECT 1
      FROM resourcepolicy rp
      WHERE rp.dspace_object = bs.uuid
        AND rp.action_id = 0
        AND rp.epersongroup_id = anon.uuid
  );

-- 7. Drop the now redundant visibility grants. Submission (ADD, action 3),
--    workflow/submission policies and administrative grants are untouched.
DELETE FROM resourcepolicy rp
USING epersongroup g
WHERE rp.epersongroup_id = g.uuid
  AND (g.name = 'Usuarios_Logados' OR g.name LIKE 'PCIRN_Setor_%')
  AND rp.action_id IN (0, 9, 10);

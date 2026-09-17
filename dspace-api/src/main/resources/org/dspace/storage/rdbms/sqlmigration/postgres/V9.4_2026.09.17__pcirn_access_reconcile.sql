-- PCIRN access reconciliation.
--
-- Fixes the current public-read state without editing applied migrations:
--   * normalizes PCIRN policies to the DSpace "TYPE_CUSTOM" policy type
--     (V9.4_2026.08.* wrote the unrecognized literal 'CUSTOM');
--   * removes anonymous READ from non-public objects: items that are not
--     archived (drafts/workflow) or are withdrawn, their bundles and
--     bitstreams, and deleted bitstreams. V9.4_2026.08.18 granted anonymous
--     READ on items of the Portarias collections without those filters;
--   * backfills anonymous READ / DEFAULT_ITEM_READ / DEFAULT_BITSTREAM_READ on
--     communities and collections, and anonymous READ on archived
--     non-withdrawn items and their bundles/bitstreams, so objects created
--     after V9.4_2026.09.15 also follow the public-read intent.
--
-- Idempotent: safe to re-run manually.

-- 1. Fail fast when the special Anonymous group is missing.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM epersongroup WHERE name = 'Anonymous') THEN
        RAISE EXCEPTION 'PCIRN access reconcile: Anonymous group not found';
    END IF;
END $$;

-- 2. Normalize the policy type used by the PCIRN migrations.
UPDATE resourcepolicy SET rptype = 'TYPE_CUSTOM' WHERE rptype = 'CUSTOM';

-- 3. Anonymous READ on every community.
INSERT INTO resourcepolicy (
    policy_id, resource_type_id, action_id, rpname, rptype,
    epersongroup_id, dspace_object
)
SELECT nextval('resourcepolicy_seq'), 4, 0, 'PCIRN public read', 'TYPE_CUSTOM',
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

-- 4. Anonymous READ and collection defaults on every collection.
INSERT INTO resourcepolicy (
    policy_id, resource_type_id, action_id, rpname, rptype,
    epersongroup_id, dspace_object
)
SELECT nextval('resourcepolicy_seq'), 3, actions.action_id,
       'PCIRN public read', 'TYPE_CUSTOM', anon.uuid, c.uuid
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

-- 5. Anonymous READ on every archived item that is not withdrawn.
INSERT INTO resourcepolicy (
    policy_id, resource_type_id, action_id, rpname, rptype,
    epersongroup_id, dspace_object
)
SELECT nextval('resourcepolicy_seq'), 2, 0, 'PCIRN public read', 'TYPE_CUSTOM',
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

-- 6. Anonymous READ on the bundles of every public item.
INSERT INTO resourcepolicy (
    policy_id, resource_type_id, action_id, rpname, rptype,
    epersongroup_id, dspace_object
)
SELECT nextval('resourcepolicy_seq'), 1, 0, 'PCIRN public read', 'TYPE_CUSTOM',
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

-- 7. Anonymous READ on the bitstreams of every public item.
INSERT INTO resourcepolicy (
    policy_id, resource_type_id, action_id, rpname, rptype,
    epersongroup_id, dspace_object
)
SELECT nextval('resourcepolicy_seq'), 0, 0, 'PCIRN public read', 'TYPE_CUSTOM',
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

-- 8. Drop anonymous READ from objects that must not be public.
DELETE FROM resourcepolicy rp
USING epersongroup g
WHERE rp.epersongroup_id = g.uuid
  AND g.name = 'Anonymous'
  AND rp.action_id = 0
  AND (
      EXISTS (
          SELECT 1
          FROM item i
          WHERE i.uuid = rp.dspace_object
            AND (i.in_archive = false OR i.withdrawn = true)
      )
      OR EXISTS (
          SELECT 1
          FROM item i
          JOIN item2bundle i2b ON i2b.item_id = i.uuid
          WHERE i2b.bundle_id = rp.dspace_object
            AND (i.in_archive = false OR i.withdrawn = true)
      )
      OR EXISTS (
          SELECT 1
          FROM item i
          JOIN item2bundle i2b ON i2b.item_id = i.uuid
          JOIN bundle2bitstream b2b ON b2b.bundle_id = i2b.bundle_id
          WHERE b2b.bitstream_id = rp.dspace_object
            AND (i.in_archive = false OR i.withdrawn = true)
      )
      OR EXISTS (
          SELECT 1
          FROM bitstream bs
          WHERE bs.uuid = rp.dspace_object
            AND bs.deleted = true
      )
  );

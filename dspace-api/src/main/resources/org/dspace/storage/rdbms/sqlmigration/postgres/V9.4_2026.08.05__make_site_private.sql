--
-- The contents of this file are subject to the license and copyright
-- detailed in the LICENSE and NOTICE files at the root of the source
-- tree and available online at
--
-- http://www.dspace.org/license/
--

--------------------------------------------------------------------------------
-- Make the whole site visible only to authenticated users (internal system).
--
-- In DSpace, "public" means: has a READ ResourcePolicy for the special
-- "Anonymous" group (anonymous visitors are always members of it). This
-- migration converts every policy that granted anonymous READ into one that
-- grants the same READ to the group "Usuarios_Logados" instead:
--   * READ (action_id = 0) on every DSpaceObject
--     (communities, collections, items, bundles, bitstreams)
--   * DEFAULT_ITEM_READ (10) and DEFAULT_BITSTREAM_READ (9) on collections,
--     so NEW items/bitstreams inherit the restricted group as well
-- Existing embargo dates are preserved. WRITE/ADD/ADMIN policies are untouched.
--
-- Idempotent: safe to re-run manually if the group is ever recreated.
--------------------------------------------------------------------------------

-- 1. Ensure the groups exist. epersongroup.uuid references dspaceobject.uuid;
--    inserting only epersongroup fails on fresh installations.
DO $$
DECLARE
    group_uuid uuid;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM epersongroup WHERE name = 'Anonymous') THEN
        group_uuid := gen_random_uuid();
        INSERT INTO dspaceobject (uuid) VALUES (group_uuid);
        INSERT INTO epersongroup (uuid, name, permanent)
        VALUES (group_uuid, 'Anonymous', true);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM epersongroup WHERE name = 'Administrator') THEN
        group_uuid := gen_random_uuid();
        INSERT INTO dspaceobject (uuid) VALUES (group_uuid);
        INSERT INTO epersongroup (uuid, name, permanent)
        VALUES (group_uuid, 'Administrator', true);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM epersongroup WHERE name = 'Usuarios_Logados') THEN
        group_uuid := gen_random_uuid();
        INSERT INTO dspaceobject (uuid) VALUES (group_uuid);
        INSERT INTO epersongroup (uuid, name, permanent)
        VALUES (group_uuid, 'Usuarios_Logados', false);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM epersongroup WHERE name = 'NUGECID') THEN
        group_uuid := gen_random_uuid();
        INSERT INTO dspaceobject (uuid) VALUES (group_uuid);
        INSERT INTO epersongroup (uuid, name, permanent)
        VALUES (group_uuid, 'NUGECID', false);
    END IF;
END $$;

-- Repair a partially-created group if an earlier manual attempt inserted its
-- row without the required dspaceobject parent.
INSERT INTO dspaceobject (uuid)
SELECT g.uuid
FROM epersongroup g
WHERE NOT EXISTS (SELECT 1 FROM dspaceobject d WHERE d.uuid = g.uuid);

-- 2. Make every registered EPerson a member of the group (idempotent).
--    New accounts created later must be added to the group manually (or by
--    re-running this INSERT).
INSERT INTO epersongroup2eperson (eperson_group_id, eperson_id)
SELECT g.uuid, e.uuid
FROM epersongroup g
CROSS JOIN eperson e
WHERE g.name = 'Usuarios_Logados'
  AND NOT EXISTS (
      SELECT 1 FROM epersongroup2eperson m
      WHERE m.eperson_group_id = g.uuid AND m.eperson_id = e.uuid
  );

-- 3. Swap Anonymous -> Usuarios_Logados on every visibility-granting policy.
UPDATE resourcepolicy rp
SET epersongroup_id = g.uuid
FROM epersongroup anon
JOIN epersongroup g ON g.name = 'Usuarios_Logados'
WHERE rp.epersongroup_id = anon.uuid
  AND anon.name = 'Anonymous'
  AND rp.action_id IN (0, 9, 10);

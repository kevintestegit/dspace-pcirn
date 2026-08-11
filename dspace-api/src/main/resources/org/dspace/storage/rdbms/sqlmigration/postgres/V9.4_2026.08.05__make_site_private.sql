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

-- 1. Ensure the default groups exist (may be missing on fresh installs, since
--    GroupServiceInitializer only runs AFTER all migrations).
INSERT INTO epersongroup (uuid, name, permanent)
SELECT gen_random_uuid(), 'Anonymous', true
WHERE NOT EXISTS (SELECT 1 FROM epersongroup WHERE name = 'Anonymous');

INSERT INTO epersongroup (uuid, name, permanent)
SELECT gen_random_uuid(), 'Administrator', true
WHERE NOT EXISTS (SELECT 1 FROM epersongroup WHERE name = 'Administrator');

-- 2. Target group for authenticated users (create if missing).
INSERT INTO epersongroup (uuid, name, permanent)
SELECT gen_random_uuid(), 'Usuarios_Logados', false
WHERE NOT EXISTS (SELECT 1 FROM epersongroup WHERE name = 'Usuarios_Logados');

-- 3. Make every registered EPerson a member of the group (idempotent).
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

-- 4. Swap Anonymous -> Usuarios_Logados on every visibility-granting policy.
UPDATE resourcepolicy rp
SET epersongroup_id = g.uuid
FROM epersongroup anon
JOIN epersongroup g ON g.name = 'Usuarios_Logados'
WHERE rp.epersongroup_id = anon.uuid
  AND anon.name = 'Anonymous'
  AND rp.action_id IN (0, 9, 10);

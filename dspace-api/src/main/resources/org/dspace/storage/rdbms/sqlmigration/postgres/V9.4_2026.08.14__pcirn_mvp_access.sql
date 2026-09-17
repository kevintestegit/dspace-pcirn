-- PCIRN MVP access reconciliation.
-- Keeps the native DSpace authorization model and is safe to re-run manually.

DO $$
DECLARE
    group_uuid uuid;
BEGIN
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

    IF NOT EXISTS (SELECT 1 FROM epersongroup WHERE name = 'PCIRN_Depositantes') THEN
        group_uuid := gen_random_uuid();
        INSERT INTO dspaceobject (uuid) VALUES (group_uuid);
        INSERT INTO epersongroup (uuid, name, permanent)
        VALUES (group_uuid, 'PCIRN_Depositantes', false);
    END IF;
END $$;

-- Every provisioned password user is an internal authenticated user.
INSERT INTO epersongroup2eperson (eperson_group_id, eperson_id)
SELECT g.uuid, e.uuid
FROM epersongroup g
CROSS JOIN eperson e
WHERE g.name = 'Usuarios_Logados'
  AND NOT EXISTS (
      SELECT 1
      FROM epersongroup2eperson m
      WHERE m.eperson_group_id = g.uuid
        AND m.eperson_id = e.uuid
  );

-- Bootstrap the two local MVP operators when they exist.
INSERT INTO epersongroup2eperson (eperson_group_id, eperson_id)
SELECT g.uuid, e.uuid
FROM epersongroup g
JOIN eperson e ON e.email IN ('admin@localhost', 'gesiele@localhost.com')
WHERE g.name IN ('NUGECID', 'PCIRN_Depositantes')
  AND NOT EXISTS (
      SELECT 1
      FROM epersongroup2eperson m
      WHERE m.eperson_group_id = g.uuid
        AND m.eperson_id = e.uuid
  );

-- Replace anonymous visibility on all current objects and collection defaults.
UPDATE resourcepolicy rp
SET epersongroup_id = logged.uuid
FROM epersongroup anonymous
JOIN epersongroup logged ON logged.name = 'Usuarios_Logados'
WHERE rp.epersongroup_id = anonymous.uuid
  AND anonymous.name = 'Anonymous'
  AND rp.action_id IN (0, 9, 10);

-- Permit the bootstrap depositors to submit into every current PCIRN collection.
INSERT INTO resourcepolicy (
    policy_id, resource_type_id, action_id, rpname, rptype,
    epersongroup_id, dspace_object
)
SELECT nextval('resourcepolicy_seq'), 3, 3, 'PCIRN depositantes', 'CUSTOM',
       g.uuid, c.uuid
FROM collection c
CROSS JOIN epersongroup g
WHERE g.name = 'PCIRN_Depositantes'
  AND NOT EXISTS (
      SELECT 1
      FROM resourcepolicy rp
      WHERE rp.dspace_object = c.uuid
        AND rp.action_id = 3
      AND rp.epersongroup_id = g.uuid
  );

-- Route every current collection through the repository NUGECID editor role.
INSERT INTO cwf_collectionrole (role_id, collection_id, group_id)
SELECT 'editor', c.uuid, g.uuid
FROM collection c
CROSS JOIN epersongroup g
WHERE g.name = 'NUGECID'
  AND NOT EXISTS (
      SELECT 1
      FROM cwf_collectionrole r
      WHERE r.role_id = 'editor'
        AND r.collection_id = c.uuid
        AND r.group_id = g.uuid
  );

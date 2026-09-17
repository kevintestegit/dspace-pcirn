-- PCIRN sector submission and authenticated shared read reconciliation.
-- Sector membership is the only non-administrative ADD authorization path.

CREATE TEMP TABLE pcirn_sector_targets (
    group_name text PRIMARY KEY,
    community_title text NOT NULL,
    group_uuid uuid NOT NULL,
    community_uuid uuid NOT NULL
) ON COMMIT DROP;

DO $$
DECLARE
    target record;
    title_field integer;
    group_uuid uuid;
    community_uuid uuid;
    match_count integer;
    orphan_count integer;
BEGIN
    SELECT metadata_field_id
    INTO title_field
    FROM metadatafieldregistry
    WHERE metadata_schema_id = (
        SELECT metadata_schema_id
        FROM metadataschemaregistry
        WHERE short_id = 'dc'
    )
      AND element = 'title'
      AND qualifier IS NULL;

    IF title_field IS NULL THEN
        RAISE EXCEPTION 'PCIRN sector submission migration: dc.title metadata field not found';
    END IF;

    FOR target IN
        SELECT *
        FROM (VALUES
            ('PCIRN_Setor_DG', 'Gestão Estratégica e Administrativa (DG)'),
            ('PCIRN_Setor_IC', 'Instituto de Criminalística (IC)'),
            ('PCIRN_Setor_II', 'Instituto de Identificação (II)'),
            ('PCIRN_Setor_IML', 'Instituto de Medicina Legal (IML)'),
            ('PCIRN_Setor_NUGECID', 'Núcleo de Gestão do Conhecimento, Informação, Documentação e Memória (NUGECID)')
        ) AS sectors(group_name, community_title)
    LOOP
        SELECT uuid
        INTO group_uuid
        FROM epersongroup
        WHERE name = target.group_name;

        IF group_uuid IS NULL THEN
            RAISE EXCEPTION 'PCIRN sector submission migration: group not found: %', target.group_name;
        END IF;

        SELECT count(*)
        INTO match_count
        FROM community c
        JOIN metadatavalue mv ON mv.dspace_object_id = c.uuid
        WHERE mv.metadata_field_id = title_field
          AND mv.text_value = target.community_title;

        IF match_count = 0 THEN
            RAISE EXCEPTION 'PCIRN sector submission migration: community not found: %', target.community_title;
        ELSIF match_count > 1 THEN
            RAISE EXCEPTION 'PCIRN sector submission migration: duplicate community title: %', target.community_title;
        END IF;

        SELECT c.uuid
        INTO community_uuid
        FROM community c
        JOIN metadatavalue mv ON mv.dspace_object_id = c.uuid
        WHERE mv.metadata_field_id = title_field
          AND mv.text_value = target.community_title;

        INSERT INTO pcirn_sector_targets (group_name, community_title, group_uuid, community_uuid)
        VALUES (target.group_name, target.community_title, group_uuid, community_uuid);
    END LOOP;

    IF NOT EXISTS (SELECT 1 FROM epersongroup WHERE name = 'NUGECID') THEN
        RAISE EXCEPTION 'PCIRN sector submission migration: NUGECID group not found';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM epersongroup WHERE name = 'Usuarios_Logados') THEN
        RAISE EXCEPTION 'PCIRN sector submission migration: Usuarios_Logados group not found';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM epersongroup WHERE name = 'PCIRN_Depositantes') THEN
        RAISE EXCEPTION 'PCIRN sector submission migration: PCIRN_Depositantes group not found';
    END IF;

    -- Abort before changing any policy if a legacy depositor has no sector.
    SELECT count(*)
    INTO orphan_count
    FROM epersongroup2eperson legacy_membership
    JOIN epersongroup legacy_group ON legacy_group.uuid = legacy_membership.eperson_group_id
    WHERE legacy_group.name = 'PCIRN_Depositantes'
      AND NOT EXISTS (
          SELECT 1
          FROM epersongroup2eperson sector_membership
          JOIN pcirn_sector_targets sector ON sector.group_uuid = sector_membership.eperson_group_id
          WHERE sector_membership.eperson_id = legacy_membership.eperson_id
      )
      AND NOT EXISTS (
          SELECT 1
          FROM epersongroup2eperson admin_membership
          JOIN epersongroup admin_group ON admin_group.uuid = admin_membership.eperson_group_id
          WHERE admin_membership.eperson_id = legacy_membership.eperson_id
            AND admin_group.name IN ('Administrator', 'Administrators')
      );

    IF orphan_count > 0 THEN
        RAISE EXCEPTION 'PCIRN sector submission migration: % non-administrator PCIRN_Depositantes member(s) lack a sector group', orphan_count;
    END IF;
END $$;

-- Create the NUGECID submission collection and its handle once.
DO $$
DECLARE
    title_field integer;
    uri_field integer;
    nug_ecid_community_uuid uuid;
    collection_uuid uuid;
    match_count integer;
    handle_id bigint;
    handle_number bigint;
    handle_value text;
BEGIN
    SELECT metadata_field_id
    INTO title_field
    FROM metadatafieldregistry
    WHERE metadata_schema_id = (
        SELECT metadata_schema_id
        FROM metadataschemaregistry
        WHERE short_id = 'dc'
    )
      AND element = 'title'
      AND qualifier IS NULL;

    SELECT metadata_field_id
    INTO uri_field
    FROM metadatafieldregistry
    WHERE metadata_schema_id = (
        SELECT metadata_schema_id
        FROM metadataschemaregistry
        WHERE short_id = 'dc'
    )
      AND element = 'identifier'
      AND qualifier = 'uri';

    SELECT community_uuid
    INTO nug_ecid_community_uuid
    FROM pcirn_sector_targets
    WHERE group_name = 'PCIRN_Setor_NUGECID';

    SELECT count(*)
    INTO match_count
    FROM collection c
    JOIN community2collection cc ON cc.collection_id = c.uuid
    JOIN metadatavalue mv ON mv.dspace_object_id = c.uuid
    WHERE cc.community_id = nug_ecid_community_uuid
      AND mv.metadata_field_id = title_field
      AND mv.text_value = 'Documentos do NUGECID';

    IF match_count > 1 THEN
        RAISE EXCEPTION 'PCIRN sector submission migration: duplicate NUGECID collection';
    END IF;

    IF match_count = 0 THEN
        collection_uuid := gen_random_uuid();
        INSERT INTO dspaceobject (uuid) VALUES (collection_uuid);
        INSERT INTO collection (uuid) VALUES (collection_uuid);
        INSERT INTO community2collection (collection_id, community_id)
        VALUES (collection_uuid, nug_ecid_community_uuid);
        INSERT INTO metadatavalue (
            metadata_field_id, text_value, text_lang, place, confidence, dspace_object_id
        ) VALUES (
            title_field, 'Documentos do NUGECID', 'pt-BR', 0, -1, collection_uuid
        );
    ELSE
        SELECT c.uuid
        INTO collection_uuid
        FROM collection c
        JOIN community2collection cc ON cc.collection_id = c.uuid
        JOIN metadatavalue mv ON mv.dspace_object_id = c.uuid
        WHERE cc.community_id = nug_ecid_community_uuid
          AND mv.metadata_field_id = title_field
          AND mv.text_value = 'Documentos do NUGECID';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM handle
        WHERE resource_id = collection_uuid
          AND resource_type_id = 3
    ) THEN
        handle_number := nextval('handle_seq');
        handle_id := nextval('handle_id_seq');
        handle_value := '123456789/' || handle_number;
        INSERT INTO handle (handle_id, handle, resource_type_id, resource_id)
        VALUES (handle_id, handle_value, 3, collection_uuid);
    ELSE
        SELECT handle
        INTO handle_value
        FROM handle
        WHERE resource_id = collection_uuid
          AND resource_type_id = 3
        LIMIT 1;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM metadatavalue
        WHERE dspace_object_id = collection_uuid
          AND metadata_field_id = uri_field
    ) THEN
        INSERT INTO metadatavalue (
            metadata_field_id, text_value, text_lang, place, confidence, dspace_object_id
        ) VALUES (
            uri_field, 'http://localhost:4000/handle/' || handle_value, NULL, 0, -1, collection_uuid
        );
    END IF;
END $$;

CREATE TEMP TABLE pcirn_sector_collections (
    group_uuid uuid NOT NULL,
    community_uuid uuid NOT NULL,
    collection_uuid uuid PRIMARY KEY
) ON COMMIT DROP;

INSERT INTO pcirn_sector_collections (group_uuid, community_uuid, collection_uuid)
SELECT DISTINCT sector.group_uuid, sector.community_uuid, cc.collection_id
FROM pcirn_sector_targets sector
JOIN community2collection cc ON cc.community_id = sector.community_uuid;

-- Remove the legacy global submission path before installing sector ADD policies.
DELETE FROM resourcepolicy
WHERE action_id = 3
  AND epersongroup_id = (
      SELECT uuid FROM epersongroup WHERE name = 'PCIRN_Depositantes'
  );

-- Every sector collection can be submitted to only by its matching sector group.
INSERT INTO resourcepolicy (
    policy_id, resource_type_id, action_id, rpname, rptype,
    epersongroup_id, dspace_object
)
SELECT nextval('resourcepolicy_seq'), 3, 3, 'PCIRN sector submission', 'CUSTOM',
       sector.group_uuid, sector.collection_uuid
FROM pcirn_sector_collections sector
WHERE NOT EXISTS (
    SELECT 1
    FROM resourcepolicy rp
    WHERE rp.dspace_object = sector.collection_uuid
      AND rp.action_id = 3
      AND rp.epersongroup_id = sector.group_uuid
);

-- Authenticated users can read every sector community and its collection tree.
INSERT INTO resourcepolicy (
    policy_id, resource_type_id, action_id, rpname, rptype,
    epersongroup_id, dspace_object
)
SELECT nextval('resourcepolicy_seq'), 4, 0, 'PCIRN sector read', 'CUSTOM',
       logged.uuid, sector.community_uuid
FROM pcirn_sector_targets sector
CROSS JOIN epersongroup logged
WHERE logged.name = 'Usuarios_Logados'
  AND NOT EXISTS (
      SELECT 1
      FROM resourcepolicy rp
      WHERE rp.dspace_object = sector.community_uuid
        AND rp.action_id = 0
        AND rp.epersongroup_id = logged.uuid
  );

INSERT INTO resourcepolicy (
    policy_id, resource_type_id, action_id, rpname, rptype,
    epersongroup_id, dspace_object
)
SELECT nextval('resourcepolicy_seq'), 3, actions.action_id,
       'PCIRN sector read', 'CUSTOM', logged.uuid, sector.collection_uuid
FROM pcirn_sector_collections sector
CROSS JOIN epersongroup logged
CROSS JOIN (VALUES (0), (9), (10)) AS actions(action_id)
WHERE logged.name = 'Usuarios_Logados'
  AND NOT EXISTS (
      SELECT 1
      FROM resourcepolicy rp
      WHERE rp.dspace_object = sector.collection_uuid
        AND rp.action_id = actions.action_id
        AND rp.epersongroup_id = logged.uuid
  );

INSERT INTO resourcepolicy (
    policy_id, resource_type_id, action_id, rpname, rptype,
    epersongroup_id, dspace_object
)
SELECT nextval('resourcepolicy_seq'), 2, 0,
       'PCIRN sector read', 'CUSTOM', logged.uuid, objects.item_uuid
FROM (
    SELECT DISTINCT sector.collection_uuid, c2i.item_id AS item_uuid
    FROM pcirn_sector_collections sector
    JOIN collection2item c2i ON c2i.collection_id = sector.collection_uuid
) objects
CROSS JOIN epersongroup logged
WHERE logged.name = 'Usuarios_Logados'
  AND NOT EXISTS (
      SELECT 1
      FROM resourcepolicy rp
      WHERE rp.dspace_object = objects.item_uuid
        AND rp.action_id = 0
        AND rp.epersongroup_id = logged.uuid
  );

INSERT INTO resourcepolicy (
    policy_id, resource_type_id, action_id, rpname, rptype,
    epersongroup_id, dspace_object
)
SELECT nextval('resourcepolicy_seq'), 1, 0,
       'PCIRN sector read', 'CUSTOM', logged.uuid, objects.bundle_uuid
FROM (
    SELECT DISTINCT i2b.bundle_id AS bundle_uuid
    FROM pcirn_sector_collections sector
    JOIN collection2item c2i ON c2i.collection_id = sector.collection_uuid
    JOIN item2bundle i2b ON i2b.item_id = c2i.item_id
) objects
CROSS JOIN epersongroup logged
WHERE logged.name = 'Usuarios_Logados'
  AND NOT EXISTS (
      SELECT 1
      FROM resourcepolicy rp
      WHERE rp.dspace_object = objects.bundle_uuid
        AND rp.action_id = 0
        AND rp.epersongroup_id = logged.uuid
  );

INSERT INTO resourcepolicy (
    policy_id, resource_type_id, action_id, rpname, rptype,
    epersongroup_id, dspace_object
)
SELECT nextval('resourcepolicy_seq'), 0, 0,
       'PCIRN sector read', 'CUSTOM', logged.uuid, objects.bitstream_uuid
FROM (
    SELECT DISTINCT b2s.bitstream_id AS bitstream_uuid
    FROM pcirn_sector_collections sector
    JOIN collection2item c2i ON c2i.collection_id = sector.collection_uuid
    JOIN item2bundle i2b ON i2b.item_id = c2i.item_id
    JOIN bundle2bitstream b2s ON b2s.bundle_id = i2b.bundle_id
) objects
CROSS JOIN epersongroup logged
WHERE logged.name = 'Usuarios_Logados'
  AND NOT EXISTS (
      SELECT 1
      FROM resourcepolicy rp
      WHERE rp.dspace_object = objects.bitstream_uuid
        AND rp.action_id = 0
        AND rp.epersongroup_id = logged.uuid
  );

-- Route every collection through the existing native NUGECID workflow role.
INSERT INTO cwf_collectionrole (role_id, collection_id, group_id)
SELECT 'editor', c.uuid, nug_ecid.uuid
FROM collection c
CROSS JOIN epersongroup nug_ecid
WHERE nug_ecid.name = 'NUGECID'
  AND NOT EXISTS (
      SELECT 1
      FROM cwf_collectionrole role
      WHERE role.role_id = 'editor'
        AND role.collection_id = c.uuid
        AND role.group_id = nug_ecid.uuid
  );

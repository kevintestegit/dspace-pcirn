-- PCIRN sector collections: Portarias e Atos Normativos Internos.
-- IC, II and IML also issue internal ordinances, mirroring the DG community.
-- Idempotent: safe to re-run manually.

-- Resolve the three target sectors by community dc.title and, for each,
-- create the "Portarias e Atos Normativos Internos" collection with the same
-- access contract as the existing PCIRN collections:
--   * sector-group READ / DEFAULT_ITEM_READ / DEFAULT_BITSTREAM_READ
--   * PCIRN_Depositantes ADD
--   * NUGECID editor workflow role

CREATE TEMP TABLE pcirn_portarias_map (
    sector_group text PRIMARY KEY,
    community_title text NOT NULL,
    community_uuid uuid,
    collection_uuid uuid
) ON COMMIT DROP;

INSERT INTO pcirn_portarias_map (sector_group, community_title)
VALUES
    ('PCIRN_Setor_IC', 'Instituto de Criminalística (IC)'),
    ('PCIRN_Setor_II', 'Instituto de Identificação (II)'),
    ('PCIRN_Setor_IML', 'Instituto de Medicina Legal (IML)');

DO $$
DECLARE
    entry record;
    title_field integer;
    uri_field integer;
    collection_name constant text := 'Portarias e Atos Normativos Internos';
    group_uuid uuid;
    depositors_uuid uuid;
    nug_ecid_uuid uuid;
    resolved_uuid uuid;
    new_collection_uuid uuid;
    new_handle_id bigint;
    new_handle_num bigint;
    handle_value text;
BEGIN
    SELECT metadata_field_id
    INTO title_field
    FROM metadatafieldregistry
    WHERE metadata_schema_id = (SELECT metadata_schema_id
                                FROM metadataschemaregistry
                                WHERE short_id = 'dc')
      AND element = 'title'
      AND qualifier IS NULL;

    SELECT metadata_field_id
    INTO uri_field
    FROM metadatafieldregistry
    WHERE metadata_schema_id = (SELECT metadata_schema_id
                                FROM metadataschemaregistry
                                WHERE short_id = 'dc')
      AND element = 'identifier'
      AND qualifier = 'uri';

    IF title_field IS NULL OR uri_field IS NULL THEN
        RAISE EXCEPTION 'The dc.title or dc.identifier.uri metadata field is missing';
    END IF;

    SELECT uuid INTO depositors_uuid FROM epersongroup WHERE name = 'PCIRN_Depositantes';
    SELECT uuid INTO nug_ecid_uuid FROM epersongroup WHERE name = 'NUGECID';

    IF depositors_uuid IS NULL OR nug_ecid_uuid IS NULL THEN
        RAISE EXCEPTION 'PCIRN_Depositantes or NUGECID group is missing';
    END IF;

    FOR entry IN SELECT * FROM pcirn_portarias_map LOOP
        SELECT c.uuid INTO resolved_uuid
        FROM community c
        JOIN metadatavalue mv ON mv.dspace_object_id = c.uuid
                              AND mv.metadata_field_id = title_field
        WHERE mv.text_value = entry.community_title;

        IF resolved_uuid IS NULL THEN
            RAISE EXCEPTION 'PCIRN sector community not found: %', entry.community_title;
        END IF;

        UPDATE pcirn_portarias_map
        SET community_uuid = resolved_uuid
        WHERE sector_group = entry.sector_group;

        -- The collection already exists in this community: reuse it.
        SELECT col.uuid INTO new_collection_uuid
        FROM collection col
        JOIN community2collection cc ON cc.collection_id = col.uuid
        JOIN metadatavalue mv ON mv.dspace_object_id = col.uuid
                              AND mv.metadata_field_id = title_field
        WHERE cc.community_id = resolved_uuid
          AND mv.text_value = collection_name;

        IF new_collection_uuid IS NULL THEN
            new_collection_uuid := gen_random_uuid();
            INSERT INTO dspaceobject (uuid) VALUES (new_collection_uuid);
            INSERT INTO collection (uuid) VALUES (new_collection_uuid);
            INSERT INTO community2collection (collection_id, community_id)
            VALUES (new_collection_uuid, resolved_uuid);

            INSERT INTO metadatavalue (
                metadata_field_id, text_value, text_lang, place, confidence, dspace_object_id
            ) VALUES (
                title_field, collection_name, NULL, 0, -1, new_collection_uuid
            );

            new_handle_num := nextval('handle_seq');
            new_handle_id := nextval('handle_id_seq');
            handle_value := '123456789/' || new_handle_num;
            INSERT INTO handle (handle_id, handle, resource_type_id, resource_id)
            VALUES (new_handle_id, handle_value, 3, new_collection_uuid);

            INSERT INTO metadatavalue (
                metadata_field_id, text_value, text_lang, place, confidence, dspace_object_id
            ) VALUES (
                uri_field, 'http://localhost:4000/handle/' || handle_value, NULL, 0, -1,
                new_collection_uuid
            );
        END IF;

        -- Register the collection in the map whether it was created or reused,
        -- so the policy and workflow inserts below always target a real UUID.
        UPDATE pcirn_portarias_map
        SET collection_uuid = new_collection_uuid
        WHERE sector_group = entry.sector_group;
    END LOOP;

    -- Grant the exact policies of the existing PCIRN collections.
    FOR entry IN SELECT * FROM pcirn_portarias_map LOOP
        SELECT uuid INTO group_uuid FROM epersongroup WHERE name = entry.sector_group;

        IF group_uuid IS NULL THEN
            RAISE EXCEPTION 'PCIRN sector group not found: %', entry.sector_group;
        END IF;

        -- Sector READ (0), DEFAULT_ITEM_READ (10) and DEFAULT_BITSTREAM_READ (9).
        INSERT INTO resourcepolicy (
            policy_id, resource_type_id, action_id, epersongroup_id, dspace_object
        )
        SELECT nextval('resourcepolicy_seq'), 3, a.action_id, group_uuid, entry.collection_uuid
        FROM (VALUES (0), (9), (10)) AS a(action_id)
        WHERE NOT EXISTS (
            SELECT 1
            FROM resourcepolicy rp
            WHERE rp.dspace_object = entry.collection_uuid
              AND rp.action_id = a.action_id
              AND rp.epersongroup_id = group_uuid
        );

        -- Depositors ADD (3).
        INSERT INTO resourcepolicy (
            policy_id, resource_type_id, action_id, rpname, rptype,
            epersongroup_id, dspace_object
        )
        SELECT nextval('resourcepolicy_seq'), 3, 3, 'PCIRN depositantes', 'CUSTOM',
               depositors_uuid, entry.collection_uuid
        WHERE NOT EXISTS (
            SELECT 1
            FROM resourcepolicy rp
            WHERE rp.dspace_object = entry.collection_uuid
              AND rp.action_id = 3
              AND rp.epersongroup_id = depositors_uuid
        );

        -- Route the collection through the repository NUGECID editor role.
        INSERT INTO cwf_collectionrole (role_id, collection_id, group_id)
        SELECT 'editor', entry.collection_uuid, nug_ecid_uuid
        WHERE NOT EXISTS (
            SELECT 1
            FROM cwf_collectionrole r
            WHERE r.role_id = 'editor'
              AND r.collection_id = entry.collection_uuid
              AND r.group_id = nug_ecid_uuid
        );
    END LOOP;
END $$;
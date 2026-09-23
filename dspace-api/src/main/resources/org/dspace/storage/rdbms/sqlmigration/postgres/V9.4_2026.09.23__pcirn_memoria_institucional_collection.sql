-- PCIRN collection: Memória Institucional (NUGECID community).
--
-- Mirrors the access contract of the sibling NUGECID collections:
--   * anonymous READ / DEFAULT_ITEM_READ / DEFAULT_BITSTREAM_READ
--   * PCIRN_Setor_NUGECID ADD (the only non-administrative submission path)
--   * repository NUGECID editor workflow role
--
-- Idempotent: safe to re-run manually.

DO $$
DECLARE
    title_field integer;
    uri_field integer;
    community_title constant text := 'Núcleo de Gestão do Conhecimento, Informação, Documentação e Memória (NUGECID)';
    collection_name constant text := 'Memória Institucional';
    community_uuid uuid;
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

    IF title_field IS NULL OR uri_field IS NULL THEN
        RAISE EXCEPTION 'PCIRN memoria institucional migration: dc.title or dc.identifier.uri metadata field is missing';
    END IF;

    SELECT c.uuid
    INTO community_uuid
    FROM community c
    JOIN metadatavalue mv ON mv.dspace_object_id = c.uuid
    WHERE mv.metadata_field_id = title_field
      AND mv.text_value = community_title;

    IF community_uuid IS NULL THEN
        RAISE EXCEPTION 'PCIRN memoria institucional migration: community not found: %', community_title;
    END IF;

    SELECT count(*)
    INTO match_count
    FROM collection c
    JOIN community2collection cc ON cc.collection_id = c.uuid
    JOIN metadatavalue mv ON mv.dspace_object_id = c.uuid
    WHERE cc.community_id = community_uuid
      AND mv.metadata_field_id = title_field
      AND mv.text_value = collection_name;

    IF match_count > 1 THEN
        RAISE EXCEPTION 'PCIRN memoria institucional migration: duplicate collection in the NUGECID community';
    END IF;

    IF match_count = 0 THEN
        collection_uuid := gen_random_uuid();
        INSERT INTO dspaceobject (uuid) VALUES (collection_uuid);
        INSERT INTO collection (uuid) VALUES (collection_uuid);
        INSERT INTO community2collection (collection_id, community_id)
        VALUES (collection_uuid, community_uuid);
        INSERT INTO metadatavalue (
            metadata_field_id, text_value, text_lang, place, confidence, dspace_object_id
        ) VALUES (
            title_field, collection_name, 'pt-BR', 0, -1, collection_uuid
        );
    ELSE
        SELECT c.uuid
        INTO collection_uuid
        FROM collection c
        JOIN community2collection cc ON cc.collection_id = c.uuid
        JOIN metadatavalue mv ON mv.dspace_object_id = c.uuid
        WHERE cc.community_id = community_uuid
          AND mv.metadata_field_id = title_field
          AND mv.text_value = collection_name;
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

    -- Anonymous READ (0), DEFAULT_BITSTREAM_READ (9) and DEFAULT_ITEM_READ (10).
    INSERT INTO resourcepolicy (
        policy_id, resource_type_id, action_id, rpname, rptype,
        epersongroup_id, dspace_object
    )
    SELECT nextval('resourcepolicy_seq'), 3, actions.action_id,
           'PCIRN public read', 'TYPE_CUSTOM', anon.uuid, collection_uuid
    FROM epersongroup anon
    CROSS JOIN (VALUES (0), (9), (10)) AS actions(action_id)
    WHERE anon.name = 'Anonymous'
      AND NOT EXISTS (
          SELECT 1
          FROM resourcepolicy rp
          WHERE rp.dspace_object = collection_uuid
            AND rp.action_id = actions.action_id
            AND rp.epersongroup_id = anon.uuid
      );

    -- Sector submission: only the NUGECID sector group can ADD (3).
    INSERT INTO resourcepolicy (
        policy_id, resource_type_id, action_id, rpname, rptype,
        epersongroup_id, dspace_object
    )
    SELECT nextval('resourcepolicy_seq'), 3, 3,
           'PCIRN sector submission', 'TYPE_CUSTOM', sector.uuid, collection_uuid
    FROM epersongroup sector
    WHERE sector.name = 'PCIRN_Setor_NUGECID'
      AND NOT EXISTS (
          SELECT 1
          FROM resourcepolicy rp
          WHERE rp.dspace_object = collection_uuid
            AND rp.action_id = 3
            AND rp.epersongroup_id = sector.uuid
      );

    -- Route the collection through the repository NUGECID editor role.
    INSERT INTO cwf_collectionrole (role_id, collection_id, group_id)
    SELECT 'editor', collection_uuid, curators.uuid
    FROM epersongroup curators
    WHERE curators.name = 'NUGECID'
      AND NOT EXISTS (
          SELECT 1
          FROM cwf_collectionrole role
          WHERE role.role_id = 'editor'
            AND role.collection_id = collection_uuid
            AND role.group_id = curators.uuid
      );
END $$;

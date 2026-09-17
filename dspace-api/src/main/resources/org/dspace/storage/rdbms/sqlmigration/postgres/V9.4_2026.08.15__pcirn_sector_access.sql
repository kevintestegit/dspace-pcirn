-- PCIRN sector access reconciliation.
-- Sector membership is separate from the existing NUGECID workflow role.

CREATE TEMP TABLE pcirn_sector_map (
    group_name text PRIMARY KEY,
    community_title text NOT NULL,
    community_uuid uuid
) ON COMMIT DROP;

INSERT INTO pcirn_sector_map (group_name, community_title)
VALUES
    ('PCIRN_Setor_DG', 'Gestão Estratégica e Administrativa (DG)'),
    ('PCIRN_Setor_IC', 'Instituto de Criminalística (IC)'),
    ('PCIRN_Setor_II', 'Instituto de Identificação (II)'),
    ('PCIRN_Setor_IML', 'Instituto de Medicina Legal (IML)'),
    ('PCIRN_Setor_NUGECID', 'Núcleo de Gestão do Conhecimento, Informação, Documentação e Memória (NUGECID)');

DO $$
DECLARE
    sector record;
    group_uuid uuid;
    resolved_community_uuid uuid;
    title_field integer;
    object_uuid uuid;
BEGIN
    SELECT metadata_field_id
    INTO title_field
    FROM metadatafieldregistry
    WHERE metadata_schema_id = (SELECT metadata_schema_id
                                FROM metadataschemaregistry
                                WHERE short_id = 'dc')
      AND element = 'title'
      AND qualifier IS NULL;

    IF title_field IS NULL THEN
        RAISE EXCEPTION 'The dc.title metadata field is missing';
    END IF;

    FOR sector IN SELECT * FROM pcirn_sector_map LOOP
        SELECT uuid INTO group_uuid
        FROM epersongroup
        WHERE name = sector.group_name;

        IF group_uuid IS NULL THEN
            group_uuid := gen_random_uuid();
            INSERT INTO dspaceobject (uuid) VALUES (group_uuid);
            INSERT INTO epersongroup (uuid, name, permanent)
            VALUES (group_uuid, sector.group_name, false);
        END IF;

        SELECT c.uuid INTO resolved_community_uuid
        FROM community c
        JOIN metadatavalue mv ON mv.dspace_object_id = c.uuid
                              AND mv.metadata_field_id = title_field
        WHERE mv.text_value = sector.community_title;

        -- NUGECID is a sector in the approved structure but had no community yet.
        IF resolved_community_uuid IS NULL AND sector.group_name = 'PCIRN_Setor_NUGECID' THEN
            resolved_community_uuid := gen_random_uuid();
            INSERT INTO dspaceobject (uuid) VALUES (resolved_community_uuid);
            INSERT INTO community (uuid) VALUES (resolved_community_uuid);
            INSERT INTO metadatavalue (
                metadata_field_id, text_value, text_lang, place, confidence, dspace_object_id
            ) VALUES (
                title_field, sector.community_title, 'pt-BR', 0, -1, resolved_community_uuid
            );
        END IF;

        IF resolved_community_uuid IS NULL THEN
            RAISE EXCEPTION 'PCIRN sector community not found: %', sector.community_title;
        END IF;

        UPDATE pcirn_sector_map sm
        SET community_uuid = resolved_community_uuid
        WHERE sm.group_name = sector.group_name;
    END LOOP;

    -- Move existing PCIRN visibility policies from the generic authenticated group
    -- to the sector group that owns the object tree.
    FOR sector IN SELECT * FROM pcirn_sector_map LOOP
        SELECT uuid INTO group_uuid
        FROM epersongroup
        WHERE name = sector.group_name;

        FOR object_uuid IN
            SELECT sector.community_uuid
            UNION
            SELECT c.uuid
            FROM collection c
            JOIN community2collection cc ON cc.collection_id = c.uuid
            WHERE cc.community_id = sector.community_uuid
            UNION
            SELECT i.uuid
            FROM item i
            JOIN collection c ON c.uuid = i.owning_collection
            JOIN community2collection cc ON cc.collection_id = c.uuid
            WHERE cc.community_id = sector.community_uuid
            UNION
            SELECT b.uuid
            FROM bundle b
            JOIN item2bundle ib ON ib.bundle_id = b.uuid
            JOIN item i ON i.uuid = ib.item_id
            JOIN collection c ON c.uuid = i.owning_collection
            JOIN community2collection cc ON cc.collection_id = c.uuid
            WHERE cc.community_id = sector.community_uuid
            UNION
            SELECT bs.uuid
            FROM bitstream bs
            JOIN bundle2bitstream b2bs ON b2bs.bitstream_id = bs.uuid
            JOIN bundle b ON b.uuid = b2bs.bundle_id
            JOIN item2bundle ib ON ib.bundle_id = b.uuid
            JOIN item i ON i.uuid = ib.item_id
            JOIN collection c ON c.uuid = i.owning_collection
            JOIN community2collection cc ON cc.collection_id = c.uuid
            WHERE cc.community_id = sector.community_uuid
        LOOP
            INSERT INTO resourcepolicy (
                policy_id, resource_type_id, resource_id, action_id,
                start_date, end_date, rpname, rptype, rpdescription,
                eperson_id, epersongroup_id, dspace_object
            )
            SELECT nextval('resourcepolicy_seq'), rp.resource_type_id, rp.resource_id, rp.action_id,
                   rp.start_date, rp.end_date, rp.rpname, rp.rptype, rp.rpdescription,
                   NULL, group_uuid, rp.dspace_object
            FROM resourcepolicy rp
            JOIN epersongroup logged ON logged.uuid = rp.epersongroup_id
            WHERE logged.name = 'Usuarios_Logados'
              AND rp.dspace_object = object_uuid
              AND rp.action_id IN (0, 9, 10)
              AND NOT EXISTS (
                  SELECT 1
                  FROM resourcepolicy existing
                  WHERE existing.dspace_object = rp.dspace_object
                    AND existing.action_id = rp.action_id
                    AND existing.epersongroup_id = group_uuid
              );

            DELETE FROM resourcepolicy rp
            USING epersongroup logged
            WHERE logged.uuid = rp.epersongroup_id
              AND logged.name = 'Usuarios_Logados'
              AND rp.dspace_object = object_uuid
              AND rp.action_id IN (0, 9, 10);
        END LOOP;

        -- The newly-created NUGECID community has no inherited policy to move.
        INSERT INTO resourcepolicy (
            policy_id, resource_type_id, action_id, rpname, rptype,
            epersongroup_id, dspace_object
        )
        SELECT nextval('resourcepolicy_seq'), 4, 0, 'PCIRN sector read', 'CUSTOM',
               group_uuid, sector.community_uuid
        WHERE NOT EXISTS (
            SELECT 1
            FROM resourcepolicy rp
            WHERE rp.dspace_object = sector.community_uuid
              AND rp.action_id = 0
              AND rp.epersongroup_id = group_uuid
        );
    END LOOP;
END $$;

-- Gesiele is already a NUGECID workflow operator; expose the new NUGECID sector
-- without changing the existing NUGECID curator role.
INSERT INTO epersongroup2eperson (eperson_group_id, eperson_id)
SELECT sector.uuid, e.uuid
FROM epersongroup sector
CROSS JOIN eperson e
WHERE sector.name = 'PCIRN_Setor_NUGECID'
  AND e.email = 'gesiele@localhost.com'
  AND NOT EXISTS (
      SELECT 1
      FROM epersongroup2eperson m
      WHERE m.eperson_group_id = sector.uuid
        AND m.eperson_id = e.uuid
  );

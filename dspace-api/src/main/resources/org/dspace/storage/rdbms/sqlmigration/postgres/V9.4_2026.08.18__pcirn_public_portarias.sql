-- PCIRN public access for the exact Portarias collection in the four public communities.
-- Idempotent: preserve existing sector, workflow and other policies.

CREATE TEMP TABLE pcirn_public_portarias_targets (
    community_title text PRIMARY KEY,
    collection_title text NOT NULL,
    community_uuid uuid,
    collection_uuid uuid
) ON COMMIT DROP;

INSERT INTO pcirn_public_portarias_targets (community_title, collection_title)
VALUES
    ('Gestão Estratégica e Administrativa (DG)', 'Portarias e Atos Normativos Internos'),
    ('Instituto de Criminalística (IC)', 'Portarias e Atos Normativos Internos'),
    ('Instituto de Identificação (II)', 'Portarias e Atos Normativos Internos'),
    ('Instituto de Medicina Legal (IML)', 'Portarias e Atos Normativos Internos');

CREATE TEMP TABLE pcirn_public_portarias_context (
    anonymous_uuid uuid NOT NULL
) ON COMMIT DROP;

DO $$
DECLARE
    target record;
    anonymous_uuid uuid;
    title_field integer;
    match_count integer;
    resolved_community_uuid uuid;
    resolved_collection_uuid uuid;
BEGIN
    SELECT uuid
    INTO anonymous_uuid
    FROM epersongroup
    WHERE name = 'Anonymous';

    IF NOT FOUND THEN
        RAISE EXCEPTION 'PCIRN public portarias migration: Anonymous group not found';
    END IF;

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

    IF NOT FOUND THEN
        RAISE EXCEPTION 'PCIRN public portarias migration: dc.title metadata field not found';
    END IF;

    INSERT INTO pcirn_public_portarias_context (anonymous_uuid)
    VALUES (anonymous_uuid);

    FOR target IN SELECT * FROM pcirn_public_portarias_targets LOOP
        SELECT count(*)
        INTO match_count
        FROM community c
        JOIN metadatavalue mv ON mv.dspace_object_id = c.uuid
        WHERE mv.metadata_field_id = title_field
          AND mv.text_value = target.community_title;

        IF match_count = 0 THEN
            RAISE EXCEPTION 'PCIRN public portarias migration: community not found: %',
                target.community_title;
        ELSIF match_count > 1 THEN
            RAISE EXCEPTION 'PCIRN public portarias migration: multiple communities found: %',
                target.community_title;
        END IF;

        SELECT c.uuid
        INTO resolved_community_uuid
        FROM community c
        JOIN metadatavalue mv ON mv.dspace_object_id = c.uuid
        WHERE mv.metadata_field_id = title_field
          AND mv.text_value = target.community_title;

        SELECT count(*)
        INTO match_count
        FROM collection col
        JOIN community2collection cc ON cc.collection_id = col.uuid
        JOIN metadatavalue mv ON mv.dspace_object_id = col.uuid
        WHERE cc.community_id = resolved_community_uuid
          AND mv.metadata_field_id = title_field
          AND mv.text_value = target.collection_title;

        IF match_count = 0 THEN
            RAISE EXCEPTION 'PCIRN public portarias migration: collection not found: % in community %',
                target.collection_title, target.community_title;
        ELSIF match_count > 1 THEN
            RAISE EXCEPTION 'PCIRN public portarias migration: multiple collections found: % in community %',
                target.collection_title, target.community_title;
        END IF;

        SELECT col.uuid
        INTO resolved_collection_uuid
        FROM collection col
        JOIN community2collection cc ON cc.collection_id = col.uuid
        JOIN metadatavalue mv ON mv.dspace_object_id = col.uuid
        WHERE cc.community_id = resolved_community_uuid
          AND mv.metadata_field_id = title_field
          AND mv.text_value = target.collection_title;

        UPDATE pcirn_public_portarias_targets
        SET community_uuid = resolved_community_uuid,
            collection_uuid = resolved_collection_uuid
        WHERE community_title = target.community_title;
    END LOOP;
END $$;

-- A community has only a direct READ policy.
INSERT INTO resourcepolicy (policy_id, resource_type_id, action_id, epersongroup_id, dspace_object)
SELECT nextval('resourcepolicy_seq'), 4, 0, context.anonymous_uuid, target.community_uuid
FROM pcirn_public_portarias_targets target
CROSS JOIN pcirn_public_portarias_context context
WHERE NOT EXISTS (
    SELECT 1
    FROM resourcepolicy rp
    WHERE rp.dspace_object = target.community_uuid
      AND rp.action_id = 0
      AND rp.epersongroup_id = context.anonymous_uuid
);

-- Collections provide access and defaults for future items and bitstreams.
INSERT INTO resourcepolicy (policy_id, resource_type_id, action_id, epersongroup_id, dspace_object)
SELECT nextval('resourcepolicy_seq'), 3, actions.action_id,
       context.anonymous_uuid, target.collection_uuid
FROM pcirn_public_portarias_targets target
CROSS JOIN pcirn_public_portarias_context context
CROSS JOIN (VALUES (0), (9), (10)) AS actions(action_id)
WHERE NOT EXISTS (
    SELECT 1
    FROM resourcepolicy rp
    WHERE rp.dspace_object = target.collection_uuid
      AND rp.action_id = actions.action_id
      AND rp.epersongroup_id = context.anonymous_uuid
);

-- Existing items, bundles and bitstreams need direct READ policies.
INSERT INTO resourcepolicy (policy_id, resource_type_id, action_id, epersongroup_id, dspace_object)
SELECT nextval('resourcepolicy_seq'), 2, 0, context.anonymous_uuid, objects.object_uuid
FROM (
    SELECT DISTINCT c2i.item_id AS object_uuid
    FROM pcirn_public_portarias_targets target
    JOIN collection2item c2i ON c2i.collection_id = target.collection_uuid
) objects
CROSS JOIN pcirn_public_portarias_context context
WHERE NOT EXISTS (
    SELECT 1
    FROM resourcepolicy rp
    WHERE rp.dspace_object = objects.object_uuid
      AND rp.action_id = 0
      AND rp.epersongroup_id = context.anonymous_uuid
);

INSERT INTO resourcepolicy (policy_id, resource_type_id, action_id, epersongroup_id, dspace_object)
SELECT nextval('resourcepolicy_seq'), 1, 0, context.anonymous_uuid, objects.object_uuid
FROM (
    SELECT DISTINCT i2b.bundle_id AS object_uuid
    FROM pcirn_public_portarias_targets target
    JOIN collection2item c2i ON c2i.collection_id = target.collection_uuid
    JOIN item2bundle i2b ON i2b.item_id = c2i.item_id
) objects
CROSS JOIN pcirn_public_portarias_context context
WHERE NOT EXISTS (
    SELECT 1
    FROM resourcepolicy rp
    WHERE rp.dspace_object = objects.object_uuid
      AND rp.action_id = 0
      AND rp.epersongroup_id = context.anonymous_uuid
);

INSERT INTO resourcepolicy (policy_id, resource_type_id, action_id, epersongroup_id, dspace_object)
SELECT nextval('resourcepolicy_seq'), 0, 0, context.anonymous_uuid, objects.object_uuid
FROM (
    SELECT DISTINCT b2s.bitstream_id AS object_uuid
    FROM pcirn_public_portarias_targets target
    JOIN collection2item c2i ON c2i.collection_id = target.collection_uuid
    JOIN item2bundle i2b ON i2b.item_id = c2i.item_id
    JOIN bundle2bitstream b2s ON b2s.bundle_id = i2b.bundle_id
) objects
CROSS JOIN pcirn_public_portarias_context context
WHERE NOT EXISTS (
    SELECT 1
    FROM resourcepolicy rp
    WHERE rp.dspace_object = objects.object_uuid
      AND rp.action_id = 0
      AND rp.epersongroup_id = context.anonymous_uuid
);

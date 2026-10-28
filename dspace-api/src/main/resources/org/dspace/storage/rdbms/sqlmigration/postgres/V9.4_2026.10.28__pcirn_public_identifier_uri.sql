-- PCIRN: point stored item/collection URIs at the public repository host.
--
-- The PCIRN migrations that created the initial collections wrote
-- dc.identifier.uri with the development host (localhost / 10.9.233.96).
-- Those values are displayed on the item page and used by
-- citation_abstract_html_url, so they must not leak outside the local machine.
--
-- New content already receives dspace.ui.url from HandleService. This
-- migration only repairs the legacy rows and is idempotent.

DO $$
DECLARE
    uri_field_id integer;
    updated_rows integer;
BEGIN
    SELECT mfr.metadata_field_id
    INTO uri_field_id
    FROM metadatafieldregistry mfr
    JOIN metadataschemaregistry msr
      ON msr.metadata_schema_id = mfr.metadata_schema_id
    WHERE msr.short_id = 'dc'
      AND mfr.element = 'identifier'
      AND mfr.qualifier = 'uri';

    IF uri_field_id IS NULL THEN
        RAISE EXCEPTION 'dc.identifier.uri metadata field is missing';
    END IF;

    UPDATE metadatavalue
    SET text_value = regexp_replace(
            text_value,
            '^https?://(localhost|10\.9\.233\.96):4000',
            'https://repositorio.pci.rn.gov.br')
    WHERE metadata_field_id = uri_field_id
      AND text_value ~ '^https?://(localhost|10\.9\.233\.96):4000';

    GET DIAGNOSTICS updated_rows = ROW_COUNT;
    RAISE NOTICE 'PCIRN public URI migration: % metadata values updated', updated_rows;
END $$;

--
-- The contents of this file are subject to the license and copyright
-- detailed in the LICENSE and NOTICE files at the root of the source
-- tree and available online at
--
-- http://www.dspace.org/license/
--

-- PCIRN: fold the former "Guias e Manuais" category into PAP.
--
-- The manual document types are no longer part of the controlled vocabulary.
-- Existing items were catalogued as PAP plus PORTARIA, as PAP plus a MANUAL_*
-- type, or as MANUAL_* only. This migration normalizes the types, strips the
-- "MANUAL / " title prefix and removes the generic "Manual" subject from PAP
-- items. Identifier and alternative-title metadata are left untouched.
--
-- Idempotent: a second run updates zero rows.

DO $$
DECLARE
    type_field_id integer;
    title_field_id integer;
    subject_field_id integer;
    removed_portaria integer := 0;
    removed_manual_types integer := 0;
    converted_manual_types integer := 0;
    fixed_titles integer := 0;
    removed_subjects integer := 0;
BEGIN
    SELECT mfr.metadata_field_id
    INTO type_field_id
    FROM metadatafieldregistry mfr
    JOIN metadataschemaregistry msr
      ON msr.metadata_schema_id = mfr.metadata_schema_id
    WHERE msr.short_id = 'dc'
      AND mfr.element = 'type'
      AND mfr.qualifier IS NULL;

    SELECT mfr.metadata_field_id
    INTO title_field_id
    FROM metadatafieldregistry mfr
    JOIN metadataschemaregistry msr
      ON msr.metadata_schema_id = mfr.metadata_schema_id
    WHERE msr.short_id = 'dc'
      AND mfr.element = 'title'
      AND mfr.qualifier IS NULL;

    SELECT mfr.metadata_field_id
    INTO subject_field_id
    FROM metadatafieldregistry mfr
    JOIN metadataschemaregistry msr
      ON msr.metadata_schema_id = mfr.metadata_schema_id
    WHERE msr.short_id = 'dc'
      AND mfr.element = 'subject'
      AND mfr.qualifier IS NULL;

    IF type_field_id IS NULL OR title_field_id IS NULL OR subject_field_id IS NULL THEN
        RAISE EXCEPTION 'PCIRN PAP cleanup: dc.type, dc.title or dc.subject metadata field is missing';
    END IF;

    -- Items that are already PAP lose the legacy manual type.
    DELETE FROM metadatavalue mv
    WHERE mv.metadata_field_id = type_field_id
      AND mv.text_value IN ('MANUAL_GESTAO', 'MANUAL_GUIA')
      AND EXISTS (
          SELECT 1
          FROM metadatavalue pap
          WHERE pap.dspace_object_id = mv.dspace_object_id
            AND pap.metadata_field_id = type_field_id
            AND pap.text_value = 'PAP'
      );
    GET DIAGNOSTICS removed_manual_types = ROW_COUNT;

    -- Items catalogued only as manual become PAP.
    UPDATE metadatavalue
    SET text_value = 'PAP'
    WHERE metadata_field_id = type_field_id
      AND text_value IN ('MANUAL_GESTAO', 'MANUAL_GUIA');
    GET DIAGNOSTICS converted_manual_types = ROW_COUNT;

    -- PAP items must not keep the overlapping PORTARIA type.
    DELETE FROM metadatavalue mv
    WHERE mv.metadata_field_id = type_field_id
      AND mv.text_value = 'PORTARIA'
      AND EXISTS (
          SELECT 1
          FROM metadatavalue pap
          WHERE pap.dspace_object_id = mv.dspace_object_id
            AND pap.metadata_field_id = type_field_id
            AND pap.text_value = 'PAP'
      );
    GET DIAGNOSTICS removed_portaria = ROW_COUNT;

    UPDATE metadatavalue mv
    SET text_value = regexp_replace(mv.text_value, '^MANUAL\s*/\s*', '', 'i')
    WHERE mv.metadata_field_id = title_field_id
      AND mv.text_value ~* '^MANUAL\s*/\s*'
      AND EXISTS (
          SELECT 1
          FROM metadatavalue pap
          WHERE pap.dspace_object_id = mv.dspace_object_id
            AND pap.metadata_field_id = type_field_id
            AND pap.text_value = 'PAP'
      );
    GET DIAGNOSTICS fixed_titles = ROW_COUNT;

    DELETE FROM metadatavalue mv
    WHERE mv.metadata_field_id = subject_field_id
      AND mv.text_value IN ('Manual', 'Manuais')
      AND EXISTS (
          SELECT 1
          FROM metadatavalue pap
          WHERE pap.dspace_object_id = mv.dspace_object_id
            AND pap.metadata_field_id = type_field_id
            AND pap.text_value = 'PAP'
      );
    GET DIAGNOSTICS removed_subjects = ROW_COUNT;

    RAISE NOTICE 'PCIRN PAP cleanup: % manual type value(s) removed, % converted to PAP, % PORTARIA value(s) removed, % title(s) fixed, % subject value(s) removed',
        removed_manual_types, converted_manual_types, removed_portaria, fixed_titles, removed_subjects;
END $$;

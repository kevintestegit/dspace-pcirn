-- Keep the sector membership in sync with the existing NUGECID curator role.
-- The role remains separate; this only grants the corresponding sector view.

INSERT INTO epersongroup2eperson (eperson_group_id, eperson_id)
SELECT sector.uuid, member.eperson_id
FROM epersongroup sector
JOIN epersongroup curator ON curator.name = 'NUGECID'
JOIN epersongroup2eperson member ON member.eperson_group_id = curator.uuid
WHERE sector.name = 'PCIRN_Setor_NUGECID'
  AND NOT EXISTS (
      SELECT 1
      FROM epersongroup2eperson existing
      WHERE existing.eperson_group_id = sector.uuid
        AND existing.eperson_id = member.eperson_id
  );

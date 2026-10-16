--
-- The contents of this file are subject to the license and copyright
-- detailed in the LICENSE and NOTICE files at the root of the source
-- tree and available online at
--
-- http://www.dspace.org/license/
--

-- Empty repositories have no institutional users, communities or collections.
-- Create only the generic roles used by PCIRN authorization and submission.
DO $$
DECLARE
    role_name text;
    role_uuid uuid;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['Usuarios_Logados', 'NUGECID', 'PCIRN_Depositantes'] LOOP
        IF NOT EXISTS (SELECT 1 FROM epersongroup WHERE name = role_name) THEN
            role_uuid := gen_random_uuid();
            INSERT INTO dspaceobject (uuid) VALUES (role_uuid);
            INSERT INTO epersongroup (uuid, name, permanent) VALUES (role_uuid, role_name, false);
        END IF;
    END LOOP;
END $$;

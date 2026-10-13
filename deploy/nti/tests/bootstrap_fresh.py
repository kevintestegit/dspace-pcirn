#!/usr/bin/env python3
"""Prove empty bootstrap using a new PostgreSQL container and an isolated backend.

No existing network, container, database or volume is reused or removed. Containers
are stopped on exit and retained for inspection. Requires an explicitly built API jar.
"""
import argparse
import json
from pathlib import Path
import secrets
import subprocess
import time
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api-jar', required=True, type=Path)
    parser.add_argument('--backend-image', required=True)
    parser.add_argument('--postgres-image', default='postgres:15')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    jar = args.api_jar.resolve(strict=True)
    prefix = 'pcirn-bootstrap-' + uuid4().hex[:12]
    password = secrets.token_hex(24)
    containers = []

    def docker(*command, check=True):
        result = subprocess.run(['docker', *command], check=False, text=True, capture_output=True)
        if check and result.returncode:
            raise RuntimeError('Disposable Docker operation failed: '
                               + result.stderr.replace(password, '[redacted]'))
        return result

    def sql(query, database='dspace'):
        return docker('exec', prefix + '-pg', 'psql', '-U', 'postgres', '-d', database,
                      '-XAt', '-v', 'ON_ERROR_STOP=1', '-c', query).stdout.strip()

    def backend(action, profile='fresh', database='dspace'):
        name = prefix + '-backend-' + str(len(containers))
        containers.append(name)
        result = docker('run', '--name', name, '--label',
                        'org.dspacepcirn.purpose=disposable-bootstrap', '--network', prefix,
                        '--mount', f'type=bind,src={jar},dst=/dspace/lib/dspace-api-9.4-SNAPSHOT.jar,readonly',
                        '-e', 'db__P__url=jdbc:postgresql://' + prefix + '-pg:5432/' + database,
                        '-e', 'db__P__username=postgres', '-e', 'db__P__password=' + password,
                        '-e', 'db__P__pcirn__P__profile=' + profile,
                        '-e', 'discovery__P__autoReindex=false', '--entrypoint', '/dspace/bin/dspace',
                        args.backend_image, 'database', action, check=False)
        # Save diagnostic output with restrictive permissions; never print credentials.
        log = args.output.with_name(args.output.name + '.' + name + '.' + action + '.log')
        log.write_text((result.stdout + result.stderr).replace(password, '[redacted]'))
        log.chmod(0o600)
        return result

    try:
        docker('network', 'create', '--label', 'org.dspacepcirn.purpose=disposable-bootstrap', prefix)
        containers.append(prefix + '-pg')
        docker('run', '-d', '--name', prefix + '-pg', '--network', prefix, '--label',
               'org.dspacepcirn.purpose=disposable-bootstrap', '--tmpfs', '/var/lib/postgresql/data',
               '-e', 'POSTGRES_PASSWORD=' + password, '-e', 'POSTGRES_DB=dspace', args.postgres_image)
        deadline = time.monotonic() + 60
        while docker('exec', prefix + '-pg', 'pg_isready', '-U', 'postgres', check=False).returncode:
            if time.monotonic() >= deadline:
                raise RuntimeError('Disposable PostgreSQL did not become ready')
            time.sleep(0.25)
        capability = backend('fresh-capability')
        assert capability.returncode == 0 and capability.stdout.strip() == 'pcirn-fresh-v1'
        sql('CREATE DATABASE guard_existing;')
        sql('CREATE TABLE preserved_document (id integer PRIMARY KEY); '
            'INSERT INTO preserved_document VALUES (42);', 'guard_existing')
        rejected = backend('migrate', database='guard_existing')
        assert rejected.returncode != 0, 'Database without history but with existing objects was adopted'
        assert sql('SELECT id FROM preserved_document;', 'guard_existing') == '42'
        assert backend('migrate').returncode == 0, 'Fresh migrate failed; inspect private log'
        assert sql('SELECT count(*) FROM community;') == '0'
        assert sql('SELECT count(*) FROM collection;') == '0'
        assert sql('SELECT count(*) FROM eperson;') == '0'
        assert int(sql('SELECT count(*) FROM metadatafieldregistry;')) > 0
        assert sql("SELECT count(*) FROM epersongroup WHERE name IN ('Anonymous','Administrator');") == '2'
        assert sql('SELECT count(*) FROM schema_version WHERE NOT success;') == '0'
        query = """SELECT json_agg(json_build_object('version', version, 'script', script,
                   'checksum', checksum) ORDER BY installed_rank) FROM schema_version
                   WHERE success AND version IS NOT NULL;"""
        history = json.loads(sql(query))
        assert backend('migrate').returncode == 0, 'Fresh resume failed'
        assert backend('validate').returncode == 0, 'Flyway checksum validation failed'
        assert history == json.loads(sql(query)), 'Resume changed history'
        assert backend('validate', 'institutional').returncode != 0, 'Profile switch must fail'
        sql("INSERT INTO schema_version (installed_rank, version, description, type, script, checksum, "
            "installed_by, execution_time, success) VALUES (999, '9.4.2026.8.15', 'guard fixture', "
            "'SQL', 'V9.4_2026.08.15__pcirn_sector_access.sql', 1, 'postgres', 0, true);")
        rejected = backend('validate')
        assert rejected.returncode != 0, 'Fresh profile adopted institutional history'
        assert 'cannot replace institutional migration history' in rejected.stderr + rejected.stdout
        args.output.write_text(json.dumps(history, indent=2) + '\n')
        args.output.chmod(0o600)
        print(f'Fresh bootstrap, resume and profile guard OK: {len(history)} migrations; {prefix}')
    finally:
        for name in reversed(containers):
            docker('stop', name, check=False)


if __name__ == '__main__':
    main()

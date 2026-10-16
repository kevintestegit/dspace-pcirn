#!/usr/bin/env python3
"""Opt-in real Docker/TLS/resumption proof in a disposable Ubuntu 24.04 runner.

Run with a unique /tmp/pcirn-host-postgres-* root bind-mounted at the same host
path, host networking, and the local Docker socket. Requires PostgreSQL16
clients, OpenSSL and Docker Compose. Creates only its own labeled PostgreSQL
resources, stops its database on completion and retains all volumes and files.
PCIRN_E2E_POSTGRES_IMAGE can supply a previously validated official immutable
PostgreSQL16 digest when repeating the storage checks without registry discovery.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
import re
from pathlib import Path
import secrets
import socket
import sys
import tempfile
from types import SimpleNamespace
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pcirn import Deployment, Error, checksum, provision, read_json, write_json
import preflight
from releases import docker_architecture, postgres_image
from wizard import provision_postgres


def main(root, backend_image=None, api_jar=None):
    root = Path(root).absolute()
    if not str(root).startswith('/tmp/pcirn-host-postgres-') or root.resolve() != root:
        raise Error('Use um diretório descartável /tmp/pcirn-host-postgres-* sem links')
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if list(root.iterdir()):
        raise Error('O teste exige um diretório novo e vazio; nada foi alterado')
    os.umask(0o077)
    runner = Deployment.__new__(Deployment)
    runner.env = {k: v for k, v in os.environ.items()
                  if not k.startswith(('PG', 'DOCKER_', 'COMPOSE_', 'DB_', 'DSPACE_'))}
    image = os.environ.get('PCIRN_E2E_POSTGRES_IMAGE')
    if image:
        if not re.fullmatch(r'postgres@sha256:[a-f0-9]{64}', image):
            raise Error('O teste exige um digest oficial PostgreSQL previamente validado')
    else:
        image = postgres_image(runner.run, docker_architecture(runner.run))
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    config = {'DB_URL': f'jdbc:postgresql://127.0.0.1:{port}/dspace?' +
                       urlencode({'sslmode': 'verify-ca', 'sslrootcert':
                                  str(root / 'postgres-tls/server.crt')}),
              'DB_USERNAME': 'dspace', 'DB_PASSWORD': secrets.token_urlsafe(48),
              'PG_MODE': 'docker', 'PG_IMAGE': image, 'PG_MAJOR': '16',
              'PUBLIC_UI_URL': 'https://repository.invalid',
              'PUBLIC_REST_URL': 'https://repository.invalid/server',
              'PUBLIC_REST_HOST': 'repository.invalid'}
    if bool(backend_image) != bool(api_jar):
        raise Error('--backend-image e --api-jar devem ser informados juntos')
    if backend_image:
        api_jar = Path(api_jar).resolve(strict=True)
        backend_image = runner.run(['docker', 'image', 'inspect', backend_image,
                                    '--format', '{{.Id}}'], timeout=30).strip()
        if not re.fullmatch(r'sha256:[a-f0-9]{64}', backend_image):
            raise Error('A imagem backend de teste deve estar disponível localmente')
        config['DB_PROFILE'] = 'fresh'
    config.update(preflight.select_resources(runner.run, root))
    release = {'schema_version': 1, 'version': '1.0.0-e2e', 'commit': '0' * 40,
               'images': {name: 'ghcr.io/kevintestegit/e2e-' + name + '@sha256:' + '1' * 64
                          for name in ('backend', 'solr', 'frontend')},
               'database': {'migrations': [{'version': '1', 'script': 'e2e.sql', 'checksum': 1}]}}
    if backend_image:
        history = read_json(Path(__file__).resolve().parents[3] / 'scripts/flyway-fresh-history.json')
        release['database'].update(fresh_bootstrap='pcirn-fresh-v1', fresh_migrations=history)
    write_json(root / 'e2e-config.json', config)
    write_json(root / 'e2e-release.json', release)
    dep = provision(SimpleNamespace(root=root, config=root / 'e2e-config.json',
                                   manifest=root / 'e2e-release.json'))
    cli_containers = []
    if backend_image:
        original_override = dep.tls_override

        @contextmanager
        def fresh_override():
            with original_override() as original:
                document = read_json(original) if original else {'services': {'dspace': {'volumes': []}}}
                service = document['services']['dspace']
                service.update(image=backend_image, pull_policy='never')
                service['volumes'].append({'type': 'bind', 'source': str(api_jar),
                                          'target': '/dspace/lib/dspace-api-9.4-SNAPSHOT.jar',
                                          'read_only': True, 'bind': {'create_host_path': False}})
                with tempfile.NamedTemporaryFile(mode='w', dir=root, prefix='.e2e-api-',
                                                 suffix='.json') as stream:
                    json.dump(document, stream)
                    stream.flush()
                    yield stream.name

        dep.tls_override = fresh_override

        def backend(action):
            name = 'pcirn-host-fresh-' + hashlib.sha256(str(root).encode()).hexdigest()[:12] + '-' + action
            cli_containers.append(name)
            try:
                return dep.compose(release, 'run', '--no-deps', '-T', '--name', name,
                                   '--entrypoint', '/dspace/bin/dspace', 'dspace', 'database', action)
            finally:
                try:
                    logs = dep.run(['docker', 'logs', name], timeout=30)
                    (root / ('backend-' + action + '.log')).write_text(
                        logs.replace(config['DB_PASSWORD'], '[redacted]'))
                except Error:
                    pass

    try:
        provision_postgres(dep)
        pg = preflight.database(dep)
        assert pg['ssl'] and pg['server'] // 10000 == 16
        assert all(pg[k] for k in ('connect', 'create', 'schema', 'owner', 'objects'))
        if backend_image:
            assert dep.sql("SELECT NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole "
                           "FROM pg_roles WHERE rolname=current_user;") == 't'
            assert dep.user_objects() == 0
            assert backend('fresh-capability').strip() == 'pcirn-fresh-v1'
            assert dep.pending(release)
            backend('migrate')
            assert not dep.pending(release)
            backend('validate')
            for table in ('community', 'collection', 'eperson'):
                assert dep.sql('SELECT count(*) FROM ' + table + ';') == '0'
            assert int(dep.sql('SELECT count(*) FROM metadatafieldregistry;')) > 0
            assert dep.sql("SELECT count(*) FROM epersongroup WHERE name IN ('Anonymous','Administrator');") == '2'
            checked = preflight.database(dep)
            assert checked['ssl'] and checked['objects'] and checked['owner']
            print('PCIRN_FRESH_RESTRICTED_TLS_DEFAULTS_OK: empty PostgreSQL16, '
                  'NOSUPERUSER dspace role, managed TLS, discovery defaults, '
                  'capability, migrations, checksums and object ownership')
        external_config = dict(config, PG_MODE='external')
        external_config.pop('PG_IMAGE')
        external = Deployment(root, config=external_config)
        external_pg = preflight.database(external)
        assert external_pg['ssl'] and external_pg['server'] // 10000 == 16
        dep.run(['psql', '-X', '--no-password', '-v', 'ON_ERROR_STOP=1', '-c',
                 "CREATE TABLE pcirn_e2e_sentinel (value text); "
                 "INSERT INTO pcirn_e2e_sentinel VALUES ('preserve-me');"],
                pg=True, timeout=30)
        hashes = {name: checksum(root / name) for name in
                  ('postgres-password', 'postgres-tls/server.key', 'postgres-tls/server.crt')}
        dep.compose(dep.current(), 'stop', '--timeout', '30', 'postgres')
        provision_postgres(dep)
        assert dep.sql('SELECT value FROM pcirn_e2e_sentinel;') == 'preserve-me'
        assert hashes == {name: checksum(root / name) for name in hashes}
        journal = read_json(root / 'postgres.json')
        assert journal['status'] == 'ready'
        journal['status'] = 'creating'
        write_json(root / 'postgres.json', journal)
        provision_postgres(dep)
        assert read_json(root / 'postgres.json')['status'] == 'ready'
        assert dep.sql('SELECT value FROM pcirn_e2e_sentinel;') == 'preserve-me'
        assert hashes == {name: checksum(root / name) for name in hashes}
        preflight.database(dep)
        print('PCIRN_HOST_POSTGRES_E2E_OK: Docker/external TLS, clients16, privileges, '
              'stop/start ownership, ready and interrupted-commit resume, sentinel preserved')
        print('Root: ' + str(root))
        print('Volume: dspacepcirn-pg-' + hashlib.sha256(str(root).encode()).hexdigest()[:12])
    finally:
        for name in cli_containers:
            try:
                dep.run(['docker', 'stop', name], timeout=30)
            except Error:
                pass
        if (root / 'postgres.json').exists():
            dep.compose(dep.current(), 'stop', '--timeout', '30', 'postgres')


if __name__ == '__main__':
    try:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('root')
        parser.add_argument('--backend-image')
        parser.add_argument('--api-jar', type=Path)
        args = parser.parse_args()
        main(args.root, args.backend_image, args.api_jar)
    except (Error, OSError, ValueError, KeyError, IndexError) as error:
        print(str(error) if isinstance(error, Error) else type(error).__name__, file=sys.stderr)
        sys.exit(1)

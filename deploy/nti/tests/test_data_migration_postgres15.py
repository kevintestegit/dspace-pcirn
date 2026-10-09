"""Opt-in PostgreSQL 15 round trip in a new container with no host ports or volumes."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pcirn


@unittest.skipUnless(os.environ.get('PCIRN_RUN_POSTGRES15') == '1',
                     'Set PCIRN_RUN_POSTGRES15=1 to create a disposable PostgreSQL 15')
class PostgreSQL15MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='pcirn-pg15-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.base.chmod(0o755)
        self.docker = shutil.which('docker')
        self.name = 'pcirn-pg15-test-' + uuid4().hex
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                        '-keyout', str(self.base / 'server.key'), '-out', str(self.base / 'server.crt'),
                        '-subj', '/CN=localhost', '-days', '1'], check=True, capture_output=True)
        self.addCleanup(lambda: subprocess.run([self.docker, '--context', 'default', 'rm', '-f', self.name],
                                               capture_output=True, check=False))
        subprocess.run([self.docker, '--context', 'default', 'run', '-d', '--name', self.name,
                        '--network', 'none', '--tmpfs', '/var/lib/postgresql/data',
                        '--mount', f'type=bind,src={self.base},dst={self.base}',
                        '-e', 'POSTGRES_PASSWORD=fictional-pg15', '--entrypoint', '/bin/sh',
                        'postgres:15', '-c',
                        'chown postgres:postgres "$1/server.key"; chmod 600 "$1/server.key"; '
                        'exec /usr/local/bin/docker-entrypoint.sh postgres -c ssl=on '
                        '-c ssl_cert_file="$1/server.crt" -c ssl_key_file="$1/server.key"',
                        'sh', str(self.base)], check=True, capture_output=True)
        deadline = time.monotonic() + 40
        while True:
            ready = self.exec('postgres', 'pg_isready', '-h', '127.0.0.1', check=False)
            if ready.returncode == 0:
                break
            if time.monotonic() > deadline:
                self.fail('Disposable PostgreSQL 15 did not start')
            time.sleep(0.2)
        self.assertTrue(self.sql('postgres', 'SHOW server_version;').startswith('15.'))
        self.sql('postgres', 'CREATE DATABASE fictional_source;')
        self.sql('postgres', 'CREATE DATABASE fictional_target;')
        self.bin = self.base / 'bin'
        self.bin.mkdir()
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ['PATH'])
        client = f'''#!/usr/bin/env python3
import os, pathlib, subprocess, sys
args = [{self.docker!r}, '--context', 'default', 'exec', '--user', {str(os.getuid()) + ':' + str(os.getgid())!r}]
for key, value in os.environ.items():
    if key.startswith('PG'): args += ['-e', key + '=' + value]
args += [{self.name!r}, pathlib.Path(sys.argv[0]).name, *sys.argv[1:]]
sys.exit(subprocess.run(args).returncode)
'''
        for tool in ('psql', 'pg_dump', 'pg_restore'):
            path = self.bin / tool
            path.write_text(client)
            path.chmod(0o700)
        # Only the application lifecycle is simulated; PostgreSQL clients run in the new cluster.
        app = self.bin / 'docker'
        app.write_text('''#!/usr/bin/env python3
import sys
args = sys.argv[1:]
if 'compose' not in args or not ('ps' in args or 'stop' in args): sys.exit(99)
''')
        app.chmod(0o700)
        self.release = self.base / 'release.json'
        self.release.write_text(json.dumps({
            'schema_version': 1, 'version': '1.0.0',
            'images': {key: 'ghcr.io/fictional/' + key + '@sha256:' + '1' * 64
                       for key in pcirn.IMAGE_KEYS},
            'database': {'migrations': [{'version': '1', 'script': 'V1__fictional.sql', 'checksum': 1}]}}))
        self.roots = {}
        for label in ('source', 'target'):
            root = self.base / label
            config = self.base / f'{label}.json'
            config.write_text(json.dumps({
                'DB_URL': f'jdbc:postgresql://127.0.0.1:5432/fictional_{label}?sslmode=require',
                'DB_USERNAME': 'postgres', 'DB_PASSWORD': 'fictional-pg15',
                'PUBLIC_UI_URL': 'https://fictional.invalid',
                'PUBLIC_REST_URL': 'https://fictional.invalid/server',
                'PUBLIC_REST_HOST': 'fictional.invalid'}))
            config.chmod(0o600)
            pcirn.provision(type('Args', (), {'root': root, 'config': config, 'manifest': self.release})())
            self.roots[label] = root
        assets = self.roots['source'] / 'data/assetstore/12/34/56'
        assets.mkdir(parents=True)
        payload = b'documento ficticio PostgreSQL 15\n'
        (assets / '123456789012').write_bytes(payload)
        stats = self.roots['source'] / 'data/solr/statistics/data'
        stats.mkdir(parents=True)
        (stats / 'fictional.segment').write_bytes(b'fictional Solr statistics bytes')
        self.sql('fictional_source', f'''
CREATE TABLE item (uuid uuid PRIMARY KEY);
CREATE TABLE eperson (uuid uuid PRIMARY KEY);
CREATE TABLE epersongroup (id integer PRIMARY KEY);
CREATE TABLE community (uuid uuid PRIMARY KEY);
CREATE TABLE collection (uuid uuid PRIMARY KEY);
CREATE TABLE handle (handle text PRIMARY KEY, resource_id uuid REFERENCES item);
CREATE TABLE resourcepolicy (id serial PRIMARY KEY, object_uuid uuid REFERENCES item,
 action_id integer, epersongroup_id integer REFERENCES epersongroup);
CREATE TABLE metadatavalue (text_value text, place integer);
CREATE TABLE schema_version (version text, script text, checksum integer, success boolean);
CREATE TABLE bitstream (uuid uuid PRIMARY KEY, internal_id text, store_number integer,
 deleted boolean, size_bytes bigint, checksum_algorithm text, checksum text);
INSERT INTO item VALUES ('00000000-0000-0000-0000-000000000001');
INSERT INTO epersongroup VALUES (2);
INSERT INTO handle VALUES ('123456789/1', '00000000-0000-0000-0000-000000000001');
INSERT INTO resourcepolicy(object_uuid,action_id,epersongroup_id)
 VALUES ('00000000-0000-0000-0000-000000000001',0,2);
INSERT INTO metadatavalue VALUES ('Documento fictício',0);
INSERT INTO schema_version VALUES ('1','V1__fictional.sql',1,true);
INSERT INTO bitstream VALUES ('00000000-0000-0000-0000-000000000002','123456789012',0,
 false,{len(payload)},'MD5','{hashlib.md5(payload).hexdigest()}');
''')

    def exec(self, database, *args, check=True):
        return subprocess.run([self.docker, '--context', 'default', 'exec',
                               '-e', 'PGPASSWORD=fictional-pg15', '-e', 'PGSSLMODE=require',
                               '-e', 'PGUSER=postgres', '-e', 'PGDATABASE=' + database,
                               self.name, *args], capture_output=True, text=True, check=check)

    def sql(self, database, query):
        return self.exec(database, 'psql', '-h', '127.0.0.1', '-X', '-qAt',
                         '-v', 'ON_ERROR_STOP=1', '-c', query).stdout.strip()

    def cli(self, label, command, *args, expected=0):
        root = self.roots[label]
        result = subprocess.run([str(root / 'bin/dspacepcirn'), command, '--root', str(root),
                                 *map(str, args)], env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stderr + result.stdout)
        return result

    def test_export_restore_verify_and_refuse_occupied_database(self):
        package = self.base / 'package'
        self.cli('source', 'export-data', '--output', package)
        self.assertEqual(set(json.loads((package / 'checksums.json').read_text())),
                         {'database.dump', 'assetstore.tar.gz', 'solr.tar.gz',
                          'source-report.json', 'release.json'})
        self.cli('target', 'migrate-data', '--data-package', package)
        self.cli('target', 'verify-data', '--expected', package / 'source-report.json')
        for table in ('item', 'handle', 'resourcepolicy', 'schema_version', 'metadatavalue', 'bitstream'):
            query = f'SELECT json_agg(t)::text FROM {table} t;'
            self.assertEqual(self.sql('fictional_source', query), self.sql('fictional_target', query))
        self.assertEqual(self.sql('fictional_target',
                                 "SELECT nextval(pg_get_serial_sequence('resourcepolicy','id'));"), '2')
        self.assertEqual((self.roots['target'] / 'data/solr/statistics/data/fictional.segment').read_bytes(),
                         b'fictional Solr statistics bytes')
        # Removing only the local import marker must never bypass the occupied DB guard.
        (self.roots['target'] / 'data-import.json').unlink()
        denied = self.cli('target', 'migrate-data', '--data-package', package,
                          '--authorize-restore', expected=1)
        self.assertIn('Banco não vazio', denied.stderr)
        self.assertEqual(self.sql('fictional_target', 'SELECT count(*) FROM item;'), '1')
        self.sql('fictional_target', "UPDATE handle SET handle='fictitious/changed';")
        self.cli('target', 'verify-data', '--expected', package / 'source-report.json', expected=1)
        self.sql('fictional_target', "UPDATE handle SET handle='123456789/1';")
        self.sql('fictional_target', 'UPDATE resourcepolicy SET action_id=2;')
        self.cli('target', 'verify-data', '--expected', package / 'source-report.json', expected=1)
        self.sql('fictional_target', 'UPDATE resourcepolicy SET action_id=0;')
        stats = self.roots['target'] / 'data/solr/statistics/data/fictional.segment'
        stats.write_bytes(b'corruption')
        self.cli('target', 'verify-data', '--expected', package / 'source-report.json', expected=1)


if __name__ == '__main__':
    unittest.main()

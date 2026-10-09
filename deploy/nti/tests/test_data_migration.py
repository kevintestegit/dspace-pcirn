"""Fictitious database and documents; subprocess shims never access host services."""
import hashlib
import json
from pathlib import Path
import sys
import tarfile
import unittest

import test_installer as installer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import data_migration as migration


FAKE = installer.FAKE.replace(
    "query = args[args.index('-c') + 1]", "query = args[-1]"
).replace(
    "if 'UPDATE public.pcirn_homolog_probe' in query:",
    """if 'pg_stat_ssl' in query: print('f' if failure == 'tls' else 't')
    elif 'pg_stat_activity' in query:
        db['connection_checks'] = db.get('connection_checks', 0) + 1; save()
        print('1' if failure == 'connections' or
              (failure == 'late-connections' and db['connection_checks'] > 1) else '0')
    elif 'SELECT count(*) FROM pg_namespace' in query: print('1' if failure == 'schemas' else '0')
    elif 'FROM pg_tables' in query: print(json.dumps(sorted(db.get('tables', {}))))
    elif query.startswith('COPY '):
        import csv
        name = query.split('public."')[1].split('"')[0]
        writer = csv.writer(sys.stdout)
        for row in sorted(db['tables'][name], key=lambda r: json.dumps(r, sort_keys=True)):
            writer.writerow([json.dumps(row)])
    elif 'UPDATE public.pcirn_homolog_probe' in query:""").replace(
    "db.update(json.loads(pathlib.Path(args[-1]).read_text())); save()",
    "db.update(json.loads(pathlib.Path(args[-1]).read_text().removeprefix('PGDMP'))); save()"
).replace(
    "pathlib.Path(args[args.index('--file') + 1]).write_text(pathlib.Path(args[-1]).read_text())",
    "pathlib.Path(args[args.index('--file') + 1]).write_text(pathlib.Path(args[-1]).read_text().removeprefix('PGDMP'))"
)


class DataMigrationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = installer.InstallerTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.base, self.root = self.fixture.base, self.fixture.root
        for name in ('psql', 'pg_restore'):
            (self.fixture.bin / name).write_text(FAKE)
        self.package = self.base / 'package'
        self.package.mkdir()
        self.assets = self.base / 'source/assetstore'
        file = self.assets / '12/34/56/123456789012'
        file.parent.mkdir(parents=True)
        file.write_bytes(b'documento ficticio\n')
        self.solr = self.base / 'source/solr'
        (self.solr / 'statistics/data').mkdir(parents=True)
        (self.solr / 'statistics/data/fictitious.segment').write_bytes(b'fictional Solr statistics')
        self.tables = {name: [] for name in migration.REQUIRED_TABLES}
        self.tables['item'] = [{'uuid': '00000000-0000-0000-0000-000000000001'}]
        self.tables['handle'] = [{'handle': '123456789/1', 'resource_id': self.tables['item'][0]['uuid']}]
        self.tables['resourcepolicy'] = [{'policy_id': 1, 'action_id': 0, 'epersongroup_id': 2}]
        self.tables['metadatavalue'] = [{'text_value': 'Documento fictício', 'place': 0}]
        self.tables['schema_version'] = [dict(installer.release()['database']['migrations'][0], success=True)]
        self.tables['bitstream'] = [{'uuid': '00000000-0000-0000-0000-000000000002',
                                    'internal_id': file.name, 'store_number': 0, 'deleted': False,
                                    'size_bytes': file.stat().st_size, 'checksum_algorithm': 'MD5',
                                    'checksum': hashlib.md5(file.read_bytes()).hexdigest()}]
        self.report()
        self.dump()
        self.archive()
        self.hashes()

    def report(self):
        report = {'schema_version': 1, 'tables': {}, 'verified_files': 1,
                  'assetstore': migration.tree_fingerprint(self.assets),
                  'solr': migration.tree_fingerprint(self.solr)}
        for name, rows in self.tables.items():
            digest = hashlib.sha256()
            for row in sorted(rows, key=lambda r: json.dumps(r, sort_keys=True)):
                digest.update((json.dumps(row) + '\n').encode())
            report['tables'][name] = {'count': len(rows), 'sha256': digest.hexdigest()}
        (self.package / 'source-report.json').write_text(json.dumps(report))

    def dump(self):
        (self.package / 'database.dump').write_text('PGDMP' + json.dumps(
            {'rows': self.tables['schema_version'], 'tables': self.tables}))

    def archive(self):
        for name, source in (('assetstore', self.assets), ('solr', self.solr)):
            with tarfile.open(self.package / f'{name}.tar.gz', 'w:gz') as archive:
                archive.add(source, arcname=name)
        (self.package / 'release.json').write_text(json.dumps(installer.release()))

    def hashes(self):
        (self.package / 'checksums.json').write_text(json.dumps({name: migration.checksum(self.package / name)
            for name in migration.PACKAGE_FILES}))

    def cli(self, command='migrate-data', *extra, success=True):
        return self.fixture.cli(command, '--manifest', self.fixture.target,
                                '--config', self.fixture.config, '--data-package', self.package,
                                *extra, success=success)

    def test_import_then_install_preserves_rows_files_and_skips_applied_migrations(self):
        self.cli()
        self.assertEqual(self.fixture.state()['tables'], self.tables)
        self.assertEqual(migration.tree_fingerprint(self.root / 'data/solr'),
                         migration.tree_fingerprint(self.solr))
        self.assertFalse((self.root / 'installed.json').exists())
        self.assertTrue((self.root / 'data-import.json').exists())
        self.fixture.cli('verify-data', '--expected', self.package / 'source-report.json')
        self.fixture.install()
        self.assertFalse(any('migrate' in args for _, args in self.fixture.calls()))
        self.assertTrue((self.root / 'installed.json').exists())

    def test_optional_install_imports_before_start(self):
        self.cli('install')
        calls = self.fixture.calls()
        restore = next(i for i, (name, args) in enumerate(calls) if name == 'pg_restore' and '--dbname' in args)
        start = next(i for i, (_, args) in enumerate(calls) if 'up' in args)
        self.assertLess(restore, start)
        self.assertFalse(any('migrate' in args for _, args in calls))

    def test_pending_migration_runs_only_after_verification(self):
        self.fixture.next_release(migrations=2)
        self.cli('install', '--authorize-migrations')
        calls = self.fixture.calls()
        self.assertEqual(sum('migrate' in args for _, args in calls), 1)
        self.assertTrue((self.root / 'data-import.json').exists())

    def test_nonempty_refused_without_mutation(self):
        (self.base / 'fake-state.json').write_text(json.dumps({'rows': [], 'extra_objects': 1, 'running': False}))
        self.cli(success=False)
        self.assertFalse(any('--dbname' in args or 'stop' in args for _, args in self.fixture.calls()))

    def test_nonempty_refused_even_with_restore_authorization(self):
        (self.base / 'fake-state.json').write_text(json.dumps({'rows': [], 'extra_objects': 1, 'running': False}))
        self.cli('migrate-data', '--authorize-restore', success=False)
        self.assertFalse(any('--dbname' in args or 'stop' in args for _, args in self.fixture.calls()))

    def test_restore_failure_preserves_journal_and_no_install_marker(self):
        self.fixture.fail('restore')
        self.cli('install', success=False)
        journal = json.loads((self.root / 'operation.json').read_text())
        self.assertEqual(journal['status'], 'failed')
        self.assertNotIn('SECRET', json.dumps(journal))
        self.assertFalse((self.root / 'installed.json').exists())
        self.assertFalse(any('up' in args for _, args in self.fixture.calls()))
        self.fixture.cli('install', '--manifest', self.fixture.target, success=False)

    def test_corrupt_live_bitstream_blocks_completion(self):
        (self.assets / '12/34/56/123456789012').write_bytes(b'corrupt document!\n')
        self.archive(); self.hashes()
        self.cli('install', success=False)
        self.assertEqual(json.loads((self.root / 'data-verification.json').read_text())['status'], 'failed')
        self.assertTrue((self.root / 'operation.json').exists())
        self.assertFalse((self.root / 'data-import.json').exists())
        self.assertFalse(any('up' in args for _, args in self.fixture.calls()))

    def test_identity_policy_metadata_and_flyway_divergence_block_completion(self):
        for table in ('item', 'handle', 'resourcepolicy', 'metadatavalue', 'schema_version'):
            with self.subTest(table=table):
                old = self.tables[table]
                self.tables[table] = []
                self.dump(); self.hashes()
                self.cli(success=False)
                self.assertFalse((self.root / 'data-import.json').exists())
                (self.root / 'operation.json').unlink()
                (self.base / 'fake-state.json').unlink()
                self.tables[table] = old

    def test_corrupt_package_rejected_before_restore(self):
        with (self.package / 'database.dump').open('ab') as stream:
            stream.write(b'corrupt')
        self.cli(success=False)
        self.assertFalse(any('--dbname' in args for _, args in self.fixture.calls()))

    def test_corrupt_solr_rejected_before_restore_even_with_updated_archive_checksum(self):
        (self.solr / 'statistics/data/fictitious.segment').write_bytes(b'corrupted statistics')
        self.archive(); self.hashes()
        self.cli(success=False)
        self.assertFalse(any('--dbname' in args for _, args in self.fixture.calls()))

    def test_export_failure_never_publishes_incomplete_package_or_restarts_application(self):
        self.cli()
        self.fixture.fail('dump')
        output = self.base / 'exported-package'
        self.fixture.cli('export-data', '--output', output, success=False)
        self.assertFalse(output.exists())
        self.assertFalse(self.fixture.state()['running'])

    def test_export_refuses_existing_output_before_stopping_application(self):
        self.cli()
        before = len(self.fixture.calls())
        self.fixture.cli('export-data', '--output', self.package, success=False)
        self.assertFalse(any('stop' in args for _, args in self.fixture.calls()[before:]))

    def test_unsafe_tar_members_rejected(self):
        for path, kind in (('assetstore/../../outside', tarfile.REGTYPE),
                           ('/tmp/assetstore', tarfile.REGTYPE),
                           ('assetstore/link', tarfile.SYMTYPE)):
            with self.subTest(path=path):
                with tarfile.open(self.package / 'assetstore.tar.gz', 'w:gz') as archive:
                    member = tarfile.TarInfo(path)
                    member.type = kind
                    member.linkname = '/tmp'
                    archive.addfile(member)
                self.hashes()
                self.cli(success=False)
                self.assertFalse(any('--dbname' in args for _, args in self.fixture.calls()))
                (self.root / 'operation.json').unlink()

    def test_no_tls_or_other_connections_refused(self):
        for failure in ('tls', 'connections'):
            self.fixture.fail(failure)
            self.cli(success=False)
            self.assertFalse(any('--dbname' in args for _, args in self.fixture.calls()))

    def test_connection_appearing_during_staging_aborts_before_mutation(self):
        self.fixture.fail('late-connections')
        self.cli(success=False)
        self.assertFalse(any('--dbname' in args for _, args in self.fixture.calls()))
        self.assertEqual(json.loads((self.root / 'operation.json').read_text())['status'], 'failed')

    def test_registered_deleted_multistore_and_path_safety(self):
        row = self.tables['bitstream'][0].copy()
        row['deleted'] = True
        self.assertFalse(migration.check_file(self.assets, row))
        row['deleted'] = False
        row['internal_id'] = '-R12/34/56/123456789012'
        self.assertTrue(migration.check_file(self.assets, row))
        for key, value in (('internal_id', '-R../../outside'), ('internal_id', '-R/tmp/outside'),
                           ('store_number', 1), ('checksum_algorithm', 'unknown')):
            invalid = row | {key: value}
            with self.assertRaises(migration.Error):
                migration.check_file(self.assets, invalid)

    def test_existing_project_or_assetstore_is_never_changed(self):
        (self.base / 'fake-state.json').write_text(json.dumps({'rows': [], 'running': True}))
        self.cli(success=False)
        self.assertTrue(self.fixture.state()['running'])
        self.assertFalse(any('stop' in args for _, args in self.fixture.calls()))
        (self.base / 'fake-state.json').write_text(json.dumps({'rows': [], 'running': False}))
        retained = self.root / 'data/assetstore/retained'
        retained.write_bytes(b'fictitious retained data')
        self.cli(success=False)
        self.assertEqual(retained.read_bytes(), b'fictitious retained data')

    def test_initial_health_failure_keeps_installation_stopped(self):
        self.fixture.fail('health')
        self.cli('install', success=False)
        self.assertFalse(self.fixture.state()['running'])
        self.assertTrue((self.root / 'operation.json').exists())
        self.assertFalse((self.root / 'installed.json').exists())

    def test_duplicate_flyway_history_is_rejected(self):
        self.tables['schema_version'] *= 2
        self.dump(); self.hashes()
        result = self.cli(success=False)
        self.assertIn('duplicada', result.stderr)
        self.assertFalse((self.root / 'data-import.json').exists())

    def test_large_multiline_metadata_survives_csv_verification(self):
        self.tables['metadatavalue'][0]['text_value'] = 'texto, "fictício"\n' * 12000
        self.report(); self.dump(); self.hashes()
        self.cli()
        self.assertEqual(self.fixture.state()['tables'], self.tables)

    def test_supported_checksums_size_and_missing_files(self):
        row = self.tables['bitstream'][0]
        path = self.assets / '12/34/56/123456789012'
        for label, algorithm in (('MD5', 'md5'), ('SHA-1', 'sha1'), ('SHA-256', 'sha256')):
            checked = row | {'checksum_algorithm': label,
                             'checksum': hashlib.new(algorithm, path.read_bytes()).hexdigest()}
            self.assertTrue(migration.check_file(self.assets, checked))
        with self.assertRaises(migration.Error):
            migration.check_file(self.assets, row | {'size_bytes': 1})
        path.unlink()
        with self.assertRaises(migration.Error):
            migration.check_file(self.assets, row)


if __name__ == '__main__':
    unittest.main()

"""Run entirely against fake executables; never connect to Docker/PostgreSQL."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest import mock

MODULE = Path(__file__).resolve().parents[1] / 'pcirn.py'
spec = importlib.util.spec_from_file_location('pcirn', MODULE)
pcirn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pcirn)

FAKE = r'''#!/usr/bin/env python3
import json, os, pathlib, sys
root = pathlib.Path(os.environ['PCIRN_TEST'])
state_file = root / 'fake-state.json'
state = json.loads(state_file.read_text()) if state_file.exists() else {'rows': [], 'running': False}
args = sys.argv[1:]
if args[:2] == ['--context', 'default']: args = args[2:]
name = pathlib.Path(sys.argv[0]).name
with (root / 'calls.jsonl').open('a') as log:
    log.write(json.dumps([name, args]) + '\n')
db_name = os.environ.get('PGDATABASE', os.environ.get('DB_URL', '').split('/')[-1].split('?')[0])
db = state if db_name in ('', 'pcirn') else state.setdefault('databases', {}).setdefault(db_name, {'rows': []})
failure = (root / 'fail').read_text() if (root / 'fail').exists() else ''
def save(): state_file.write_text(json.dumps(state))
def fail(key):
    if failure == key:
        print('SECRET-should-not-leak', file=sys.stderr)
        sys.exit(7)
if '--version' in args and name != 'docker': print('PostgreSQL 17.1'); sys.exit()
if name == 'docker':
    if args == ['info']: fail('docker'); sys.exit()
    if args[:2] == ['compose', 'version']: print('2.24.0'); sys.exit()
    if 'pull' in args: fail('pull')
    if 'stop' in args: state['running'] = False; save()
    if 'up' in args:
        fail('health')
        state['running'] = True
        state['images'] = dict(zip(('dspace', 'dspacesolr', 'dspace-angular'), (os.environ.get(k, '') for k in ('DSPACE_IMAGE', 'SOLR_IMAGE', 'ANGULAR_IMAGE'))))
        save()
    if 'run' in args:
        state['migration_called'] = True; save()
        fail('migrate')
        db['rows'] = json.loads((root / 'wanted.json').read_text())
        if (root / 'image-rows.json').exists():
            db['rows'] = json.loads((root / 'image-rows.json').read_text())[os.environ['DSPACE_IMAGE']]
        save()
    if args[:1] == ['inspect']: print(state['images'][args[-1]])
    if 'ps' in args:
        if '-q' in args: print('dspace\ndspacesolr\ndspace-angular' if state['running'] else '')
        elif 'json' in args:
            print(json.dumps([{'Service': s, 'State': 'running' if state['running'] else 'exited',
                               'Health': 'healthy' if state['running'] else ''}
                              for s in ('dspace', 'dspacesolr', 'dspace-angular')]))
        else: print('fake dedicated project')
elif name == 'psql':
    if '-f' in args:
        fail('restore')
        path = pathlib.Path(args[-1])
        if path.name == 'probe.sql': db['probe'] = 'documento-ficticio-001'
        else: db.update(json.loads(path.read_text()))
        state['restored'] = True; save(); sys.exit()
    fail('db')
    query = args[args.index('-c') + 1]
    if 'UPDATE public.pcirn_homolog_probe' in query:
        db['probe'] = 'apos-backup' if 'apos-backup' in query else 'apos-update'
        if 'CREATE TABLE' in query: db['later'] = True
        save()
    elif 'SELECT marker' in query: print(db.get('probe', ''))
    elif 'pcirn_homolog_later' in query: print('f' if db.get('later') else 't')
    elif 'server_version_num' in query: print('170000')
    elif 'to_regclass' in query: print('t' if db['rows'] else 'f')
    elif 'user_object_count' in query:
        print('10' if db['rows'] else str(db.get('extra_objects', 0)))
    elif 'information_schema.tables' in query: print('10' if db['rows'] else '0')
    elif 'json_agg' in query: print(json.dumps(db['rows']))
    else: print('1')
elif name == 'pg_dump':
    if '--version' in args: print('pg_dump (PostgreSQL) 17.1'); sys.exit()
    fail('dump'); pathlib.Path(args[args.index('--file') + 1]).write_text(json.dumps({'rows': db['rows'], 'probe': db.get('probe'), 'later': db.get('later', False)}))
elif name == 'pg_restore':
    if '--list' in args:
        fail('verify'); print('; Dumped from database version: 17.1\n; Dumped by pg_dump version: 17.1')
    elif '--file' in args:
        pathlib.Path(args[args.index('--file') + 1]).write_text(pathlib.Path(args[-1]).read_text())
    else:
        fail('restore'); db.update(json.loads(pathlib.Path(args[-1]).read_text())); save()
'''


def release(version='1.0.0', migrations=1):
    return {'schema_version': 1, 'version': version,
            'images': {k: 'ghcr.io/nti/' + k + '@sha256:' + str(migrations) * 64
                       for k in pcirn.IMAGE_KEYS},
            'database': {'migrations': [{'version': str(n), 'script': f'V{n}__test.sql',
                                        'checksum': n} for n in range(1, migrations + 1)]}}


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='pcirn-test-')
        self.base = Path(self.temp.name)
        self.root = self.base / 'deployment'
        self.bin = self.base / 'bin'
        self.bin.mkdir()
        for name in ('docker', 'psql', 'pg_dump', 'pg_restore'):
            executable = self.bin / name
            executable.write_text(FAKE)
            executable.chmod(0o755)
        self.config = self.base / 'nti.json'
        self.config.write_text(json.dumps({'DB_URL': 'jdbc:postgresql://nti.invalid:5432/pcirn?sslmode=require',
                                          'DB_USERNAME': 'nti', 'DB_PASSWORD': "p$#'\\word",
                                          'PUBLIC_UI_URL': 'https://repo.invalid',
                                          'PUBLIC_REST_URL': 'https://repo.invalid/server',
                                          'PUBLIC_REST_HOST': 'repo.invalid'}))
        self.config.chmod(0o600)
        self.target = self.base / 'manifest.json'
        self.target.write_text(json.dumps(release()))
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ['PATH'],
                        PCIRN_TEST=str(self.base))
        self.want(release())

    def tearDown(self):
        self.temp.cleanup()

    def want(self, data):
        rows = [dict(m, success=True) for m in data['database']['migrations']]
        (self.base / 'wanted.json').write_text(json.dumps(rows))

    def state(self):
        return json.loads((self.base / 'fake-state.json').read_text())

    def calls(self):
        return [json.loads(line) for line in (self.base / 'calls.jsonl').read_text().splitlines()]

    def cli(self, command, *args, success=True):
        process = subprocess.run(['python3', str(MODULE), command, '--root', str(self.root), *map(str, args)],
                                 env=self.env, text=True, capture_output=True)
        if success:
            self.assertEqual(process.returncode, 0, process.stderr + process.stdout)
        else:
            self.assertNotEqual(process.returncode, 0, process.stdout)
        self.assertNotIn('SECRET-should-not-leak', process.stderr)
        return process

    def install(self):
        return self.cli('install', '--config', self.config, '--manifest', self.target,
                        '--authorize-migrations')

    def next_release(self, migrations=1):
        data = release('1.1.0', migrations)
        self.target.write_text(json.dumps(data))
        self.want(data)

    def fail(self, key):
        (self.base / 'fail').write_text(key)

    def backup_path(self):
        return sorted((self.root / 'backups').glob('backup-*'))[-1]

    def test_install_idempotent_and_configuration_preserved(self):
        self.install()
        local = self.root / 'dspace/config/local.cfg'
        local.write_text('custom = preserved\n')
        before = len(self.calls())
        self.install()
        operations = self.calls()[before:]
        self.assertFalse(any('migrate' in a or 'stop' in a or (n == 'pg_dump' and '--file' in a) for n, a in operations))
        self.assertEqual(local.read_text(), 'custom = preserved\n')
        self.assertEqual((self.root / 'config.json').stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.cli('version').stdout.strip(), '1.0.0')

    def test_config_mismatch_does_not_overwrite(self):
        self.install()
        before = (self.root / 'config.json').read_bytes()
        data = json.loads(self.config.read_text()); data['DB_PASSWORD'] = 'changed'
        self.config.write_text(json.dumps(data))
        self.cli('install', '--config', self.config, '--manifest', self.target, success=False)
        self.assertEqual(before, (self.root / 'config.json').read_bytes())

    def test_authorization_required_before_any_mutation(self):
        result = self.cli('install', '--config', self.config, '--manifest', self.target, success=False)
        self.assertIn('--authorize-migrations', result.stderr)
        self.assertFalse(any('migrate' in a or 'stop' in a for _, a in self.calls()))

    def test_update_backup_precedes_migration(self):
        self.install(); self.next_release(2)
        before = len(self.calls())
        self.cli('update', '--manifest', self.target, '--authorize-migrations')
        calls = self.calls()[before:]
        dump = next(i for i, (n, _) in enumerate(calls) if n == 'pg_dump' and '--file' in calls[i][1])
        migration = next(i for i, (_, a) in enumerate(calls) if 'migrate' in a)
        self.assertLess(dump, migration)
        self.assertEqual(self.cli('version').stdout.strip(), '1.1.0')

    def test_update_same_schema_skips_migrate(self):
        self.install(); self.next_release()
        before = len(self.calls())
        self.cli('update', '--manifest', self.target)
        self.assertFalse(any('migrate' in a for _, a in self.calls()[before:]))

    def test_failed_dump_aborts_update_and_recovers(self):
        self.install(); self.next_release(2); self.fail('dump')
        before = len(self.calls())
        self.cli('update', '--manifest', self.target, '--authorize-migrations', success=False)
        self.assertFalse(any('migrate' in a for _, a in self.calls()[before:]))
        self.assertEqual(self.cli('version').stdout.strip(), '1.0.0')
        self.assertTrue(self.state()['running'])
        self.assertFalse((self.root / 'operation.json').exists())

    def test_failed_pull_leaves_stack_running(self):
        self.install(); self.next_release(); self.fail('pull')
        self.cli('update', '--manifest', self.target, success=False)
        self.assertTrue(self.state()['running'])
        self.assertFalse((self.root / 'operation.json').exists())

    def test_failed_migration_stays_stopped_with_recovery_journal(self):
        self.install(); self.next_release(2); self.fail('migrate')
        self.cli('update', '--manifest', self.target, '--authorize-migrations', success=False)
        self.assertFalse(self.state()['running'])
        journal = json.loads((self.root / 'operation.json').read_text())
        self.assertTrue(journal['migration_started'])
        self.assertTrue(Path(journal['backup']).is_dir())
        self.cli('update', '--manifest', self.target, '--authorize-migrations', success=False)
        self.cli('rollback', success=False)

    def test_failed_health_preserves_old_release_and_journal(self):
        self.install(); self.next_release(); self.fail('health')
        self.cli('update', '--manifest', self.target, success=False)
        self.assertEqual(self.cli('version').stdout.strip(), '1.0.0')
        self.assertTrue((self.root / 'operation.json').exists())

    def test_restore_and_rollback_require_explicit_authorization(self):
        self.install(); self.next_release()
        self.cli('update', '--manifest', self.target)
        self.cli('rollback', success=False)
        self.cli('rollback', '--authorize-restore')
        self.assertEqual(self.cli('version').stdout.strip(), '1.0.0')
        self.assertTrue(self.state()['restored'])

    def test_corrupt_backup_rejected_before_stop(self):
        self.install(); self.cli('backup')
        backup = self.backup_path()
        (backup / 'database.dump').write_text('corrupt')
        before = len(self.calls())
        self.cli('restore', '--backup', backup, '--authorize-restore', success=False)
        self.assertFalse(any('stop' in a for _, a in self.calls()[before:]))

    def test_restore_failure_stays_stopped(self):
        self.install(); self.cli('backup'); self.fail('restore')
        self.cli('restore', '--backup', self.backup_path(), '--authorize-restore', success=False)
        self.assertFalse(self.state()['running'])
        self.assertTrue((self.root / 'operation.json').exists())

    def test_digest_validation(self):
        data = release(); data['images']['backend'] = 'ghcr.io/nti/backend:latest'
        self.target.write_text(json.dumps(data))
        self.cli('install', '--config', self.config, '--manifest', self.target, success=False)
        self.assertFalse((self.base / 'calls.jsonl').exists())

    def test_config_permissions_and_tls_validation(self):
        self.config.chmod(0o644)
        with self.assertRaises(pcirn.Error): pcirn.configuration(self.config)
        self.config.chmod(0o600)
        data = json.loads(self.config.read_text()); data['DB_URL'] += '&unsupported=yes'
        self.config.write_text(json.dumps(data))
        with self.assertRaises(pcirn.Error): pcirn.configuration(self.config)

    def test_health_doctor_status_logs_and_db_failure(self):
        self.install()
        for command in ('health', 'doctor', 'status', 'logs'): self.cli(command)
        self.fail('db')
        self.cli('doctor', success=False)
        self.cli('health', success=False)

    def test_archive_path_traversal_rejected(self):
        self.install(); self.cli('backup'); backup = self.backup_path()
        with tarfile.open(backup / 'assetstore.tar.gz', 'w:gz') as archive:
            item = tarfile.TarInfo('assetstore/../../outside'); item.size = 0
            archive.addfile(item)
        hashes = json.loads((backup / 'checksums.json').read_text())
        hashes['assetstore.tar.gz'] = pcirn.checksum(backup / 'assetstore.tar.gz')
        (backup / 'checksums.json').write_text(json.dumps(hashes))
        self.cli('restore', '--backup', backup, '--authorize-restore', success=False)

    def test_interrupted_restore_can_be_retried_after_first_rename(self):
        self.install(); self.cli('backup'); backup = self.backup_path()
        original = Path.rename
        def interrupted(path, target):
            if path.name == 'assetstore' and path.parent.name.startswith('.restore-'):
                raise KeyboardInterrupt
            return original(path, target)
        with mock.patch.dict(os.environ, self.env), mock.patch.object(Path, 'rename', interrupted):
            dep = pcirn.Deployment(self.root)
            with self.assertRaises(KeyboardInterrupt): dep.restore(backup, True)
        self.assertFalse((self.root / 'data/assetstore').exists())
        self.cli('restore', '--backup', backup, '--authorize-restore')
        self.assertTrue((self.root / 'data/assetstore').is_dir())
        self.assertTrue(self.state()['running'])

    def test_update_metadata_write_failure_recovers_release_record(self):
        self.install(); self.next_release()
        original = pcirn.write_json
        def failed(path, value):
            if Path(path).name == 'installed.json' and value['version'] == '1.1.0': raise OSError('simulated disk failure')
            original(path, value)
        with mock.patch.dict(os.environ, self.env), mock.patch.object(pcirn, 'write_json', failed):
            dep = pcirn.Deployment(self.root)
            with self.assertRaisesRegex(OSError, 'simulated disk failure'): dep.deploy(pcirn.manifest(self.target), False)
        self.assertEqual(pcirn.read_json(self.root / 'release.json')['version'], '1.0.0')
        self.assertEqual(self.cli('version').stdout.strip(), '1.0.0')
        self.assertTrue(self.state()['running'])

    def test_backup_directory_failure_restarts_stack(self):
        self.install()
        with mock.patch.dict(os.environ, self.env), mock.patch.object(pcirn.tempfile, 'mkdtemp', side_effect=OSError('disk full')):
            with self.assertRaises(OSError): pcirn.Deployment(self.root).backup(release())
        self.assertTrue(self.state()['running'])

    def test_predictable_temporary_symlink_does_not_overwrite_external_file(self):
        external = self.base / 'external'; external.write_text('keep')
        target = self.base / 'release.json'
        target.with_suffix('.tmp').symlink_to(external)
        pcirn.write_json(target, release())
        self.assertEqual(external.read_text(), 'keep')

    def test_existing_executable_symlink_rejected_before_any_operation(self):
        self.install()
        executable = self.root / 'bin/dspacepcirn'
        executable.unlink(); executable.symlink_to(self.base / 'outside')
        self.cli('install', '--manifest', self.target, success=False)

    def test_divergent_history_rejected_even_with_authorization(self):
        self.install(); self.next_release(2)
        data = self.state(); data['rows'][0]['checksum'] = 999
        (self.base / 'fake-state.json').write_text(json.dumps(data))
        before = len(self.calls())
        self.cli('update', '--manifest', self.target, '--authorize-migrations', success=False)
        self.assertFalse(any('stop' in a or 'migrate' in a for _, a in self.calls()[before:]))

    def test_backup_restart_failure_has_recoverable_journal(self):
        self.install(); self.fail('health')
        self.cli('backup', success=False)
        self.assertTrue((self.root / 'operation.json').exists())
        (self.base / 'fail').unlink()
        self.cli('rollback')
        self.assertFalse((self.root / 'operation.json').exists())
        self.assertTrue(self.state()['running'])

    def test_installed_cli_and_empty_envfile_with_literal_credentials(self):
        self.install()
        command = self.root / 'bin/dspacepcirn'
        result = subprocess.run([str(command), 'version', '--root', str(self.root)], env=self.env,
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), '1.0.0')
        with mock.patch.dict(os.environ, self.env):
            dep = pcirn.Deployment(self.root)
            def inspect(args, **kwargs):
                envfile = Path(args[args.index('--env-file') + 1])
                self.assertEqual(envfile.read_text(), '')
                self.assertEqual(dep.env['DB_PASSWORD'], json.loads(self.config.read_text())['DB_PASSWORD'])
                self.assertEqual(dep.env['DSPACE_IMAGE'], release()['images']['backend'])
                return ''
            dep.run = inspect
            dep.env['DSPACE_IMAGE'] = 'untrusted:latest'
            dep.compose(release(), 'config', '--quiet')

    def test_empty_database_with_extra_objects_blocks_migrations(self):
        (self.base / 'fake-state.json').write_text(json.dumps({'rows': [], 'running': False, 'extra_objects': 1}))
        self.cli('install', '--config', self.config, '--manifest', self.target,
                 '--authorize-migrations', success=False)
        self.assertFalse(any('migrate' in a or 'pull' in a for _, a in self.calls()))

    def test_readonly_tool_timeout_kills_child(self):
        process = mock.Mock()
        process.communicate.side_effect = [subprocess.TimeoutExpired('docker', 30), ('', '')]
        with mock.patch.dict(os.environ, self.env), mock.patch.object(pcirn.subprocess, 'Popen', return_value=process):
            dep = pcirn.Deployment(self.root, config=pcirn.configuration(self.config))
            with self.assertRaisesRegex(pcirn.Error, 'tempo limite'):
                dep.run(['docker', 'info'], timeout=30)
        process.kill.assert_called_once()

    def test_concurrent_operation_rejected(self):
        self.install()
        with (self.root / '.lock').open('a') as lock:
            pcirn.fcntl.flock(lock, pcirn.fcntl.LOCK_EX)
            result = self.cli('backup', success=False)
            self.assertIn('Outra operação', result.stderr)


if __name__ == '__main__':
    unittest.main()

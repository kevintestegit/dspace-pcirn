"""Wizard safety and recovery using fictitious data and fake process boundaries."""
from contextlib import ExitStack, redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pcirn
import preflight
import wizard
import data_migration
import test_data_migration as migration_tests


class WizardTests(unittest.TestCase):
    def setUp(self):
        self.fixture = migration_tests.DataMigrationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fx = self.fixture.fixture
        self.root = self.fixture.root
        self.args = SimpleNamespace(root=self.root, manifest=self.fx.target,
                                    config=self.fx.config, data_package=self.fixture.package)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.dict(os.environ, self.fx.env))
        self.host = self.stack.enter_context(mock.patch.object(preflight, 'check'))
        self.db = self.stack.enter_context(mock.patch.object(preflight, 'database'))
        self.output = io.StringIO()
        self.stack.enter_context(redirect_stdout(self.output))
        os.umask(0o077)

    def run_wizard(self):
        return wizard.install(self.args)

    def test_external_end_to_end_and_repeat_never_reimports(self):
        self.run_wizard()
        calls = self.fx.calls()
        restore = next(i for i, (n, a) in enumerate(calls) if n == 'pg_restore' and '--dbname' in a)
        up = next(i for i, (_, a) in enumerate(calls) if 'up' in a)
        self.assertLess(restore, up)
        self.assertFalse(any('migrate' in a for _, a in calls))
        self.assertEqual(self.fx.state()['tables'], self.fixture.tables)
        report = pcirn.read_json(self.root / 'report.json')
        self.assertEqual(report['postgresql'], 'external')
        self.assertEqual(len(report['steps']), 7)
        self.assertNotIn('DB_PASSWORD', json.dumps(report))
        self.assertNotIn('NTI', self.output.getvalue())
        before = len(calls)
        self.run_wizard()
        self.assertFalse(any('--dbname' in a or 'up' in a for _, a in self.fx.calls()[before:]))
        for name in ('wizard.json', 'config.json', 'report.json', 'wizard-config.json'):
            self.assertEqual((self.root / name).stat().st_mode & 0o777, 0o600)
        self.assertNotIn(pcirn.configuration(self.fx.config)['DB_PASSWORD'], self.output.getvalue())

    def configure_docker(self, root):
        config = pcirn.read_json(self.fx.config)
        config.update(PG_MODE='docker', PG_IMAGE='postgres@sha256:' + '1' * 64,
                      DB_URL='jdbc:postgresql://127.0.0.1:55432/pcirn?sslmode=verify-ca&sslrootcert=' +
                      str(root / 'postgres-tls/server.crt'))
        pcirn.write_json(self.fx.config, config)

    def fake_provision(self, dep):
        tls = dep.root / 'postgres-tls'
        tls.mkdir(exist_ok=True)
        (tls / 'server.crt').write_text('fake certificate')
        state = self.fx.base / 'fake-state.json'
        if not state.exists():
            state.write_text(json.dumps({'rows': [], 'running': False, 'postgres_running': True}))
        docker = self.fx.bin / 'docker'
        script = docker.read_text()
        script = script.replace(
            "if '-q' in args: print('dspace\\ndspacesolr\\ndspace-angular' if state['running'] else '')",
            "if '-q' in args: print('dspace\\ndspacesolr\\ndspace-angular' if state['running'] else ('postgres' if state.get('postgres_running') and 'dspace' not in args else ''))")
        docker.write_text(script)

    def test_docker_end_to_end_uses_same_data_import_and_validation(self):
        self.configure_docker(self.root)
        with mock.patch.object(wizard, 'provision_postgres', side_effect=self.fake_provision) as pg:
            self.run_wizard()
        pg.assert_called_once()
        self.assertEqual(pcirn.read_json(self.root / 'report.json')['postgresql'], 'docker')
        self.assertEqual(self.fx.state()['tables'], self.fixture.tables)
        self.assertFalse(any('migrate' in a for _, a in self.fx.calls()))
        calls = self.fx.calls()
        restore = next(i for i, (n, a) in enumerate(calls) if n == 'pg_restore' and '--dbname' in a)
        up = next(i for i, (_, a) in enumerate(calls) if 'up' in a)
        self.assertLess(restore, up)
        for _, args in calls:
            if 'stop' in args:
                self.assertEqual(args[-3:], list(pcirn.SERVICES))

    def test_docker_failure_at_each_stage_and_resume(self):
        for index, name in enumerate(('diagnostic', 'postgres', 'import_data', 'institutional',
                                      'installation', 'services', 'report')):
            with self.subTest(stage=index + 1):
                self.args.root = self.root.with_name('docker-stage-' + str(index))
                self.configure_docker(self.args.root)
                (self.fx.base / 'fake-state.json').unlink(missing_ok=True)
                with mock.patch.object(wizard, 'provision_postgres', side_effect=self.fake_provision):
                    with mock.patch.object(wizard.Wizard, name, side_effect=pcirn.Error('falha fictícia')):
                        with self.assertRaises(pcirn.Error): self.run_wizard()
                    self.assertEqual(pcirn.read_json(self.args.root / 'wizard.json')['completed'], list(range(index)))
                    self.run_wizard()
                    self.assertEqual(pcirn.read_json(self.args.root / 'wizard.json')['completed'], list(range(7)))

    def test_failure_at_every_stage_preserves_checkpoint_and_resumes(self):
        actions = ('diagnostic', 'postgres', 'import_data', 'institutional',
                   'installation', 'services', 'report')
        # Use separate fake deployments so each failure starts with an empty destination.
        for index, name in enumerate(actions):
            with self.subTest(stage=index + 1):
                self.args.root = self.root.with_name('stage-' + str(index))
                (self.fx.base / 'fake-state.json').unlink(missing_ok=True)
                with mock.patch.object(wizard.Wizard, name, side_effect=pcirn.Error('falha fictícia')):
                    with self.assertRaises(pcirn.Error):
                        self.run_wizard()
                state = pcirn.read_json(self.args.root / 'wizard.json')
                self.assertEqual(state['completed'], list(range(index)))
                self.run_wizard()
                self.assertEqual(pcirn.read_json(self.args.root / 'wizard.json')['completed'], list(range(7)))

    def test_restore_failure_blocks_resume_and_backend(self):
        self.fx.fail('restore')
        with self.assertRaises(pcirn.Error): self.run_wizard()
        calls = self.fx.calls()
        self.assertFalse(any('up' in a for _, a in calls))
        before = len(calls)
        (self.fx.base / 'fail').unlink()
        with self.assertRaisesRegex(pcirn.Error, 'sem reimportação'): self.run_wizard()
        self.assertEqual(self.fx.calls()[before:], [])
        self.assertTrue((self.root / 'operation.json').exists())

    def test_external_connection_error_allows_corrected_config_before_provisioning(self):
        self.db.side_effect = pcirn.Error('conexão fictícia recusada')
        with self.assertRaises(pcirn.Error): self.run_wizard()
        self.assertFalse((self.root / 'config.json').exists())
        config = pcirn.read_json(self.fx.config)
        config['DB_PASSWORD'] = 'corrected-password'
        pcirn.write_json(self.fx.config, config)
        self.db.side_effect = None
        self.run_wizard()
        self.assertEqual(pcirn.configuration(self.root / 'config.json')['DB_PASSWORD'], 'corrected-password')

    def test_pull_failure_resumes_after_import_without_second_restore(self):
        self.fx.fail('pull')
        with self.assertRaises(pcirn.Error): self.run_wizard()
        self.assertTrue((self.root / 'data-import.json').exists())
        before = len(self.fx.calls())
        (self.fx.base / 'fail').unlink()
        self.run_wizard()
        self.assertFalse(any('--dbname' in a for _, a in self.fx.calls()[before:]))

    def test_verify_failure_after_import_never_starts_or_reimports(self):
        original = data_migration.verify_data
        def failed(dep, *args, **kwargs):
            if 'assetstore' not in kwargs:
                raise pcirn.Error('validação fictícia falhou')
            return original(dep, *args, **kwargs)
        with mock.patch.object(data_migration, 'verify_data', side_effect=failed):
            with self.assertRaises(pcirn.Error): self.run_wizard()
        self.assertTrue((self.root / 'data-import.json').exists())
        self.assertFalse(any('up' in a for _, a in self.fx.calls()))
        before = len(self.fx.calls())
        self.run_wizard()
        self.assertFalse(any('--dbname' in a for _, a in self.fx.calls()[before:]))

    def test_nonempty_external_database_rejected(self):
        (self.fx.base / 'fake-state.json').write_text(json.dumps({'rows': [], 'running': False, 'extra_objects': 1}))
        with self.assertRaisesRegex(pcirn.Error, 'não vazio'): self.run_wizard()
        self.assertFalse(any('up' in a or '--dbname' in a for _, a in self.fx.calls()))

    def test_corrupt_package_does_not_restore_or_start_backend(self):
        (self.fixture.package / 'database.dump').write_bytes(b'corrupt')
        with self.assertRaisesRegex(pcirn.Error, 'checksum'): self.run_wizard()
        self.assertFalse(any('up' in a or '--dbname' in a for _, a in self.fx.calls()))

    def test_changed_manifest_is_rejected_on_resume(self):
        with mock.patch.object(wizard.Wizard, 'import_data', side_effect=pcirn.Error('stop')):
            with self.assertRaises(pcirn.Error): self.run_wizard()
        self.fx.next_release()
        with self.assertRaisesRegex(pcirn.Error, 'Manifesto alterado'): self.run_wizard()

    def test_pending_migrations_are_never_authorized_by_wizard(self):
        with mock.patch.object(wizard.Wizard, 'installation', side_effect=pcirn.Error('stop')):
            with self.assertRaises(pcirn.Error): self.run_wizard()
        with mock.patch.object(pcirn.Deployment, 'pending', return_value=True):
            with self.assertRaises(pcirn.Error): self.run_wizard()
        self.assertFalse(any('migrate' in a or 'up' in a for _, a in self.fx.calls()))

    def test_symlink_and_insecure_directory_rejected(self):
        self.root.mkdir(mode=0o755)
        self.root.chmod(0o755)
        with self.assertRaises(pcirn.Error): self.run_wizard()
        self.root.chmod(0o700)
        (self.root / 'wizard.json').symlink_to(self.fx.config)
        with self.assertRaises(pcirn.Error): self.run_wizard()

    def test_interactive_correction_retries_failed_stage(self):
        self.args.config = None
        self.stack.enter_context(mock.patch.object(wizard.os, 'isatty', return_value=True))
        self.stack.enter_context(mock.patch.object(wizard.os, 'geteuid', return_value=0))
        with mock.patch.object(wizard.Wizard, 'diagnostic', side_effect=[pcirn.Error('falha'), None]) as diagnostic, \
                mock.patch.object(wizard, 'ask', return_value='1'), \
                ExitStack() as patches:
            for method in ('postgres', 'import_data', 'institutional', 'installation', 'services', 'report'):
                patches.enter_context(mock.patch.object(wizard.Wizard, method))
            self.run_wizard()
        self.assertEqual(diagnostic.call_count, 2)

    def test_menu_routes_existing_administration_commands(self):
        with mock.patch.object(wizard.os, 'isatty', return_value=True), \
                mock.patch.object(wizard.os, 'geteuid', return_value=0), \
                mock.patch.object(wizard, 'ask', side_effect=['6', '/new/package', '7', '0']), \
                mock.patch.object(pcirn, 'main') as main:
            wizard.menu(self.args)
        self.assertEqual(main.call_args_list[0].args[0], ['export-data', '--root', str(self.root), '--output', '/new/package'])
        self.assertEqual(main.call_args_list[1].args[0], ['verify-data', '--root', str(self.root)])


class DockerPostgresTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.root.chmod(0o700)
        self.config = {'PG_MODE': 'docker', 'PG_IMAGE': 'postgres@sha256:' + '1' * 64,
                       'DB_USERNAME': 'dspace', 'DB_PASSWORD': "secret'\\password", 'DB_URL':
                       'jdbc:postgresql://127.0.0.1:55432/dspace?sslmode=verify-ca&sslrootcert=' +
                       str(self.root / 'postgres-tls/server.crt')}
        self.dep = mock.Mock(root=self.root, config=self.config,
                             env={'PGPORT': '55432', 'PGDATABASE': 'dspace'})
        self.dep.run.side_effect = self.tool_run
        self.calls = []
        self.volumes, self.containers = [], []
        self.name = 'dspacepcirn-pg-' + wizard.hashlib.sha256(str(self.root).encode()).hexdigest()[:12]
        self.patch = mock.patch.object(wizard.os, 'chown')
        self.patch.start()
        self.addCleanup(self.patch.stop)
        os.umask(0o077)

    def tool_run(self, args, **kwargs):
        self.calls.append((args, kwargs))
        if args[:3] == ['docker', 'context', 'inspect']: return json.dumps('unix:///var/run/docker.sock')
        if args[:3] == ['docker', 'volume', 'ls']: return '\n'.join(self.volumes)
        if args[:3] == ['docker', 'ps', '-a']: return '\n'.join(self.containers)
        if args[:3] == ['docker', 'volume', 'create']:
            self.volumes.append(self.name)
        if args[:3] == ['docker', 'volume', 'inspect']:
            return json.dumps({'org.dspacepcirn.root': str(self.root),
                               'org.dspacepcirn.install': pcirn.read_json(self.root / 'postgres.json')['token']})
        if args[:2] == ['docker', 'run']:
            return 'postgres (PostgreSQL) 17.1' if '--version' in args else '999'
        if '--version' in args: return 'PostgreSQL 17.1'
        if args[0] == 'openssl':
            (self.root / 'postgres-tls/server.crt').write_text('fake certificate')
            (self.root / 'postgres-tls/server.key').write_text('fake key')
        if args[:2] == ['docker', 'exec']: self.containers.append(self.name)
        return ''

    def test_docker_tls_scram_loopback_persistence_and_no_secret_in_argv(self):
        wizard.provision_postgres(self.dep)
        document = pcirn.read_json(self.root / 'postgres-compose.json')
        pg = document['services']['postgres']
        self.assertEqual(pg['ports'][0]['host_ip'], '127.0.0.1')
        self.assertTrue(document['volumes']['postgres_data']['external'])
        self.assertIn('ssl=on', pg['command'])
        self.assertIn('127.0.0.1', pg['healthcheck']['test'])
        self.assertIn('password_encryption=scram-sha-256', pg['command'])
        self.assertNotIn(self.config['DB_PASSWORD'], json.dumps(document))
        self.assertNotIn(self.config['DB_PASSWORD'], json.dumps([c[0] for c in self.calls]))
        self.assertIn('NOSUPERUSER', next(c[1]['input_text'] for c in self.calls if 'input_text' in c[1]))
        self.assertEqual((self.root / 'postgres-password').stat().st_mode & 0o777, 0o600)
        before = len(self.calls)
        wizard.provision_postgres(self.dep)
        self.assertFalse(any('create' in args or 'exec' in args for args, _ in self.calls[before:]))
        self.assertTrue(all('postgres' in c.args for c in self.dep.compose.call_args_list))

    def test_existing_volume_or_container_is_never_adopted(self):
        for target in (self.volumes, self.containers):
            with self.subTest(resource=target):
                target.append(self.name)
                with self.assertRaisesRegex(pcirn.Error, 'existente'): wizard.provision_postgres(self.dep)
                target.clear()
        self.assertFalse(any('create' in args or 'exec' in args for args, _ in self.calls))

    def test_failure_during_creation_blocks_automatic_retry(self):
        self.dep.compose.side_effect = pcirn.Error('falha fictícia')
        with self.assertRaises(pcirn.Error): wizard.provision_postgres(self.dep)
        before = len(self.calls)
        with self.assertRaisesRegex(pcirn.Error, 'interrompida'): wizard.provision_postgres(self.dep)
        self.assertFalse(any('create' in args or 'exec' in args for args, _ in self.calls[before:]))

    def test_volume_creation_race_never_uses_foreign_resource(self):
        original = self.dep.run.side_effect
        self.dep.run.side_effect = lambda args, **kw: '{}' if args[:3] == ['docker', 'volume', 'inspect'] else original(args, **kw)
        with self.assertRaisesRegex(pcirn.Error, 'preexistente'): wizard.provision_postgres(self.dep)
        self.dep.compose.assert_not_called()

    def test_remote_daemon_rejected_before_mutation(self):
        self.dep.run.side_effect = lambda args, **kw: json.dumps('ssh://remote.invalid')
        with self.assertRaisesRegex(pcirn.Error, 'Unix local'): wizard.provision_postgres(self.dep)
        self.dep.compose.assert_not_called()
        self.assertFalse((self.root / 'postgres.json').exists())

    def test_foreign_volume_label_rejected(self):
        wizard.provision_postgres(self.dep)
        original = self.dep.run.side_effect
        self.dep.run.side_effect = lambda args, **kw: '{}' if args[:3] == ['docker', 'volume', 'inspect'] else original(args, **kw)
        with self.assertRaisesRegex(pcirn.Error, 'outra instalação'): wizard.provision_postgres(self.dep)

    def test_missing_volume_is_not_recreated(self):
        wizard.provision_postgres(self.dep)
        self.volumes.clear()
        with self.assertRaisesRegex(pcirn.Error, 'nada recriado'): wizard.provision_postgres(self.dep)

    def test_unsafe_database_configuration_rejected(self):
        for key, value in (('PG_IMAGE', 'postgres:latest'), ('DB_USERNAME', 'postgres'),
                           ('DB_URL', self.config['DB_URL'].replace('127.0.0.1', 'remote.invalid'))):
            with self.subTest(key=key), self.assertRaises(pcirn.Error):
                wizard.validate_docker_config(self.config | {key: value}, self.root)

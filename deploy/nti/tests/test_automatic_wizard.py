"""Automatic choices and fresh initialization failure boundaries without real services."""
from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pcirn
import wizard
import manager_update
import preflight


class AutomaticWizardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)
        self.args = SimpleNamespace(root=self.root, config=None, manifest=None, data_package=None)
        os.umask(0o077)
        self.wiz = wizard.Wizard(self.args)
        self.release = {'version': '1.0.0', 'database': {'fresh_bootstrap': 'pcirn-fresh-v1',
                                                      'fresh_migrations': [{'version': '1'}]}}

    def test_new_mode_requires_no_package(self):
        with mock.patch.object(wizard, 'ask', return_value='1'), \
                mock.patch.object(self.wiz, 'release', return_value=self.release), \
                mock.patch.object(self.wiz, 'validate_bootstrap'):
            self.wiz.import_data()
        self.assertEqual(self.wiz.inputs['installation_mode'], 'new')
        self.assertNotIn('package', self.wiz.inputs)

    def test_unsupported_new_choice_does_not_trap_resume_in_that_mode(self):
        with mock.patch.object(wizard, 'ask', return_value='1'), \
                mock.patch.object(self.wiz, 'release', return_value={'database': {}}), \
                mock.patch.object(self.wiz, 'validate_bootstrap', side_effect=pcirn.Error('unsupported')):
            with self.assertRaises(pcirn.Error): self.wiz.import_data()
        self.assertNotIn('installation_mode', self.wiz.inputs)

    def test_rc4_blocks_fresh_before_pull_or_database_changes(self):
        self.wiz.dep = mock.Mock()
        with mock.patch.object(wizard, 'Deployment', return_value=self.wiz.dep), \
                mock.patch.object(self.wiz, 'release', return_value={'database': {}}):
            with self.assertRaisesRegex(pcirn.Error, 'não oferece instalação nova'):
                self.wiz.validate_bootstrap()
        self.wiz.dep.compose.assert_not_called()
        self.wiz.dep.sql.assert_not_called()

    def fresh(self, authorized=True):
        dep = mock.Mock()
        dep.user_objects.return_value = 0
        dep.pending.side_effect = [True, False]
        self.wiz.inputs['config'] = {'DB_PROFILE': 'fresh'}
        self.wiz.dep = dep
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(self.wiz, 'validate_bootstrap').start()
        mock.patch.object(self.wiz, 'release', return_value=self.release).start()
        mock.patch.object(self.wiz, 'confirm', return_value=authorized).start()
        return dep

    def test_fresh_requires_explicit_authorization(self):
        dep = self.fresh(False)
        with self.assertRaisesRegex(pcirn.Error, 'não autorizada'):
            self.wiz.new_installation()
        dep.compose.assert_not_called()
        dep.up.assert_not_called()
        self.assertFalse((self.root / 'operation.json').exists())

    def test_fresh_rejects_nonempty_database(self):
        dep = self.fresh()
        dep.user_objects.return_value = 1
        with self.assertRaisesRegex(pcirn.Error, 'não vazio'):
            self.wiz.new_installation()
        dep.compose.assert_not_called()

    def test_health_failure_resumes_without_repeating_migrations(self):
        dep = self.fresh()
        dep.up.side_effect = pcirn.Error('health failure')
        with self.assertRaises(pcirn.Error):
            self.wiz.new_installation()
        self.assertEqual(pcirn.read_json(self.root / 'operation.json')['stage'], 'migrated')
        first = dep.compose.call_count
        dep.up.side_effect = None
        dep.pending.side_effect = None
        dep.pending.return_value = False
        self.wiz.new_installation()
        self.assertEqual(dep.compose.call_count, first)
        self.assertTrue((self.root / 'installed.json').exists())

    def test_unknown_journal_never_runs_migrations(self):
        dep = self.fresh()
        pcirn.write_json(self.root / 'operation.json', {'kind': 'restore'})
        with self.assertRaisesRegex(pcirn.Error, 'diverge'):
            self.wiz.new_installation()
        dep.compose.assert_not_called()

    def test_partial_migration_rechecks_authorization_and_history(self):
        dep = self.fresh()
        dep.compose.side_effect = [None, pcirn.Error('interrupted')]
        with self.assertRaises(pcirn.Error):
            self.wiz.new_installation()
        self.assertEqual(pcirn.read_json(self.root / 'operation.json')['stage'], 'migrating')
        self.wiz.confirm.return_value = False
        dep.pending.side_effect = None
        dep.pending.return_value = True
        before = dep.compose.call_count
        with self.assertRaisesRegex(pcirn.Error, 'não autorizada'):
            self.wiz.new_installation()
        self.assertEqual(dep.compose.call_count, before)

    def test_topology_avoids_docker_subnet_overlap(self):
        def run(args, **kwargs):
            return 'n' if 'ls' in args else json.dumps([{'IPAM': {'Config': [{'Subnet': '10.250.50.0/24'}]}}])
        result = preflight.select_resources(run, self.root)
        self.assertEqual(result['DSPACE_NETWORK_SUBNET'], '10.250.51.0/24')
        self.assertEqual(result['TRUSTED_PROXY_NETWORK'], '10.250.51')

    def test_completed_fresh_resumes_after_checkpoint_interruption(self):
        dep = self.fresh()
        pcirn.write_json(self.root / 'installed.json', {'version': self.release['version']})
        dep.pending.side_effect = None
        dep.pending.return_value = False
        self.wiz.new_installation()
        dep.healthy.assert_called_once()
        dep.user_objects.assert_not_called()
        dep.compose.assert_not_called()

    def test_occupied_ports_require_pinned_owned_running_containers(self):
        release = {'images': {'backend': 'backend@digest', 'frontend': 'frontend@digest'}}
        pcirn.write_json(self.root / 'operation.json', {'kind': 'fresh-install', 'target': release})
        project = 'dspacepcirn-' + hashlib.sha256(str(self.root).encode()).hexdigest()[:12]
        rows = [{'Config': {'Image': 'backend@digest', 'Labels': {
            'com.docker.compose.project': project, 'com.docker.compose.service': 'dspace'}},
            'State': {'Running': True}, 'NetworkSettings': {'Ports': {
                '8080/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '8501'}]}}}]
        dep = mock.Mock(root=self.root)
        dep.run.side_effect = lambda args, **kwargs: 'owned' if 'ps' in args else json.dumps(rows)
        with mock.patch.object(preflight, 'ports_available', side_effect=lambda ports: ports == (4000,)):
            self.assertTrue(preflight.owns_application_ports(dep, release, (8501, 4000)))
            rows[0]['Config']['Image'] = 'foreign@digest'
            self.assertFalse(preflight.owns_application_ports(dep, release, (8501, 4000)))

    def test_streamed_logs_redact_database_credentials(self):
        dep = pcirn.Deployment.__new__(pcirn.Deployment)
        dep.env = dict(os.environ)
        dep.config = {'DB_PASSWORD': 'fictitious-private-token'}
        output = io.StringIO()
        with redirect_stdout(output):
            dep.run([sys.executable, '-c', "import sys; print('fictitious-private-token'); "
                     "print('fictitious-private-token', file=sys.stderr)"], capture=False)
        self.assertNotIn('fictitious-private-token', output.getvalue())
        self.assertEqual(output.getvalue().count('[credencial omitida]'), 2)

    def test_private_root_refuses_foreign_owner(self):
        metadata = self.root.stat()
        foreign = SimpleNamespace(st_uid=123456, st_mode=metadata.st_mode)
        with mock.patch.object(Path, 'stat', return_value=foreign):
            with self.assertRaises(pcirn.Error): pcirn.secure_ancestors(self.root)


class ManagerUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.library = self.root / 'lib/dspacepcirn'
        self.library.mkdir(parents=True)
        (self.library / 'pcirn.py').write_text('old = True\n')

    def package(self, bad=None):
        path = self.root / 'manager.tar.gz'
        with tarfile.open(path, 'w:gz') as archive:
            for name in manager_update.FILES:
                data = b'new = True\n'
                member = tarfile.TarInfo(name if bad is None or name != 'pcirn.py' else bad)
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
        return path, pcirn.checksum(path)

    def test_code_update_preserves_old_library(self):
        package, digest = self.package()
        manager_update.update(package, digest, self.library)
        self.assertEqual((self.library / 'pcirn.py').read_text(), 'new = True\n')
        previous = list((self.root / 'lib').glob('dspacepcirn.previous-*'))
        self.assertEqual((previous[0] / 'pcirn.py').read_text(), 'old = True\n')

    def test_checksum_and_traversal_fail_without_replacement(self):
        package, digest = self.package('../escape')
        with self.assertRaises(pcirn.Error): manager_update.update(package, digest, self.library)
        with self.assertRaises(pcirn.Error): manager_update.update(package, '0' * 64, self.library)
        self.assertEqual((self.library / 'pcirn.py').read_text(), 'old = True\n')
        self.assertFalse((self.root / 'escape').exists())

    def test_interruption_after_atomic_exchange_keeps_active_manager(self):
        package, digest = self.package()
        with mock.patch.object(Path, 'rename', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                manager_update.update(package, digest, self.library)
        self.assertEqual((self.library / 'pcirn.py').read_text(), 'new = True\n')
        retained = list((self.root / 'lib').glob('.dspacepcirn-update-*'))
        self.assertEqual((retained[0] / 'pcirn.py').read_text(), 'old = True\n')

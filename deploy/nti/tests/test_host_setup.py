"""Host preparation boundaries: never use the host package manager or daemon."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import host_setup as host
REAL_RESOURCES = host.resources


class HostSetupTests(unittest.TestCase):
    def setUp(self):
        self.info = {'distribution': 'ubuntu', 'version': '24.04', 'codename': 'noble',
                     'architecture': 'arm64'}
        self.commands = []
        self.compose = '2.24.0'
        self.active = self.enabled = True
        self.major = 16
        self.tools = {'docker', 'python3', 'openssl', 'gpg', 'psql', 'pg_dump', 'pg_restore'}
        self.run = mock.Mock(side_effect=self.command)
        self.confirm = mock.Mock(return_value=True)
        self.patches = [mock.patch.object(host, 'detect', return_value=self.info.copy()),
                        mock.patch.object(host, 'resources', return_value={'ports': {}}),
                        mock.patch.object(host, 'network'),
                        mock.patch.object(host.os, 'geteuid', return_value=0),
                        mock.patch.object(host.shutil, 'which', side_effect=lambda tool:
                                          '/usr/bin/' + tool if tool in self.tools else None),
                        mock.patch.dict(host.os.environ, {}, clear=True)]
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in reversed(self.patches):
            patch.stop()

    def command(self, args, **kwargs):
        self.commands.append(args)
        if args[:3] == ['docker', 'compose', 'version']:
            if self.compose is None:
                raise host.Error('absent')
            return self.compose
        if args[0] in ('psql', 'pg_dump', 'pg_restore'):
            return f'{args[0]} (PostgreSQL) {self.major}.2'
        if args[:2] == ['systemctl', 'is-active']:
            return 'active' if self.active else 'inactive'
        if args[:2] == ['systemctl', 'is-enabled']:
            return 'enabled' if self.enabled else 'disabled'
        if args[:3] == ['docker', 'context', 'inspect']:
            return json.dumps('unix:///var/run/docker.sock')
        if args[:2] == ['docker', 'info']:
            return json.dumps({'OSType': 'linux', 'Architecture': 'aarch64'})
        if args[0] == 'dpkg-query':
            raise host.Error('not installed')
        if args[0] == 'apt-get' and 'install' in args:
            mappings = {'gnupg': ['gpg'], 'docker-ce': ['docker'],
                        'python3': ['python3'], 'openssl': ['openssl']}
            for package, tools in mappings.items():
                if package in args:
                    self.tools.update(tools)
            if any('compose' in package for package in args):
                self.compose = '2.24.0'
            for package in args:
                if package.startswith('postgresql-client-'):
                    self.major = int(package.rsplit('-', 1)[1])
                    self.tools.update(('psql', 'pg_dump', 'pg_restore'))
        return 'valid'

    def test_insufficient_cpu_memory_disk_fail_before_install(self):
        memory = 'MemTotal: 8388608 kB\nMemAvailable: 4194304 kB\n'
        with mock.patch.object(host.Path, 'read_text', return_value=memory), \
                mock.patch.object(host.os, 'cpu_count', return_value=1):
            with self.assertRaisesRegex(host.Error, 'CPUs'):
                REAL_RESOURCES('/tmp')
        with mock.patch.object(host.Path, 'read_text', return_value=
                               'MemTotal: 1024 kB\nMemAvailable: 1024 kB\n'), \
                mock.patch.object(host.os, 'cpu_count', return_value=2):
            with self.assertRaisesRegex(host.Error, 'RAM'):
                REAL_RESOURCES('/tmp')
        with mock.patch.object(host.Path, 'read_text', return_value=memory), \
                mock.patch.object(host.os, 'cpu_count', return_value=2), \
                mock.patch.object(host.shutil, 'disk_usage', return_value=mock.Mock(free=1024)):
            with self.assertRaisesRegex(host.Error, 'disco'):
                REAL_RESOURCES('/tmp')
        self.assertFalse(self.commands)

    def test_remote_endpoint_blocked_before_changes(self):
        original = self.command
        self.active = False
        self.run.side_effect = lambda args, **kwargs: (json.dumps('tcp://remote:2375')
            if args[:3] == ['docker', 'context', 'inspect'] else original(args, **kwargs))
        with self.assertRaisesRegex(host.Error, 'Unix local'):
            host.prepare(self.run, self.confirm)
        self.confirm.assert_not_called()
        self.assertFalse(any(c[0] == 'apt-get' or c[:2] == ['systemctl', 'start']
                             for c in self.commands))

    def test_complete_existing_host_changes_nothing(self):
        result = host.prepare(self.run, self.confirm)
        self.assertEqual(result['architecture'], 'arm64')
        self.confirm.assert_not_called()
        self.assertFalse(any(c[0] == 'apt-get' or c[:2] in
                             (['systemctl', 'start'], ['systemctl', 'enable']) for c in self.commands))

    def test_missing_dependencies_one_confirmation_no_server_package(self):
        self.tools.clear()
        with mock.patch.object(host, 'repository') as repo:
            host.prepare(self.run, self.confirm)
        self.confirm.assert_called_once()
        self.assertEqual(repo.call_args.args[:2], (self.run, 'docker'))
        self.assertEqual(repo.call_args.args[2]['architecture'], 'arm64')
        installs = [c for c in self.commands if c[0] == 'apt-get' and 'install' in c]
        self.assertTrue(installs)
        self.assertTrue(any('postgresql-client-16' in c for c in installs))
        self.assertFalse(any('postgresql' in c or 'postgresql-16' in c for c in installs))
        self.assertTrue(all('--no-remove' in c for c in installs))

    def test_declining_causes_no_changes(self):
        self.tools.remove('openssl')
        self.confirm.return_value = False
        with self.assertRaisesRegex(host.Error, 'cancelada'):
            host.prepare(self.run, self.confirm)
        self.assertFalse(any(c[0] == 'apt-get' for c in self.commands))

    def test_docker_service_only_changes_when_needed(self):
        self.active = False
        host.prepare(self.run, self.confirm)
        self.assertIn(['systemctl', 'start', 'docker'], self.commands)
        self.assertNotIn(['systemctl', 'enable', 'docker'], self.commands)
        self.confirm.assert_called_once()

    def test_external_major_uses_clients_only(self):
        with mock.patch.object(host, 'repository') as repo:
            host.ensure_clients(self.run, self.confirm, 15)
        repo.assert_called_once_with(self.run, 'postgresql', self.info)
        self.assertTrue(any('postgresql-client-15' in c for c in self.commands))
        self.assertFalse(any('postgresql-15' in c for c in self.commands))

    def test_unsupported_host_and_major_fail_before_mutation(self):
        with mock.patch.object(host, 'detect', return_value=dict(self.info, version='22.04')):
            with self.assertRaisesRegex(host.Error, '24.04'):
                host.prepare(self.run, self.confirm)
        with self.assertRaisesRegex(host.Error, '13 a 17'):
            host.ensure_clients(self.run, self.confirm, 18)
        self.assertFalse(self.commands)

    def test_network_failure_precedes_confirmation_and_mutation(self):
        with mock.patch.object(host, 'network', side_effect=host.Error('rede')):
            with self.assertRaisesRegex(host.Error, 'rede'):
                host.prepare(self.run, self.confirm)
        self.confirm.assert_not_called()
        self.assertFalse(self.commands)

    def test_compose_binary_package_ownership_checked(self):
        binary = '/usr/libexec/docker/cli-plugins/docker-compose'
        def run(args, **kwargs):
            if args[1] == '-S':
                return 'docker-compose-v2: ' + binary
            return 'install ok installed'
        with mock.patch.object(host.Path, 'exists', return_value=False), \
                mock.patch.object(host.Path, 'is_file', lambda path: str(path) == binary):
            self.assertEqual(host.tracked_compose(run), 'docker-compose-v2')

    def test_custom_binary_shadowing_package_refused(self):
        binary = str(Path.home() / '.docker/cli-plugins/docker-compose')
        def run(args, **kwargs):
            return '' if args[1] == '-S' else 'install ok installed'
        with mock.patch.object(host.Path, 'exists', return_value=False), \
                mock.patch.object(host.Path, 'is_file', lambda path: str(path) == binary):
            with self.assertRaisesRegex(host.Error, 'personalizado'):
                host.tracked_compose(run)

    def test_old_official_compose_upgrade_only_target_package(self):
        for package in ('docker-compose-v2', 'docker-compose-plugin'):
            with self.subTest(package=package):
                self.compose = '2.19.1'
                self.commands.clear()
                self.confirm.reset_mock()
                with mock.patch.object(host, 'tracked_compose', return_value=package), \
                        mock.patch.object(host, 'repository'):
                    host.prepare(self.run, self.confirm)
                self.confirm.assert_called_once()
                installs = [c for c in self.commands if c[0] == 'apt-get' and 'install' in c]
                upgrade = [c for c in installs if '--no-upgrade' not in c]
                self.assertEqual(len(upgrade), 1)
                self.assertEqual(upgrade[0][-1], package)
                self.assertIn('--no-remove', upgrade[0])
                self.assertFalse(any('upgrade' in c for c in self.commands))
                self.assertEqual(self.compose, '2.24.0')

    def test_old_compose_upgrade_cancelled_without_changes(self):
        self.compose = '2.19.1'
        self.confirm.return_value = False
        with mock.patch.object(host, 'tracked_compose', return_value='docker-compose-v2'):
            with self.assertRaisesRegex(host.Error, 'cancelada'):
                host.prepare(self.run, self.confirm)
        self.assertFalse(any(c[0] == 'apt-get' for c in self.commands))

    def test_old_custom_compose_blocked_without_overwriting(self):
        self.compose = '2.19.1'
        with mock.patch.object(host.Path, 'is_file', return_value=False):
            with self.assertRaisesRegex(host.Error, 'personalizado'):
                host.prepare(self.run, self.confirm)
        self.confirm.assert_not_called()
        self.assertFalse(any(c[0] == 'apt-get' for c in self.commands))

    def test_bootstrap_confirmation_carried_to_python(self):
        self.tools.remove('openssl')
        with mock.patch.dict(host.os.environ, {'DSPACEPCIRN_BOOTSTRAP_APPROVED': '1'}):
            host.prepare(self.run, self.confirm)
        self.confirm.assert_not_called()

    def test_conflicting_docker_package_never_removed(self):
        self.tools.remove('docker')
        original = self.command
        self.run.side_effect = lambda args, **kwargs: ('install ok installed'
            if args[0] == 'dpkg-query' and args[-1] == 'containerd' else original(args, **kwargs))
        with self.assertRaisesRegex(host.Error, 'conflitante'):
            host.prepare(self.run, self.confirm)
        self.assertFalse(any(c[0] == 'apt-get' for c in self.commands))

    def test_existing_official_repository_reused(self):
        run = mock.Mock(return_value='500 https://download.docker.com/linux/ubuntu noble/stable')
        with mock.patch.object(host, 'urlopen') as download, \
                mock.patch.object(host, 'write_repository_file') as write:
            host.repository(run, 'docker', self.info)
        download.assert_not_called()
        write.assert_not_called()

    def test_repository_key_fingerprint_required(self):
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = b'-----BEGIN PGP PUBLIC KEY BLOCK-----\n'
        with mock.patch.object(host, 'urlopen', return_value=response), \
                mock.patch.object(host, 'write_repository_file') as write:
            with self.assertRaisesRegex(host.Error, 'Identidade'):
                host.repository(self.run, 'docker', self.info)
        write.assert_not_called()

    def test_repository_file_not_overwritten_or_symlinked(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'repo'
            host.write_repository_file(path, b'original', 0o644)
            host.write_repository_file(path, b'original', 0o644)
            with self.assertRaisesRegex(host.Error, 'diverge'):
                host.write_repository_file(path, b'changed', 0o644)
            link = Path(directory) / 'link'
            link.symlink_to(path)
            with self.assertRaisesRegex(host.Error, 'link'):
                host.write_repository_file(link, b'original', 0o644)
            self.assertEqual(path.read_bytes(), b'original')

    def test_repository_exact_source_and_signing_key(self):
        response = mock.MagicMock()
        key = b'-----BEGIN PGP PUBLIC KEY BLOCK-----\n'
        response.__enter__.return_value.read.return_value = key
        with mock.patch.object(host, 'urlopen', return_value=response), \
                mock.patch.object(host, 'write_repository_file') as write:
            run = mock.Mock(side_effect=lambda args, **kwargs: '' if args[0] == 'apt-cache' else
                            'pub::::::::::\nfpr:::::::::' + host.DOCKER_FINGERPRINT + ':')
            host.repository(run, 'docker', self.info)
        self.assertEqual(write.call_count, 2)
        source = write.call_args_list[1].args[1].decode()
        self.assertIn('Architectures: arm64', source)
        self.assertIn('Signed-By: /etc/apt/keyrings/dspacepcirn-docker.asc', source)
        self.assertIn('Suites: noble', source)


if __name__ == '__main__':
    unittest.main()

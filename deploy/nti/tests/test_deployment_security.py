"""Regression checks using fake Docker/PostgreSQL executables only."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest import mock

import test_installer as simulated


class DeploymentSecurityTests(unittest.TestCase):
    def setUp(self):
        self.fixture = simulated.InstallerTests(methodName='runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)

    def certificates(self):
        paths = []
        for name in ('root $CA.pem', 'client.crt', 'client.key'):
            path = self.fixture.base / name
            path.write_text('fictional TLS material')
            path.chmod(0o600)
            paths.append(path)
        data = json.loads(self.fixture.config.read_text())
        from urllib.parse import urlencode
        data['DB_URL'] = 'jdbc:postgresql://nti.invalid:5432/pcirn?' + urlencode(dict(
            sslmode='verify-full', sslrootcert=str(paths[0]),
            sslcert=str(paths[1]), sslkey=str(paths[2])))
        self.fixture.config.write_text(json.dumps(data))
        return paths

    def require_tls_mounts(self, paths):
        executable = self.fixture.bin / 'docker'
        script = executable.read_text()
        script = script.replace("if name == 'docker':", """if name == 'docker':
    if '-f' in args:
        files = [args[i + 1] for i, arg in enumerate(args) if arg == '-f']
        if len(files) != 2: sys.exit(8)
        mounts = json.loads(pathlib.Path(files[-1]).read_text())['services']['dspace']['volumes']
        expected = json.loads(os.environ['PCIRN_REQUIRED_TLS'])
        for mount in mounts:
            mount['source'] = mount['source'].replace('$$', '$')
            mount['target'] = mount['target'].replace('$$', '$')
        if {m['target'] for m in mounts} != set(expected): sys.exit(8)
        for mount in mounts:
            if (mount['source'] != mount['target'] or not mount['read_only']
                    or mount['bind']['create_host_path']
                    or not pathlib.Path(mount['source']).is_file()): sys.exit(8)
""")
        executable.write_text(script)
        self.fixture.env['PCIRN_REQUIRED_TLS'] = json.dumps(list(map(str, paths)))

    def test_install_and_installed_update_mount_tls_before_migrations(self):
        paths = self.certificates()
        self.require_tls_mounts(paths)
        self.fixture.install()
        self.fixture.next_release(2)
        before = len(self.fixture.calls())
        denied = self.fixture.cli('update', '--manifest', self.fixture.target, success=False)
        self.assertIn('--authorize-migrations', denied.stderr)
        self.assertFalse(any('migrate' in args or 'stop' in args or 'up' in args
                             for _, args in self.fixture.calls()[before:]))
        cli = self.fixture.root / 'bin/dspacepcirn'
        result = subprocess.run([
            str(cli), 'update', '--root', str(self.fixture.root),
            '--manifest', str(self.fixture.target), '--authorize-migrations'
        ], env=self.fixture.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.fixture.state()['images']['dspace'],
                         simulated.release('1.1.0', 2)['images']['backend'])
        self.assertFalse(list(self.fixture.root.glob('.tls-*')))

    def test_missing_tls_file_blocks_before_provisioning_or_external_commands(self):
        paths = self.certificates()
        paths[0].unlink()
        result = self.fixture.cli('install', '--config', self.fixture.config,
                                  '--manifest', self.fixture.target, success=False)
        self.assertIn('certificado PostgreSQL', result.stderr)
        self.assertFalse((self.fixture.root / 'config.json').exists())
        self.assertFalse((self.fixture.base / 'calls.jsonl').exists())

    @unittest.skipUnless(shutil.which('docker'), 'Docker CLI required for Compose rendering only')
    def test_real_compose_renders_read_only_tls_mounts_and_database_url(self):
        paths = self.certificates()
        self.fixture.install()
        config = simulated.pcirn.configuration(self.fixture.config)
        dep = simulated.pcirn.Deployment(self.fixture.root, config=config)
        rendered = json.loads(dep.compose(simulated.release(), 'config', '--format', 'json'))
        backend = rendered['services']['dspace']
        mounts = {mount['target'].replace('$$', '$'): mount for mount in backend['volumes']}
        for path in paths:
            mount = mounts[str(path)]
            self.assertEqual(mount['source'].replace('$$', '$'), str(path))
            self.assertTrue(mount['read_only'])
            self.assertFalse(mount['bind'].get('create_host_path', False))
        self.assertEqual(backend['environment']['db__P__url'], config['DB_URL'])
        self.assertEqual(backend['environment']['db__P__password'].replace('$$', '$'),
                         config['DB_PASSWORD'])

    def test_directory_and_relative_tls_paths_are_rejected(self):
        paths = self.certificates()
        data = json.loads(self.fixture.config.read_text())
        for invalid in (str(self.fixture.base), 'relative-ca.pem'):
            with self.subTest(path=invalid):
                config = dict(data, DB_URL='jdbc:postgresql://nti.invalid/pcirn?'
                              'sslmode=verify-full&sslrootcert=' + invalid)
                with self.assertRaises(simulated.pcirn.Error):
                    simulated.pcirn.pg_environment(config)

    def test_verified_tls_requires_an_explicit_ca_for_host_and_backend(self):
        data = json.loads(self.fixture.config.read_text())
        for mode in ('verify-ca', 'verify-full'):
            with self.subTest(mode=mode):
                config = dict(data, DB_URL='jdbc:postgresql://nti.invalid/pcirn?sslmode=' + mode)
                with self.assertRaisesRegex(simulated.pcirn.Error, 'sslrootcert'):
                    simulated.pcirn.pg_environment(config)

    def test_docker_config_survives_install_and_installed_update(self):
        docker_config = self.fixture.base / 'operator-docker'
        docker_config.mkdir()
        (docker_config / 'config.json').write_text('{"auths": {"ghcr.io": {}}}')
        self.fixture.env['DOCKER_CONFIG'] = str(docker_config)
        executable = self.fixture.bin / 'docker'
        executable.write_text(executable.read_text().replace("if name == 'docker':", """if name == 'docker':
    if os.environ.get('DOCKER_CONFIG') != os.environ['PCIRN_REQUIRED_DOCKER_CONFIG']:
        sys.exit(9)
"""))
        self.fixture.env['PCIRN_REQUIRED_DOCKER_CONFIG'] = str(docker_config)
        self.fixture.install()
        self.fixture.next_release(2)
        cli = self.fixture.root / 'bin/dspacepcirn'
        result = subprocess.run([
            str(cli), 'update', '--root', str(self.fixture.root),
            '--manifest', str(self.fixture.target), '--authorize-migrations'
        ], env=self.fixture.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_docker_config_does_not_enable_remote_or_injected_deployment(self):
        config = simulated.pcirn.configuration(self.fixture.config)
        with mock.patch.dict(os.environ, {'DOCKER_CONFIG': '/operator/docker',
                                         'DOCKER_HOST': 'ssh://remote.invalid',
                                         'DOCKER_CONTEXT': 'remote',
                                         'COMPOSE_FILE': '/untrusted.yml',
                                         'PGPASSWORD': 'untrusted'}):
            dep = simulated.pcirn.Deployment(self.fixture.root, config=config)
        self.assertEqual(dep.env.get('DOCKER_CONFIG'), '/operator/docker')
        for key in ('DOCKER_HOST', 'DOCKER_CONTEXT', 'COMPOSE_FILE'):
            self.assertNotIn(key, dep.env)
        self.assertEqual(dep.env['PGPASSWORD'], config['DB_PASSWORD'])

    def test_tls_override_is_removed_after_command_failure(self):
        paths = self.certificates()
        self.fixture.install()
        config = simulated.pcirn.configuration(self.fixture.config)
        dep = simulated.pcirn.Deployment(self.fixture.root, config=config)
        overrides = []
        def failed(args, **kwargs):
            files = [args[i + 1] for i, arg in enumerate(args) if arg == '-f']
            self.assertEqual(len(files), 2)
            overrides.append(Path(files[-1]))
            self.assertTrue(overrides[-1].is_file())
            raise simulated.pcirn.Error('fictional command failure')
        with mock.patch.object(dep, 'run', side_effect=failed):
            with self.assertRaises(simulated.pcirn.Error):
                dep.compose(simulated.release(), 'config', '--quiet')
        self.assertTrue(overrides)
        self.assertFalse(any(path.exists() for path in overrides))


if __name__ == '__main__':
    unittest.main()

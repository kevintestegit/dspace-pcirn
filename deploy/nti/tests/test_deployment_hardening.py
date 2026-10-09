"""Deployment hardening: TLS material for the backend and registry credentials.

Everything here runs against fake executables. The PostgreSQL certificates are
fictional files; nothing connects to Docker, PostgreSQL or a registry.
"""
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock
from urllib.parse import urlencode

import test_installer as harness

pcirn = harness.pcirn
release = harness.release


class DeploymentTestCase(unittest.TestCase):
    """Shared fixture: a provisionable deployment with fake executables."""

    def setUp(self):
        self.fixture = harness.InstallerTests(methodName='runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)

    def certificates(self):
        paths = []
        for name in ('root $CA.pem', 'client.crt', 'client.key'):
            path = self.fixture.base / name
            path.write_text('fictional TLS material')
            path.chmod(0o600)
            paths.append(path)
        return paths

    def configure(self, **params):
        """Rewrite the deployment configuration with the given JDBC parameters."""
        data = json.loads(self.fixture.config.read_text())
        data['DB_URL'] = 'jdbc:postgresql://nti.invalid:5432/pcirn?' + urlencode(params)
        self.fixture.config.write_text(json.dumps(data))
        self.fixture.config.chmod(0o600)
        return data

    def deployment(self, create_root=True):
        if create_root:
            self.fixture.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        return pcirn.Deployment(self.fixture.root,
                                config=pcirn.configuration(self.fixture.config))

    def captured_compose(self, deployment, *args):
        """Run a Compose command with a fake runner and return what it received."""
        seen = []

        def capture(command, **kwargs):
            files = [command[index + 1] for index, value in enumerate(command) if value == '-f']
            mounts = []
            text = ''
            if len(files) > 1:
                text = Path(files[-1]).read_text()
                mounts = json.loads(text)['services']['dspace']['volumes']
            seen.append({'files': files, 'mounts': mounts, 'override': Path(files[-1]),
                         'text': text})
            return ''

        with mock.patch.object(deployment, 'run', side_effect=capture):
            deployment.compose(release(), *args)
        return seen[-1]


class TlsMaterialTests(DeploymentTestCase):
    def test_verification_requires_an_explicit_root_certificate(self):
        # psql honours sslmode=require without a CA; the backend would silently
        # skip verification too. Both clients are made to verify explicitly.
        for mode in ('verify-ca', 'verify-full'):
            with self.subTest(mode=mode):
                self.configure(sslmode=mode)
                with self.assertRaisesRegex(pcirn.Error, 'sslrootcert'):
                    pcirn.configuration(self.fixture.config)

    def test_certificate_paths_must_be_absolute_readable_files(self):
        ca, _, _ = self.certificates()
        invalid = (str(self.fixture.base), 'root-ca.pem', str(ca) + '.missing')
        for path in invalid:
            with self.subTest(path=path):
                self.configure(sslmode='verify-full', sslrootcert=path)
                with self.assertRaisesRegex(pcirn.Error, 'sslrootcert'):
                    pcirn.configuration(self.fixture.config)

    def test_absolute_readable_certificates_are_accepted_untouched(self):
        ca, cert, key = self.certificates()
        data = self.configure(sslmode='verify-full', sslrootcert=str(ca),
                              sslcert=str(cert), sslkey=str(key))
        config = pcirn.configuration(self.fixture.config)
        self.assertEqual(config['DB_URL'], data['DB_URL'])
        deployment = self.deployment()
        self.assertEqual(deployment.tls_paths, sorted(map(str, (ca, cert, key))))

    def test_compose_mounts_every_certificate_read_only_at_its_own_path(self):
        ca, cert, key = self.certificates()
        self.configure(sslmode='verify-full', sslrootcert=str(ca),
                       sslcert=str(cert), sslkey=str(key))
        deployment = self.deployment()
        result = self.captured_compose(deployment, 'config', '--quiet')
        # Compose turns "$$" back into a literal "$" before mounting.
        mounts = {mount['target'].replace('$$', '$'): mount for mount in result['mounts']}
        self.assertEqual(set(mounts), {str(path) for path in (ca, cert, key)})
        for mount in mounts.values():
            # Host clients and JDBC read the same absolute path.
            self.assertEqual(mount['source'].replace('$$', '$'), mount['target'].replace('$$', '$'))
            self.assertTrue(mount['read_only'])
            self.assertFalse(mount['bind']['create_host_path'])
        # A "$" in a certificate name must survive Compose interpolation.
        self.assertIn('root $$CA.pem', result['text'])
        self.assertFalse(result['override'].exists(), 'override must not outlive the command')

    def test_no_override_is_written_when_only_the_mode_is_set(self):
        self.configure(sslmode='require')
        result = self.captured_compose(self.deployment(), 'config', '--quiet')
        self.assertEqual(len(result['files']), 1)
        self.assertEqual(result['mounts'], [])

    def test_override_is_removed_even_when_the_command_fails(self):
        ca, _, _ = self.certificates()
        self.configure(sslmode='verify-full', sslrootcert=str(ca))
        deployment = self.deployment()
        overrides = []

        def fail(command, **kwargs):
            overrides.append(Path([command[i + 1] for i, v in enumerate(command) if v == '-f'][-1]))
            raise pcirn.Error('fictional command failure')

        with mock.patch.object(deployment, 'run', side_effect=fail):
            with self.assertRaises(pcirn.Error):
                deployment.compose(release(), 'config', '--quiet')
        self.assertTrue(overrides)
        self.assertFalse(any(path.exists() for path in overrides))

    def test_missing_certificate_blocks_before_any_local_change_or_command(self):
        ca, _, _ = self.certificates()
        self.configure(sslmode='verify-full', sslrootcert=str(ca))
        ca.unlink()
        result = self.fixture.cli('install', '--config', self.fixture.config,
                                  '--manifest', self.fixture.target, success=False)
        self.assertIn('sslrootcert', result.stderr)
        self.assertFalse((self.fixture.root / 'config.json').exists())
        self.assertFalse((self.fixture.base / 'calls.jsonl').exists(),
                         'no external command may run before the configuration is valid')

    @unittest.skipUnless(shutil.which('docker'), 'Docker CLI required to render Compose')
    def test_real_compose_renders_the_mounts_and_the_jdbc_url(self):
        ca, cert, key = self.certificates()
        self.configure(sslmode='verify-full', sslrootcert=str(ca),
                       sslcert=str(cert), sslkey=str(key))
        self.fixture.install()
        deployment = self.deployment()
        # Provisioning used the fake CLI; rendering must use the real one.
        deployment.env['PATH'] = os.pathsep.join(
            entry for entry in deployment.env['PATH'].split(os.pathsep)
            if entry != str(self.fixture.bin))
        rendered = json.loads(deployment.compose(release(), 'config', '--format', 'json'))
        backend = rendered['services']['dspace']
        mounts = {mount['target'].replace('$$', '$'): mount for mount in backend['volumes']}
        for path in (ca, cert, key):
            mount = mounts[str(path)]
            self.assertEqual(mount['source'].replace('$$', '$'), str(path))
            self.assertTrue(mount['read_only'])
            self.assertFalse(mount['bind'].get('create_host_path', False))
        # The JDBC driver reads the URL and the mounted paths from the same names.
        # Compose renders a literal "$" as "$$" in its own output.
        self.assertEqual(backend['environment']['db__P__url'], deployment.config['DB_URL'])
        self.assertEqual(backend['environment']['db__P__password'].replace('$$', '$'),
                         deployment.config['DB_PASSWORD'])


class RegistryCredentialTests(DeploymentTestCase):
    def test_explicit_docker_config_is_preserved(self):
        with mock.patch.dict(os.environ, {'DOCKER_CONFIG': '/operator/docker'}):
            deployment = self.deployment()
        self.assertEqual(deployment.env['DOCKER_CONFIG'], '/operator/docker')

    def test_sudo_uses_the_invoking_users_login(self):
        with tempfile.TemporaryDirectory(prefix='pcirn-home-') as home:
            credentials = Path(home) / '.docker'
            credentials.mkdir()
            (credentials / 'config.json').write_text('{"auths": {"ghcr.io": {}}}')
            environ = {key: value for key, value in os.environ.items() if key != 'DOCKER_CONFIG'}
            environ['SUDO_USER'] = 'operator'
            account = mock.Mock(pw_dir=home)
            with mock.patch.dict(os.environ, environ, clear=True), \
                    mock.patch.object(pcirn.os, 'geteuid', return_value=0), \
                    mock.patch.object(pcirn.pwd, 'getpwnam', return_value=account) as lookup:
                deployment = self.deployment()
            lookup.assert_called_once_with('operator')
            self.assertEqual(deployment.env['DOCKER_CONFIG'], str(credentials))

    def test_sudo_without_a_login_falls_back_to_the_docker_default(self):
        with tempfile.TemporaryDirectory(prefix='pcirn-home-') as home:
            environ = {key: value for key, value in os.environ.items() if key != 'DOCKER_CONFIG'}
            environ['SUDO_USER'] = 'operator'
            with mock.patch.dict(os.environ, environ, clear=True), \
                    mock.patch.object(pcirn.os, 'geteuid', return_value=0), \
                    mock.patch.object(pcirn.pwd, 'getpwnam', return_value=mock.Mock(pw_dir=home)):
                deployment = self.deployment()
        self.assertNotIn('DOCKER_CONFIG', deployment.env)

    def test_root_shell_is_left_to_the_docker_default(self):
        environ = {key: value for key, value in os.environ.items() if key != 'DOCKER_CONFIG'}
        with mock.patch.dict(os.environ, environ, clear=True), \
                mock.patch.object(pcirn.os, 'geteuid', return_value=0):
            deployment = self.deployment()
        self.assertNotIn('DOCKER_CONFIG', deployment.env)

    def test_credentials_do_not_reopen_remote_or_injected_deployment(self):
        injected = {'DOCKER_CONFIG': '/operator/docker', 'DOCKER_HOST': 'ssh://remote.invalid',
                    'DOCKER_CONTEXT': 'remote', 'COMPOSE_FILE': '/untrusted.yml',
                    'COMPOSE_PROJECT_NAME': 'other', 'PGPASSWORD': 'untrusted'}
        with mock.patch.dict(os.environ, injected):
            deployment = self.deployment()
        self.assertEqual(deployment.env['DOCKER_CONFIG'], '/operator/docker')
        for key in ('DOCKER_HOST', 'DOCKER_CONTEXT', 'COMPOSE_FILE', 'COMPOSE_PROJECT_NAME'):
            self.assertNotIn(key, deployment.env)
        self.assertEqual(deployment.env['PGPASSWORD'], deployment.config['DB_PASSWORD'])


if __name__ == '__main__':
    unittest.main()

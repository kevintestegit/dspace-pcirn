"""No network, daemon or database: preflight boundary tests."""
import importlib.util
import json
from pathlib import Path
import tempfile
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location('preflight', Path(__file__).parents[1] / 'preflight.py')
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'stack'
        self.dep = mock.Mock()
        self.dep.root = self.root
        self.dep.config = {'DB_PASSWORD': 'fictional'}
        self.dep.env = {}
        self.info = {'OSType': 'linux', 'Architecture': 'x86_64', 'NCPU': 4,
                     'MemTotal': 8 * 1024 ** 3, 'DockerRootDir': self.temp.name}
        self.release = {'images': {'backend': 'digest-a', 'solr': 'digest-b', 'frontend': 'digest-c'}}
        self.dep.sql.return_value = json.dumps({'ssl': True, 'connect': True, 'create': True,
                                               'schema': True, 'owner': True, 'objects': True,
                                               'server': 170000, 'size': 1000})
        def run(args, **kwargs):
            if args[:3] == ['docker', 'context', 'inspect']: return json.dumps('unix:///var/run/docker.sock')
            if '--version' in args: return 'PostgreSQL 17.1'
            if args[:2] == ['docker', 'info']: return json.dumps(self.info)
            if args[:3] == ['docker', 'manifest', 'inspect']:
                return json.dumps({'Descriptor': {'platform': {'os': 'linux', 'architecture': 'amd64'}}})
            if args[:3] == ['docker', 'network', 'ls']: return ''
            return '2.24.0'
        self.dep.run.side_effect = run
        self.patches = [mock.patch.object(preflight.shutil, 'which', return_value='/bin/tool'),
                        mock.patch.object(preflight, 'ubuntu', return_value=True),
                        mock.patch.object(preflight, 'available_memory', return_value=5 * 1024 ** 3),
                        mock.patch.object(preflight.shutil, 'disk_usage', return_value=mock.Mock(free=50 * 1024 ** 3)),
                        mock.patch.object(preflight, 'ports_available', return_value=True)]
        for patch in self.patches: patch.start()

    def tearDown(self):
        for patch in reversed(self.patches): patch.stop()
        self.temp.cleanup()

    def test_pass_without_creating_installation(self):
        preflight.check(self.dep, self.release)
        self.assertFalse(self.root.exists())
        self.assertFalse(any('pull' in c.args[0] or 'up' in c.args[0] for c in self.dep.run.call_args_list))

    def test_low_memory_blocks(self):
        self.info['MemTotal'] = 2 * 1024 ** 3
        with self.assertRaisesRegex(preflight.Error, 'memória'): preflight.check(self.dep, self.release)

    def test_low_disk_blocks(self):
        preflight.shutil.disk_usage.return_value.free = 100
        with self.assertRaisesRegex(preflight.Error, 'disco'): preflight.check(self.dep, self.release)

    def test_wrong_architecture_blocks(self):
        self.info['Architecture'] = 'aarch64'
        with self.assertRaisesRegex(preflight.Error, 'arquitetura'): preflight.check(self.dep, self.release)

    def test_missing_docker_blocks(self):
        preflight.shutil.which.return_value = None
        with self.assertRaisesRegex(preflight.Error, 'docker'): preflight.check(self.dep, self.release)

    def test_missing_postgres_privileges_blocks(self):
        result = json.loads(self.dep.sql.return_value); result['owner'] = False
        self.dep.sql.return_value = json.dumps(result)
        with self.assertRaisesRegex(preflight.Error, 'permissões'): preflight.check(self.dep, self.release)

    def test_tls_required(self):
        result = json.loads(self.dep.sql.return_value); result['ssl'] = False
        self.dep.sql.return_value = json.dumps(result)
        with self.assertRaisesRegex(preflight.Error, 'TLS'): preflight.check(self.dep, self.release)

    def test_occupied_ports_blocks(self):
        preflight.ports_available.return_value = False
        with self.assertRaisesRegex(preflight.Error, 'portas'): preflight.check(self.dep, self.release)

    def test_overlapping_network_blocks(self):
        original = self.dep.run.side_effect
        def run(args, **kwargs):
            if args[:3] == ['docker', 'network', 'ls']: return 'other-network'
            if args[:3] == ['docker', 'network', 'inspect']:
                return json.dumps([{'Name': 'other', 'IPAM': {'Config': [{'Subnet': '10.250.50.0/24'}]}}])
            return original(args, **kwargs)
        self.dep.run.side_effect = run
        with self.assertRaisesRegex(preflight.Error, 'sobrepõe'): preflight.check(self.dep, self.release)

    def test_filesystem_permissions_block(self):
        with mock.patch.object(preflight.os, 'access', return_value=False):
            with self.assertRaisesRegex(preflight.Error, 'permissões'): preflight.check(self.dep, self.release)

    def test_newer_dump_client_blocks(self):
        data = json.loads(self.dep.sql.return_value); data['server'] = 160000
        self.dep.sql.return_value = json.dumps(data)
        with self.assertRaisesRegex(preflight.Error, 'major'): preflight.check(self.dep, self.release)

    def test_remote_docker_context_blocks(self):
        original = self.dep.run.side_effect
        def run(args, **kwargs):
            if args[:3] == ['docker', 'context', 'inspect']: return json.dumps('ssh://remote.invalid')
            return original(args, **kwargs)
        self.dep.run.side_effect = run
        with self.assertRaisesRegex(preflight.Error, 'local'): preflight.check(self.dep, self.release)

    def test_registry_failure_blocks(self):
        self.dep.run.side_effect = preflight.Error('GHCR indisponível')
        with self.assertRaises(preflight.Error): preflight.check(self.dep, self.release)


if __name__ == '__main__': unittest.main()

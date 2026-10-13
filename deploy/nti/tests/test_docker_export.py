"""Private export freezes only the selected source services and always restarts them."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import data_migration
from pcirn import Error
from remote_data import validate_package

spec = importlib.util.spec_from_file_location('docker_export',
        Path(__file__).resolve().parents[3] / 'scripts/export-docker-data.py')
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


class DockerExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / 'export'
        self.args = SimpleNamespace(output=self.output, manifest='fixture.json', backend='backend',
                                    frontend='frontend', solr='solr', postgres='database',
                                    username='dspace', database='dspace')
        self.rows = [{'Id': name, 'State': {'Running': True}}
                     for name in ('backend-id', 'frontend-id', 'solr-id', 'database-id')]
        self.calls = []
        self.failure = None
        self.endpoint = 'unix:///var/run/docker.sock'

    def run_command(self, command, **kwargs):
        self.calls.append(command)
        if 'cp' in command:
            (Path(command[-1]) / 'preserved-document').write_bytes(b'document')
        if 'pg_dump' in command:
            if self.failure == 'dump':
                raise subprocess.CalledProcessError(1, command)
            kwargs['stdout'].write(b'PGDMPfixture')
        return SimpleNamespace(returncode=1 if self.failure == 'restart' and 'start' in command else 0)

    def export(self, pending=False):
        with mock.patch.object(exporter, 'manifest', return_value={'version': '1.0.0-rc5'}), \
                mock.patch.object(exporter.Source, 'pending', return_value=pending), \
                mock.patch.object(exporter.Source, 'sql', return_value='0'), \
                mock.patch.object(exporter, 'snapshot', return_value={'schema_version': 1}), \
                mock.patch.object(exporter.subprocess, 'check_output', side_effect=lambda args, **kwargs:
                                  self.endpoint if 'context' in args else json.dumps(self.rows)), \
                mock.patch.object(exporter.subprocess, 'run', side_effect=self.run_command):
            exporter.export(self.args)

    def test_remote_endpoint_refused_before_stopping_services(self):
        self.endpoint = 'ssh://example.org'
        with self.assertRaisesRegex(Error, 'local Docker Unix socket'):
            self.export()
        self.assertEqual(self.calls, [])

    def test_export_is_flat_private_and_preserves_source_database(self):
        self.export()
        validate_package(self.output)
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o700)
        self.assertEqual({p.name for p in self.output.iterdir()},
                         data_migration.PACKAGE_FILES | {'checksums.json'})
        self.assertFalse(any('database-id' in c and ('stop' in c or 'start' in c) for c in self.calls))
        self.assertEqual([c[-1] for c in self.calls if 'start' in c],
                         ['solr-id', 'frontend-id', 'backend-id'])

    def test_failed_dump_restarts_all_services_and_keeps_partial_copy_private(self):
        self.failure = 'dump'
        with self.assertRaises(subprocess.CalledProcessError):
            self.export()
        self.assertFalse(self.output.exists())
        self.assertEqual(len([c for c in self.calls if 'start' in c]), 3)
        self.assertTrue(list(self.output.parent.glob('.private-export-*')))

    def test_restart_failure_still_attempts_every_service(self):
        self.failure = 'restart'
        with self.assertRaisesRegex(Error, 'restart requires attention'):
            self.export()
        self.assertEqual(len([c for c in self.calls if 'start' in c]), 3)

    def test_incompatible_history_and_existing_output_never_stop_services(self):
        with self.assertRaisesRegex(Error, 'history'):
            self.export(pending=True)
        self.assertEqual(self.calls, [])
        self.output.mkdir()
        with self.assertRaisesRegex(Error, 'already exists'):
            self.export()
        self.assertEqual(self.calls, [])

    def test_local_socket_check_never_accepts_remote_plaintext(self):
        dep = mock.Mock()
        dep.sql.return_value = 'f'
        with self.assertRaisesRegex(Error, 'verified local socket'):
            data_migration.snapshot(dep, Path('/unused'), Path('/unused'), local_socket=True)
        dep.sql.assert_called_once_with('SELECT inet_client_addr() IS NULL;')
        dep.pending.assert_not_called()

    def test_source_commands_force_container_unix_socket(self):
        source = exporter.Source('database-id', 'dspace', 'dspace', {})
        with mock.patch.object(exporter.subprocess, 'run',
                               return_value=SimpleNamespace(returncode=0, stdout='t')) as run:
            self.assertEqual(source.sql('SELECT 1;'), 't')
        command = run.call_args.args[0]
        self.assertIn('/var/run/postgresql', command)
        self.assertIn('BEGIN READ ONLY;', command[-1])
        with self.assertRaises(Error):
            source.run(['docker', 'stop', 'database-id'])

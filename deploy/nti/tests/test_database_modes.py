"""Backup/restore lifecycle in both modes, with fake services and real Compose parsing."""
import json
import os
from pathlib import Path
import shutil
import sys
import unittest
from unittest import mock

import test_installer as harness

pcirn = harness.pcirn
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class DatabaseModesTests(unittest.TestCase):
    def deployment(self, mode):
        fixture = harness.InstallerTests(methodName='runTest')
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        config = pcirn.read_json(fixture.config)
        if mode == 'docker':
            tls = fixture.root / 'postgres-tls'
            tls.mkdir(parents=True)
            (tls / 'server.crt').write_text('fictional certificate')
            config.update(PG_MODE=mode, PG_IMAGE='postgres@sha256:' + '1' * 64,
                          DB_URL='jdbc:postgresql://127.0.0.1:55432/pcirn?sslmode=verify-ca&sslrootcert=' +
                          str(tls / 'server.crt'))
            pcirn.write_json(fixture.config, config)
        args = mock.Mock(root=fixture.root, config=fixture.config, manifest=fixture.target)
        with mock.patch.dict(os.environ, fixture.env):
            dep = pcirn.provision(args)
        return fixture, dep

    def test_backup_and_restore_preserve_postgres_and_use_host_connection(self):
        for mode in ('external', 'docker'):
            with self.subTest(mode=mode):
                fx, dep = self.deployment(mode)
                dep.deploy(harness.release(), True, initial=True)
                (fx.root / 'data/assetstore/document').write_text('before backup')
                backup = dep.backup(dep.current())
                (fx.root / 'data/assetstore/document').write_text('after backup')
                dep.restore(backup, True)
                self.assertEqual((fx.root / 'data/assetstore/document').read_text(), 'before backup')
                self.assertTrue(fx.state()['running'])
                for _, args in fx.calls():
                    if 'stop' in args:
                        self.assertEqual(args[-3:], list(pcirn.SERVICES))
                    self.assertNotIn('down', args)
                self.assertEqual(dep.env['PGHOST'], '127.0.0.1' if mode == 'docker' else 'nti.invalid')
                self.assertEqual(dep.env['PGPORT'], '55432' if mode == 'docker' else '5432')

    def test_incompatible_clients_block_before_stopping_or_restoring(self):
        for mode in ('external', 'docker'):
            with self.subTest(mode=mode):
                fx, dep = self.deployment(mode)
            with mock.patch.object(dep, 'sql', return_value='150000'), \
                    mock.patch.object(dep, 'run', return_value='PostgreSQL 17.1'), \
                    mock.patch.object(dep, 'stop') as stop, \
                    mock.patch.object(dep, 'compose') as compose:
                with self.assertRaisesRegex(pcirn.Error, 'major'):
                    dep.backup(harness.release())
                with self.assertRaisesRegex(pcirn.Error, 'major'):
                    dep.restore(Path('/fictional/backup'), True)
                stop.assert_not_called()
                compose.assert_not_called()
            tool = fx.bin / 'pg_dump'
            tool.write_text(tool.read_text().replace("print('PostgreSQL 17.1')",
                                                     "print('PostgreSQL 18.1')"))
            result = fx.cli('backup', success=False)
            self.assertIn('major', result.stderr)
            self.assertFalse((fx.root / 'operation.json').exists())

    @unittest.skipUnless(shutil.which('docker'), 'Docker CLI required only for Compose parsing')
    def test_docker_compose_routes_backend_to_persistent_database(self):
        fx, dep = self.deployment('docker')
        (fx.root / 'postgres-password').write_text('fictional administrative password')
        dep.env['PATH'] = os.environ['PATH']
        rendered = json.loads(dep.compose(harness.release(), 'config', '--format', 'json'))
        pg = rendered['services']['postgres']
        volume = next(v for v in pg['volumes'] if v['type'] == 'volume')
        self.assertEqual(volume['target'], '/var/lib/postgresql/data')
        self.assertTrue(rendered['volumes'][volume['source']]['external'])
        self.assertEqual(pg['ports'][0]['host_ip'], '127.0.0.1')
        self.assertEqual(pg['ports'][0]['published'], '55432')
        self.assertTrue(rendered['services']['dspace']['environment']['db__P__url']
                        .startswith('jdbc:postgresql://postgres:5432/pcirn?'))
        self.assertEqual(dep.env['PGHOST'], '127.0.0.1')

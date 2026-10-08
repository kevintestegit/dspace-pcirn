"""Exercise the VM runner end to end against tiny fake tools and fictional data."""
from argparse import Namespace
import json
from pathlib import Path
import os
import unittest
from unittest import mock

import test_installer as simulated
release = simulated.release
import e2e_homolog


class HomologationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = simulated.InstallerTests()
        self.fixture.setUp()
        self.base = self.fixture.base
        configs = []
        for name in ('pcirn_homolog_restored', 'pcirn_homolog_empty'):
            data = json.loads(self.fixture.config.read_text())
            data['DB_URL'] = f'jdbc:postgresql://nti.invalid:5432/{name}?sslmode=require'
            path = self.base / f'{name}.json'
            path.write_text(json.dumps(data)); path.chmod(0o600)
            configs.append(str(path))
        b = self.base / 'b.json'; b.write_text(json.dumps(release('1.1.0', 2)))
        self.fixture.want(release())
        image_rows = {release()['images']['backend']: [dict(m, success=True) for m in release()['database']['migrations']],
                      release('1.1.0', 2)['images']['backend']: [dict(m, success=True) for m in release('1.1.0', 2)['database']['migrations']]}
        (self.base / 'image-rows.json').write_text(json.dumps(image_rows))
        dump = self.base / 'fictional.dump'
        dump.write_text(json.dumps({'rows': image_rows[release()['images']['backend']]}))
        self.args = Namespace(execute_on_disposable_vm=True, root=str(self.base / 'dspacepcirn-homolog'),
                              restored_config=configs[0], empty_config=configs[1],
                              manifest_a=str(self.fixture.target), manifest_b=str(b), fixture_dump=str(dump),
                              authorize_migrations=True, authorize_empty_migrations=True)

    def tearDown(self):
        self.fixture.tearDown()

    def test_full_restored_and_empty_lifecycle(self):
        with mock.patch.dict(os.environ, self.fixture.env), mock.patch.object(e2e_homolog.preflight, 'check'):
            self.assertEqual(e2e_homolog.run(self.args), 0)
        report = json.loads((Path(self.args.root) / 'homolog-report.json').read_text())
        self.assertTrue(report['passed'])
        self.assertEqual(report['authorized_empty'], 'passed')
        commands = {row.get('command') for row in report['steps']}
        self.assertTrue({'install', 'update', 'backup', 'restore', 'rollback', 'health'} <= commands)

    def test_empty_database_with_non_table_objects_is_rejected_before_writes(self):
        state = {'rows': [], 'running': False,
                 'databases': {'pcirn_homolog_empty': {'rows': [], 'extra_objects': 1}}}
        (self.base / 'fake-state.json').write_text(json.dumps(state))
        with mock.patch.dict(os.environ, self.fixture.env), mock.patch.object(e2e_homolog.preflight, 'check'):
            with self.assertRaisesRegex(e2e_homolog.pcirn.Error, 'vazios'):
                e2e_homolog.run(self.args)
        self.assertFalse(Path(self.args.root).exists())

    def test_fixture_major_mismatch_rejected_before_writes(self):
        header = '; Dumped from database version: 18.1\n; Dumped by pg_dump version: 18.1'
        with mock.patch.object(e2e_homolog.preflight, 'check'), \
                mock.patch.object(e2e_homolog.pcirn.Deployment, 'user_objects', return_value=0), \
                mock.patch.object(e2e_homolog.pcirn.Deployment, 'sql', return_value='170000'), \
                mock.patch.object(e2e_homolog.pcirn.Deployment, 'run', return_value=header):
            with self.assertRaisesRegex(e2e_homolog.pcirn.Error, 'Fixture'):
                e2e_homolog.run(self.args)
        self.assertFalse(Path(self.args.root).exists())

    def test_runner_cannot_execute_without_vm_opt_in(self):
        self.args.execute_on_disposable_vm = False
        with self.assertRaisesRegex(e2e_homolog.pcirn.Error, 'Execução bloqueada'):
            e2e_homolog.run(self.args)
        self.assertFalse(Path(self.args.root).exists())

    def test_production_database_name_is_rejected(self):
        self.args.empty_config = str(self.fixture.config)
        with self.assertRaisesRegex(e2e_homolog.pcirn.Error, 'somente bancos'):
            e2e_homolog.validate(self.args)


if __name__ == '__main__': unittest.main()

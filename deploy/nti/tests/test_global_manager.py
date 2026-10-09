"""Install a standalone manager in a temporary prefix; never access real services."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import test_installer as harness

REPO = Path(__file__).resolve().parents[3]


class GlobalManagerTests(unittest.TestCase):
    def test_installed_manager_provisions_without_source_from_another_directory(self):
        fixture = harness.InstallerTests(methodName='runTest')
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        source = fixture.base / 'source'
        shutil.copytree(REPO / 'deploy/nti', source / 'deploy/nti',
                        ignore=shutil.ignore_patterns('tests', '__pycache__'))
        for name in ('docker-compose.yml', 'smtp.env.example'):
            shutil.copy2(REPO / name, source / name)
        prefix = fixture.base / 'usr/local'
        result = subprocess.run(['bash', str(source / 'deploy/nti/install-manager.sh'), str(prefix)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        source.rename(fixture.base / 'unavailable-source')
        env = fixture.env | {'PATH': str(prefix / 'bin') + os.pathsep + fixture.env['PATH']}
        result = subprocess.run(['dspacepcirn', 'install', '--root', str(fixture.root),
                                 '--config', str(fixture.config), '--manifest', str(fixture.target),
                                 '--authorize-migrations'], env=env, cwd='/',
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((fixture.root / 'bin/wizard.py').is_file())
        result = subprocess.run(['dspacepcirn', 'version', '--root', str(fixture.root)],
                                env=env, cwd='/', capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), '1.0.0')

    def test_existing_global_command_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory)
            (prefix / 'bin').mkdir()
            command = prefix / 'bin/dspacepcirn'
            command.write_text('existing work')
            result = subprocess.run(['bash', str(REPO / 'deploy/nti/install-manager.sh'), str(prefix)],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(command.read_text(), 'existing work')
            self.assertFalse((prefix / 'lib/dspacepcirn').exists())

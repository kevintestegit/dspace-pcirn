"""Release metadata is explicit and based on the measured fresh Flyway history."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]


@unittest.skipUnless(shutil.which('jq'), 'Release artifact generator requires jq')
class FreshBootstrapManifestTests(unittest.TestCase):
    def generate(self, fresh=None):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'release.json'
            command = [str(ROOT / 'scripts/release-manifest.sh'), '--version', '1.0.0-test',
                       '--commit', '1' * 40, '--repository-owner', 'fixture', '--output', str(output),
                       '--migrations', str(ROOT / 'scripts/flyway-history.json')]
            for name in ('backend', 'angular', 'solr'):
                command.extend(['--' + name + '-digest', 'sha256:' + '1' * 64])
            if fresh is not None:
                command.extend(['--fresh-migrations', str(fresh)])
            result = subprocess.run(command, capture_output=True, text=True)
            return result, json.loads(output.read_text()) if output.exists() else None

    def test_old_manifest_does_not_claim_bootstrap(self):
        result, manifest = self.generate()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('fresh_bootstrap', manifest['database'])

    def test_measured_history_enables_bootstrap(self):
        history = ROOT / 'scripts/flyway-fresh-history.json'
        result, manifest = self.generate(history)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(manifest['database']['fresh_bootstrap'], 'pcirn-fresh-v1')
        self.assertEqual(manifest['database']['fresh_migrations'], json.loads(history.read_text()))
        institutional = {'V9.4_2026.08.15__pcirn_sector_access.sql',
                         'V9.4_2026.09.23__pcirn_memoria_institucional_collection.sql'}
        self.assertFalse(institutional & {row['script'] for row in manifest['database']['fresh_migrations']})

    def test_institutional_history_cannot_claim_fresh_capability(self):
        result, manifest = self.generate(ROOT / 'scripts/flyway-history.json')
        self.assertNotEqual(result.returncode, 0)
        self.assertIsNone(manifest)

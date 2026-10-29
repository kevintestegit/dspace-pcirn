"""The transfer artifact must include the runner and reproduce byte for byte."""
import importlib.util
from pathlib import Path
import tarfile
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[3] / 'scripts/package-installer.py'
spec = importlib.util.spec_from_file_location('packaging', SCRIPT)
packaging = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packaging)


class PackagingTests(unittest.TestCase):
    def test_python_sources_stay_within_project_limit(self):
        for name in ('pcirn.py', 'pcirn_config.py', 'pcirn_cli.py',
                     'data_migration.py', 'preflight.py'):
            source = Path(__file__).resolve().parents[1] / name
            self.assertLessEqual(len(source.read_text().splitlines()), 500, name)

    def test_reproducible_and_complete_without_private_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / 'one.tar.gz'
            second = Path(directory) / 'two.tar.gz'
            self.assertEqual(packaging.package(first), packaging.package(second))
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with tarfile.open(first) as archive:
                names = archive.getnames()
            for required in ('tests/e2e_homolog.py', 'tests/fixtures/probe.sql',
                             'homolog/release-a.json', 'homolog/release-b.json'):
                self.assertIn('dspacepcirn-installer/deploy/nti/' + required, names)
            self.assertFalse(any(name.endswith(('.dump', '.env', 'config.json')) for name in names))

    def test_symlink_input_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('install.sh', 'deploy/nti/pcirn.py', 'deploy/nti/tests/e2e_homolog.py',
                         'deploy/nti/homolog/release-a.json', 'deploy/nti/homolog/release-b.json'):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            (root / 'install.sh').unlink()
            (root / 'install.sh').symlink_to(SCRIPT)
            with self.assertRaisesRegex(ValueError, 'regular'):
                packaging.package(root / 'output.tar.gz', root)

"""Keep local artifacts out of Git and the backend build context."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[3]


class RepositoryHygieneTests(unittest.TestCase):
    def test_no_ignored_files_are_tracked(self):
        result = subprocess.run(['git', 'ls-files', '-ci', '--exclude-standard'],
                                cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout, '')

    def test_operator_artifacts_are_ignored_but_shared_dotfiles_remain(self):
        ignored = ['.superpowers/probe', '.worktrees/probe', '.codex/probe',
                   'node_modules/probe', '.angular/probe', 'transfer.dump',
                   '.env.private', 'tls/server.key',
                   'deploy/nti/__pycache__/probe.pyc', 'dspacepcirn-manager.tar.gz',
                   'release-manifest.json', 'data-package.json']
        result = subprocess.run(['git', 'check-ignore', '--no-index', *ignored],
                                cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertEqual(set(result.stdout.splitlines()), set(ignored))
        result = subprocess.run(['git', 'check-ignore', '--no-index', '.github/workflows/build.yml',
                                 '.gitmodules', '.dockerignore', '.env.example'],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, '')

    def test_build_context_excludes_private_data_and_tooling(self):
        patterns = set((ROOT / '.dockerignore').read_text().splitlines())
        for pattern in ('.git/', '.env', '**/*.dump', '.estabilizacao-backup/',
                        '.worktrees/', '.superpowers/', '.codex/', 'output/',
                        '**/node_modules/', '**/__pycache__/', 'docs/pcirn-publicados/'):
            self.assertIn(pattern, patterns)

    def test_heavy_checks_are_explicit_and_release_keeps_full_gate(self):
        import yaml
        workflow = yaml.safe_load((ROOT / '.github/workflows/build.yml').read_text())
        triggers = workflow.get('on', workflow.get(True))
        self.assertNotIn('push', triggers)
        self.assertFalse(triggers['workflow_dispatch']['inputs']['integration']['default'])
        self.assertIn('inputs.integration', workflow['jobs']['tests']['strategy']['matrix']['type'])
        quick = (ROOT / '.github/workflows/installer.yml').read_text()
        self.assertIn('scripts/check-installer.py', quick)
        self.assertNotIn('--full', quick)
        release = (ROOT / '.github/workflows/publish-images.yml').read_text()
        self.assertIn('unittest discover', release)
        self.assertIn("PCIRN_RUN_POSTGRES15: '1'", release)
        self.assertIn('bootstrap_fresh.py', release)

    def test_api_unit_classes_use_one_isolated_jvm_at_a_time(self):
        import xml.etree.ElementTree as xml
        pom = xml.parse(ROOT / 'dspace-api/pom.xml')
        ns = {'m': 'http://maven.apache.org/POM/4.0.0'}
        plugins = pom.findall('.//m:plugin', ns)
        plugin = next(p for p in plugins if p.findtext('m:artifactId', namespaces=ns)
                      == 'maven-surefire-plugin')
        self.assertEqual(plugin.findtext('m:configuration/m:forkCount', namespaces=ns), '1')
        self.assertEqual(plugin.findtext('m:configuration/m:reuseForks', namespaces=ns), 'false')

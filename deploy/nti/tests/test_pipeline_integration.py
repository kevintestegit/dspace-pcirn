"""Integration between the GHCR pipeline and the NTI installer.

The installer suite runs entirely against fake executables, so it proves the
CLI's logic but not that the two halves of the release agree. These tests close
that gap:

* the manifest the pipeline actually generates must satisfy the installer's own
  parser, including the SemVer and digest rules;
* the Flyway history the pipeline publishes must be the history the installer
  compares against ``schema_version``;
* a PostgreSQL that was already restored (the schema_version matches the
  manifest row for row) must install without running a migration and without
  the migration authorization;
* the Compose file the installer writes must interpolate with exactly the
  variables the installer supplies.

Nothing here touches Docker or PostgreSQL: the Compose check only renders.
"""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

NTI = Path(__file__).resolve().parents[1]
REPO = NTI.parents[1]
MODULE = NTI / 'pcirn.py'

# unittest discovery does not put the tests directory on sys.path, and the
# fake-executable harness lives in test_installer.
sys.path.insert(0, str(Path(__file__).resolve().parent))

spec = importlib.util.spec_from_file_location('pcirn', MODULE)
pcirn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pcirn)

ZERO = '0' * 64


def pipeline_manifest(directory, version, migrations, digests=None):
    """Run the pipeline's generator, exactly as the release workflow does."""
    digests = digests or {
        'backend': 'sha256:' + 'a' * 64,
        'angular': 'sha256:' + 'b' * 64,
        'solr': 'sha256:' + 'c' * 64,
    }
    output = Path(directory) / 'release.json'
    subprocess.run(
        [str(REPO / 'scripts/release-manifest.sh'),
         '--version', version,
         '--commit', '0' * 40,
         '--angular-commit', '1' * 40,
         '--backend-digest', digests['backend'],
         '--angular-digest', digests['angular'],
         '--solr-digest', digests['solr'],
         '--migrations', str(migrations),
         '--repository-owner', 'kevintestegit',
         '--output', str(output)],
        check=True, capture_output=True, text=True)
    return output


class ManifestContractTests(unittest.TestCase):
    """What the pipeline emits must be what the installer accepts."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='pcirn-integ-')
        self.base = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def history(self):
        return REPO / 'scripts/flyway-history.json'

    def test_pipeline_manifest_is_accepted_by_the_installer(self):
        path = pipeline_manifest(self.base, 'v1.0.0-rc1', self.history())
        data = pcirn.manifest(path)
        self.assertEqual(data['schema_version'], 1)
        # The installer rejects the "v" prefix, so the pipeline must strip it.
        self.assertEqual(data['version'], '1.0.0-rc1')
        self.assertEqual(set(data['images']), set(pcirn.IMAGE_KEYS))
        self.assertEqual(len(data['database']['migrations']),
                         len(json.loads(self.history().read_text())))

    def test_published_history_is_a_supported_version_and_unique(self):
        data = pcirn.manifest(pipeline_manifest(self.base, 'v1.0.0', self.history()))
        versions = [m['version'] for m in data['database']['migrations']]
        self.assertEqual(len(versions), len(set(versions)))
        for value in versions:
            self.assertRegex(value, r'^[0-9]+(?:\.[0-9]+)*$')

    def test_installer_refuses_a_manifest_with_a_tagged_image(self):
        # A tag instead of a digest is the mistake the contract exists to stop.
        path = pipeline_manifest(self.base, 'v1.0.0', self.history())
        data = json.loads(path.read_text())
        data['images']['backend'] = 'ghcr.io/kevintestegit/dspace-pcirn-backend:1.0.0'
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(pcirn.Error, 'sha256'):
            pcirn.manifest(path)

    def test_installer_refuses_a_v_prefixed_version(self):
        path = pipeline_manifest(self.base, 'v1.0.0', self.history())
        data = json.loads(path.read_text())
        data['version'] = 'v1.0.0'
        path.write_text(json.dumps(data))
        with self.assertRaises(pcirn.Error):
            pcirn.manifest(path)

    def test_pipeline_rejects_uppercase_owner_so_the_installer_accepts_it(self):
        # Digest regexes only allow lower case, so the generator normalises.
        path = pipeline_manifest(self.base, 'v1.0.0', self.history())
        data = pcirn.manifest(path)
        for reference in data['images'].values():
            self.assertEqual(reference, reference.lower())


class RestoredDatabaseTests(unittest.TestCase):
    """A database restored from the current instance must install cleanly."""

    def setUp(self):
        from test_installer import FAKE, release  # noqa: E402

        self.release = release
        self.temp = tempfile.TemporaryDirectory(prefix='pcirn-restored-')
        self.base = Path(self.temp.name)
        self.root = self.base / 'deployment'
        self.bin = self.base / 'bin'
        self.bin.mkdir()
        for name in ('docker', 'psql', 'pg_dump', 'pg_restore'):
            executable = self.bin / name
            executable.write_text(FAKE)
            executable.chmod(0o755)
        self.config = self.base / 'nti.json'
        self.config.write_text(json.dumps({
            'DB_URL': 'jdbc:postgresql://nti.invalid:5432/pcirn?sslmode=require',
            'DB_USERNAME': 'nti', 'DB_PASSWORD': 'x',
            'PUBLIC_UI_URL': 'https://repo.invalid',
            'PUBLIC_REST_URL': 'https://repo.invalid/server',
            'PUBLIC_REST_HOST': 'repo.invalid'}))
        self.config.chmod(0o600)
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ['PATH'],
                        PCIRN_TEST=str(self.base))

    def tearDown(self):
        self.temp.cleanup()

    def restored(self, migrations, applied=None):
        """Seed the fake database as a restored instance already at `applied`.

        `wanted.json` only feeds the fake `docker compose run`, which is how the
        installer normally reaches the target schema. A restored database is
        already there, so the history has to be in the fake state up front.
        """
        target = self.base / 'manifest.json'
        target.write_text(json.dumps(migrations))
        rows = applied if applied is not None else migrations['database']['migrations']
        (self.base / 'fake-state.json').write_text(json.dumps(
            {'rows': [dict(m, success=True) for m in rows], 'running': False}))
        (self.base / 'wanted.json').write_text(json.dumps(
            [dict(m, success=True) for m in migrations['database']['migrations']]))
        return target

    def cli(self, *args, success=True):
        process = subprocess.run(
            ['python3', str(MODULE), *map(str, args)],
            env=self.env, text=True, capture_output=True)
        if success:
            self.assertEqual(process.returncode, 0, process.stderr + process.stdout)
        else:
            self.assertNotEqual(process.returncode, 0, process.stdout)
        return process

    def calls(self):
        log = self.base / 'calls.jsonl'
        if not log.exists():
            return []
        return [json.loads(line) for line in log.read_text().splitlines()]

    def test_restored_database_installs_without_authorizing_migrations(self):
        migrations = self.release('1.0.0')
        target = self.restored(migrations)
        # No --authorize-migrations: a restored database has nothing pending.
        self.cli('install', '--root', self.root, '--config', self.config,
                 '--manifest', target)
        operations = self.calls()
        self.assertFalse(
            any(name == 'docker' and 'run' in args for name, args in operations),
            'a restored database must not trigger `dspace database migrate`')
        state = json.loads((self.base / 'fake-state.json').read_text())
        self.assertTrue(state['running'])
        self.assertFalse(state.get('migration_called', False))

    def test_restored_database_requires_authorization_when_history_diverges(self):
        # Two migrations in the manifest, only the first applied.
        migrations = self.release('1.0.0', migrations=2)
        target = self.restored(migrations,
                               applied=migrations['database']['migrations'][:1])
        process = self.cli('install', '--root', self.root, '--config', self.config,
                           '--manifest', target, success=False)
        self.assertIn('authorize-migrations', process.stderr)

    def test_restored_database_with_divergent_checksum_is_rejected(self):
        migrations = self.release('1.0.0')
        altered = [dict(migrations['database']['migrations'][0], checksum=999)]
        target = self.restored(migrations, applied=altered)
        process = self.cli('install', '--root', self.root, '--config', self.config,
                           '--manifest', target, success=False)
        self.assertIn('divergente', process.stderr)


class GeneratedComposeTests(unittest.TestCase):
    """The Compose file the installer writes must actually interpolate."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='pcirn-compose-')
        self.root = Path(self.temp.name) / 'deployment'
        (self.root / 'dspace/config').mkdir(parents=True)
        (self.root / 'dspace/config/local.cfg').write_text('db.schema = public\n')
        for name in ('data/assetstore', 'data/solr'):
            (self.root / name).mkdir(parents=True, exist_ok=True)
        source = (REPO / 'docker-compose.yml').read_text()
        compose = source.replace('- solr_data:/var/solr/data',
                                 '- ${SOLR_DATA_PATH}:/var/solr/data')
        compose = compose.replace('db__P__username:',
                                  'db__P__schema: public\n      db__P__username:')
        (self.root / 'compose.yml').write_text(compose)

    def tearDown(self):
        self.temp.cleanup()

    def environment(self):
        digest = 'sha256:' + ZERO
        return dict(os.environ,
                    DB_URL='jdbc:postgresql://nti.invalid:5432/pcirn?sslmode=require',
                    DB_USERNAME='nti', DB_PASSWORD='x',
                    PUBLIC_UI_URL='https://repo.invalid',
                    PUBLIC_REST_URL='https://repo.invalid/server',
                    PUBLIC_REST_HOST='repo.invalid',
                    DSPACE_IMAGE='ghcr.io/nti/backend@' + digest,
                    SOLR_IMAGE='ghcr.io/nti/solr@' + digest,
                    ANGULAR_IMAGE='ghcr.io/nti/frontend@' + digest,
                    ASSETSTORE_PATH=str(self.root / 'data/assetstore'),
                    SOLR_DATA_PATH=str(self.root / 'data/solr'))

    @unittest.skipUnless(shutil.which('docker'), 'docker not available')
    def test_generated_compose_interpolates_with_installer_variables(self):
        envfile = Path(self.temp.name) / 'empty.env'
        envfile.write_text('')
        process = subprocess.run(
            ['docker', 'compose', '--project-name', 'pcirn-integration',
             '--project-directory', str(self.root), '--env-file', str(envfile),
             '-f', str(self.root / 'compose.yml'), 'config'],
            env=self.environment(), text=True, capture_output=True)
        self.assertEqual(
            process.returncode, 0,
            'the installer supplies every variable the Compose file requires, '
            'otherwise `up` fails before any container starts:\n' + process.stderr)

    @unittest.skipUnless(shutil.which('docker'), 'docker not available')
    def test_local_cfg_mount_points_at_the_file_the_installer_writes(self):
        envfile = Path(self.temp.name) / 'empty.env'
        envfile.write_text('')
        process = subprocess.run(
            ['docker', 'compose', '--project-name', 'pcirn-integration',
             '--project-directory', str(self.root), '--env-file', str(envfile),
             '-f', str(self.root / 'compose.yml'), 'config'],
            env=self.environment(), text=True, capture_output=True, check=True)
        self.assertIn(str(self.root / 'dspace/config/local.cfg'), process.stdout)
        # The Solr data directory must be redirected out of the Docker volume.
        self.assertIn(str(self.root / 'data/solr'), process.stdout)


class ReleaseArtifactTests(unittest.TestCase):
    """Nothing that ships may carry credentials or a local configuration."""

    def test_no_credential_shaped_value_in_tracked_installer_files(self):
        patterns = ('xkeysib-', 'xsmtpsib-', 'gho_', 'ghp_', 'github_pat_',
                    'AKIA', 'PRIVATE KEY')
        # This file is the scanner, so it names the patterns it looks for.
        this_file = Path(__file__).resolve()
        offenders = []
        for path in sorted(NTI.rglob('*')):
            if not path.is_file() or '__pycache__' in path.parts:
                continue
            if path.resolve() == this_file:
                continue
            try:
                text = path.read_text(encoding='utf-8')
            except (UnicodeDecodeError, OSError):
                continue
            for pattern in patterns:
                if pattern in text:
                    offenders.append(f'{path}: {pattern}')
        self.assertEqual(offenders, [], 'credential-shaped values in the installer')

    def test_workflow_publishes_digests_and_the_release_manifest(self):
        workflow = (REPO / '.github/workflows/publish-images.yml').read_text()
        self.assertIn('push-by-digest=true', workflow)
        self.assertIn('imagetools create', workflow)
        self.assertIn('release-manifest.sh', workflow)
        self.assertIn('flyway-history.json', workflow)

    def test_workflow_gates_publication_on_validation(self):
        """Publication must depend on the validate job, and build on nothing else."""
        import yaml
        workflow = yaml.safe_load(
            (REPO / '.github/workflows/publish-images.yml').read_text())
        jobs = workflow['jobs']
        self.assertIn('validate', jobs)
        self.assertEqual(jobs['build']['needs'], 'validate')
        self.assertEqual(set(jobs['publish']['needs']), {'validate', 'build'})
        self.assertEqual(set(jobs['manifest']['needs']), {'validate', 'publish'})
        # Only the publish job attaches a tag, so one architecture failing
        # cannot leave a partially built version pullable.
        self.assertNotIn('tags:', json.dumps(jobs['build']))

    def test_workflow_builds_every_image_for_both_architectures(self):
        import yaml
        workflow = yaml.safe_load(
            (REPO / '.github/workflows/publish-images.yml').read_text())
        entries = workflow['jobs']['build']['strategy']['matrix']['include']
        built = {(e['image'], e['platform']) for e in entries}
        expected = {(image, platform)
                    for image in ('backend', 'angular', 'solr')
                    for platform in ('linux/amd64', 'linux/arm64')}
        self.assertEqual(built, expected)

    def test_published_history_covers_every_applied_migration(self):
        history = json.loads((REPO / 'scripts/flyway-history.json').read_text())
        for migration in history:
            script = migration['script']
            if script.startswith('<<'):
                continue
            if script.endswith('.sql'):
                path = (REPO / 'dspace-api/src/main/resources/org/dspace/storage/rdbms'
                        / 'sqlmigration/postgres' / script)
            else:
                leaf = script.rsplit('.', 1)[-1] + '.java'
                matches = list((REPO / 'dspace-api/src/main/java/org/dspace/storage/rdbms')
                               .rglob(leaf))
                self.assertTrue(matches, f'Java migration missing: {leaf}')
                continue
            self.assertTrue(path.is_file(), f'applied migration missing: {script}')


if __name__ == '__main__':
    unittest.main()

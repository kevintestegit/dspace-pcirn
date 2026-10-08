"""Operational surface around the installer: Compose, backup, publication, SMTP.

``pcirn.py`` and its fake-executable suite cover the CLI. These tests cover the
rest of what an operator touches, where the code review found the same class of
defect: configuration read with the wrong parser, plumbing that drops what it
was handed, and a runbook that promises something the stack does not do.

* #7  ``docker compose run --rm dspace <comando>`` must reach DSpace with its
  arguments; the entrypoint used to swallow them;
* #8  ``scripts/backup-dspace.sh`` must read ``.env.production`` as a Compose
  env file, never as a shell script;
* #17 the TLS parameters of ``DB_URL`` must reach the PostgreSQL client;
* #10 the Solr statistics core is original data and belongs in the backup;
* #19 the production stack must load the SMTP file the runbook documents;
* #9  a manual publication must build the revision the tag points at.

Docker is used for two things only: rendering Compose configurations and, in the
backup tests, delegating the env-file parsing to the very parser that starts the
stack. No container is started and no daemon state is touched.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest

NTI = Path(__file__).resolve().parents[1]
REPO = NTI.parents[1]
COMPOSE = REPO / 'docker-compose.yml'
DEV_COMPOSE = REPO / 'docker-compose.dev.yml'
BACKUP = REPO / 'scripts/backup-dspace.sh'
WORKFLOW = REPO / '.github/workflows/publish-images.yml'
REAL_DOCKER = shutil.which('docker')

# The fake executables in test_installer live in this directory; unittest
# discovery does not put it on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent))

spec = importlib.util.spec_from_file_location('pcirn', NTI / 'pcirn.py')
pcirn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pcirn)

DIGEST = 'sha256:' + '0' * 64


def compose_service(name, path=None):
    import yaml
    return yaml.safe_load((path or COMPOSE).read_text())['services'][name]


def workflow_jobs():
    import yaml
    return yaml.safe_load(WORKFLOW.read_text())['jobs']


def valid_config(directory, url='jdbc:postgresql://nti.invalid:5432/pcirn?sslmode=require'):
    path = Path(directory) / 'nti.json'
    path.write_text(json.dumps({
        'DB_URL': url, 'DB_USERNAME': 'nti', 'DB_PASSWORD': 'x',
        'PUBLIC_UI_URL': 'https://repo.invalid',
        'PUBLIC_REST_URL': 'https://repo.invalid/server',
        'PUBLIC_REST_HOST': 'repo.invalid'}))
    path.chmod(0o600)
    return path


def provisioned_deployment(base):
    """Provision with the installer itself; the tests then use its own output."""
    from test_installer import release  # noqa: E402

    target = Path(base) / 'release.json'
    target.write_text(json.dumps(release('1.0.0')))
    root = Path(base) / 'deployment'
    pcirn.provision(argparse.Namespace(root=str(root), config=str(valid_config(base)),
                                       manifest=str(target)))
    return root


def installer_environment(root):
    return dict(os.environ,
                DB_URL='jdbc:postgresql://nti.invalid:5432/pcirn?sslmode=require',
                DB_USERNAME='nti', DB_PASSWORD='x',
                PUBLIC_UI_URL='https://repo.invalid',
                PUBLIC_REST_URL='https://repo.invalid/server',
                PUBLIC_REST_HOST='repo.invalid',
                DSPACE_IMAGE='ghcr.io/nti/backend@' + DIGEST,
                SOLR_IMAGE='ghcr.io/nti/solr@' + DIGEST,
                ANGULAR_IMAGE='ghcr.io/nti/frontend@' + DIGEST,
                ASSETSTORE_PATH=str(Path(root) / 'data/assetstore'),
                SOLR_DATA_PATH=str(Path(root) / 'data/solr'))


def render_config(root, environment):
    """Render the generated Compose file and return it as JSON."""
    envfile = Path(root) / 'empty.env'
    envfile.write_text('')
    process = subprocess.run(
        ['docker', 'compose', '--project-name', 'pcirn-operations',
         '--project-directory', str(root), '--env-file', str(envfile),
         '-f', str(Path(root) / 'compose.yml'), 'config', '--format', 'json'],
        env=environment, text=True, capture_output=True)
    if process.returncode:
        raise AssertionError('the generated Compose file does not render:\n' + process.stderr)
    return json.loads(process.stdout)


def service_environment(rendered, service):
    value = rendered['services'][service].get('environment') or {}
    if isinstance(value, list):
        return dict(item.split('=', 1) for item in value if '=' in item)
    return dict(value)


class AdminCommandTests(unittest.TestCase):
    """#7: documented `run --rm dspace` commands must reach DSpace intact."""

    def docker_argv(self, *command, compose=None):
        """The argv Docker builds: the entrypoint, then the command.

        `docker compose run <service> <args>` replaces the service command with
        those arguments; everything else keeps it. Compose unescapes `$$` to `$`
        before the container reads the script.
        """
        service = compose_service('dspace', compose or COMPOSE)
        argv = [str(item) for item in service['entrypoint']]
        argv += [str(item) for item in (command or service.get('command') or [])]
        return [item.replace('$$', '$') for item in argv]

    def stub(self, directory, name):
        """An executable that records the arguments it was handed."""
        record = Path(directory) / f'{name}.args'
        stub = Path(directory) / name
        stub.write_text('#!/usr/bin/env python3\n'
                        'import json, sys\n'
                        f'open({str(record)!r}, "w").write(json.dumps(sys.argv[1:]))\n')
        stub.chmod(0o755)
        return stub, record

    def test_admin_command_reaches_dspace_with_its_arguments(self):
        with tempfile.TemporaryDirectory(prefix='pcirn-admin-') as temp:
            dspace, record = self.stub(temp, 'dspace')
            # Exactly what Docker runs: the service entrypoint, then the
            # arguments of `docker compose run --rm dspace <command>`.
            process = subprocess.run(
                self.docker_argv(str(dspace), 'database', 'migrate'),
                text=True, capture_output=True, timeout=60)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(
                json.loads(record.read_text()), ['database', 'migrate'],
                'the administrative command must reach DSpace with its arguments; '
                '`sh -c` keeps only the first word and silently drops the rest')

    def test_development_stack_forwards_arguments_too(self):
        # Both stacks bootstrap the application through an entrypoint, and both
        # used to discard the arguments of `run`.
        with tempfile.TemporaryDirectory(prefix='pcirn-admin-') as temp:
            dspace, record = self.stub(temp, 'dspace')
            process = subprocess.run(
                self.docker_argv(str(dspace), 'user', '--add', '-e', 'nti@example.org',
                                 compose=DEV_COMPOSE),
                text=True, capture_output=True, timeout=60)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(json.loads(record.read_text()),
                             ['user', '--add', '-e', 'nti@example.org'])

    def test_startup_starts_the_application_when_no_command_is_given(self):
        with tempfile.TemporaryDirectory(prefix='pcirn-admin-') as temp:
            java, record = self.stub(temp, 'java')
            environment = dict(
                os.environ, PATH=str(temp) + os.pathsep + os.environ['PATH'],
                dspace__P__server__P__url='https://repo.invalid/server',
                dspace__P__ui__P__url='https://repo.invalid')
            process = subprocess.run(self.docker_argv(), env=environment,
                                     text=True, capture_output=True, timeout=60)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(json.loads(record.read_text()),
                             ['-jar', '/dspace/webapps/server-boot.jar'])

    def test_startup_rejects_a_public_url_that_is_not_https(self):
        with tempfile.TemporaryDirectory(prefix='pcirn-admin-') as temp:
            self.stub(temp, 'java')
            environment = dict(
                os.environ, PATH=str(temp) + os.pathsep + os.environ['PATH'],
                dspace__P__server__P__url='http://repo.invalid/server',
                dspace__P__ui__P__url='https://repo.invalid')
            process = subprocess.run(self.docker_argv(), env=environment,
                                     text=True, capture_output=True, timeout=60)
            self.assertEqual(process.returncode, 1, process.stdout)
            self.assertIn('HTTPS', process.stderr)


# The backup script derives its repository root from its own location, so the
# tests run it from a throwaway checkout rather than write .env.production into
# the real one. `compose config` is delegated to the real CLI: Compose is the
# parser the backup has to agree with, and emulating it here would only test the
# emulation.
FAKE_DOCKER = r'''#!/usr/bin/env python3
import io, json, os, pathlib, subprocess, sys, tarfile

real = os.environ['BACKUP_TEST_REAL_DOCKER']
root = pathlib.Path(os.environ['BACKUP_TEST'])
args = sys.argv[1:]
with (root / 'calls.jsonl').open('a') as log:
    log.write(json.dumps(args) + '\n')

def out_directory():
    for item in args:
        if item.endswith(':/out'):
            return pathlib.Path(item[:-len(':/out')])
    raise SystemExit('fake docker: no /out bind in ' + repr(args))

if args[:1] == ['compose'] and 'config' in args:
    raise SystemExit(subprocess.run([real, *args]).returncode)

def stream(directory, name):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:gz') as archive:
        archive.add(directory, arcname=name)
    sys.stdout.buffer.write(buffer.getvalue())

if args[:1] == ['compose'] and 'config' in args:
    raise SystemExit(subprocess.run([real, *args]).returncode)

if 'ps' in args:
    # Only the development stack has a database container.
    if (root / 'development').exists():
        print('dspacedb')
    raise SystemExit(0)

if 'exec' in args and 'pg_dump' in args:
    sys.stdout.write('fake custom-format dump')
    raise SystemExit(0)

if 'pg_dump' in args:
    (out_directory() / 'dspace.dump').write_bytes(b'fake custom-format dump')
    raise SystemExit(0)

if 'pg_restore' in args:
    raise SystemExit(0)

if 'tar' in args and 'exec' in args:
    stream(root / 'assetstore', 'assetstore')
    raise SystemExit(0)

if 'tar' in args:
    if (root / 'no-statistics').exists():
        print('tar: statistics: No such file or directory', file=sys.stderr)
        raise SystemExit(2)
    stream(root / 'statistics', 'statistics')
    raise SystemExit(0)

raise SystemExit('fake docker: unexpected arguments ' + repr(args))
'''


@unittest.skipUnless(REAL_DOCKER, 'the env file is read by the Compose CLI')
class BackupScriptTests(unittest.TestCase):
    """#8/#10/#17: the backup reads Compose data, keeps data and honours TLS."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='pcirn-backup-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / 'repo'
        (self.repo / 'scripts').mkdir(parents=True)
        shutil.copy2(BACKUP, self.repo / 'scripts/backup-dspace.sh')
        shutil.copy2(COMPOSE, self.repo / 'docker-compose.yml')
        # The production Compose file loads this file, so it has to exist for
        # the config to render at all.
        (self.repo / 'smtp.env').write_text('# no mail configured in this test\n')
        self.destination = self.base / 'dest'
        (self.base / 'assetstore').mkdir()
        (self.base / 'assetstore/bitstream.txt').write_text('bitstream\n')
        statistics = self.base / 'statistics'
        (statistics / 'data/index').mkdir(parents=True)
        (statistics / 'core.properties').write_text('name=statistics\n')
        (statistics / 'data/index/segments_1').write_bytes(b'index')
        binary = self.base / 'bin'
        binary.mkdir()
        docker = binary / 'docker'
        docker.write_text(FAKE_DOCKER)
        docker.chmod(0o755)
        self.certificate = self.base / 'ca.pem'
        self.certificate.write_text('-----BEGIN CERTIFICATE-----\nfake\n')
        self.env = dict(os.environ,
                        PATH=str(binary) + os.pathsep + os.environ['PATH'],
                        BACKUP_TEST=str(self.base),
                        BACKUP_TEST_REAL_DOCKER=str(REAL_DOCKER))

    def write_env_file(self, url=None, extra=()):
        values = {
            'DB_URL': url or 'jdbc:postgresql://db.invalid:5432/dspace?sslmode=require',
            'DB_USERNAME': 'dspace',
            'DB_PASSWORD': 'secret',
            'PUBLIC_UI_URL': 'https://repo.invalid',
            'PUBLIC_REST_URL': 'https://repo.invalid/server',
            'PUBLIC_REST_HOST': 'repo.invalid',
            'ASSETSTORE_PATH': str(self.base / 'assetstore'),
            'DSPACE_IMAGE': 'ghcr.io/nti/dspace-pcirn-backend@' + DIGEST,
            'SOLR_IMAGE': 'ghcr.io/nti/dspace-pcirn-solr@' + DIGEST,
            'ANGULAR_IMAGE': 'ghcr.io/nti/dspace-pcirn-angular@' + DIGEST,
        }
        values.update(dict(item.split('=', 1) for item in extra))
        (self.repo / '.env.production').write_text(
            '\n'.join(f'{key}={value}' for key, value in values.items()) + '\n')
        return values

    def backup(self, success=True):
        process = subprocess.run([str(self.repo / 'scripts/backup-dspace.sh'),
                                  str(self.destination)],
                                 env=self.env, text=True, capture_output=True,
                                 timeout=300)
        if success:
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        else:
            self.assertNotEqual(process.returncode, 0, process.stdout)
        return process

    def calls(self):
        log = self.base / 'calls.jsonl'
        return [json.loads(line) for line in log.read_text().splitlines()]

    def call(self, *needles):
        for argv in self.calls():
            if all(needle in argv for needle in needles):
                return argv
        self.fail(f'no docker call matching {needles}: {self.calls()}')

    def client_environment(self):
        argv = self.call('pg_dump')
        pairs = {}
        for index, item in enumerate(argv):
            if item == '-e' and '=' in argv[index + 1]:
                key, value = argv[index + 1].split('=', 1)
                pairs[key] = value
        return argv, pairs

    def backup_directory(self):
        directories = list(self.destination.glob('dspace-*'))
        self.assertEqual(len(directories), 1, f'expected one backup in {self.destination}')
        return directories[0]

    def test_env_file_is_data_and_is_never_executed(self):
        marker = self.base / 'executed'
        self.write_env_file(extra=[f'DSPACE_NAME=`touch {marker}`'])
        self.backup()
        self.assertFalse(marker.exists(),
                         '.env.production is a Compose env file: reading it must not run it')

    def test_value_with_spaces_does_not_break_the_backup(self):
        # The shipped example sets exactly this: an unquoted value with a space.
        self.write_env_file(extra=['DSPACE_NAME=Repositório PCIRN'])
        self.backup()
        self.assertTrue((self.backup_directory() / 'dspace.dump').is_file())

    def test_password_is_passed_as_compose_interpolates_it(self):
        self.write_env_file(extra=['DB_PASSWORD=pa$$w0rd'])
        self.backup()
        _, environment = self.client_environment()
        self.assertEqual(environment['PGPASSWORD'], 'pa$w0rd')

    def test_tls_parameters_of_db_url_reach_the_client(self):
        url = ('jdbc:postgresql://db.invalid:5432/dspace'
               f'?sslmode=verify-full&sslrootcert={self.certificate}')
        self.write_env_file(url=url)
        self.backup()
        argv, environment = self.client_environment()
        self.assertEqual(environment.get('PGSSLMODE'), 'verify-full')
        self.assertEqual(environment.get('PGSSLROOTCERT'), str(self.certificate))
        self.assertIn(f'{self.certificate}:{self.certificate}:ro', argv,
                      'verify-full needs the CA inside the throwaway client')

    def test_jdbc_parameter_the_client_cannot_use_is_refused(self):
        url = ('jdbc:postgresql://db.invalid:5432/dspace'
               '?sslmode=require&ApplicationName=pcirn')
        self.write_env_file(url=url)
        process = self.backup(success=False)
        self.assertIn('ApplicationName', process.stderr)

    def test_development_mode_dumps_inside_the_database_container(self):
        # The development stack has its own PostgreSQL container and no
        # .env.production: the same script must still produce every artifact.
        (self.base / 'development').touch()
        process = self.backup()
        self.assertIn('Backup (development)', process.stdout)
        self.call('exec', 'pg_dump')
        directory = self.backup_directory()
        for name in ('dspace.dump', 'assetstore.tar.gz', 'solr-statistics.tar.gz'):
            self.assertTrue((directory / name).is_file(), name)

    def test_missing_statistics_core_publishes_nothing(self):
        self.write_env_file()
        (self.base / 'no-statistics').touch()
        process = self.backup(success=False)
        self.assertIn('statistics', process.stderr)
        self.assertEqual(list(self.destination.glob('dspace-*')), [],
                         'a backup without the statistics core must not look usable')

    def test_solr_statistics_core_is_preserved(self):
        self.write_env_file()
        self.backup()
        directory = self.backup_directory()
        archive = directory / 'solr-statistics.tar.gz'
        self.assertTrue(archive.is_file(),
                        'usage statistics exist only in the Solr statistics core; '
                        'index-discovery rebuilds search, never statistics')
        with tarfile.open(archive) as tar:
            names = tar.getnames()
        self.assertIn('statistics/core.properties', names)
        self.assertIn('statistics/data/index/segments_1', names)
        self.assertIn('solr-statistics.tar.gz', (directory / 'SHA256SUMS').read_text())
        self.assertEqual(stat.S_IMODE(archive.stat().st_mode), 0o600)


class SmtpConfigurationTests(unittest.TestCase):
    """#19: the SMTP file the runbook documents must actually be loaded."""

    def test_production_service_loads_smtp_env(self):
        files = json.dumps(compose_service('dspace').get('env_file'))
        self.assertIn('smtp.env', files,
                      'PRODUCTION.md tells the operator to write smtp.env; without '
                      'env_file nothing reads it and mail is unconfigured')

    def test_installer_provisions_the_file_the_compose_requires(self):
        with tempfile.TemporaryDirectory(prefix='pcirn-smtp-') as temp:
            root = provisioned_deployment(temp)
            smtp = root / 'smtp.env'
            self.assertTrue(smtp.is_file(),
                            'the generated Compose loads <root>/smtp.env, so install must write it')
            self.assertEqual(stat.S_IMODE(smtp.stat().st_mode), 0o600)

    def test_installer_preserves_smtp_settings(self):
        with tempfile.TemporaryDirectory(prefix='pcirn-smtp-') as temp:
            root = provisioned_deployment(temp)
            smtp = root / 'smtp.env'
            smtp.write_text('mail__P__server=smtp.institucional.example\n')
            provisioned_deployment(temp)
            self.assertEqual(smtp.read_text(),
                             'mail__P__server=smtp.institucional.example\n')

    @unittest.skipUnless(REAL_DOCKER, 'docker not available')
    def test_institutional_smtp_settings_reach_the_backend(self):
        with tempfile.TemporaryDirectory(prefix='pcirn-smtp-') as temp:
            root = provisioned_deployment(temp)
            (root / 'smtp.env').write_text(
                'mail__P__server=smtp.institucional.example\n'
                'mail__P__server__P__port=587\n'
                'mail__P__from__P__address=no-reply@example.org\n')
            rendered = render_config(root, installer_environment(root))
            environment = service_environment(rendered, 'dspace')
            self.assertEqual(environment.get('mail__P__server'),
                             'smtp.institucional.example')
            self.assertEqual(environment.get('mail__P__server__P__port'), '587')


class GeneratedComposeTests(unittest.TestCase):
    """The Compose file the installer writes must actually interpolate."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='pcirn-compose-')
        self.addCleanup(self.temp.cleanup)
        self.root = provisioned_deployment(self.temp.name)

    @unittest.skipUnless(REAL_DOCKER, 'docker not available')
    def test_generated_compose_interpolates_with_installer_variables(self):
        # The installer supplies every variable the Compose file requires,
        # otherwise `up` fails before any container starts.
        render_config(self.root, installer_environment(self.root))

    @unittest.skipUnless(REAL_DOCKER, 'docker not available')
    def test_local_cfg_mount_points_at_the_file_the_installer_writes(self):
        rendered = render_config(self.root, installer_environment(self.root))
        mounts = json.dumps(rendered['services']['dspace']['volumes'])
        self.assertIn(str(self.root / 'dspace/config/local.cfg'), mounts)
        # The Solr data directory must be redirected out of the Docker volume.
        self.assertIn(str(self.root / 'data/solr'),
                      json.dumps(rendered['services']['dspacesolr']['volumes']))


class ManualPublicationTests(unittest.TestCase):
    """#9: workflow_dispatch must publish the revision the tag points at."""

    def version_step(self):
        for step in workflow_jobs()['validate']['steps']:
            if step.get('id') == 'version':
                return step
        self.fail('the validate job has no version step')

    def git(self, repository, *args):
        return subprocess.run(['git', *args], cwd=repository, check=True,
                              capture_output=True, text=True).stdout.strip()

    def test_manual_dispatch_resolves_the_tag_and_not_the_branch_head(self):
        with tempfile.TemporaryDirectory(prefix='pcirn-tag-') as temp:
            repository = Path(temp) / 'repository'
            repository.mkdir()
            self.git(repository, 'init', '-q')
            self.git(repository, 'config', 'user.email', 'nti@example.org')
            self.git(repository, 'config', 'user.name', 'NTI')
            (repository / 'file').write_text('published\n')
            self.git(repository, 'add', 'file')
            self.git(repository, 'commit', '-qm', 'published')
            tagged = self.git(repository, 'rev-parse', 'HEAD')
            self.git(repository, 'tag', '-a', 'v1.0.0', '-m', 'release')
            (repository / 'file').write_text('later work\n')
            self.git(repository, 'commit', '-qam', 'later')
            head = self.git(repository, 'rev-parse', 'HEAD')
            self.assertNotEqual(tagged, head, 'the fixture must separate tag and branch')

            output = Path(temp) / 'github-output'
            output.write_text('')
            process = subprocess.run(
                ['bash', '-c', self.version_step()['run']], cwd=repository,
                text=True, capture_output=True,
                env=dict(os.environ, INPUT_TAG='v1.0.0', GITHUB_REF_NAME='main',
                         GITHUB_REF='refs/heads/main', GITHUB_OUTPUT=str(output)))
            self.assertEqual(process.returncode, 0, process.stderr)
            values = dict(line.split('=', 1) for line in output.read_text().splitlines()
                          if '=' in line)
            self.assertEqual(values.get('version'), 'v1.0.0')
            self.assertEqual(values.get('ref'), 'refs/tags/v1.0.0',
                             'a manual publication must resolve the tag to build')
            self.assertEqual(self.git(repository, 'rev-parse', 'refs/tags/v1.0.0^{commit}'),
                             tagged)

    def test_tag_push_resolves_its_own_ref(self):
        with tempfile.TemporaryDirectory(prefix='pcirn-tag-') as temp:
            repository = Path(temp) / 'repository'
            repository.mkdir()
            self.git(repository, 'init', '-q')
            self.git(repository, 'config', 'user.email', 'nti@example.org')
            self.git(repository, 'config', 'user.name', 'NTI')
            (repository / 'file').write_text('published\n')
            self.git(repository, 'add', 'file')
            self.git(repository, 'commit', '-qm', 'published')
            self.git(repository, 'tag', 'v2.0.0')
            output = Path(temp) / 'github-output'
            output.write_text('')
            process = subprocess.run(
                ['bash', '-c', self.version_step()['run']], cwd=repository,
                text=True, capture_output=True,
                env=dict(os.environ, INPUT_TAG='', GITHUB_REF_NAME='v2.0.0',
                         GITHUB_REF='refs/tags/v2.0.0', GITHUB_OUTPUT=str(output)))
            self.assertEqual(process.returncode, 0, process.stderr)
            values = dict(line.split('=', 1) for line in output.read_text().splitlines()
                          if '=' in line)
            self.assertEqual(values.get('version'), 'v2.0.0')
            self.assertEqual(values.get('ref'), 'refs/tags/v2.0.0')

    def test_every_job_builds_the_resolved_ref(self):
        jobs = workflow_jobs()
        for job in ('build', 'manifest'):
            checkouts = [step for step in jobs[job]['steps']
                         if str(step.get('uses', '')).startswith('actions/checkout')]
            self.assertTrue(checkouts, f'{job} does not check out the code')
            for step in checkouts:
                self.assertEqual(step.get('with', {}).get('ref'),
                                 '${{ needs.validate.outputs.ref }}',
                                 f'{job} must build the revision that was resolved, '
                                 'not the branch the workflow was started from')

    def test_validation_runs_on_the_published_revision(self):
        steps = workflow_jobs()['validate']['steps']
        checkouts = [step for step in steps
                     if str(step.get('uses', '')).startswith('actions/checkout')]
        self.assertEqual(len(checkouts), 2,
                         'resolve the tag first, then check out the revision it names')
        self.assertEqual(checkouts[-1].get('with', {}).get('ref'),
                         '${{ steps.version.outputs.ref }}')
        names = [step.get('name') for step in steps]
        self.assertLess(names.index(checkouts[-1]['name']),
                        names.index('Build and run the unit tests'),
                        'the build gate must test the published revision')

    def test_release_manifest_records_the_checked_out_commit(self):
        steps = workflow_jobs()['manifest']['steps']
        generate = next(step for step in steps
                        if step.get('name') == 'Generate the release manifest')
        # GITHUB_SHA is the branch tip under workflow_dispatch; the manifest must
        # record what was actually built.
        self.assertIn('git rev-parse HEAD', generate['run'])
        self.assertNotIn('GITHUB_SHA', generate['run'])


if __name__ == '__main__':
    unittest.main()

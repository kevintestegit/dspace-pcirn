#!/usr/bin/env python3
"""Administrative operations for a dedicated NTI deployment (Linux, Python 3.9+)."""
from contextlib import ExitStack
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

# Also allows tests that load this file through importlib to resolve siblings.
_SOURCE_DIR = str(Path(__file__).resolve().parent)
if _SOURCE_DIR not in sys.path:
    sys.path.insert(0, _SOURCE_DIR)

from pcirn_config import (
    DIGEST,
    IMAGE_KEYS,
    SERVICES,
    VERSION,
    Error,
    configuration,
    manifest,
    pg_environment,
    read_json,
    require_compose,
    require_pg_clients,
    require_tools,
    validate_history,
    write_json,
    write_text,
)

SOURCE = Path(__file__).resolve().parents[2]


class Deployment:
    def __init__(self, root, config=None):
        self.root = Path(root).absolute()
        if self.root.is_symlink() or self.root.resolve() != self.root:
            raise Error('Diretório de instalação não pode conter links simbólicos')
        self.config = config if config is not None else configuration(self.root / 'config.json')
        self.env = {k: v for k, v in os.environ.items()
                    if k == 'DOCKER_CONFIG'
                    or not k.startswith(('COMPOSE_', 'DOCKER_', 'PG', 'DSPACE_', 'DB_'))}
        self.env.update(pg_environment(self.config))

    def run(self, args, capture=True, pg=False, timeout=None, stdout_file=None):
        if args[0] == 'docker':
            args = ['docker', '--context', 'default', *args[1:]]
        env = self.env.copy()
        if not pg:
            env = {k: v for k, v in env.items() if not k.startswith('PG')}
        process = subprocess.Popen(args, env=env, text=True,
                                   stdout=stdout_file if stdout_file is not None else
                                   subprocess.PIPE if capture else None,
                                   stderr=subprocess.PIPE if capture else None)
        try:
            output, _ = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            raise Error(f'{Path(args[0]).name}: tempo limite excedido')
        except KeyboardInterrupt:
            process.terminate()
            try:
                process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
            raise
        if process.returncode:
            # Tools may echo URLs/passwords. Never relay unfiltered stderr.
            raise Error(f'{Path(args[0]).name}: falha (código {process.returncode})')
        return output if capture else ''

    def current(self):
        return manifest(self.root / 'release.json')

    def compose(self, release, *args, capture=True):
        values = self.config | dict(zip(('DSPACE_IMAGE', 'SOLR_IMAGE', 'ANGULAR_IMAGE'),
                                        (release['images'][k] for k in IMAGE_KEYS)))
        values.update(ASSETSTORE_PATH=str(self.root / 'data/assetstore'),
                      SOLR_DATA_PATH=str(self.root / 'data/solr'))
        with tempfile.NamedTemporaryFile(mode='w', dir=self.root, prefix='.env-') as envfile, \
                ExitStack() as files:
            certificates = {path for key, path in pg_environment(self.config).items()
                            if key in ('PGSSLROOTCERT', 'PGSSLCERT', 'PGSSLKEY')}
            mounts = [{'type': 'bind', 'source': path.replace('$', '$$'),
                       'target': path.replace('$', '$$'), 'read_only': True,
                       'bind': {'create_host_path': False}}
                      for path in sorted(certificates)]
            overrides = []
            if mounts:
                tls = files.enter_context(tempfile.NamedTemporaryFile(
                    mode='w', dir=self.root, prefix='.tls-', suffix='.json'))
                json.dump({'services': {'dspace': {'volumes': mounts}}}, tls)
                tls.flush()
                overrides = ['-f', tls.name]
            saved_env = self.env
            # An empty env-file prevents implicit .env loading; process env preserves secrets literally.
            self.env = self.env | values
            project = 'dspacepcirn-' + hashlib.sha256(str(self.root).encode()).hexdigest()[:12]
            try:
                return self.run(['docker', 'compose', '--project-name', project,
                                 '--project-directory', str(self.root), '--env-file', envfile.name,
                                 '-f', str(self.root / 'compose.yml'), *overrides, *args], capture=capture)
            finally:
                self.env = saved_env

    def doctor(self):
        require_tools()
        require_compose(self)
        self.run(['docker', 'info'])
        server = int(self.sql('SHOW server_version_num;')) // 10000
        require_pg_clients(self, server)
        self.compose(self.current(), 'config', '--quiet')
        print('doctor: Docker, Compose, PostgreSQL TLS e configuração OK')

    def sql(self, query):
        return self.run(['psql', '-X', '-q', '--no-password', '-At', '-v', 'ON_ERROR_STOP=1',
                         '-c', 'BEGIN READ ONLY; ' + query + ' COMMIT;'], pg=True, timeout=30).strip()

    def pending(self, release):
        history = 'fresh_migrations' if self.config.get('DB_PROFILE') == 'fresh' else 'migrations'
        if history not in release['database']:
            raise Error('Manifesto não suporta o perfil do banco; nenhuma migration executada')
        table = self.sql("SELECT to_regclass('public.schema_version') IS NOT NULL;")
        if table == 'f':
            if self.user_objects() != 0:
                raise Error('Banco sem histórico Flyway deve estar vazio; avaliação NTI necessária')
            return True
        if table != 't':
            raise Error('Resposta inesperada ao consultar histórico Flyway')
        rows = json.loads(self.sql('SELECT COALESCE(json_agg(row_to_json(h)),\'[]\'::json) '
                                   'FROM (SELECT version, script, checksum, success '
                                   'FROM public.schema_version) h;'))
        expected = {m['version']: m for m in release['database'][history]}
        applied = set()
        for row in rows:
            if row['version'] is None or not row['success']:
                raise Error('Histórico repetível/falho requer avaliação NTI')
            wanted = expected.get(row['version'])
            if not wanted or any(row[k] != wanted[k] for k in ('script', 'checksum')):
                raise Error('Histórico Flyway divergente do manifesto; nenhuma migration executada')
            if row['version'] in applied:
                raise Error('Histórico Flyway contém versão duplicada')
            applied.add(row['version'])
        return bool(set(expected) - applied)

    def user_objects(self):
        """Count user schemas and objects; an empty database may contain only system objects."""
        return int(self.sql("WITH namespaces AS (SELECT oid, nspname FROM pg_namespace "
                            "WHERE nspname !~ '^pg_' AND nspname <> 'information_schema'), "
                            "objects AS (SELECT oid AS namespace FROM namespaces WHERE nspname <> 'public' "
                            "UNION ALL SELECT relnamespace FROM pg_class "
                            "UNION ALL SELECT pronamespace FROM pg_proc "
                            "UNION ALL SELECT typnamespace FROM pg_type "
                            "UNION ALL SELECT extnamespace FROM pg_extension) "
                            "SELECT count(*) AS user_object_count FROM objects "
                            "JOIN namespaces ON namespaces.oid=objects.namespace;"))

    def healthy(self, release):
        output = self.compose(release, 'ps', '--all', '--format', 'json').strip()
        try:
            rows = json.loads(output or '[]')
        except json.JSONDecodeError:
            rows = [json.loads(line) for line in output.splitlines()]
        if isinstance(rows, dict):
            rows = [rows]
        states = {row['Service']: row for row in rows}
        if any(s not in states or states[s].get('State') != 'running'
               or states[s].get('Health') != 'healthy' for s in SERVICES):
            raise Error('health: todos os três serviços devem estar running/healthy')
        if self.sql('SELECT 1;') != '1':
            raise Error('health: resposta inesperada do PostgreSQL')
        print('health: aplicação, Solr, frontend e PostgreSQL OK')

    def up(self, release):
        self.compose(release, 'up', '-d', '--wait', '--wait-timeout', '600')
        self.healthy(release)

    def stop(self, release):
        self.compose(release, 'stop', '--timeout', '60')

    def backup(self, release, restart=True):
        try:
            self.stop(release)
            directory = Path(tempfile.mkdtemp(prefix='.incomplete-', dir=self.root / 'backups'))
            self.run(['pg_dump', '--no-password', '--format=custom', '--no-owner',
                      '--no-acl', '--file', str(directory / 'database.dump')], pg=True)
            self.run(['pg_restore', '--list', str(directory / 'database.dump')])
            for name in ('assetstore', 'solr'):
                with tarfile.open(directory / f'{name}.tar.gz', 'w:gz') as archive:
                    archive.add(self.root / 'data' / name, arcname=name)
            write_json(directory / 'release.json', release)
            metadata = {'db_url': self.config['DB_URL'],
                        'db_user': self.config['DB_USERNAME'], 'root': str(self.root)}
            if self.config.get('DB_PROFILE') == 'fresh':
                metadata['database_profile'] = 'fresh'
            write_json(directory / 'metadata.json', metadata)
            names = ('database.dump', 'assetstore.tar.gz', 'solr.tar.gz', 'release.json', 'metadata.json')
            write_json(directory / 'checksums.json', {n: checksum(directory / n) for n in names})
            verified_backup(directory, self)
            final = directory.with_name(directory.name.replace('.incomplete-', 'backup-'))
            directory.rename(final)
            print(f'backup: {final}')
            return final
        finally:
            if restart:
                self.up(release)

    def deploy(self, target, authorize, initial=False):
        old = self.current()
        if old == target and (self.root / 'installed.json').exists():
            self.healthy(old)
            print('update: versão já instalada')
            return
        needs_migration = self.pending(target)
        if needs_migration and not authorize:
            raise Error('Migrations necessárias: repita com --authorize-migrations')
        self.compose(target, 'pull')
        journal = {'previous': old, 'target': target, 'backup': None, 'migration_started': False}
        write_json(self.root / 'operation.json', journal)
        try:
            journal['backup'] = str(self.backup(old, restart=False))
            write_json(self.root / 'operation.json', journal)
            if needs_migration:
                journal['migration_started'] = True
                write_json(self.root / 'operation.json', journal)
                self.compose(target, 'run', '--rm', '--no-deps', '-T', '--entrypoint',
                             '/dspace/bin/dspace', 'dspace', 'database', 'migrate')
                if self.pending(target):
                    raise Error('Migrations incompletas: aplicação permanece parada')
            self.up(target)
            write_json(self.root / 'release.json', target)
            write_json(self.root / 'installed.json', {'version': target['version']})
            write_json(self.root / 'previous.json', journal)
            (self.root / 'operation.json').unlink()
            print(f"{'install' if initial else 'update'}: {target['version']}")
        except (Error, OSError, KeyboardInterrupt, ValueError, tarfile.TarError):
            if initial:
                (self.root / 'installed.json').unlink(missing_ok=True)
                self.stop(target)
            elif not journal['migration_started']:
                try:
                    write_json(self.root / 'release.json', old)
                    if (self.root / 'installed.json').exists():
                        write_json(self.root / 'installed.json', {'version': old['version']})
                    self.up(old)
                    (self.root / 'operation.json').unlink()
                except (Error, OSError):
                    print('Recuperação falhou; operation.json preservado', file=sys.stderr)
            else:
                self.stop(target)
                print('Migration iniciada: restore/rollback exige --authorize-restore; '
                      f"backup={journal['backup']}", file=sys.stderr)
            raise

    def restore(self, directory, authorize):
        if not authorize:
            raise Error('Restore substitui banco/dados: --authorize-restore obrigatório')
        release = verified_backup(directory, self)
        self.compose(release, 'pull')
        journal_file = self.root / 'operation.json'
        prior = read_json(journal_file) if journal_file.exists() else {}
        safety = prior.get('backup') if prior.get('restore') else None
        if safety:
            verified_backup(Path(safety), self)
        journal = {'restore': str(directory), 'backup': safety}
        write_json(journal_file, journal)
        staging = self.root
        try:
            if not safety:
                journal['backup'] = str(self.backup(self.current(), restart=False))
                write_json(journal_file, journal)
            staging = Path(tempfile.mkdtemp(prefix='.restore-', dir=self.root))
            journal['staging'] = str(staging)
            write_json(journal_file, journal)
            for name in ('assetstore', 'solr'):
                with tarfile.open(directory / f'{name}.tar.gz') as archive:
                    archive.extractall(staging)
            self.run(['pg_restore', '--clean', '--if-exists', '--no-owner', '--no-acl', '--file',
                      str(staging / 'database.sql'), str(directory / 'database.dump')])
            (staging / 'reset.sql').write_text('DROP SCHEMA public CASCADE; CREATE SCHEMA public;\n')
            # pg_restore --clean alone leaves tables introduced after the backup.
            self.run(['psql', '-X', '--no-password', '--single-transaction', '-v',
                      'ON_ERROR_STOP=1', '-f', str(staging / 'reset.sql'),
                      '-f', str(staging / 'database.sql')], pg=True)
            for name in ('assetstore', 'solr'):
                target = self.root / 'data' / name
                if target.exists():
                    target.rename(staging / f'{name}.previous')
                (staging / name).rename(target)
            self.up(release)
            write_json(self.root / 'release.json', release)
            write_json(self.root / 'installed.json', {'version': release['version']})
            (self.root / 'operation.json').unlink()
            print(f'restore: OK; dados anteriores preservados em {staging}')
        except (Error, OSError, KeyboardInterrupt, ValueError, tarfile.TarError):
            self.stop(release)
            print(f'Restore incompleto; aplicação parada. Dados em {staging}', file=sys.stderr)
            raise


def checksum(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def verified_backup(directory, deployment):
    directory = Path(directory)
    expected = {'database.dump', 'assetstore.tar.gz', 'solr.tar.gz', 'release.json', 'metadata.json'}
    hashes = read_json(directory / 'checksums.json')
    if set(hashes) != expected or any(checksum(directory / n) != hashes[n] for n in expected):
        raise Error('Backup incompleto ou checksum divergente')
    metadata = read_json(directory / 'metadata.json')
    expected_metadata = {'db_url': deployment.config['DB_URL'],
                         'db_user': deployment.config['DB_USERNAME'], 'root': str(deployment.root)}
    if deployment.config.get('DB_PROFILE') == 'fresh':
        expected_metadata['database_profile'] = 'fresh'
    if metadata != expected_metadata:
        raise Error('Backup pertence a outra instalação/banco')
    for name in ('assetstore', 'solr'):
        with tarfile.open(directory / f'{name}.tar.gz') as archive:
            for item in archive:
                parts = Path(item.name).parts
                if (not parts or parts[0] != name or '..' in parts
                        or not (item.isfile() or item.isdir())):
                    raise Error('Archive contém caminho/link/dispositivo inseguro')
    deployment.run(['pg_restore', '--list', str(directory / 'database.dump')])
    return manifest(directory / 'release.json')


def source_file(name, fallback):
    candidate = Path(__file__).with_name(name)
    return candidate if candidate.exists() else SOURCE / fallback


def management_files():
    """Files installed under ROOT/bin; refreshed on install and update."""
    source = Path(__file__).resolve().parent
    compose_source = source_file('compose.template.yml', 'docker-compose.yml')
    smtp_source = source_file('smtp.env.example', 'smtp.env.example')
    return {
        'bin/pcirn.py': Path(__file__).read_text(),
        'bin/pcirn_config.py': (source / 'pcirn_config.py').read_text(),
        'bin/pcirn_cli.py': (source / 'pcirn_cli.py').read_text(),
        'bin/data_migration.py': (source / 'data_migration.py').read_text(),
        'bin/preflight.py': (source / 'preflight.py').read_text(),
        'bin/dspacepcirn': (source / 'dspacepcirn').read_text(),
        'bin/compose.template.yml': compose_source.read_text(),
        'bin/smtp.env.example': smtp_source.read_text(),
    }


def refresh_management(root):
    root = Path(root)
    for relative, content in management_files().items():
        path = root / relative
        if path.exists() and path.read_text() == content:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        write_text(path, content, 0o700 if path.name == 'dspacepcirn' else 0o600)


def provision(args):
    root = Path(args.root).absolute()
    if root == Path('/') or root.resolve() != root:
        raise Error('Use um diretório dedicado sem links simbólicos')
    config = configuration(args.config) if args.config else None
    release = manifest(args.manifest)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not (root / 'config.json').exists():
        if config is None:
            raise Error('Primeira instalação exige --config fornecido pelo NTI')
        write_json(root / 'config.json', config)
    elif config is not None and config != configuration(root / 'config.json'):
        raise Error('Configuração existente diverge; nada sobrescrito')
    compose_source = source_file('compose.template.yml', 'docker-compose.yml')
    # The generated Compose file loads <root>/smtp.env, so the file has to exist
    # before the first `up`. It is seeded from the repository template, which
    # leaves mail explicitly disabled; mail settings are the NTI's to fill in.
    smtp_source = source_file('smtp.env.example', 'smtp.env.example')
    compose = compose_source.read_text().replace('- solr_data:/var/solr/data',
                                                '- ${SOLR_DATA_PATH}:/var/solr/data')
    if '- ${SOLR_DATA_PATH}:/var/solr/data' not in compose:
        raise Error('Template do Compose sem o volume solr_data esperado')
    compose = compose.replace('db__P__username:', 'db__P__schema: public\n      db__P__username:')
    if 'db__P__schema: public' not in compose:
        raise Error('Template do Compose sem db__P__username esperado')
    if config and config.get('DB_PROFILE') == 'fresh':
        compose = compose.replace('db__P__schema: public',
                                  'db__P__schema: public\n      db__P__pcirn__P__profile: fresh')
    files = {root / 'compose.yml': compose,
             root / 'smtp.env': smtp_source.read_text(),
             root / 'dspace/config/local.cfg': 'db.schema = public\n' +
             ('db.pcirn.profile = fresh\n' if config and config.get('DB_PROFILE') == 'fresh' else '')}
    for path, content in files.items():
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        write_text(path, content)
    refresh_management(root)
    for name in ('assetstore', 'solr'):
        (root / 'data' / name).mkdir(parents=True, exist_ok=True)
    (root / 'backups').mkdir(exist_ok=True, mode=0o700)
    if not (root / 'release.json').exists():
        write_json(root / 'release.json', release)
    elif manifest(root / 'release.json') != release:
        raise Error('Versão existente diverge: use update')
    return Deployment(root)


if __name__ == '__main__':
    import sys

    sys.modules['pcirn'] = sys.modules[__name__]
    from pcirn_cli import run

    sys.exit(run())

#!/usr/bin/env python3
"""Administrative operations for a dedicated NTI deployment (Linux, Python 3.9+)."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
from urllib.parse import parse_qsl, urlsplit

SERVICES = ('dspace', 'dspacesolr', 'dspace-angular')
IMAGE_KEYS = ('backend', 'solr', 'frontend')
DIGEST = re.compile(r'ghcr\.io/[a-z0-9._/-]+@sha256:[a-f0-9]{64}\Z')
VERSION = re.compile(r'[0-9]+\.[0-9]+\.[0-9]+(?:-[a-zA-Z0-9.-]+)?\Z')
SOURCE = Path(__file__).resolve().parents[2]


class Error(Exception):
    """An operation could not safely finish."""


def read_json(path):
    with Path(path).open() as stream:
        return json.load(stream)


def write_json(path, value):
    path = Path(path)
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(value, stream, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def manifest(path):
    data = read_json(path)
    if data.get('schema_version') != 1 or not VERSION.fullmatch(data.get('version', '')):
        raise Error('Manifesto: schema_version=1 e version SemVer obrigatórios')
    if set(data.get('images', {})) != set(IMAGE_KEYS):
        raise Error('Manifesto: imagens backend, solr e frontend obrigatórias')
    if any(not DIGEST.fullmatch(data['images'][key]) for key in IMAGE_KEYS):
        raise Error('Imagens devem usar ghcr.io/repository@sha256:<64 hex>, sem tags')
    migrations = data.get('database', {}).get('migrations')
    if not isinstance(migrations, list) or not migrations:
        raise Error('Manifesto: database.migrations deve listar o histórico Flyway esperado')
    versions = set()
    for item in migrations:
        if (set(item) != {'version', 'script', 'checksum'}
                or not re.fullmatch(r'\d+(?:\.\d+)*', item['version'])
                or not isinstance(item['script'], str)
                or (item['checksum'] is not None and type(item['checksum']) is not int)
                or item['version'] in versions):
            raise Error('Manifesto: migration inválida/duplicada')
        versions.add(item['version'])
    return data


def configuration(path):
    path = Path(path)
    if path.stat().st_mode & 0o077:
        raise Error('Configuração contém credenciais: execute chmod 600')
    data = read_json(path)
    required = {'DB_URL', 'DB_USERNAME', 'DB_PASSWORD', 'PUBLIC_UI_URL',
                'PUBLIC_REST_URL', 'PUBLIC_REST_HOST'}
    if set(data) - required or not required <= set(data):
        raise Error('Configuração: informe apenas DB_* e PUBLIC_* documentados')
    if any(not isinstance(v, str) or not v or any(c in v for c in '\n\r\x00')
           for v in data.values()):
        raise Error('Configuração: valores devem ser strings não vazias em uma linha')
    for key in ('PUBLIC_UI_URL', 'PUBLIC_REST_URL'):
        url = urlsplit(data[key])
        if url.scheme != 'https' or not url.hostname or url.username:
            raise Error('URLs públicas devem usar HTTPS')
    if (urlsplit(data['PUBLIC_REST_URL']).hostname != data['PUBLIC_REST_HOST']
            or urlsplit(data['PUBLIC_REST_URL']).path != '/server'):
        raise Error('PUBLIC_REST_HOST deve corresponder à URL REST terminada em /server')
    pg_environment(data)
    return data


def pg_environment(config):
    if not config['DB_URL'].startswith('jdbc:postgresql://'):
        raise Error('DB_URL deve ser jdbc:postgresql://host:porta/banco?sslmode=...')
    url = urlsplit(config['DB_URL'][5:])
    if not url.hostname or url.username or not re.fullmatch(r'/[A-Za-z0-9_-]+', url.path):
        raise Error('DB_URL inválida; use um host e um banco dedicado')
    params = dict(parse_qsl(url.query, strict_parsing=True))
    mapping = {'sslmode': 'PGSSLMODE', 'sslrootcert': 'PGSSLROOTCERT',
               'sslcert': 'PGSSLCERT', 'sslkey': 'PGSSLKEY'}
    if set(params) - set(mapping):
        raise Error('Parâmetro JDBC não suportado pelos clientes PostgreSQL')
    if params.get('sslmode') not in ('require', 'verify-ca', 'verify-full'):
        raise Error('DB_URL deve especificar sslmode=require, verify-ca ou verify-full')
    return dict(PGHOST=url.hostname, PGPORT=str(url.port or 5432), PGDATABASE=url.path[1:],
                PGUSER=config['DB_USERNAME'], PGPASSWORD=config['DB_PASSWORD'],
                PGSSLMODE=params.get('sslmode', 'verify-full'), PGCONNECT_TIMEOUT='10',
                **{mapping[k]: v for k, v in params.items() if k != 'sslmode'})


class Deployment:
    def __init__(self, root, config=None):
        self.root = Path(root).absolute()
        if self.root.is_symlink() or self.root.resolve() != self.root:
            raise Error('Diretório de instalação não pode conter links simbólicos')
        self.config = config if config is not None else configuration(self.root / 'config.json')
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith(('COMPOSE_', 'DOCKER_', 'PG', 'DSPACE_', 'DB_'))}
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
        with tempfile.NamedTemporaryFile(mode='w', dir=self.root, prefix='.env-') as envfile:
            saved_env = self.env
            # An empty env-file prevents implicit .env loading; process env preserves secrets literally.
            self.env = self.env | values
            project = 'dspacepcirn-' + hashlib.sha256(str(self.root).encode()).hexdigest()[:12]
            try:
                return self.run(['docker', 'compose', '--project-name', project,
                                 '--project-directory', str(self.root), '--env-file', envfile.name,
                                 '-f', str(self.root / 'compose.yml'), *args], capture=capture)
            finally:
                self.env = saved_env

    def doctor(self):
        for tool in ('docker', 'psql', 'pg_dump', 'pg_restore'):
            if not shutil.which(tool):
                raise Error(f'Pré-requisito ausente: {tool}')
        compose_version = self.run(['docker', 'compose', 'version', '--short']).strip().lstrip('v')
        if tuple(int(n) for n in compose_version.split('.')[:2]) < (2, 20):
            raise Error('Docker Compose >= 2.20 obrigatório')
        self.run(['docker', 'info'])
        server = int(self.sql('SHOW server_version_num;')) // 10000
        for tool in ('pg_dump', 'pg_restore'):
            client = re.search(r'(\d+)\.', self.run([tool, '--version']))
            if not client or int(client[1]) != server:
                raise Error('pg_dump/pg_restore devem ter o mesmo major do PostgreSQL externo')
        self.compose(self.current(), 'config', '--quiet')
        print('doctor: Docker, Compose, PostgreSQL TLS e configuração OK')

    def sql(self, query):
        return self.run(['psql', '-X', '-q', '--no-password', '-At', '-v', 'ON_ERROR_STOP=1',
                         '-c', 'BEGIN READ ONLY; ' + query + ' COMMIT;'], pg=True, timeout=30).strip()

    def pending(self, release):
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
        expected = {m['version']: m for m in release['database']['migrations']}
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
            write_json(directory / 'metadata.json', {'db_url': self.config['DB_URL'],
                       'db_user': self.config['DB_USERNAME'], 'root': str(self.root)})
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
    if metadata != {'db_url': deployment.config['DB_URL'],
                    'db_user': deployment.config['DB_USERNAME'], 'root': str(deployment.root)}:
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
    compose_source = Path(__file__).with_name('compose.template.yml')
    if not compose_source.exists():
        compose_source = SOURCE / 'docker-compose.yml'
    # The generated Compose file loads <root>/smtp.env, so the file has to exist
    # before the first `up`. It is seeded from the repository template, which
    # leaves mail explicitly disabled; mail settings are the NTI's to fill in.
    smtp_source = Path(__file__).with_name('smtp.env.example')
    if not smtp_source.exists():
        smtp_source = SOURCE / 'smtp.env.example'
    compose = compose_source.read_text().replace('- solr_data:/var/solr/data',
                                                '- ${SOLR_DATA_PATH}:/var/solr/data')
    compose = compose.replace('db__P__username:', 'db__P__schema: public\n      db__P__username:')
    files = {root / 'compose.yml': compose,
             root / 'smtp.env': smtp_source.read_text(),
             root / 'dspace/config/local.cfg': 'db.schema = public\n',
             root / 'bin/pcirn.py': Path(__file__).read_text(),
             root / 'bin/data_migration.py': Path(__file__).with_name('data_migration.py').read_text(),
             root / 'bin/preflight.py': Path(__file__).with_name('preflight.py').read_text(),
             root / 'bin/dspacepcirn': Path(__file__).with_name('dspacepcirn').read_text(),
             root / 'bin/compose.template.yml': compose_source.read_text(),
             # Kept so a later provision from the installed copy can still seed
             # smtp.env, exactly like the Compose template above.
             root / 'bin/smtp.env.example': smtp_source.read_text()}
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(content)
            path.chmod(0o700 if path.name == 'dspacepcirn' else 0o600)
    for name in ('assetstore', 'solr'):
        (root / 'data' / name).mkdir(parents=True, exist_ok=True)
    (root / 'backups').mkdir(exist_ok=True, mode=0o700)
    if not (root / 'release.json').exists():
        write_json(root / 'release.json', release)
    elif manifest(root / 'release.json') != release:
        raise Error('Versão existente diverge: use update')
    return Deployment(root)


def main(argv=None):
    os.umask(0o077)
    parser = argparse.ArgumentParser(description='Administração PCIRN / NTI')
    parser.add_argument('command', choices=('install', 'update', 'status', 'version', 'doctor',
                                          'health', 'logs', 'backup', 'restore', 'rollback',
                                          'export-data', 'migrate-data', 'verify-data'))
    parser.add_argument('--root', default='/srv/dspacepcirn')
    parser.add_argument('--manifest')
    parser.add_argument('--config')
    parser.add_argument('--backup', type=Path)
    parser.add_argument('--authorize-migrations', action='store_true')
    parser.add_argument('--authorize-restore', action='store_true')
    parser.add_argument('--follow', action='store_true')
    parser.add_argument('--data-package', type=Path)
    parser.add_argument('--expected', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    if args.command in ('install', 'update') and not args.manifest:
        parser.error('install/update exige --manifest')
    if args.command == 'restore' and not args.backup:
        parser.error('restore exige --backup')
    if args.command == 'export-data' and not args.output:
        parser.error('export-data exige --output')
    if args.command == 'migrate-data' and not args.data_package:
        parser.error('migrate-data exige --data-package')
    if args.data_package and args.command not in ('install', 'migrate-data'):
        parser.error('--data-package vale apenas para install/migrate-data')
    root = Path(args.root).absolute()
    if root == Path('/') or root.resolve() != root:
        raise Error('Use um diretório dedicado sem links simbólicos')
    if args.command == 'install' or (args.command == 'migrate-data' and args.manifest):
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
    for relative in ('config.json', '.lock', 'compose.yml', 'smtp.env', 'release.json',
                     'operation.json', 'installed.json', 'previous.json', 'bin',
                     'bin/dspacepcirn', 'bin/pcirn.py', 'bin/preflight.py',
                     'bin/data_migration.py', 'data-verification.json', 'data-import.json',
                     'bin/compose.template.yml', 'bin/smtp.env.example', 'data',
                     'data/assetstore', 'data/solr', 'backups', 'dspace', 'dspace/config',
                     'dspace/config/local.cfg'):
        path = root / relative
        if path.resolve() != path:
            raise Error('Arquivos/diretórios administrativos não podem ser links simbólicos')
    with (root / '.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise Error('Outra operação administrativa está em execução') from exc
        dep = provision(args) if (args.command == 'install' or
                                  (args.command == 'migrate-data' and args.manifest)) else Deployment(root)
        if (root / 'operation.json').exists() and args.command in ('install', 'update', 'backup',
                                                                 'export-data', 'migrate-data', 'health'):
            raise Error('Operação interrompida: examine operation.json e execute restore/rollback')
        release = dep.current()
        if args.command == 'version':
            print(release['version'])
        elif args.command == 'status':
            print(dep.compose(release, 'ps', '--all'), end='')
            if (root / 'operation.json').exists():
                print('ATENÇÃO: operação pendente em operation.json')
        elif args.command == 'doctor':
            dep.doctor()
        elif args.command == 'health':
            dep.healthy(release)
        elif args.command == 'logs':
            dep.compose(release, 'logs', '--tail', '200', *(['--follow'] if args.follow else []),
                        capture=False)
        elif args.command in ('install', 'update'):
            dep.doctor()
            if args.data_package:
                from data_migration import migrate_data
                migrate_data(dep, args.data_package)
            dep.deploy(manifest(args.manifest), args.authorize_migrations,
                       initial=args.command == 'install')
        elif args.command == 'export-data':
            from data_migration import export_data
            export_data(dep, args.output)
        elif args.command == 'migrate-data':
            from data_migration import migrate_data
            migrate_data(dep, args.data_package)
        elif args.command == 'verify-data':
            from data_migration import verify_data
            verify_data(dep, args.expected, args.output)
        elif args.command == 'backup':
            write_json(root / 'operation.json', {'previous': release, 'backup': None,
                                               'migration_started': False})
            dep.backup(release)
            (root / 'operation.json').unlink()
        elif args.command == 'restore':
            dep.restore(args.backup, args.authorize_restore)
        elif args.command == 'rollback':
            journal_path = root / 'operation.json'
            history = read_json(journal_path if journal_path.exists() else root / 'previous.json')
            if not history.get('backup'):
                if history.get('previous') and not history.get('migration_started'):
                    dep.up(history['previous'])
                    write_json(root / 'release.json', history['previous'])
                    journal_path.unlink()
                else:
                    raise Error('Rollback sem backup disponível: execute restore --backup')
            else:
                dep.restore(Path(history['backup']), args.authorize_restore)
    return 0


if __name__ == '__main__':
    sys.modules['pcirn'] = sys.modules[__name__]
    def interrupted(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    try:
        sys.exit(main())
    except (Error, OSError, ValueError, KeyError, TypeError, tarfile.TarError) as error:
        # Parsing exceptions can include secrets; display only our own safe messages.
        message = str(error) if isinstance(error, Error) else type(error).__name__
        print(f'dspacepcirn: {message}', file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print('dspacepcirn: interrompido; examine status/operation.json', file=sys.stderr)
        sys.exit(130)

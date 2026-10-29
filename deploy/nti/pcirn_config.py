"""Configuration, manifest and file helpers for the NTI installer."""
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from urllib.parse import parse_qsl, urlsplit


SERVICES = ('dspace', 'dspacesolr', 'dspace-angular')
IMAGE_KEYS = ('backend', 'solr', 'frontend')
DIGEST = re.compile(r'ghcr\.io/[a-z0-9._/-]+@sha256:[a-f0-9]{64}\Z')
VERSION = re.compile(r'[0-9]+\.[0-9]+\.[0-9]+(?:-[a-zA-Z0-9.-]+)?\Z')


class Error(Exception):
    """An operation could not safely finish."""


def read_json(path):
    with Path(path).open() as stream:
        return json.load(stream)


def write_json(path, value):
    write_text(path, json.dumps(value, indent=2) + '\n')


def write_text(path, content, mode=0o600):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
            os.chmod(temporary, mode)
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
    database = data.get('database', {})
    fresh = 'fresh_migrations' in database or 'fresh_bootstrap' in database
    if fresh:
        if database.get('fresh_bootstrap') != 'pcirn-fresh-v1' or not database.get('fresh_migrations'):
            raise Error('Manifesto: bootstrap fresh sem capacidade/histórico comprovado')
        validate_history(database['fresh_migrations'], 'database.fresh_migrations')
    if 'migrations' in database:
        validate_history(database['migrations'])
    if not fresh and 'migrations' not in database:
        raise Error('Manifesto: database.migrations ou database.fresh_migrations obrigatório')
    return data


def validate_history(migrations, name='database.migrations'):
    if not isinstance(migrations, list) or not migrations:
        raise Error(f'Manifesto: {name} deve listar o histórico Flyway esperado')
    versions = set()
    for item in migrations:
        if (set(item) != {'version', 'script', 'checksum'}
                or not re.fullmatch(r'\d+(?:\.\d+)*', item['version'])
                or not isinstance(item['script'], str)
                or (item['checksum'] is not None and type(item['checksum']) is not int)
                or item['version'] in versions):
            raise Error('Manifesto: migration inválida/duplicada')
        versions.add(item['version'])


def configuration(path):
    path = Path(path)
    if path.stat().st_mode & 0o077:
        raise Error('Configuração contém credenciais: execute chmod 600')
    data = read_json(path)
    required = {'DB_URL', 'DB_USERNAME', 'DB_PASSWORD', 'PUBLIC_UI_URL',
                'PUBLIC_REST_URL', 'PUBLIC_REST_HOST'}
    if data.get('DB_PROFILE', 'institutional') not in ('fresh', 'institutional'):
        raise Error('DB_PROFILE deve ser fresh ou institutional')
    if set(data) - required - {'DB_PROFILE'} or not required <= set(data):
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
    if params['sslmode'] in ('verify-ca', 'verify-full') and not params.get('sslrootcert'):
        raise Error('Configuração: sslrootcert explícito obrigatório para verificar TLS no host e backend')
    for key in ('sslrootcert', 'sslcert', 'sslkey'):
        if key in params:
            path = Path(params[key])
            if not path.is_absolute() or not path.is_file() or not os.access(path, os.R_OK):
                raise Error('Configuração: certificado PostgreSQL exige arquivo absoluto e legível')
    return dict(PGHOST=url.hostname, PGPORT=str(url.port or 5432), PGDATABASE=url.path[1:],
                PGUSER=config['DB_USERNAME'], PGPASSWORD=config['DB_PASSWORD'],
                PGSSLMODE=params.get('sslmode', 'verify-full'), PGCONNECT_TIMEOUT='10',
                **{mapping[k]: v for k, v in params.items() if k != 'sslmode'})


REQUIRED_TOOLS = ('docker', 'psql', 'pg_dump', 'pg_restore')


def require_tools(prefix=''):
    for tool in REQUIRED_TOOLS:
        if not shutil.which(tool):
            raise Error(f'{prefix}pré-requisito ausente: {tool}')


def require_compose(dep, prefix=''):
    version = dep.run(['docker', 'compose', 'version', '--short'], timeout=30).strip().lstrip('v')
    try:
        major = tuple(int(part) for part in version.split('.')[:2])
    except ValueError as exc:
        raise Error(f'{prefix}versão do Docker Compose inválida: {version}') from exc
    if major < (2, 20):
        raise Error(f'{prefix}Docker Compose >= 2.20 obrigatório')


def require_pg_clients(dep, server_major, prefix='', include_psql=False):
    tools = (('psql',) if include_psql else ()) + ('pg_dump', 'pg_restore')
    for tool in tools:
        client = re.search(r'(\d+)\.', dep.run([tool, '--version'], timeout=30))
        if not client or int(client[1]) != server_major:
            raise Error(
                f'{prefix}{tool} deve ter o mesmo major do PostgreSQL externo'
            )

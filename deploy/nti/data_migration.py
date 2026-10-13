"""Initial import and read-only verification of a quiescent DSpace database."""
import csv
import hashlib
import json
from pathlib import Path
import re
import sys
import tarfile
import tempfile
from uuid import UUID

from pcirn import SERVICES, Error, checksum, manifest, read_json, write_json

REQUIRED_TABLES = {'item', 'bitstream', 'eperson', 'community', 'collection', 'handle',
                   'schema_version', 'resourcepolicy', 'metadatavalue', 'epersongroup'}
PACKAGE_FILES = {'database.dump', 'assetstore.tar.gz', 'solr.tar.gz',
                 'source-report.json', 'release.json'}
csv.field_size_limit(sys.maxsize)


def check_file(root, row):
    """Validate each live bitstream using DSpace's default local storage layout."""
    if row['deleted']:
        return False
    identifier = row['internal_id']
    if row['store_number'] != 0 or not isinstance(identifier, str):
        raise Error('Bitstream requires local assetstore 0')
    if identifier.startswith('-R'):
        relative = Path(identifier[2:])
    else:
        if not identifier.isdigit() or len(identifier) < 6:
            raise Error('Invalid bitstream internal_id')
        relative = Path(identifier[:2], identifier[2:4], identifier[4:6], identifier)
    path = root / relative
    if relative.is_absolute() or '..' in relative.parts or path.resolve() != path:
        raise Error('Unsafe bitstream path')
    if not path.is_file() or path.stat().st_size != row['size_bytes']:
        raise Error('Missing bitstream or size mismatch')
    algorithm = {'MD5': 'md5', 'SHA-1': 'sha1', 'SHA-256': 'sha256'}.get(row['checksum_algorithm'])
    if not algorithm or not row['checksum']:
        raise Error('Missing bitstream checksum or unsupported algorithm')
    digest = hashlib.new(algorithm)
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    if digest.hexdigest().lower() != row['checksum'].lower():
        raise Error('Bitstream checksum mismatch')
    return True


def snapshot(dep, assetstore, solr, *, local_socket=False):
    """Fingerprint all public table rows, including identifiers, metadata and policies."""
    transport = ('SELECT inet_client_addr() IS NULL;' if local_socket else
                 'SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid();')
    if dep.sql(transport) != 't':
        raise Error('PostgreSQL requires TLS or a verified local socket')
    dep.pending(dep.current())
    names = json.loads(dep.sql("SELECT COALESCE(json_agg(tablename ORDER BY tablename), '[]') "
                               "FROM pg_tables WHERE schemaname='public';"))
    if not REQUIRED_TABLES <= set(names):
        raise Error('Incomplete DSpace database: required tables missing')
    report = {'schema_version': 1, 'tables': {}, 'verified_files': 0}
    if dep.config.get('DB_PROFILE') == 'fresh':
        report['database_profile'] = 'fresh'
    for name in names:
        quoted = '"' + name.replace('"', '""') + '"'
        # COPY CSV preserves JSON escapes; each row is decoded by the CSV reader below.
        query = (f'COPY (SELECT to_jsonb(t)::text FROM public.{quoted} t '
                 'ORDER BY to_jsonb(t)::text COLLATE "C") TO STDOUT WITH (FORMAT csv);')
        with tempfile.TemporaryFile(mode='w+') as stream:
            dep.run(['psql', '-X', '-q', '--no-password', '-v', 'ON_ERROR_STOP=1',
                     '-c', "SET timezone = 'UTC'; SET extra_float_digits = 3; SET bytea_output = 'hex';",
                     '-c', query], pg=True, stdout_file=stream)
            stream.seek(0)
            digest = hashlib.sha256()
            count = 0
            for record in csv.reader(stream):
                digest.update((record[0] + '\n').encode())
                count += 1
                if name == 'bitstream':
                    value = json.loads(record[0])
                    try:
                        if check_file(assetstore, value):
                            report['verified_files'] += 1
                    except Error as error:
                        identifier = str(UUID(value['uuid']))
                        raise Error(f'Bitstream {identifier}: {error}') from error
            report['tables'][name] = {'count': count, 'sha256': digest.hexdigest()}
    report['assetstore'] = tree_fingerprint(assetstore)
    report['solr'] = tree_fingerprint(solr)
    return report


def tree_fingerprint(root):
    digest = hashlib.sha256()
    count = 0
    if not root.is_dir() or root.is_symlink():
        raise Error('Missing or unsafe data directory')
    for path in sorted(root.rglob('*')):
        if path.is_symlink() or not (path.is_dir() or path.is_file()):
            raise Error('Data contains unsafe links or devices')
        if path.is_file():
            digest.update(json.dumps([str(path.relative_to(root)), checksum(path)]).encode())
            count += 1
    return {'count': count, 'sha256': digest.hexdigest()}


def quiescent(dep):
    if dep.compose(dep.current(), 'ps', '--status', 'running', '-q', *SERVICES).strip():
        raise Error('Import requires a stopped application')
    if dep.sql("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() "
               "AND pid <> pg_backend_pid();") != '0':
        raise Error('Suspend all other connections to the dedicated database')


def export_data(dep, output):
    output = Path(output).absolute()
    if output.exists() or output.resolve() != output or dep.root == output or dep.root in output.parents:
        raise Error('Export requires a new directory outside the installation, without symlinks')
    dep.stop(dep.current())
    quiescent(dep)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.export-', dir=output.parent))
    report = verify_data(dep, output=staging / 'source-report.json')
    dep.run(['pg_dump', '--no-password', '--format=custom', '--no-owner', '--no-acl',
             '--file', str(staging / 'database.dump')], pg=True)
    dep.run(['pg_restore', '--list', str(staging / 'database.dump')])
    for name in ('assetstore', 'solr'):
        with tarfile.open(staging / f'{name}.tar.gz', 'w:gz') as archive:
            archive.add(dep.root / 'data' / name, arcname=name)
    if snapshot(dep, dep.root / 'data/assetstore', dep.root / 'data/solr') != report:
        raise Error('Source changed during export; package not published')
    quiescent(dep)
    write_json(staging / 'release.json', dep.current())
    write_json(staging / 'checksums.json', {name: checksum(staging / name) for name in PACKAGE_FILES})
    staging.rename(output)
    print(f'export-data: {output}; application remains stopped')


def verify_data(dep, expected=None, output=None, assetstore=None, solr=None):
    """Persist a private report and return failure if data or files diverge."""
    report_path = output or dep.root / 'data-verification.json'
    try:
        report = snapshot(dep, assetstore or dep.root / 'data/assetstore', solr or dep.root / 'data/solr')
        if expected and report != read_json(expected):
            raise Error('Data differs from the source report')
        write_json(report_path, report)
        print('verify-data: records, Flyway and files OK')
        return report
    except (Error, OSError, ValueError, KeyError, TypeError, csv.Error) as error:
        write_json(report_path, {'status': 'failed',
                                'error': str(error) if isinstance(error, Error) else type(error).__name__})
        if isinstance(error, csv.Error):
            raise Error('Invalid verification CSV') from error
        raise


def migrate_data(dep, package):
    """Restore into an empty dedicated database without starting the application."""
    if (dep.root / 'installed.json').exists() or (dep.root / 'data-import.json').exists():
        raise Error('migrate-data is for initial installation only; no reimport')
    if dep.user_objects() != 0:
        raise Error('Database is not empty; initial import refused')
    if dep.sql('SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid();') != 't':
        raise Error('PostgreSQL connection without TLS')
    quiescent(dep)
    if any((dep.root / 'data' / name).exists() and
           any((dep.root / 'data' / name).iterdir()) for name in ('assetstore', 'solr')):
        raise Error('Initial import requires empty assetstore and Solr')
    package = Path(package).resolve()
    names = PACKAGE_FILES
    hashes = read_json(package / 'checksums.json')
    if set(hashes) != names or any(checksum(package / name) != hashes[name] for name in names):
        raise Error('Package incomplete or checksum mismatch')
    manifest(package / 'release.json')
    expected = read_json(package / 'source-report.json')
    if expected.get('schema_version') != 1 or not REQUIRED_TABLES <= set(expected.get('tables', {})):
        raise Error('Invalid source report')
    profile = expected.get('database_profile', 'institutional')
    if profile not in ('institutional', 'fresh') or profile != dep.config.get('DB_PROFILE', 'institutional'):
        raise Error('Database profile differs from package; configure DB_PROFILE before restore')
    with (package / 'database.dump').open('rb') as stream:
        if stream.read(5) != b'PGDMP':
            raise Error('Dump must use pg_dump -Fc')
    dep.run(['pg_restore', '--list', str(package / 'database.dump')])
    server = int(dep.sql('SHOW server_version_num;')) // 10000
    version = re.search(r'(\d+)\.', dep.run(['pg_restore', '--version']))
    if not version or int(version[1]) != server:
        raise Error('pg_restore must match the PostgreSQL major version')
    journal = {'operation': 'migrate-data', 'status': 'started', 'checksums': hashes}
    write_json(dep.root / 'operation.json', journal)
    try:
        staging = Path(tempfile.mkdtemp(prefix='.migrate-', dir=dep.root))
        journal['staging'] = str(staging)
        write_json(dep.root / 'operation.json', journal)
        for name in ('assetstore', 'solr'):
            with tarfile.open(package / f'{name}.tar.gz') as archive:
                seen = set()
                for member in archive.getmembers():
                    parts = Path(member.name).parts
                    if (not parts or parts[0] != name or '..' in parts
                            or not (member.isfile() or member.isdir()) or parts in seen):
                        raise Error('Archive contains duplicate or unsafe paths, links or devices')
                    seen.add(parts)
                archive.extractall(staging)
            if not (staging / name).is_dir():
                raise Error('Package lacks a required data directory')
        if tree_fingerprint(staging / 'solr') != expected.get('solr'):
            raise Error('Solr statistics differ from the source report')
        quiescent(dep)
        if dep.user_objects():
            raise Error('Database is no longer empty')
        dep.run(['pg_restore', '--no-password', '--no-owner', '--no-acl',
                 '--single-transaction', '--exit-on-error', '--dbname', dep.env['PGDATABASE'],
                 str(package / 'database.dump')], pg=True)
        verify_data(dep, package / 'source-report.json', assetstore=staging / 'assetstore',
                    solr=staging / 'solr')
        for name in ('assetstore', 'solr'):
            target = dep.root / 'data' / name
            if target.exists():
                target.rmdir()
            (staging / name).rename(target)
        write_json(dep.root / 'data-import.json', {'status': 'verified', 'checksums': hashes})
        (dep.root / 'operation.json').unlink()
        print('migrate-data: import verified; application not started')
    except (Error, OSError, ValueError, KeyError, TypeError, csv.Error,
            tarfile.TarError, KeyboardInterrupt) as error:
        journal['status'] = 'failed'
        journal['error'] = str(error) if isinstance(error, Error) else type(error).__name__
        write_json(dep.root / 'operation.json', journal)
        raise

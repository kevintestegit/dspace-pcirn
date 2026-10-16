#!/usr/bin/env python3
"""Export an existing Docker repository privately, without changing its configuration."""
import argparse
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tarfile
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'deploy/nti'))
from pcirn import Deployment, Error, checksum, manifest, secure_ancestors, write_json
from data_migration import PACKAGE_FILES, snapshot

DOCKER = ['docker', '--context', 'default']
SOURCE_SERVICES = {'dspace': 'dspace', 'dspacedb': 'dspacedb',
                   'dspacesolr': 'dspacesolr', 'dspace-angular': 'dspace-angular'}

class Source(Deployment):
    """Read the source over its Unix socket using clients inside its own container."""
    def __init__(self, container, database, username, release):
        self.container, self.database, self.username = container, database, username
        self.release, self.config = release, {}

    def current(self):
        return self.release

    def run(self, args, pg=False, stdout_file=None, **kwargs):
        if not pg or args[0] not in ('psql', 'pg_dump'):
            raise Error('Export permits only PostgreSQL read commands')
        command = [*DOCKER, 'exec', '--user', 'postgres', self.container,
                   args[0], '-h', '/var/run/postgresql', '-U', self.username,
                   '-d', self.database, *args[1:]]
        result = subprocess.run(command, text=True, stdout=stdout_file or subprocess.PIPE,
                                stderr=subprocess.PIPE, check=False, timeout=kwargs.get('timeout'))
        if result.returncode:
            raise Error('Source PostgreSQL command failed; private export incomplete')
        return result.stdout or ''


def export(args):
    os.umask(0o077)
    output = Path(args.output).absolute()
    secure_ancestors(output)
    if output.exists():
        raise Error('Output already exists; nothing overwritten')
    ancestor = output.parent
    while not ancestor.exists():
        ancestor = ancestor.parent
    try:
        git_root = Path(subprocess.check_output(['git', '-C', str(ancestor),
                    'rev-parse', '--show-toplevel'], text=True, stderr=subprocess.DEVNULL).strip()).resolve()
    except subprocess.CalledProcessError:
        git_root = None
    if git_root and (output.resolve() == git_root or git_root in output.resolve().parents):
        raise Error('Private export destination cannot be inside a Git working tree')
    release = manifest(args.manifest)
    endpoint = subprocess.check_output([*DOCKER, 'context', 'inspect', 'default',
                '--format', '{{.Endpoints.docker.Host}}'], text=True).strip()
    if endpoint != 'unix:///var/run/docker.sock':
        raise Error('Private export requires the local Docker Unix socket')
    requested = {'dspace': args.backend, 'dspace-angular': args.frontend,
                 'dspacesolr': args.solr, 'dspacedb': args.postgres}
    names = list(requested.values())
    if (len(set(names)) != 4 or requested != {name: name for name in SOURCE_SERVICES}):
        raise Error('Select the four d9 source containers with their expected service roles')
    rows = json.loads(subprocess.check_output([*DOCKER, 'inspect', *names]))
    if not all(row['State']['Running'] for row in rows):
        raise Error('All source services must be running before export')
    selected = dict(zip((args.backend, args.frontend, args.solr, args.postgres), rows))
    for name, row in selected.items():
        labels = row.get('Config', {}).get('Labels') or {}
        if (row.get('Name') != '/' + name
                or labels.get('com.docker.compose.project') != 'd9'
                or labels.get('com.docker.compose.service') != SOURCE_SERVICES[name]):
            raise Error('Source container identity does not match the d9 stack')
    db_row, app_row = selected['dspacedb'], selected['dspace']
    db_env = dict(value.split('=', 1) for value in db_row['Config'].get('Env', []))
    app_env = dict(value.split('=', 1) for value in app_row['Config'].get('Env', []))
    database, username = db_env.get('POSTGRES_DB', 'postgres'), db_env.get('POSTGRES_USER', 'postgres')
    if args.database != database or args.username != username:
        raise Error('Database or user does not match the inspected d9 container')
    if not re.fullmatch(r'jdbc:postgresql://dspacedb:5432/' + re.escape(database)
                        + r'(?:\?[^#]*)?', app_env.get('db__P__url', '')):
        raise Error('Application JDBC URL does not match the inspected d9 database')
    mounts = (('dspace', '/dspace/assetstore', 'd9_assetstore'),
              ('dspacesolr', '/var/solr/data', 'd9_solr_data'))
    for name, destination, volume in mounts:
        matching = [mount for mount in selected[name].get('Mounts', [])
                    if mount.get('Destination') == destination]
        if len(matching) != 1 or matching[0].get('Type') != 'volume' or matching[0].get('Name') != volume:
            raise Error('Source data volume does not match the d9 stack')
    networks = {name: row.get('NetworkSettings', {}).get('Networks', {}) for name, row in selected.items()}
    if not any('dspacedb' in (networks['dspacedb'][name].get('Aliases') or [])
               for name in set(networks['dspacedb']) & set(networks['dspace'])):
        raise Error('Application and PostgreSQL do not share the expected d9 network')
    ids = [row['Id'] for row in rows]
    dep = Source(ids[3], args.database, args.username, release)
    if dep.pending(release):
        raise Error('Source history must match the target manifest exactly')
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    stage = Path(tempfile.mkdtemp(prefix='.private-export-', dir=output.parent))
    copies = Path(tempfile.mkdtemp(prefix='.private-copy-', dir=output.parent))
    stopped = []
    def interrupted(signum, frame):
        raise Error('Export interrupted; restarting source services')
    handled = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
    previous_handlers = {sig: signal.signal(sig, interrupted) for sig in handled}
    try:
        for identifier in ids[:3]:
            stopped.append(identifier)
            subprocess.run([*DOCKER, 'stop', '--time', '60', identifier],
                           check=True, stdout=subprocess.DEVNULL)
        def ensure_frozen():
            states = json.loads(subprocess.check_output([*DOCKER, 'inspect', *ids]))
            if any(row.get('State', {}).get('Running') is not False for row in states[:3]):
                raise Error('Source application, frontend and Solr must remain stopped during export')
        ensure_frozen()
        if dep.sql('SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() '
                   'AND pid <> pg_backend_pid();') != '0':
            raise Error('Other database connections remain; export refused')
        for name, identifier, path in (('assetstore', ids[0], '/dspace/assetstore'),
                                       ('solr', ids[2], '/var/solr/data')):
            target = copies / name
            target.mkdir(mode=0o700)
            subprocess.run([*DOCKER, 'cp', identifier + ':' + path + '/.', str(target)], check=True)
        ensure_frozen()
        report = snapshot(dep, copies / 'assetstore', copies / 'solr', local_socket=True)
        if int(dep.sql('SHOW server_version_num;')) // 10000 != 15:
            raise Error('Source export requires PostgreSQL 15')
        with (stage / 'database.dump').open('wb') as stream:
            subprocess.run([*DOCKER, 'exec', '--user', 'postgres', ids[3],
                            'pg_dump', '-h', '/var/run/postgresql', '-U', args.username,
                            '-d', args.database, '--format=custom', '--no-owner', '--no-acl'],
                           stdout=stream, check=True)
        with (stage / 'database.dump').open('rb') as stream:
            subprocess.run([*DOCKER, 'exec', '-i', '--user', 'postgres', ids[3],
                            'pg_restore', '--list'], stdin=stream,
                           stdout=subprocess.DEVNULL, check=True)
        if report != snapshot(dep, copies / 'assetstore', copies / 'solr', local_socket=True):
            raise Error('Source changed during export; partial copy preserved privately')
        for name in ('assetstore', 'solr'):
            with tarfile.open(stage / (name + '.tar.gz'), 'w:gz') as archive:
                archive.add(copies / name, arcname=name)
        if dep.sql('SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() '
                   'AND pid <> pg_backend_pid();') != '0':
            raise Error('Other connections appeared; partial export preserved privately')
        ensure_frozen()
        write_json(stage / 'source-report.json', report)
        write_json(stage / 'release.json', release)
        identity = {'schema_version': 1, 'project': 'd9', 'release_equivalence': False,
                    'containers': {name: {'id': row['Id'], 'image_id': row['Image'],
                                          'configured_image': row['Config']['Image']}
                                   for name, row in selected.items()}}
        write_json(stage / 'source-identity.json', identity)
        write_json(stage / 'checksums.json', {name: checksum(stage / name)
                   for name in PACKAGE_FILES | {'source-identity.json'}})
        stage.rename(output)
        print('Private export verified: ' + str(output))
    finally:
        for sig in handled:
            signal.signal(sig, signal.SIG_IGN)
        failures = []
        for identifier in reversed(stopped):
            result = subprocess.run([*DOCKER, 'start', identifier], stdout=subprocess.DEVNULL)
            if result.returncode:
                failures.append(identifier[:12])
        for sig, handler in previous_handlers.items():
            signal.signal(sig, handler)
        if failures:
            raise Error('Source restart requires attention: ' + ', '.join(failures))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--backend', default='dspace')
    parser.add_argument('--frontend', default='dspace-angular')
    parser.add_argument('--solr', default='dspacesolr')
    parser.add_argument('--postgres', default='dspacedb')
    parser.add_argument('--database', default='dspace')
    parser.add_argument('--username', default='dspace')
    export(parser.parse_args())

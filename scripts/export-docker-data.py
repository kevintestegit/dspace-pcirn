#!/usr/bin/env python3
"""Export an existing Docker repository privately, without changing its configuration."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'deploy/nti'))
from pcirn import Deployment, Error, checksum, manifest, secure_ancestors, write_json
from data_migration import PACKAGE_FILES, snapshot

DOCKER = ['docker', '--context', 'default']

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
    release = manifest(args.manifest)
    endpoint = subprocess.check_output([*DOCKER, 'context', 'inspect', 'default',
                '--format', '{{.Endpoints.docker.Host}}'], text=True).strip()
    if endpoint != 'unix:///var/run/docker.sock':
        raise Error('Private export requires the local Docker Unix socket')
    names = [args.backend, args.frontend, args.solr, args.postgres]
    if len(set(names)) != 4:
        raise Error('Select four distinct source containers')
    rows = json.loads(subprocess.check_output([*DOCKER, 'inspect', *names]))
    if not all(row['State']['Running'] for row in rows):
        raise Error('All source services must be running before export')
    ids = [row['Id'] for row in rows]
    dep = Source(ids[3], args.database, args.username, release)
    if dep.pending(release):
        raise Error('Source history must match the target manifest exactly')
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    stage = Path(tempfile.mkdtemp(prefix='.private-export-', dir=output.parent))
    copies = Path(tempfile.mkdtemp(prefix='.private-copy-', dir=output.parent))
    stopped = []
    try:
        for identifier in ids[:3]:
            stopped.append(identifier)
            subprocess.run([*DOCKER, 'stop', '--time', '60', identifier],
                           check=True, stdout=subprocess.DEVNULL)
        if dep.sql('SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() '
                   'AND pid <> pg_backend_pid();') != '0':
            raise Error('Other database connections remain; export refused')
        for name, identifier, path in (('assetstore', ids[0], '/dspace/assetstore'),
                                       ('solr', ids[2], '/var/solr/data')):
            target = copies / name
            target.mkdir(mode=0o700)
            subprocess.run([*DOCKER, 'cp', identifier + ':' + path + '/.', str(target)], check=True)
        report = snapshot(dep, copies / 'assetstore', copies / 'solr', local_socket=True)
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
        write_json(stage / 'source-report.json', report)
        write_json(stage / 'release.json', release)
        write_json(stage / 'checksums.json', {name: checksum(stage / name) for name in PACKAGE_FILES})
        stage.rename(output)
        print('Private export verified: ' + str(output))
    finally:
        failures = []
        for identifier in reversed(stopped):
            result = subprocess.run([*DOCKER, 'start', identifier], stdout=subprocess.DEVNULL)
            if result.returncode:
                failures.append(identifier[:12])
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

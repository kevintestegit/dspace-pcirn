"""Command-line entry point for the NTI installer."""
import argparse
import fcntl
import os
from pathlib import Path
import signal
import sys
import tarfile

from pcirn import (
    Deployment,
    Error,
    manifest,
    provision,
    read_json,
    refresh_management,
    write_json,
)


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
                     'bin/dspacepcirn', 'bin/pcirn.py', 'bin/pcirn_config.py',
                     'bin/pcirn_cli.py', 'bin/preflight.py', 'bin/data_migration.py',
                     'data-verification.json', 'data-import.json',
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
        if args.command == 'install' or (args.command == 'migrate-data' and args.manifest):
            dep = provision(args)
        else:
            dep = Deployment(root)
            if args.command == 'update':
                refresh_management(root)
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


def run(argv=None):
    def interrupted(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    try:
        return main(argv)
    except (Error, OSError, ValueError, KeyError, TypeError, tarfile.TarError) as error:
        # Parsing exceptions can include secrets; display only our own safe messages.
        message = str(error) if isinstance(error, Error) else type(error).__name__
        print(f'dspacepcirn: {message}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('dspacepcirn: interrompido; examine status/operation.json', file=sys.stderr)
        return 130

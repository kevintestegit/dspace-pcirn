#!/usr/bin/env python3
"""Opt-in lifecycle tests for a disposable Ubuntu VM and two dedicated databases."""
import argparse
import json
import os
import re
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pcirn
import preflight

FIXTURES = Path(__file__).with_name('fixtures')
MARKER = 'documento-ficticio-001'


def validate(args):
    if not args.execute_on_disposable_vm:
        raise pcirn.Error('Execução bloqueada: use --execute-on-disposable-vm apenas em VM descartável')
    base = Path(args.root).absolute()
    if base.name != 'dspacepcirn-homolog' or base.resolve() != base or base.exists():
        raise pcirn.Error('ROOT deve ser um novo diretório dspacepcirn-homolog sem links')
    configs = [pcirn.configuration(args.restored_config), pcirn.configuration(args.empty_config)]
    for config, name in zip(configs, ('pcirn_homolog_restored', 'pcirn_homolog_empty')):
        if pcirn.pg_environment(config)['PGDATABASE'] != name:
            raise pcirn.Error('Use somente bancos pcirn_homolog_restored e pcirn_homolog_empty')
    a, b = pcirn.manifest(args.manifest_a), pcirn.manifest(args.manifest_b)
    if a['version'] == b['version'] or a['images'] == b['images']:
        raise pcirn.Error('Homologação exige duas releases com versões e digests distintos')
    if not Path(args.fixture_dump).is_file():
        raise pcirn.Error('Forneça dump DSpace fictício confiável compatível com release A')
    return base, configs, a, b


def run(args):
    os.umask(0o077)
    base, configs, a, b = validate(args)
    restored = pcirn.Deployment(base / 'restored', config=configs[0])
    empty = pcirn.Deployment(base / 'empty', config=configs[1])
    # No writes until both hosts/databases/images pass readiness and isolation checks.
    for dep in (empty, restored):
        preflight.check(dep, a)
        preflight.check(dep, b)
        if dep.user_objects() != 0:
            raise pcirn.Error('Ambos os bancos de homologação devem estar vazios antes do ensaio')
    header = restored.run(['pg_restore', '--list', str(Path(args.fixture_dump).absolute())], timeout=30)
    versions = re.findall(r'Dumped (?:from database|by pg_dump) version: (\d+)\.', header)
    server = int(restored.sql('SHOW server_version_num;')) // 10000
    if len(versions) != 2 or any(int(version) != server for version in versions):
        raise pcirn.Error('Fixture e clientes de dump devem corresponder ao major PostgreSQL da VM')
    base.mkdir(mode=0o700, parents=True)
    report = {'fixture_sha256': pcirn.checksum(Path(args.fixture_dump)), 'steps': [],
              'release_a': a['version'], 'release_b': b['version'],
              'scope': 'restored-lifecycle-and-empty-denial', 'passed': False}
    report_path = base / 'homolog-report.json'

    def cli(dep, command, *options, expected=0):
        result = subprocess.run([sys.executable, str(Path(pcirn.__file__)), command,
                                 '--root', str(dep.root), *map(str, options)],
                                capture_output=True, text=True)
        report['steps'].append({'command': command, 'root': dep.root.name,
                                'returncode': result.returncode, 'expected': expected})
        pcirn.write_json(report_path, report)
        if result.returncode != expected:
            raise pcirn.Error(f'E2E {command}: retorno {result.returncode}; esperado {expected}')
        return result

    def ensure(condition, name):
        report['steps'].append({'assertion': name, 'passed': bool(condition)})
        pcirn.write_json(report_path, report)
        if not condition:
            raise pcirn.Error('E2E: critério reprovado: ' + name)

    def marker(dep):
        return dep.sql('SELECT marker FROM public.pcirn_homolog_probe WHERE id=1;')

    def verify_images(dep, release):
        rows = dep.compose(release, 'ps', '-q').split()
        ensure(len(rows) == 3, 'três containers na stack dedicada')
        refs = [dep.run(['docker', 'inspect', '--format', '{{.Config.Image}}', cid]).strip() for cid in rows]
        ensure(set(refs) == set(release['images'].values()), 'containers usam os três digests esperados')

    try:
        before = empty.user_objects()
        denied = cli(empty, 'install', '--config', args.empty_config, '--manifest', args.manifest_a, expected=1)
        ensure('--authorize-migrations' in denied.stderr, 'banco vazio recusado por falta de autorização')
        ensure(empty.user_objects() == before,
               'tentativa sem autorização preserva banco vazio')
        ensure(not empty.compose(a, 'ps', '-q').strip(), 'tentativa negada não cria containers')
        ensure(not list((empty.root / 'backups').glob('backup-*')), 'tentativa negada não cria backups')
        ensure(not (empty.root / 'installed.json').exists(), 'banco vazio não registrado como instalado')
        ensure(not (empty.root / 'operation.json').exists(), 'sem operação mutável na tentativa negada')

        restored.run(['pg_restore', '--no-password', '--clean', '--if-exists', '--no-owner', '--no-acl',
                      '--single-transaction', '--exit-on-error', '--dbname',
                      pcirn.pg_environment(configs[0])['PGDATABASE'], str(Path(args.fixture_dump).absolute())], pg=True)
        restored.run(['psql', '-X', '--no-password', '-v', 'ON_ERROR_STOP=1',
                      '-f', str(FIXTURES / 'probe.sql')], pg=True)
        ensure(not restored.pending(a), 'histórico do banco restaurado corresponde à release A')
        assets = restored.root / 'data/assetstore'
        assets.mkdir(parents=True)
        probe = assets / 'pcirn-homolog.txt'
        probe.write_bytes((FIXTURES / 'probe.txt').read_bytes())
        probe_hash = pcirn.checksum(probe)
        preflight.check(restored, a)
        cli(restored, 'install', '--config', args.restored_config, '--manifest', args.manifest_a)
        cli(restored, 'health'); verify_images(restored, a)
        ensure(marker(restored) == MARKER, 'instalação preserva registro fictício restaurado')
        config_hash = pcirn.checksum(restored.root / 'config.json')
        cli(restored, 'install', '--config', args.restored_config, '--manifest', args.manifest_a)
        ensure(pcirn.checksum(restored.root / 'config.json') == config_hash, 'reinstalação preserva configuração')

        prior = set((restored.root / 'backups').glob('backup-*'))
        cli(restored, 'backup')
        created = set((restored.root / 'backups').glob('backup-*')) - prior
        ensure(len(created) == 1, 'backup completo publicado')
        snapshot = created.pop()
        pcirn.verified_backup(snapshot, restored)
        restored.run(['psql', '-X', '--no-password', '-v', 'ON_ERROR_STOP=1', '-c',
                      "UPDATE public.pcirn_homolog_probe SET marker='apos-backup' WHERE id=1; "
                      'CREATE TABLE public.pcirn_homolog_later (id integer);'], pg=True)
        probe.write_text('alteração fictícia após backup\n')
        cli(restored, 'restore', '--backup', snapshot, expected=1)
        ensure(marker(restored) == 'apos-backup', 'restore negado não altera dados')
        cli(restored, 'restore', '--backup', snapshot, '--authorize-restore')
        ensure(marker(restored) == MARKER and pcirn.checksum(probe) == probe_hash,
               'restore recupera registro e bytes do assetstore')
        ensure(restored.sql("SELECT to_regclass('public.pcirn_homolog_later') IS NULL;") == 't',
               'restore remove objeto criado após backup')
        cli(restored, 'health')

        needs = restored.pending(b)
        if needs:
            cli(restored, 'update', '--manifest', args.manifest_b, expected=1)
            ensure(args.authorize_migrations, 'migrations de B exigem --authorize-migrations no executor')
        options = ['--authorize-migrations'] if needs else []
        cli(restored, 'update', '--manifest', args.manifest_b, *options)
        history = pcirn.read_json(restored.root / 'previous.json')
        ensure(pcirn.manifest(Path(history['backup']) / 'release.json') == a,
               'atualização guarda backup da release A')
        ensure(cli(restored, 'version').stdout.strip() == b['version'], 'versão B registrada')
        verify_images(restored, b); cli(restored, 'health')
        restored.run(['psql', '-X', '--no-password', '-v', 'ON_ERROR_STOP=1', '-c',
                      "UPDATE public.pcirn_homolog_probe SET marker='apos-update' WHERE id=1;"], pg=True)
        probe.write_text('alteração fictícia após update\n')
        cli(restored, 'rollback', expected=1)
        cli(restored, 'rollback', '--authorize-restore')
        ensure(cli(restored, 'version').stdout.strip() == a['version'], 'rollback registra release A')
        ensure(marker(restored) == MARKER and pcirn.checksum(probe) == probe_hash,
               'rollback recupera registro e bytes anteriores ao update')
        ensure(pcirn.checksum(restored.root / 'config.json') == config_hash, 'configuração preservada no ciclo')
        verify_images(restored, a); cli(restored, 'health')

        if args.authorize_empty_migrations:
            # Only this runner's stack is removed; external DB and all data remain.
            restored.compose(a, 'down')
            preflight.check(empty, a)
            cli(empty, 'install', '--config', args.empty_config, '--manifest', args.manifest_a,
                '--authorize-migrations')
            ensure(not empty.pending(a), 'banco vazio autorizado recebe histórico completo')
            cli(empty, 'health'); verify_images(empty, a)
            report['authorized_empty'] = 'passed'
        else:
            report['authorized_empty'] = 'not_run'
        report['passed'] = True
        pcirn.write_json(report_path, report)
        print(f'E2E: aprovado; evidências em {report_path}')
        return 0
    except (pcirn.Error, OSError, ValueError, KeyboardInterrupt):
        report['passed'] = False
        pcirn.write_json(report_path, report)
        print(f'E2E: interrompido/reprovado; estado preservado, evidências em {report_path}', file=sys.stderr)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-on-disposable-vm', action='store_true')
    parser.add_argument('--root', default='/srv/dspacepcirn-homolog')
    parser.add_argument('--restored-config', required=True)
    parser.add_argument('--empty-config', required=True)
    parser.add_argument('--manifest-a', required=True)
    parser.add_argument('--manifest-b', required=True)
    parser.add_argument('--fixture-dump', required=True)
    parser.add_argument('--authorize-migrations', action='store_true')
    parser.add_argument('--authorize-empty-migrations', action='store_true')
    return run(parser.parse_args(argv))


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (pcirn.Error, OSError, ValueError, KeyError, TypeError) as error:
        print(str(error) if isinstance(error, pcirn.Error) else type(error).__name__, file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)

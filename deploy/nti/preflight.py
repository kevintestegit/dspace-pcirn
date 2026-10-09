#!/usr/bin/env python3
"""Read-only readiness checks for a clean Ubuntu homologation VM."""
import argparse
import ipaddress
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import sys

from pcirn import Deployment, Error, configuration, manifest

GIB = 1024 ** 3
SUBNET = ipaddress.ip_network('10.250.50.0/24')


def ubuntu():
    return 'ID=ubuntu' in Path('/etc/os-release').read_text().splitlines()


def available_memory():
    values = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
    return int(values['MemAvailable'].split()[0]) * 1024


def ports_available():
    sockets = []
    try:
        for port in (8501, 4000):
            handle = socket.socket()
            sockets.append(handle)
            handle.bind(('127.0.0.1', port))
        return True
    except OSError:
        return False
    finally:
        for handle in sockets:
            handle.close()


def check(dep, release):
    if not ubuntu():
        raise Error('preflight: VM Ubuntu obrigatória para esta homologação')
    for tool in ('docker', 'psql', 'pg_dump', 'pg_restore'):
        if not shutil.which(tool):
            raise Error(f'preflight: pré-requisito ausente: {tool}')
    version = dep.run(['docker', 'compose', 'version', '--short'], timeout=30).strip().lstrip('v')
    if tuple(int(x) for x in version.split('.')[:2]) < (2, 20):
        raise Error('preflight: Compose >= 2.20 obrigatório')
    endpoint = json.loads(dep.run(['docker', 'context', 'inspect', 'default',
                                   '--format', '{{json .Endpoints.docker.Host}}'], timeout=30))
    if not isinstance(endpoint, str) or not endpoint.startswith('unix://'):
        raise Error('preflight: Docker precisa usar endpoint Unix local')
    info = json.loads(dep.run(['docker', 'info', '--format', '{{json .}}'], timeout=30))
    arch = {'x86_64': 'amd64', 'aarch64': 'arm64'}.get(info['Architecture'], info['Architecture'])
    if info['OSType'] != 'linux' or arch not in ('amd64', 'arm64'):
        raise Error('preflight: arquitetura Linux amd64/arm64 obrigatória')
    if info['NCPU'] < 2 or info['MemTotal'] < 8 * GIB or available_memory() < 4 * GIB:
        raise Error('preflight: mínimo 2 vCPU, memória total 8 GiB e disponível 4 GiB')
    for image in release['images'].values():
        descriptors = json.loads(dep.run(['docker', 'manifest', 'inspect', '--verbose', image], timeout=30))
        if isinstance(descriptors, dict):
            descriptors = [descriptors]
        platforms = [entry.get('Descriptor', {}).get('platform', {}) for entry in descriptors]
        if not any(p.get('os') == 'linux' and p.get('architecture') == arch for p in platforms):
            raise Error('preflight: imagem GHCR indisponível para a arquitetura da VM')
    root = dep.root
    if root == Path('/') or root.resolve() != root:
        raise Error('preflight: diretório dedicado sem links obrigatório')
    ancestor = root
    while not ancestor.exists():
        ancestor = ancestor.parent
    if not os.access(ancestor, os.W_OK | os.X_OK):
        raise Error('preflight: sem permissões para criar/gravar a instalação')
    for relative in ('data', 'data/assetstore', 'data/solr', 'backups'):
        path = root / relative
        if path.resolve() != path:
            raise Error('preflight: dados/backups não podem ser links')
        if path.exists():
            if not os.access(path, os.R_OK | os.W_OK | os.X_OK):
                raise Error('preflight: sem permissões nos dados/backups')
            for entry in path.rglob('*'):
                permissions = os.R_OK | (os.X_OK if entry.is_dir() else 0)
                if entry.is_symlink() or not os.access(entry, permissions):
                    raise Error('preflight: dados ilegíveis ou links não aceitos pelo backup')
            if path.stat().st_dev != ancestor.stat().st_dev:
                raise Error('preflight: dados e staging precisam estar no mesmo filesystem')
    pg = json.loads(dep.sql("SELECT json_build_object("
                           "'ssl', (SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()),"
                           "'connect', has_database_privilege(current_database(),'CONNECT'),"
                           "'create', has_database_privilege(current_database(),'CREATE'),"
                           "'schema', has_schema_privilege('public','USAGE,CREATE'),"
                           "'owner', pg_has_role((SELECT datdba FROM pg_database WHERE datname=current_database()),'USAGE') "
                           "AND pg_has_role((SELECT nspowner FROM pg_namespace WHERE nspname='public'),'USAGE'),"
                           "'objects', NOT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                           "WHERE n.nspname='public' AND NOT pg_has_role(c.relowner,'USAGE')),"
                           "'server', current_setting('server_version_num')::int,"
                           "'size', pg_database_size(current_database()));"))
    if not pg['ssl']:
        raise Error('preflight: conexão PostgreSQL sem TLS')
    if not all(pg[k] for k in ('connect', 'create', 'schema', 'owner', 'objects')):
        raise Error('preflight: permissões PostgreSQL insuficientes para migration/backup/restore')
    for tool in ('psql', 'pg_dump', 'pg_restore'):
        client = re.search(r'(\d+)\.', dep.run([tool, '--version'], timeout=30))
        if not client or int(client[1]) != pg['server'] // 10000:
            raise Error('preflight: clientes PostgreSQL devem ter major igual ao servidor')
    data_size = sum(p.stat().st_size for p in (root / 'data').rglob('*') if p.is_file())
    required = 30 * GIB + 3 * (pg['size'] + data_size)
    for path in (ancestor, Path(info['DockerRootDir'])):
        if shutil.disk_usage(path).free < required:
            raise Error('preflight: disco livre insuficiente (30 GiB + 3x banco/dados)')
    installed = (root / 'installed.json').exists()
    if not installed and not ports_available():
        raise Error('preflight: portas 127.0.0.1:8501/4000 ocupadas')
    project = 'dspacepcirn-' + hashlib.sha256(str(root).encode()).hexdigest()[:12]
    ids = dep.run(['docker', 'network', 'ls', '-q'], timeout=30).split()
    if ids:
        networks = json.loads(dep.run(['docker', 'network', 'inspect', *ids], timeout=30))
        for network in networks:
            if network['Name'] == project + '_dspacenet':
                continue
            for subnet in network.get('IPAM', {}).get('Config') or []:
                value = ipaddress.ip_network(subnet.get('Subnet', '0.0.0.0/32'), strict=False)
                if value.version == 4 and value.overlaps(SUBNET):
                    raise Error('preflight: subnet 10.250.50.0/24 sobrepõe rede Docker existente')
    for key in ('PGSSLROOTCERT', 'PGSSLCERT', 'PGSSLKEY'):
        certificate = dep.env.get(key)
        if certificate and not os.access(certificate, os.R_OK):
            raise Error('preflight: certificado PostgreSQL ilegível no host')
    print(f'preflight: OK — Ubuntu, Linux/{arch}, recursos, GHCR, rede, TLS e permissões')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='/srv/dspacepcirn')
    parser.add_argument('--config')
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--authorize-migrations', action='store_true')
    parser.add_argument('--data-package', type=Path)
    parser.add_argument('--authorize-restore', action='store_true')
    args = parser.parse_args(argv)
    root = Path(args.root).absolute()
    config = configuration(args.config or root / 'config.json')
    dep = Deployment(root, config=config)
    check(dep, manifest(args.manifest))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (Error, OSError, ValueError, KeyError, TypeError) as error:
        print(str(error) if isinstance(error, Error) else type(error).__name__, file=sys.stderr)
        sys.exit(1)

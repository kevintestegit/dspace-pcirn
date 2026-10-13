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


def ports_available(ports=(8501, 4000)):
    sockets = []
    try:
        for port in ports:
            handle = socket.socket()
            sockets.append(handle)
            handle.bind(('127.0.0.1', port))
        return True
    except OSError:
        return False
    finally:
        for handle in sockets:
            handle.close()


def select_resources(run, root):
    """Choose free loopback ports and a nonoverlapping private Docker subnet."""
    ports = []
    for preferred in (8501, 4000):
        with socket.socket() as listener:
            try:
                listener.bind(('127.0.0.1', preferred))
            except OSError:
                listener.bind(('127.0.0.1', 0))
            ports.append(str(listener.getsockname()[1]))
    ids = run(['docker', 'network', 'ls', '-q'], timeout=30).split()
    networks = json.loads(run(['docker', 'network', 'inspect', *ids], timeout=30)) if ids else []
    occupied = [ipaddress.ip_network(c['Subnet'], strict=False) for n in networks
                for c in n.get('IPAM', {}).get('Config') or [] if c.get('Subnet')]
    for index in range(50, 250):
        subnet = ipaddress.ip_network(f'10.250.{index}.0/24')
        if not any(n.version == 4 and n.overlaps(subnet) for n in occupied):
            return {'REST_BIND_PORT': ports[0], 'UI_BIND_PORT': ports[1],
                    'DSPACE_NETWORK_SUBNET': str(subnet), 'TRUSTED_PROXY_NETWORK': f'10.250.{index}'}
    raise Error('No dedicated Docker network available')


def owns_application_ports(dep, release, ports):
    """Accept occupied ports only from the journal's running, pinned application."""
    path = dep.root / 'operation.json'
    if not path.exists():
        return False
    journal = json.loads(path.read_text())
    if journal.get('kind') != 'fresh-install' or journal.get('target') != release:
        return False
    project = 'dspacepcirn-' + hashlib.sha256(str(dep.root).encode()).hexdigest()[:12]
    ids = dep.run(['docker', 'ps', '-q', '--filter', 'label=com.docker.compose.project=' + project],
                  timeout=30).split()
    if not ids:
        return False
    rows = json.loads(dep.run(['docker', 'inspect', *ids], timeout=30))
    owned = set()
    images = {'dspace': release['images']['backend'], 'dspace-angular': release['images']['frontend']}
    for row in rows:
        labels = row.get('Config', {}).get('Labels') or {}
        service = labels.get('com.docker.compose.service')
        if (service not in images or labels.get('com.docker.compose.project') != project
                or row['Config'].get('Image') != images[service]
                or not row.get('State', {}).get('Running')):
            continue
        for bindings in (row.get('NetworkSettings', {}).get('Ports') or {}).values():
            for binding in bindings or []:
                if binding.get('HostIp') == '127.0.0.1':
                    owned.add(int(binding['HostPort']))
    return all(port in owned or ports_available((port,)) for port in ports)


def check(dep, release, server_only=False):
    if not ubuntu():
        raise Error('preflight: Ubuntu required')
    for tool in ('docker', 'psql', 'pg_dump', 'pg_restore'):
        if not shutil.which(tool):
            raise Error(f'preflight: missing dependency: {tool}')
    version = dep.run(['docker', 'compose', 'version', '--short'], timeout=30).strip().lstrip('v')
    if tuple(int(x) for x in version.split('.')[:2]) < (2, 20):
        raise Error('preflight: Compose >= 2.20 required')
    endpoint = json.loads(dep.run(['docker', 'context', 'inspect', 'default',
                                   '--format', '{{json .Endpoints.docker.Host}}'], timeout=30))
    if not isinstance(endpoint, str) or not endpoint.startswith('unix://'):
        raise Error('preflight: Docker requires a local Unix endpoint')
    info = json.loads(dep.run(['docker', 'info', '--format', '{{json .}}'], timeout=30))
    arch = {'x86_64': 'amd64', 'aarch64': 'arm64'}.get(info['Architecture'], info['Architecture'])
    if info['OSType'] != 'linux' or arch not in ('amd64', 'arm64'):
        raise Error('preflight: Linux amd64/arm64 required')
    if info['NCPU'] < 2 or info['MemTotal'] < 8 * GIB or available_memory() < 4 * GIB:
        raise Error('preflight: minimum 2 CPUs, 8 GiB RAM, 4 GiB available RAM')
    for image in release['images'].values():
        try:
            descriptors = json.loads(dep.run(['docker', 'manifest', 'inspect', '--verbose', image], timeout=30))
        except Error as exc:
            raise Error('GHCR image unavailable; check network or login in Advanced') from exc
        if isinstance(descriptors, dict):
            descriptors = [descriptors]
        platforms = [entry.get('Descriptor', {}).get('platform', {}) for entry in descriptors]
        if not any(p.get('os') == 'linux' and p.get('architecture') == arch for p in platforms):
            raise Error('preflight: GHCR image unavailable for this architecture')
    root = dep.root
    if root == Path('/') or root.resolve() != root:
        raise Error('preflight: dedicated directory without symlinks required')
    ancestor = root
    while not ancestor.exists():
        ancestor = ancestor.parent
    if not os.access(ancestor, os.W_OK | os.X_OK):
        raise Error('preflight: cannot write installation directory')
    for relative in ('data', 'data/assetstore', 'data/solr', 'backups'):
        path = root / relative
        if path.resolve() != path:
            raise Error('preflight: data/backups cannot be symlinks')
        if path.exists():
            if not os.access(path, os.R_OK | os.W_OK | os.X_OK):
                raise Error('preflight: cannot access data/backups')
            for entry in path.rglob('*'):
                permissions = os.R_OK | (os.X_OK if entry.is_dir() else 0)
                if entry.is_symlink() or not os.access(entry, permissions):
                    raise Error('preflight: unreadable data or unsafe symlinks')
            if path.stat().st_dev != ancestor.stat().st_dev:
                raise Error('preflight: data and staging must share a filesystem')
    project = 'dspacepcirn-' + hashlib.sha256(str(root).encode()).hexdigest()[:12]
    config = getattr(dep, 'config', {})
    subnet_selected = ipaddress.ip_network(config.get('DSPACE_NETWORK_SUBNET', str(SUBNET)))
    ports = tuple(int(config.get(k, default)) for k, default in
                  (('REST_BIND_PORT', 8501), ('UI_BIND_PORT', 4000)))
    ids = dep.run(['docker', 'network', 'ls', '-q'], timeout=30).split()
    if ids:
        networks = json.loads(dep.run(['docker', 'network', 'inspect', *ids], timeout=30))
        for network in networks:
            if network['Name'] == project + '_dspacenet':
                labels = network.get('Labels') or {}
                owned_subnets = {c.get('Subnet') for c in network.get('IPAM', {}).get('Config') or []}
                if (labels.get('com.docker.compose.project') != project
                        or str(subnet_selected) not in owned_subnets):
                    raise Error('preflight: existing network ownership/integrity not verified')
                continue
            for subnet in network.get('IPAM', {}).get('Config') or []:
                value = ipaddress.ip_network(subnet.get('Subnet', '0.0.0.0/32'), strict=False)
                if value.version == 4 and value.overlaps(subnet_selected):
                    raise Error('preflight: selected subnet overlaps an existing Docker network')
    if server_only:
        if shutil.disk_usage(ancestor).free < 30 * GIB:
            raise Error("preflight: minimum 30 GiB free disk space")
        if not (root / 'installed.json').exists() and not ports_available(ports):
            raise Error("preflight: application ports in use")
        return
    pg = database(dep)
    data_size = sum(p.stat().st_size for p in (root / 'data').rglob('*') if p.is_file())
    required = 30 * GIB + 3 * (pg['size'] + data_size)
    for path in (ancestor, Path(info['DockerRootDir'])):
        if shutil.disk_usage(path).free < required:
            raise Error('preflight: insufficient disk space (30 GiB + 3x database/data)')
    installed = (root / 'installed.json').exists()
    if not installed and not ports_available(ports) and not owns_application_ports(dep, release, ports):
        raise Error('preflight: application ports in use')
    for key in ('PGSSLROOTCERT', 'PGSSLCERT', 'PGSSLKEY'):
        certificate = dep.env.get(key)
        if certificate and not os.access(certificate, os.R_OK):
            raise Error('preflight: PostgreSQL certificate is unreadable')
    print(f'preflight: OK — Ubuntu, Linux/{arch}, resources, GHCR, network, TLS and privileges')


def database(dep):
    """Validate TLS, ownership and client versions without writing database objects."""
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
        raise Error('preflight: PostgreSQL connection without TLS')
    if not all(pg[k] for k in ('connect', 'create', 'schema', 'owner', 'objects')):
        raise Error('preflight: insufficient PostgreSQL privileges for migration/backup/restore')
    for tool in ('psql', 'pg_dump', 'pg_restore'):
        client = re.search(r'(\d+)\.', dep.run([tool, '--version'], timeout=30))
        if not client or int(client[1]) != pg['server'] // 10000:
            raise Error('preflight: PostgreSQL clients must match the server major version')
    return pg


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

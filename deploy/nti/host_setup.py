"""Prepare an Ubuntu host without replacing existing services or their data."""
import json
import os
from pathlib import Path
import platform
import re
import shutil
import socket
import tempfile
from urllib.request import urlopen

from pcirn import Error

GIB = 1024 ** 3
DOCKER_FINGERPRINT = '9DC858229FC7DD38854AE2D88D81803C0EBFCD88'
PGDG_FINGERPRINT = 'B97B0AFCAA1A47F044F244A07FCC7D46ACCC4CF8'


def detect():
    """Return distribution, release and Docker architecture without shell sourcing."""
    fields = {}
    for line in Path('/etc/os-release').read_text().splitlines():
        key, separator, value = line.partition('=')
        if separator:
            fields[key] = value.strip('"\'')
    machine = platform.machine()
    return {'distribution': fields.get('ID', ''), 'version': fields.get('VERSION_ID', ''),
            'codename': fields.get('VERSION_CODENAME', ''),
            'architecture': {'x86_64': 'amd64', 'aarch64': 'arm64'}.get(machine, machine)}


def supported_host():
    info = detect()
    if (info['distribution'], info['version'], info['codename']) != ('ubuntu', '24.04', 'noble'):
        raise Error('Automatic setup requires Ubuntu 24.04; detected: '
                    + info['distribution'] + ' ' + info['version'])
    if info['architecture'] not in ('amd64', 'arm64'):
        raise Error('Supported architecture: AMD64 or ARM64')
    return info


def resources(root):
    """Check resources before installing anything; ports are reported, not reserved."""
    memory = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
    if (os.cpu_count() or 0) < 2:
        raise Error('At least 2 CPUs required')
    if int(memory['MemTotal'].split()[0]) * 1024 < 8 * GIB:
        raise Error('At least 8 GiB RAM required')
    if int(memory['MemAvailable'].split()[0]) * 1024 < 4 * GIB:
        raise Error('At least 4 GiB available RAM required')
    ancestor = Path(root).absolute()
    while not ancestor.exists():
        ancestor = ancestor.parent
    if shutil.disk_usage(ancestor).free < 30 * GIB:
        raise Error('At least 30 GiB free disk space required')
    ports = {}
    for port in (4000, 8501):
        with socket.socket() as handle:
            try:
                handle.bind(('127.0.0.1', port))
                ports[str(port)] = 'available'
            except OSError:
                ports[str(port)] = 'occupied'
    return {'cpus': os.cpu_count(), 'memory_bytes': int(memory['MemTotal'].split()[0]) * 1024,
            'disk_free_bytes': shutil.disk_usage(ancestor).free, 'ports': ports}


def network():
    """Require verified HTTPS connectivity to the release and image registries."""
    from urllib.error import HTTPError, URLError
    for url in ('https://api.github.com', 'https://ghcr.io/v2/'):
        try:
            with urlopen(url, timeout=20):
                pass
        except HTTPError as error:
            # The OCI registry challenges anonymous requests before issuing tokens.
            if url.endswith('/v2/') and error.code == 401:
                continue
            raise Error('Network unavailable: ' + url) from None
        except (URLError, OSError, TimeoutError):
            raise Error('DNS, TLS or connection failed: ' + url) from None


def available(run, command):
    try:
        return run(command, timeout=30).strip()
    except (Error, OSError):
        return None


def approve(confirm, message):
    if os.geteuid() != 0:
        raise Error('Run sudo dspacepcirn to prepare the environment')
    if os.environ.get('DSPACEPCIRN_BOOTSTRAP_APPROVED') != '1' and not confirm(message):
        raise Error('Environment setup cancelled; dependencies unchanged')


def apt_install(run, packages):
    if packages:
        run(['apt-get', 'update'], timeout=300)
        run(['apt-get', '-y', '--no-remove', '--no-upgrade', 'install', '--no-install-recommends', *packages],
            timeout=900)


def write_repository_file(path, content, mode):
    """Never overwrite a repository/key belonging to another configuration."""
    path = Path(path)
    if path.is_symlink():
        raise Error('APT repository cannot be a symlink: ' + str(path))
    if path.exists():
        if path.read_bytes() != content:
            raise Error('Existing APT repository differs: ' + str(path))
        return
    path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(content)


def repository(run, name, info):
    """Install an authenticated APT source and verify its pinned signing identity."""
    package = 'docker-ce' if name == 'docker' else 'postgresql-client-15'
    policy = available(run, ['apt-cache', 'policy', package]) or ''
    official = ('https://download.docker.com/linux/ubuntu' if name == 'docker'
                else 'https://apt.postgresql.org/pub/repos/apt')
    if official in policy:
        return
    if name == 'docker':
        key_url = 'https://download.docker.com/linux/ubuntu/gpg'
        uri, suite, component, fingerprint = ('https://download.docker.com/linux/ubuntu',
                                              'noble', 'stable', DOCKER_FINGERPRINT)
    else:
        key_url = 'https://www.postgresql.org/media/keys/ACCC4CF8.asc'
        uri, suite, component, fingerprint = ('https://apt.postgresql.org/pub/repos/apt',
                                              'noble-pgdg', 'main', PGDG_FINGERPRINT)
    try:
        with urlopen(key_url, timeout=30) as response:
            key = response.read(128 * 1024 + 1)
    except OSError:
        raise Error('Cannot download the official signing key: ' + name) from None
    if len(key) > 128 * 1024 or not key.startswith(b'-----BEGIN PGP PUBLIC KEY BLOCK-----'):
        raise Error('Invalid official signing key: ' + name)
    with tempfile.TemporaryDirectory(prefix='dspacepcirn-key-') as directory:
        path = Path(directory) / 'key.asc'
        path.write_bytes(key)
        identity = run(['gpg', '--batch', '--homedir', directory, '--show-keys', '--with-colons',
                        str(path)], timeout=30)
        fingerprints = [line.split(':')[9] for line in identity.splitlines()
                        if line.startswith('fpr:')]
        if (sum(line.startswith('pub:') for line in identity.splitlines()) != 1
                or not fingerprints or fingerprints[0] != fingerprint):
            raise Error('Official signing key fingerprint mismatch: ' + name)
    destination = '/etc/apt/keyrings/dspacepcirn-' + name + '.asc'
    write_repository_file(destination, key, 0o644)
    source = (f'Types: deb\nURIs: {uri}\nSuites: {suite}\nComponents: {component}\n'
              f'Architectures: {info["architecture"]}\nSigned-By: {destination}\n')
    write_repository_file('/etc/apt/sources.list.d/dspacepcirn-' + name + '.sources',
                          source.encode(), 0o644)


def client_path(major):
    """Return the private client bin directory without changing system alternatives."""
    if type(major) is not int or not 13 <= major <= 17:
        raise Error('Supported PostgreSQL versions: 13 to 17')
    directory = Path(f'/usr/lib/postgresql/{major}/bin')
    return str(directory) if all((directory / tool).is_file() for tool in
                                 ('psql', 'pg_dump', 'pg_restore')) else None


def client_major(run, tool, major=None):
    directory = client_path(major) if major is not None else None
    if not directory and not shutil.which(tool):
        return None
    executable = str(Path(directory) / tool) if directory else tool
    version = available(run, [executable, '--version'])
    match = re.search(r'PostgreSQL\)?\s+(\d+)\.', version or '')
    return int(match[1]) if match else None


def ensure_clients(run, confirm, major):
    """Install client tools of the exact server major; never install a host server."""
    if type(major) is not int or not 13 <= major <= 17:
        raise Error('Supported PostgreSQL versions: 13 to 17')
    if all(client_major(run, tool, major) == major for tool in ('psql', 'pg_dump', 'pg_restore')):
        return
    info = supported_host()
    approve(confirm, f'Install PostgreSQL clients {major} from the official repository?')
    if major != 16:
        if not shutil.which('gpg'):
            apt_install(run, ['gnupg', 'ca-certificates'])
        repository(run, 'postgresql', info)
    apt_install(run, [f'postgresql-client-{major}'])
    if not all(client_major(run, tool, major) == major for tool in ('psql', 'pg_dump', 'pg_restore')):
        raise Error('PostgreSQL clients do not match the server version; '
                    'check /usr/lib/postgresql')


def compose_supported(version):
    match = re.match(r'v?(\d+)\.(\d+)', version or '')
    return bool(match and tuple(map(int, match.groups())) >= (2, 20))


def tracked_compose(run):
    """Identify the selected plugin before permitting a targeted package upgrade."""
    from pcirn import docker_config
    config = Path(docker_config() or Path.home() / '.docker')
    extra = []
    document = config / 'config.json'
    if document.exists():
        try:
            extra = json.loads(document.read_text()).get('cliPluginsExtraDirs', [])
        except (OSError, ValueError, AttributeError):
            raise Error('Invalid Docker configuration; Compose update refused') from None
        if not isinstance(extra, list) or any(not isinstance(path, str) for path in extra):
            raise Error('Invalid Docker plugin directories')
    directories = [*extra, str(config / 'cli-plugins'),
                   '/usr/local/lib/docker/cli-plugins', '/usr/local/libexec/docker/cli-plugins',
                   '/usr/lib/docker/cli-plugins', '/usr/libexec/docker/cli-plugins']
    distro_docker = available(run, ['dpkg-query', '-W', '-f=${Status}', 'docker.io'])
    expected = ('docker-compose-v2' if distro_docker == 'install ok installed'
                else 'docker-compose-plugin')
    for directory in directories:
        binary = Path(directory) / 'docker-compose'
        if not binary.is_file():
            continue
        owner = available(run, ['dpkg-query', '-S', str(binary)]) or ''
        package = owner.partition(': ')[0]
        if package != expected:
            break
        status = available(run, ['dpkg-query', '-W', '-f=${Status}', package])
        if status == 'install ok installed':
            return package
        break
    raise Error('Incompatible Compose is not an official package; '
                'custom binary requires review, no automatic replacement')


def validate_endpoint(run):
    endpoint = json.loads(run(['docker', 'context', 'inspect', 'default', '--format',
                               '{{json .Endpoints.docker.Host}}'], timeout=30))
    if not isinstance(endpoint, str) or not endpoint.startswith('unix://'):
        raise Error('Docker requires a local Unix endpoint')


def prepare(run, confirm, pg_major=16, root='/srv/dspacepcirn'):
    """Prepare missing host dependencies after a single administrator confirmation."""
    info = supported_host()
    info['resources'] = resources(root)
    network()
    packages = []
    for tool, package in (('python3', 'python3'), ('openssl', 'openssl'),
                          ('gpg', 'gnupg')):
        if not shutil.which(tool):
            packages.append(package)
    docker = shutil.which('docker')
    if docker:
        validate_endpoint(run)
    compose = available(run, ['docker', 'compose', 'version', '--short']) if docker else None
    compose_upgrade = tracked_compose(run) if compose and not compose_supported(compose) else None
    if not docker:
        for package in ('docker.io', 'podman-docker', 'containerd', 'runc'):
            status = available(run, ['dpkg-query', '-W', '-f=${Status}', package])
            if status == 'install ok installed':
                raise Error('Conflicting Docker package: ' + package +
                            '; review required, no automatic removal')
        packages += ['ca-certificates', 'docker-ce', 'docker-ce-cli', 'containerd.io',
                     'docker-buildx-plugin', 'docker-compose-plugin']
    elif not compose:
        status = available(run, ['dpkg-query', '-W', '-f=${Status}', 'docker.io'])
        packages.append('docker-compose-v2' if status == 'install ok installed'
                        else 'docker-compose-plugin')
    clients_missing = any(client_major(run, tool, pg_major) != pg_major
                          for tool in ('psql', 'pg_dump', 'pg_restore'))
    active = available(run, ['systemctl', 'is-active', 'docker']) == 'active' if docker else False
    enabled = available(run, ['systemctl', 'is-enabled', 'docker']) == 'enabled' if docker else False
    if packages or compose_upgrade or clients_missing or not active or not enabled:
        approve(confirm, 'Install missing dependencies from official repositories '
                         'and enable Docker?')
    if not docker:
        apt_install(run, [p for p in packages if p in ('ca-certificates', 'gnupg')])
        repository(run, 'docker', info)
    elif (not compose and 'docker-compose-plugin' in packages) or compose_upgrade == 'docker-compose-plugin':
        apt_install(run, [p for p in packages if p == 'gnupg'] + ['ca-certificates'])
        repository(run, 'docker', info)
    apt_install(run, [p for p in dict.fromkeys(packages)
                      if docker or p not in ('ca-certificates', 'gnupg')])
    if compose_upgrade:
        run(['apt-get', 'update'], timeout=300)
        run(['apt-get', '-y', '--no-remove', 'install', '--no-install-recommends',
             compose_upgrade], timeout=900)
    ensure_clients(run, lambda _: True, pg_major)
    if not active:
        run(['systemctl', 'start', 'docker'], timeout=120)
    if not enabled:
        run(['systemctl', 'enable', 'docker'], timeout=30)
    for command in (['python3', '--version'], ['openssl', 'version'],
                    ['docker', 'compose', 'version', '--short']):
        if not available(run, command):
            raise Error('Component not working: ' + command[0])
    if not compose_supported(available(run, ['docker', 'compose', 'version', '--short'])):
        raise Error('Docker Compose is still incompatible (minimum 2.20)')
    validate_endpoint(run)
    engine = json.loads(run(['docker', 'info', '--format', '{{json .}}'], timeout=30))
    arch = {'x86_64': 'amd64', 'aarch64': 'arm64'}.get(engine.get('Architecture'),
                                                  engine.get('Architecture'))
    if engine.get('OSType') != 'linux' or arch != info['architecture']:
        raise Error('Docker does not match the detected Linux architecture')
    return info

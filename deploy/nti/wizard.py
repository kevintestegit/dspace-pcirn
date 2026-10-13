"""Interactive installation using the existing deployment and data operations."""
import fcntl
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
from types import SimpleNamespace
from urllib.parse import urlencode, urlsplit

from pcirn import (Deployment, Error, SERVICES, checksum, configuration, manifest,
                   provision, read_json, secure_ancestors, write_json)

STEPS = ('Diagnóstico do servidor', 'Preparação do PostgreSQL', 'Modo de instalação',
         'Configuração institucional', 'Instalação', 'Validação dos serviços', 'Relatório final')


def ask(label, default=None, secret=False):
    """Read a required value; passwords never echo or have a visible default."""
    while True:
        try:
            value = (getpass.getpass if secret else input)(label +
                    (f' [{default}]' if default and not secret else '') + ': ')
        except EOFError as exc:
            raise KeyboardInterrupt from exc
        value = value or default
        if value and not any(c in value for c in '\r\n\x00'):
            return value
        print('Informe um valor válido.')


def safe_root(root):
    root = Path(root).absolute()
    if root == Path('/') or root.resolve() != root:
        raise Error('Use um diretório dedicado sem links simbólicos')
    secure_ancestors(root)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.stat().st_mode & 0o077:
        raise Error('Diretório administrativo exige chmod 700')
    for name in ('wizard.json', 'wizard-config.json', 'config.json', 'postgres-password'):
        path = root / name
        if path.exists() and path.stat().st_mode & 0o077:
            raise Error('Credenciais e estado exigem chmod 600')
    for entry in root.rglob('*'):
        if entry.is_symlink():
            raise Error('Links simbólicos não são aceitos no diretório administrativo')
    return root


def validate_docker_config(config, directory=None):
    """Only a dedicated loopback PostgreSQL with verified TLS is managed here."""
    url = urlsplit(config['DB_URL'][5:])
    if (url.hostname != '127.0.0.1' or not url.port
            or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', config['DB_USERNAME'])
            or not re.fullmatch(r'/[A-Za-z_][A-Za-z0-9_]*', url.path)
            or config['DB_USERNAME'] == 'postgres' or config['DB_USERNAME'].startswith('pg_')
            or url.path[1:] in ('postgres', 'template0', 'template1')):
        raise Error('Docker exige host 127.0.0.1, porta e nomes SQL dedicados')
    if not re.fullmatch(r'(?:docker.io/library/)?postgres@sha256:[a-f0-9]{64}',
                        config.get('PG_IMAGE', '')):
        raise Error('PG_IMAGE exige postgres@sha256:<64 hex>')
    from urllib.parse import parse_qs
    params = parse_qs(url.query)
    ca = params.get('sslrootcert', [''])[0]
    if (set(params) != {'sslmode', 'sslrootcert'} or params['sslmode'] != ['verify-ca']
            or len(params['sslrootcert']) != 1 or not Path(ca).is_absolute()
            or (directory is not None and ca != str(Path(directory) / 'postgres-tls/server.crt'))):
        raise Error('Docker exige verify-ca e certificado local postgres-tls/server.crt')


def postgres_compose(dep):
    """Write a separate database service with an explicitly owned external volume."""
    ident = hashlib.sha256(str(dep.root).encode()).hexdigest()[:12]
    name = 'dspacepcirn-pg-' + ident
    document = {'services': {'postgres': {
        'image': dep.config['PG_IMAGE'], 'container_name': name,
        'labels': {'org.dspacepcirn.root': str(dep.root)},
        'restart': 'unless-stopped', 'networks': ['dspacenet'],
        'ports': [{'host_ip': '127.0.0.1', 'published': int(dep.env['PGPORT']), 'target': 5432}],
        'environment': {'POSTGRES_DB': dep.env['PGDATABASE'], 'POSTGRES_USER': 'postgres',
                        'POSTGRES_PASSWORD_FILE': '/run/secrets/postgres-password',
                        'POSTGRES_INITDB_ARGS': '--auth-host=scram-sha-256 --auth-local=peer'},
        'volumes': [
            {'type': 'volume', 'source': 'postgres_data', 'target': '/var/lib/postgresql/data'},
            *[{'type': 'bind', 'source': str(dep.root / source), 'target': target,
               'read_only': True, 'bind': {'create_host_path': False}}
              for source, target in (
                  ('postgres-password', '/run/secrets/postgres-password'),
                  ('postgres-tls', '/run/postgres-tls'))]],
        'command': ['postgres', '-c', 'ssl=on', '-c', 'ssl_cert_file=/run/postgres-tls/server.crt',
                    '-c', 'ssl_key_file=/run/postgres-tls/server.key',
                    '-c', 'hba_file=/run/postgres-tls/pg_hba.conf',
                    '-c', 'password_encryption=scram-sha-256'],
        'healthcheck': {'test': ['CMD', 'pg_isready', '-h', '127.0.0.1', '-U', 'postgres', '-d', 'postgres'],
                        'interval': '5s', 'timeout': '5s', 'retries': 30}}},
        'volumes': {'postgres_data': {'external': True, 'name': name}}}
    path = dep.root / 'postgres-compose.json'
    if path.exists() and read_json(path) != document:
        raise Error('Configuração PostgreSQL existente diverge; nada sobrescrito')
    if not path.exists():
        write_json(path, document)
    return name


def verify_postgres_container(dep, name):
    """Prove container ownership and persistent mounts before restarting it."""
    row = json.loads(dep.run(['docker', 'inspect', name], timeout=30))[0]
    mounts = {m['Destination']: m for m in row['Mounts']}
    volume = mounts.get('/var/lib/postgresql/data', {})
    tls = mounts.get('/run/postgres-tls', {})
    secret = mounts.get('/run/secrets/postgres-password', {})
    # RC4 containers have Compose ownership labels, before our explicit root label.
    labels = row['Config'].get('Labels') or {}
    project = 'dspacepcirn-' + hashlib.sha256(str(dep.root).encode()).hexdigest()[:12]
    if (labels.get('com.docker.compose.project') != project
            or labels.get('com.docker.compose.service') != 'postgres'
            or row['Config']['Image'] != dep.config['PG_IMAGE']
            or volume.get('Type') != 'volume' or volume.get('Name') != name
            or tls.get('Source') != str(dep.root / 'postgres-tls') or tls.get('RW') is not False
            or secret.get('Source') != str(dep.root / 'postgres-password') or secret.get('RW') is not False):
        raise Error('Container PostgreSQL diverge da instalação; nada reutilizado')


def provision_postgres(dep):
    """Resume only resources proved to belong to this root and durable journal."""
    validate_docker_config(dep.config, dep.root)
    endpoint = json.loads(dep.run(['docker', 'context', 'inspect', 'default',
                                   '--format', '{{json .Endpoints.docker.Host}}'], timeout=30))
    if not isinstance(endpoint, str) or not endpoint.startswith('unix://'):
        raise Error('Docker precisa usar endpoint Unix local')
    name = postgres_compose(dep)
    journal_path = dep.root / 'postgres.json'
    label = 'org.dspacepcirn.root=' + str(dep.root)
    volumes = dep.run(['docker', 'volume', 'ls', '--format', '{{.Name}}']).splitlines()
    containers = dep.run(['docker', 'ps', '-a', '--format', '{{.Names}}']).splitlines()
    journal = read_json(journal_path) if journal_path.exists() else None
    if journal is None:
        if not shutil.which('openssl'):
            raise Error('Pré-requisito ausente: openssl')
        version = dep.run(['docker', 'run', '--rm', '--entrypoint', 'postgres',
                           dep.config['PG_IMAGE'], '--version'], timeout=60)
        major = re.search(r'PostgreSQL\)? (\d+)\.', version)
        if not major or not 15 <= int(major[1]) <= 17:
            raise Error('Imagem Docker exige PostgreSQL 15, 16 ou 17')
        for tool in ('psql', 'pg_dump', 'pg_restore'):
            client = re.search(r'(\d+)\.', dep.run([tool, '--version'], timeout=30))
            if not client or client[1] != major[1]:
                raise Error('Clientes PostgreSQL devem ter o mesmo major da imagem')
        if name in volumes or name in containers:
            raise Error('Banco/container/volume existente: provisionamento recusado')
        if any((dep.root / p).exists() for p in ('postgres-password', 'postgres-tls')):
            raise Error('Credenciais PostgreSQL preexistentes: nada sobrescrito')
        token = secrets.token_hex(16)
        write_json(journal_path, {'status': 'creating', 'name': name, 'token': token})
        tls = dep.root / 'postgres-tls'
        tls.mkdir(mode=0o700)
        dep.run(['openssl', 'req', '-x509', '-newkey', 'rsa:3072', '-nodes', '-days', '3650',
                 '-subj', '/CN=postgres', '-addext', 'basicConstraints=critical,CA:TRUE', '-addext', 'subjectAltName=DNS:postgres,DNS:localhost,IP:127.0.0.1',
                 '-keyout', str(tls / 'server.key'), '-out', str(tls / 'server.crt')], timeout=60)
        # The TLS key belongs to the pinned image's PostgreSQL user.
        uid = int(dep.run(['docker', 'run', '--rm', '--entrypoint', 'id', dep.config['PG_IMAGE'], '-u', 'postgres']))
        gid = int(dep.run(['docker', 'run', '--rm', '--entrypoint', 'id', dep.config['PG_IMAGE'], '-g', 'postgres']))
        os.chown(tls, uid, gid)
        os.chown(tls / 'server.key', uid, gid)
        (tls / 'server.key').chmod(0o600)
        (tls / 'server.crt').chmod(0o644)
        (tls / 'pg_hba.conf').write_text('local all postgres peer\nhostssl all all all scram-sha-256\n')
        (tls / 'pg_hba.conf').chmod(0o644)
        descriptor = os.open(dep.root / 'postgres-password', os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                             0o600)
        with os.fdopen(descriptor, 'w') as stream:
            stream.write(secrets.token_urlsafe(48))
        dep.run(['docker', 'volume', 'create', '--label', label,
                 '--label', 'org.dspacepcirn.install=' + token, name])
        labels = json.loads(dep.run(['docker', 'volume', 'inspect', name,
                                     '--format', '{{json .Labels}}']))
        if labels.get('org.dspacepcirn.install') != token:
            raise Error('Volume preexistente: nada utilizado ou sobrescrito')
        dep.compose(dep.current(), 'up', '-d', '--wait', '--wait-timeout', '180', 'postgres')
        initialize_postgres_role(dep, name)
        write_json(journal_path, {'status': 'ready', 'name': name, 'token': token})
    else:
        if (set(journal) != {'status', 'name', 'token'} or journal.get('status') not in ('creating', 'ready')
                or journal.get('name') != name or not re.fullmatch(r'[a-f0-9]{32}', journal.get('token', ''))):
            raise Error('Criação PostgreSQL interrompida; revisão manual necessária, sem recriação')
        if name not in volumes or (journal['status'] == 'ready' and name not in containers):
            raise Error('Volume/container gerenciado ausente; nada recriado')
        labels = json.loads(dep.run(['docker', 'volume', 'inspect', name,
                                     '--format', '{{json .Labels}}']))
        if (labels.get('org.dspacepcirn.root') != str(dep.root)
                or labels.get('org.dspacepcirn.install') != journal['token']):
            raise Error('Volume pertence a outra instalação')
        for path in ('postgres-password', 'postgres-tls/server.key', 'postgres-tls/server.crt',
                     'postgres-tls/pg_hba.conf'):
            file = dep.root / path
            if not file.is_file() or file.is_symlink() or not file.stat().st_size:
                raise Error('Credenciais/TLS incompletos; revisão manual necessária, nada regenerado')
        if (dep.root / 'postgres-password').stat().st_mode & 0o077:
            raise Error('Senha PostgreSQL exige permissões 600')
        if name in containers:
            verify_postgres_container(dep, name)
        dep.compose(dep.current(), 'up', '-d', '--wait', '--wait-timeout', '180', 'postgres')
        if journal['status'] == 'creating':
            # A lost acknowledgement of COMMIT must never reset existing credentials.
            username = dep.config['DB_USERNAME']
            exists = dep.run(['docker', 'exec', '--user', 'postgres', name, 'psql', '-X', '-At',
                              '-v', 'ON_ERROR_STOP=1', '-U', 'postgres', '-d', 'postgres',
                              '-c', f"SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='{username}');"],
                             timeout=30).strip()
            if exists not in ('t', 'f'):
                raise Error('Estado da função PostgreSQL não comprovado; nada alterado')
            if exists == 'f':
                # Only a database with no user objects may finish a interrupted role setup.
                empty = dep.run(['docker', 'exec', '--user', 'postgres', name, 'psql', '-X', '-At',
                                 '-v', 'ON_ERROR_STOP=1', '-U', 'postgres', '-d', dep.env['PGDATABASE'],
                                 '-c', "SELECT NOT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n "
                                 "ON n.oid=c.relnamespace WHERE n.nspname !~ '^pg_' "
                                 "AND n.nspname <> 'information_schema');"], timeout=30).strip()
                if empty != 't':
                    raise Error('Banco contém objetos: retomada de credenciais recusada')
                initialize_postgres_role(dep, name)
            import preflight
            preflight.database(dep)
            write_json(journal_path, journal | {'status': 'ready'})


def initialize_postgres_role(dep, name):
    """Create role and transfer ownership atomically without logging credentials."""
    username, database = dep.config['DB_USERNAME'], dep.env['PGDATABASE']
    password = dep.config['DB_PASSWORD'].replace("'", "''")
    query = (f'SET log_statement=none; SET log_min_error_statement=panic; '
             f'SET standard_conforming_strings=on; BEGIN; CREATE ROLE "{username}" LOGIN NOSUPERUSER '
             f"NOCREATEDB NOCREATEROLE PASSWORD '{password}'; "
             f'ALTER DATABASE "{database}" OWNER TO "{username}"; '
             f'ALTER SCHEMA public OWNER TO "{username}"; COMMIT;\n')
    dep.run(['docker', 'exec', '-i', '--user', 'postgres', name, 'psql', '-X', '-v',
             'ON_ERROR_STOP=1', '-U', 'postgres', '-d', database], input_text=query, timeout=30)


class Wizard:
    """Seven validated stages with private, durable checkpoints."""
    def __init__(self, args):
        self.root = safe_root(args.root)
        self.interactive = not bool(args.config)
        self.authorize_migrations = bool(getattr(args, 'authorize_migrations', False))
        self.path = self.root / 'wizard.json'
        self.state = read_json(self.path) if self.path.exists() else {'completed': [], 'inputs': {}}
        if (not isinstance(self.state, dict) or set(self.state) != {'completed', 'inputs'}
                or not isinstance(self.state['inputs'], dict)
                or not isinstance(self.state['completed'], list)
                or len(self.state['completed']) > 7
                or self.state['completed'] != list(range(len(self.state['completed'])))):
            raise Error('Estado do wizard inválido')
        self.inputs = self.state['inputs']
        mode = getattr(args, 'installation_mode', None)
        if mode:
            if self.inputs.get('installation_mode', mode) != mode:
                raise Error('Retomada exige o mesmo modo de instalação')
            self.inputs['installation_mode'] = mode
        for name, value in (('manifest', args.manifest), ('package', args.data_package)):
            if value:
                value = str(Path(value).absolute())
                if self.inputs.get(name, value) != value:
                    raise Error('Retomada exige os mesmos manifesto e pacote')
                self.inputs[name] = value
        if args.config:
            incoming = configuration(args.config)
            if 'config' in self.inputs and incoming != self.inputs['config']:
                if (len(self.state['completed']) > 1 or (self.root / 'config.json').exists()
                        or (self.root / 'postgres.json').exists()):
                    raise Error('Configuração diverge do estado de retomada')
            self.inputs['config'] = incoming
        self.dep = None
        self.dependencies_approved = os.environ.get('DSPACEPCIRN_BOOTSTRAP_APPROVED') == '1'
        if 'config' in self.inputs and (self.root / 'config.json').exists():
            if configuration(self.root / 'config.json') != self.inputs['config']:
                raise Error('Configuração existente diverge; nada sobrescrito')

    def save(self):
        write_json(self.path, self.state)

    def release(self):
        if not self.inputs.get('manifest'):
            if not self.interactive:
                raise Error('--manifest obrigatório')
            from releases import discover
            print('Procurando versões disponíveis...')
            path = discover(self.root)
            found = manifest(path)
            print('Versão encontrada: ' + found['version'] +
                  (' (versão de testes)' if '-' in found['version'] else ''))
            if not self.confirm('Instalar esta versão?'):
                raise Error('Instalação cancelada; nenhum banco alterado')
            self.inputs['manifest'] = str(path)
            self.save()
        path = Path(self.inputs['manifest'])
        digest = checksum(path)
        if self.state['completed'] and self.inputs.get('manifest_checksum', digest) != digest:
            raise Error('Manifesto alterado desde o diagnóstico')
        release = manifest(path)
        self.inputs['manifest_checksum'] = digest
        return release

    def diagnostic(self):
        import preflight
        if self.interactive:
            import host_setup
            print('Verificando ambiente...')
            info = host_setup.prepare(self.host_run, self.confirm_dependencies, root=str(self.root))
            print('✓ Ubuntu ' + info['version'] + ' ' + info['architecture'].upper())
            print('✓ Docker e Docker Compose disponíveis\n✓ Recursos suficientes')
            if 'config' not in self.inputs:
                self.inputs['runtime'] = preflight.select_resources(self.host_run, self.root)
                self.save()
        release = self.release()
        # Host diagnosis precedes choosing or accessing any database.
        probe = SimpleNamespace(root=self.root, run=self.host_run,
                                config=self.inputs.get('config', self.inputs.get('runtime', {})))
        preflight.check(probe, release, server_only=True)
        print('✓ Manifesto validado\n✓ Imagens disponíveis para a arquitetura do servidor')

    def confirm(self, message):
        if not self.interactive:
            return self.authorize_migrations
        return ask(message + ' [S/n]', 'S').lower() in ('s', 'sim', 'y', 'yes')

    def confirm_dependencies(self, message):
        if not self.dependencies_approved:
            self.dependencies_approved = self.confirm(message)
        return self.dependencies_approved

    def host_run(self, args, **kwargs):
        # Reuse the filtered process runner without requiring database credentials.
        dep = Deployment.__new__(Deployment)
        from pcirn import docker_config
        dep.env = {k: v for k, v in os.environ.items()
                   if not k.startswith(('COMPOSE_', 'DOCKER_', 'PG', 'DSPACE_', 'DB_'))}
        registry = docker_config()
        if registry:
            dep.env['DOCKER_CONFIG'] = registry
        return dep.run(args, **kwargs)

    def postgres(self):
        import preflight
        if 'config' not in self.inputs:
            choice = ask('1. PostgreSQL em Docker\n2. PostgreSQL externo\nEscolha', '1')
            if choice not in ('1', '2'):
                raise Error('Escolha 1 ou 2')
            mode = 'docker' if choice == '1' else 'external'
            host = '127.0.0.1' if mode == 'docker' else ask('Host PostgreSQL')
            if mode == 'docker':
                import socket
                from releases import postgres_image
                info = json.loads(self.host_run(['docker', 'info', '--format', '{{json .}}'], timeout=30))
                arch = {'x86_64': 'amd64', 'aarch64': 'arm64'}.get(info['Architecture'], info['Architecture'])
                image = postgres_image(self.host_run, arch)
                with socket.socket() as listener:
                    listener.bind(('127.0.0.1', 0))
                    port = str(listener.getsockname()[1])
                database, username = 'dspace', 'dspace'
                password = secrets.token_urlsafe(48)
            else:
                port = ask('Porta PostgreSQL', '5432')
                database = ask('Banco', 'dspace')
                username = ask('Usuário', 'dspace')
                password = ask('Senha', secret=True)
            if mode == 'docker':
                params = {'sslmode': 'verify-ca', 'sslrootcert': str(self.root / 'postgres-tls/server.crt')}
            else:
                params = {'sslmode': 'verify-full',
                          'sslrootcert': '/etc/ssl/certs/ca-certificates.crt'}
            config = {'DB_URL': f'jdbc:postgresql://{host}:{port}/{database}?' + urlencode(params),
                      'DB_USERNAME': username, 'DB_PASSWORD': password, 'PG_MODE': mode,
                      'PUBLIC_UI_URL': 'https://repository.invalid',
                      'PUBLIC_REST_URL': 'https://repository.invalid/server',
                      'PUBLIC_REST_HOST': 'repository.invalid'}
            config.update(self.inputs.get('runtime', {}))
            if mode == 'docker':
                config['PG_IMAGE'] = image
                config['PG_MAJOR'] = '16'
                validate_docker_config(config, self.root)
            self.inputs['config'] = config
            self.save()
        config = self.inputs['config']
        if config.get('PG_MODE') == 'docker':
            validate_docker_config(config, self.root)
            self.dep = self.seed(config)
            provision_postgres(self.dep)
        temporary = self.root / 'wizard-config.json'
        write_json(temporary, config)
        config = configuration(temporary)
        probe = Deployment(self.root, config=config)
        if self.interactive and config.get('PG_MODE') != 'docker':
            import host_setup
            major = int(probe.sql('SHOW server_version_num;')) // 10000
            host_setup.ensure_clients(self.host_run, self.confirm_dependencies, major)
            config['PG_MAJOR'] = str(major)
            self.inputs['config'] = config
            write_json(temporary, config)
            probe = Deployment(self.root, config=config)
        preflight.database(probe)
        if not (self.root / 'data-import.json').exists() and probe.user_objects():
            raise Error('Banco não vazio: importação recusada')
        self.dep = self.seed(config)

    def seed(self, config):
        path = self.root / 'wizard-config.json'
        write_json(path, config)
        return provision(SimpleNamespace(root=self.root, config=path, manifest=self.inputs['manifest']))

    def import_data(self):
        selected_new = False
        if 'installation_mode' not in self.inputs:
            # Explicit packages retain the existing noninteractive migration contract.
            if self.inputs.get('package') or not self.interactive:
                choice = '2'
            else:
                available = self.release().get('database', {}).get('fresh_bootstrap') == 'pcirn-fresh-v1'
                choice = ask('Como deseja instalar o DSpace?\n1. Instalação nova' +
                             ('' if available else ' (indisponível nesta versão)') +
                             '\n2. Migrar repositório existente\nEscolha', '1' if available else '2')
            if choice not in ('1', '2'):
                raise Error('Escolha 1 ou 2')
            if choice == '1':
                self.validate_bootstrap()
                selected_new = True
            self.inputs['installation_mode'] = 'new' if choice == '1' else 'migration'
            self.save()
        if self.inputs['installation_mode'] == 'new':
            if not selected_new:
                self.validate_bootstrap()
            return
        from data_migration import PACKAGE_FILES, REQUIRED_TABLES
        if not self.inputs.get('package'):
            if not self.interactive:
                raise Error('--data-package obrigatório para o wizard')
            self.inputs['package'] = str(Path(ask('Diretório do pacote export-data')).absolute())
        package = Path(self.inputs['package'])
        hashes = read_json(package / 'checksums.json')
        if set(hashes) != PACKAGE_FILES or any(checksum(package / n) != hashes[n] for n in PACKAGE_FILES):
            raise Error('Pacote incompleto ou checksum divergente')
        if manifest(package / 'release.json') != self.release():
            raise Error('Pacote e manifesto devem usar a mesma versão; atualize após a instalação')
        report = read_json(package / 'source-report.json')
        if report.get('schema_version') != 1 or not REQUIRED_TABLES <= set(report.get('tables', {})):
            raise Error('Relatório de origem inválido')
        profile = report.get('database_profile', 'institutional')
        if profile not in ('fresh', 'institutional'):
            raise Error('Perfil do banco de origem inválido')
        if profile == 'fresh':
            self.validate_bootstrap()
        self.inputs['database_profile'] = profile
        self.inputs['package_checksums'] = hashes

    def validate_bootstrap(self):
        """Require the selected backend to implement the verified empty bootstrap."""
        self.dep = Deployment(self.root)
        release = self.release()
        if (release.get('database', {}).get('fresh_bootstrap') != 'pcirn-fresh-v1'
                or not release['database'].get('fresh_migrations')):
            raise Error('Esta versão não oferece instalação nova validada; use migração ou uma versão compatível')
        self.dep.compose(release, 'pull', 'dspace')
        capability = self.dep.compose(release, 'run', '--rm', '--no-deps', '-T',
                                      '--entrypoint', '/dspace/bin/dspace',
                                      'dspace', 'database', 'fresh-capability').strip()
        if capability != 'pcirn-fresh-v1':
            raise Error('Esta imagem não comprova suporte à instalação nova; selecione uma versão compatível')

    def institutional(self):
        config = self.inputs['config'].copy()
        if (self.inputs.get('installation_mode') == 'new'
                or self.inputs.get('database_profile') == 'fresh'):
            config['DB_PROFILE'] = 'fresh'
        if self.interactive:
            config['DSPACE_NAME'] = ask('Nome do repositório', config.get('DSPACE_NAME', 'Repositório'))
            config['DSPACE_SHORTNAME'] = config.get('DSPACE_SHORTNAME', 'DSPACEPCIRN')
            config['PUBLIC_UI_URL'] = ask('Endereço público HTTPS do repositório (ex.: https://repositorio.exemplo.br)')
            config['PUBLIC_REST_URL'] = config['PUBLIC_UI_URL'].rstrip('/') + '/server'
            config['PUBLIC_REST_HOST'] = urlsplit(config['PUBLIC_REST_URL']).hostname or ''
        path = self.root / 'wizard-config.json'
        write_json(path, config)
        configuration(path)
        # Only the wizard's own provisional configuration may be replaced.
        existing = configuration(self.root / 'config.json')
        provisional = self.inputs['config'].copy()
        provisional.pop('DB_PROFILE', None)
        if existing != self.inputs['config'] and existing != provisional:
            raise Error('Configuração existente diverge; nada sobrescrito')
        write_json(self.root / 'config.json', config)
        self.inputs['config'] = config
        self.dep = Deployment(self.root)
        import preflight
        preflight.check(self.dep, self.release())

    def installation(self):
        from data_migration import migrate_data, verify_data
        self.dep = Deployment(self.root)
        import preflight
        preflight.check(self.dep, self.release())
        if self.inputs.get('installation_mode') == 'new':
            self.new_installation()
            return
        package = Path(self.inputs['package'])
        if read_json(package / 'checksums.json') != self.inputs['package_checksums']:
            raise Error('Pacote alterado desde a validação')
        journal = self.root / 'operation.json'
        if journal.exists():
            raise Error('Operação interrompida; revisão manual necessária, sem reimportação')
        imported = self.root / 'data-import.json'
        if not imported.exists():
            migrate_data(self.dep, package)
        record = read_json(imported)
        if record != {'status': 'verified', 'checksums': self.inputs['package_checksums']}:
            raise Error('Importação existente não corresponde ao pacote')
        verify_data(self.dep, package / 'source-report.json')
        if self.dep.pending(self.release()):
            raise Error('Histórico exige migrations: execute update com autorização após revisão')
        # Existing deploy owns pull, backup, health and interrupted-operation handling.
        self.dep.deploy(self.release(), False, initial=True)

    def new_installation(self):
        release = self.release()
        self.validate_bootstrap()
        path = self.root / 'operation.json'
        fingerprint = hashlib.sha256(json.dumps(self.inputs['config'], sort_keys=True).encode()).hexdigest()
        journal = read_json(path) if path.exists() else None
        installed = self.root / 'installed.json'
        if not journal and installed.exists():
            if read_json(installed) != {'version': release['version']} or self.dep.pending(release):
                raise Error('Instalação existente diverge da inicialização solicitada')
            self.dep.healthy(release)
            return
        if journal:
            if (journal.get('kind') != 'fresh-install' or journal.get('target') != release
                    or journal.get('configuration') != fingerprint
                    or journal.get('stage') not in ('prepared', 'migrating', 'migrated')):
                raise Error('Operação interrompida diverge: revisão administrativa necessária')
        else:
            if self.dep.user_objects():
                raise Error('Banco não vazio: inicialização recusada; nada apagado')
            if not self.confirm('Autorizar a inicialização do banco e as migrations desta versão?'):
                raise Error('Inicialização não autorizada')
            self.dep.compose(release, 'pull')
            journal = {'kind': 'fresh-install', 'target': release, 'configuration': fingerprint,
                       'stage': 'prepared'}
            write_json(path, journal)
        if journal['stage'] != 'migrated':
            pending = self.dep.pending(release)
            if pending:
                if journal['stage'] == 'migrating' and not self.confirm('Autorizar a retomada das migrations?'):
                    raise Error('Retomada não autorizada; dados preservados')
                journal['stage'] = 'migrating'
                write_json(path, journal)
                self.dep.compose(release, 'run', '--rm', '--no-deps', '-T', '--entrypoint',
                                 '/dspace/bin/dspace', 'dspace', 'database', 'migrate')
                if self.dep.pending(release):
                    raise Error('Inicialização incompleta; aplicação permanece parada')
            journal['stage'] = 'migrated'
            write_json(path, journal)
        elif self.dep.pending(release):
            raise Error('Histórico diverge da inicialização validada; nada alterado')
        self.dep.up(release)
        write_json(self.root / 'installed.json', {'version': release['version']})
        path.unlink()

    def services(self):
        self.dep = Deployment(self.root)
        self.dep.healthy(self.release())

    def report(self):
        result = {'status': 'verified', 'version': self.release()['version'],
                  'postgresql': self.inputs['config'].get('PG_MODE', 'external'),
                  'steps': list(STEPS), 'data_verified': True,
                  'installation_mode': self.inputs.get('installation_mode', 'migration'),
                  'ui': self.inputs['config']['PUBLIC_UI_URL'],
                  'rest': self.inputs['config']['PUBLIC_REST_URL']}
        write_json(self.root / 'report.json', result)
        print('DSPACEPCIRN instalado com sucesso. Serviços internos verificados.')
        print('Instalação validada. Relatório: ' + str(self.root / 'report.json'))
        print('URLs HTTPS exigem proxy reverso configurado pelo administrador.')

    def run(self):
        actions = (self.diagnostic, self.postgres, self.import_data, self.institutional,
                   self.installation, self.services, self.report)
        print('DSPACEPCIRN')
        if ((self.root / 'operation.json').exists()
                and read_json(self.root / 'operation.json').get('kind') != 'fresh-install'):
            raise Error('Operação interrompida; revisão manual necessária, sem reimportação')
        if self.state['completed'] == list(range(7)):
            self.services()
            self.report()
            return 0
        for index, action in enumerate(actions):
            if index in self.state['completed']:
                continue
            while True:
                print(f'Etapa {index + 1}/7 — {STEPS[index]}')
                try:
                    action()
                    self.state['completed'].append(index)
                    self.save()
                    break
                except (Error, OSError, ValueError, KeyError, TypeError) as error:
                    self.save()
                    write_json(self.root / 'diagnostic.json', {
                        'failed_stage': STEPS[index], 'completed': self.state['completed'],
                        'message': str(error) if isinstance(error, Error) else type(error).__name__,
                        'data_preserved': True})
                    print(str(error) if isinstance(error, Error) else type(error).__name__)
                    if not self.interactive or (self.root / 'operation.json').exists():
                        raise
                    choice = ask('1. Corrigir e tentar novamente\n2. Sair e retomar depois', '2')
                    if choice != '1':
                        raise Error('Etapa pendente; execute sudo dspacepcirn para retomar')
                    if index == 0:
                        self.inputs.pop('manifest', None)
                        self.inputs.pop('manifest_checksum', None)
                    elif index == 1 and not (self.root / 'postgres.json').exists():
                        self.inputs.pop('config', None)
                    elif index == 2:
                        self.inputs.pop('package', None)
        return 0


def install(args):
    if not args.config and (not os.isatty(0) or os.geteuid() != 0):
        raise Error('Instalação interativa exige terminal e sudo dspacepcirn')
    os.umask(0o077)
    root = safe_root(args.root)
    with (root / '.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise Error('Outra operação administrativa está em execução') from exc
        return Wizard(args).run()


def menu(args):
    """Keep administration routed through the same CLI commands as automation."""
    if not os.isatty(0):
        raise Error('Menu exige terminal; use um comando com --config para automação')
    if os.geteuid() != 0:
        raise Error('Execute sudo dspacepcirn')
    from pcirn import main
    while True:
        print('\n╔══════════════════════════════════════════════╗\n'
              '║                  DSPACEPCIRN                  ║\n'
              '║          Repositório Institucional            ║\n'
              '╚══════════════════════════════════════════════╝\n'
              '1. Instalar DSpace\n2. Atualizar DSpace\n3. Fazer backup\n'
              '4. Restaurar backup\n5. Verificar funcionamento\n'
              '6. Configurações avançadas\n0. Sair')
        choice = ask('Escolha', '0')
        if choice == '0':
            return 0
        try:
            if choice == '1':
                install(args)
                continue
            if choice == '6':
                advanced(args)
                continue
            command = {'2': 'update', '3': 'backup', '4': 'restore', '5': 'health'}.get(choice)
            if not command:
                print('Escolha inválida.')
                continue
            argv = [command, '--root', str(args.root)]
            if command == 'update':
                from releases import discover
                root = safe_root(args.root)
                path = discover(root)
                release = manifest(path)
                print('Versão encontrada: ' + release['version'] +
                      (' (versão de testes)' if '-' in release['version'] else ''))
                if ask('Atualizar para esta versão? [S/n]', 'S').lower() not in ('s', 'sim'):
                    continue
                argv += ['--manifest', str(path)]
                if Deployment(root).pending(release):
                    if ask('Autorizar migrations após backup? [s/N]', 'N').lower() not in ('s', 'sim'):
                        continue
                    argv += ['--authorize-migrations']
            elif command == 'restore':
                argv += ['--backup', ask('Diretório do backup')]
                if ask('Autorizar restauração após backup de segurança? [s/N]', 'N').lower() not in ('s', 'sim'):
                    continue
                argv += ['--authorize-restore']
            main(argv)
        except (Error, OSError, ValueError, KeyError, TypeError) as error:
            print(str(error) if isinstance(error, Error) else type(error).__name__)


def advanced(args):
    """Technical administration continues to use the established CLI operations."""
    from pcirn import main
    print('1. Diagnóstico\n2. Status\n3. Logs\n4. Exportar dados para migração\n'
          '5. Verificar dados\n6. Selecionar versão para instalação\n'
          '7. Atualizar gerenciador\n8. Autenticar no GHCR\n0. Voltar')
    choice = ask('Escolha', '0')
    if choice == '0':
        return
    if choice == '8':
        user = ask('Usuário GitHub')
        token = ask('Token com permissão de leitura de pacotes', secret=True)
        Wizard(args).host_run(['docker', 'login', 'ghcr.io', '--username', user, '--password-stdin'],
                              input_text=token + '\n', timeout=30)
        print('Autenticação GHCR concluída.')
        return
    if choice == '6':
        from releases import discover
        if (Path(args.root) / 'wizard.json').exists():
            raise Error('Instalação em andamento: preserve a versão do checkpoint')
        args.manifest = discover(safe_root(args.root), version=ask('Versão oficial (ex.: v1.0.0)'))
        install(args)
        return
    command = {'1': 'doctor', '2': 'status', '3': 'logs', '4': 'export-data',
               '5': 'verify-data', '7': 'update-manager'}.get(choice)
    if not command:
        raise Error('Escolha inválida')
    argv = [command, '--root', str(args.root)]
    if command == 'export-data':
        argv += ['--output', ask('Diretório novo para exportação')]
    if command == 'update-manager':
        if ask('Atualizar somente o gerenciador? [S/n]', 'S').lower() not in ('s', 'sim'):
            return
    main(argv)

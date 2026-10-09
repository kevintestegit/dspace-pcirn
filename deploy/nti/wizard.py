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
                   provision, read_json, write_json)

STEPS = ('Diagnóstico do servidor', 'Escolha do PostgreSQL', 'Importação de dados',
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


def provision_postgres(dep):
    """Create once; uncertain creation or initialization never retries automatically."""
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
        with (dep.root / 'postgres-password').open('x') as stream:
            stream.write(secrets.token_urlsafe(48))
        dep.run(['docker', 'volume', 'create', '--label', label,
                 '--label', 'org.dspacepcirn.install=' + token, name])
        labels = json.loads(dep.run(['docker', 'volume', 'inspect', name,
                                     '--format', '{{json .Labels}}']))
        if labels.get('org.dspacepcirn.install') != token:
            raise Error('Volume preexistente: nada utilizado ou sobrescrito')
        dep.compose(dep.current(), 'up', '-d', '--wait', '--wait-timeout', '180', 'postgres')
        # Credentials travel through stdin, never argv, Compose interpolation or logs.
        username = dep.config['DB_USERNAME']
        database = dep.env['PGDATABASE']
        password = dep.config['DB_PASSWORD'].replace("'", "''")
        query = (f'SET log_statement=none; SET log_min_error_statement=panic; '
                 f'SET standard_conforming_strings=on; CREATE ROLE "{username}" LOGIN NOSUPERUSER '
                 f"NOCREATEDB NOCREATEROLE PASSWORD '{password}'; "
                 f'ALTER DATABASE "{database}" OWNER TO "{username}"; '
                 f'\n\\connect {database}\nALTER SCHEMA public OWNER TO "{username}";\n')
        dep.run(['docker', 'exec', '-i', '--user', 'postgres', name, 'psql', '-X', '-v',
                 'ON_ERROR_STOP=1', '-U', 'postgres', '-d', 'postgres'], input_text=query)
        write_json(journal_path, {'status': 'ready', 'name': name, 'token': token})
    else:
        if (set(journal) != {'status', 'name', 'token'} or journal.get('status') != 'ready'
                or journal.get('name') != name or not re.fullmatch(r'[a-f0-9]{32}', journal.get('token', ''))):
            raise Error('Criação PostgreSQL interrompida; revisão manual necessária, sem recriação')
        if name not in volumes or name not in containers:
            raise Error('Volume/container gerenciado ausente; nada recriado')
        labels = json.loads(dep.run(['docker', 'volume', 'inspect', name,
                                     '--format', '{{json .Labels}}']))
        if (labels.get('org.dspacepcirn.root') != str(dep.root)
                or labels.get('org.dspacepcirn.install') != journal['token']):
            raise Error('Volume pertence a outra instalação')
        dep.compose(dep.current(), 'up', '-d', '--wait', '--wait-timeout', '180', 'postgres')


class Wizard:
    """Seven validated stages with private, durable checkpoints."""
    def __init__(self, args):
        self.root = safe_root(args.root)
        self.interactive = not bool(args.config)
        self.path = self.root / 'wizard.json'
        self.state = read_json(self.path) if self.path.exists() else {'completed': [], 'inputs': {}}
        if (not isinstance(self.state, dict) or set(self.state) != {'completed', 'inputs'}
                or not isinstance(self.state['inputs'], dict)
                or not isinstance(self.state['completed'], list)
                or len(self.state['completed']) > 7
                or self.state['completed'] != list(range(len(self.state['completed'])))):
            raise Error('Estado do wizard inválido')
        self.inputs = self.state['inputs']
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
        if 'config' in self.inputs and (self.root / 'config.json').exists():
            if configuration(self.root / 'config.json') != self.inputs['config']:
                raise Error('Configuração existente diverge; nada sobrescrito')

    def save(self):
        write_json(self.path, self.state)

    def release(self):
        if not self.inputs.get('manifest'):
            if not self.interactive:
                raise Error('--manifest obrigatório')
            self.inputs['manifest'] = str(Path(ask('Manifesto da versão')).absolute())
        path = Path(self.inputs['manifest'])
        digest = checksum(path)
        if self.state['completed'] and self.inputs.get('manifest_checksum', digest) != digest:
            raise Error('Manifesto alterado desde o diagnóstico')
        release = manifest(path)
        self.inputs['manifest_checksum'] = digest
        return release

    def diagnostic(self):
        import preflight
        release = self.release()
        # Host diagnosis precedes choosing or accessing any database.
        probe = SimpleNamespace(root=self.root, run=self.host_run)
        preflight.check(probe, release, server_only=True)

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
            port = ask('Porta PostgreSQL', '55432' if mode == 'docker' else '5432')
            database = ask('Banco', 'dspace')
            username = ask('Usuário', 'dspace')
            password = ask('Senha', secret=True)
            if mode == 'docker':
                params = {'sslmode': 'verify-ca', 'sslrootcert': str(self.root / 'postgres-tls/server.crt')}
            else:
                tls = ask('TLS: require, verify-ca ou verify-full', 'verify-full')
                params = {'sslmode': tls}
                if tls in ('verify-ca', 'verify-full'):
                    params['sslrootcert'] = ask('Arquivo absoluto da CA')
            config = {'DB_URL': f'jdbc:postgresql://{host}:{port}/{database}?' + urlencode(params),
                      'DB_USERNAME': username, 'DB_PASSWORD': password, 'PG_MODE': mode,
                      'PUBLIC_UI_URL': 'https://repository.invalid',
                      'PUBLIC_REST_URL': 'https://repository.invalid/server',
                      'PUBLIC_REST_HOST': 'repository.invalid'}
            if mode == 'docker':
                config['PG_IMAGE'] = ask('Imagem PostgreSQL (postgres@sha256:<digest>)')
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
        preflight.database(probe)
        if not (self.root / 'data-import.json').exists() and probe.user_objects():
            raise Error('Banco não vazio: importação recusada')
        self.dep = self.seed(config)

    def seed(self, config):
        path = self.root / 'wizard-config.json'
        write_json(path, config)
        return provision(SimpleNamespace(root=self.root, config=path, manifest=self.inputs['manifest']))

    def import_data(self):
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
        self.inputs['package_checksums'] = hashes

    def institutional(self):
        config = self.inputs['config'].copy()
        if self.interactive:
            config['DSPACE_NAME'] = ask('Nome do repositório', config.get('DSPACE_NAME', 'Repositório'))
            config['DSPACE_SHORTNAME'] = ask('Sigla', config.get('DSPACE_SHORTNAME', 'DSPACEPCIRN'))
            config['PUBLIC_UI_URL'] = ask('URL pública HTTPS', config['PUBLIC_UI_URL'])
            config['PUBLIC_REST_URL'] = ask('URL REST HTTPS terminada em /server', config['PUBLIC_REST_URL'])
            config['PUBLIC_REST_HOST'] = urlsplit(config['PUBLIC_REST_URL']).hostname or ''
        path = self.root / 'wizard-config.json'
        write_json(path, config)
        configuration(path)
        # Only the wizard's own provisional configuration may be replaced.
        existing = configuration(self.root / 'config.json')
        if existing != self.inputs['config']:
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

    def services(self):
        self.dep = Deployment(self.root)
        self.dep.healthy(self.release())

    def report(self):
        result = {'status': 'verified', 'version': self.release()['version'],
                  'postgresql': self.inputs['config'].get('PG_MODE', 'external'),
                  'steps': list(STEPS), 'data_verified': True,
                  'ui': self.inputs['config']['PUBLIC_UI_URL'],
                  'rest': self.inputs['config']['PUBLIC_REST_URL']}
        write_json(self.root / 'report.json', result)
        print('Instalação validada. Relatório: ' + str(self.root / 'report.json'))
        print('URLs HTTPS exigem proxy reverso configurado pelo administrador.')

    def run(self):
        actions = (self.diagnostic, self.postgres, self.import_data, self.institutional,
                   self.installation, self.services, self.report)
        print('DSPACEPCIRN')
        if (self.root / 'operation.json').exists():
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
        print('\nDSPACEPCIRN\n1. Instalar / retomar\n2. Status\n3. Diagnóstico\n'
              '4. Validar serviços\n5. Backup\n6. Exportar dados\n7. Verificar dados\n0. Sair')
        choice = ask('Escolha', '0')
        if choice == '0':
            return 0
        if choice == '1':
            install(args)
            continue
        command = {'2': 'status', '3': 'doctor', '4': 'health', '5': 'backup',
                   '6': 'export-data', '7': 'verify-data'}.get(choice)
        if not command:
            print('Escolha inválida.')
            continue
        argv = [command, '--root', str(args.root)]
        if command == 'export-data':
            argv += ['--output', ask('Diretório novo para exportação')]
        try:
            main(argv)
        except (Error, OSError, ValueError) as error:
            print(str(error) if isinstance(error, Error) else type(error).__name__)

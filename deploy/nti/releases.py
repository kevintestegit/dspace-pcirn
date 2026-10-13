"""Resolve official releases and immutable images without executing downloads."""
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from pcirn import Error, manifest

REPOSITORY = 'kevintestegit/dspace-pcirn'
API = 'https://api.github.com/repos/' + REPOSITORY
VERSION = re.compile(r'v?([0-9]+)\.([0-9]+)\.([0-9]+)(?:-rc([0-9]+))?\Z')
SHA = re.compile(r'[a-f0-9]{40}\Z')
DIGEST = re.compile(r'sha256:[a-f0-9]{64}\Z')
TIMEOUT = 30
MAX_JSON = 2 * 1024 * 1024


class _OfficialRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlsplit(newurl)
        if (parsed.scheme != 'https' or parsed.username or parsed.password
                or parsed.hostname not in ('api.github.com', 'github.com',
                                           'release-assets.githubusercontent.com')):
            raise Error('Download recusado: redirecionamento fora do GitHub')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


urlopen = build_opener(_OfficialRedirect()).open


def _download(url, limit=MAX_JSON):
    """Read bounded HTTPS data from official GitHub hosts; hide raw network errors."""
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.hostname not in ('api.github.com', 'github.com')
            or parsed.username or parsed.password):
        raise Error('Download recusado: origem GitHub oficial obrigatória')
    request = Request(url, headers={'Accept': 'application/vnd.github+json',
                                   'User-Agent': 'dspacepcirn-installer'})
    try:
        with urlopen(request, timeout=TIMEOUT) as response:
            final = urlsplit(response.geturl())
            if final.scheme != 'https' or final.hostname not in (
                    'api.github.com', 'github.com', 'release-assets.githubusercontent.com'):
                raise Error('Download recusado: redirecionamento fora do GitHub')
            payload = response.read(limit + 1)
    except HTTPError as exc:
        if exc.code in (401, 403, 429):
            raise Error('GitHub recusou a consulta ou limitou requisições; aguarde e tente novamente') from None
        if exc.code == 404:
            raise Error('Release ou arquivo oficial não encontrado no GitHub') from None
        raise Error('GitHub indisponível; tente novamente sem alterar a instalação') from None
    except (URLError, TimeoutError, OSError):
        raise Error('Não foi possível acessar GitHub; verifique rede, DNS, HTTPS e tente novamente') from None
    if len(payload) > limit:
        raise Error('Download excedeu o tamanho permitido')
    return payload


def _json(url):
    try:
        return json.loads(_download(url))
    except (ValueError, UnicodeError):
        raise Error('GitHub retornou JSON inválido') from None


def select(version=None):
    """Choose the highest stable SemVer, otherwise the highest release candidate."""
    if version is not None:
        if not VERSION.fullmatch(version):
            raise Error('Versão inválida: use X.Y.Z ou X.Y.Z-rcN')
        result = _json(API + '/releases/tags/' + quote('v' + version.lstrip('v'), safe=''))
        if not isinstance(result, dict) or result.get('draft'):
            raise Error('Release oficial indisponível')
        if result.get('tag_name') != 'v' + version.lstrip('v'):
            raise Error('GitHub retornou uma versão diferente da solicitada')
        return result
    candidates = []
    for page in range(1, 6):
        entries = _json(API + f'/releases?per_page=100&page={page}')
        if not isinstance(entries, list):
            raise Error('Lista de releases oficial inválida')
        for entry in entries:
            match = VERSION.fullmatch(entry.get('tag_name', '')) if isinstance(entry, dict) else None
            if match and not entry.get('draft'):
                rc = match.group(4)
                # RC tags are test releases even when GitHub's flag is false.
                stable = rc is None and not entry.get('prerelease')
                if stable or rc is not None:
                    candidates.append((stable, tuple(int(match.group(i)) for i in (1, 2, 3)),
                                       int(rc or 0), entry))
        if len(entries) < 100:
            break
    else:
        raise Error('Muitas releases: selecione uma versão nas configurações avançadas')
    if not candidates:
        raise Error('Nenhuma versão estável ou RC oficial disponível')
    return max(candidates, key=lambda item: item[:3])[3]


def _asset(release, name):
    assets = [asset for asset in release.get('assets', []) if asset.get('name') == name]
    if len(assets) != 1:
        raise Error(f'Release não contém um único {name}; escolha outra versão oficial')
    asset = assets[0]
    expected = 'https://github.com/' + REPOSITORY + '/releases/download/' + release['tag_name'] + '/' + name
    if asset.get('browser_download_url') != expected:
        raise Error('Arquivo não pertence à release oficial selecionada')
    digest = asset.get('digest', '')
    if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
        raise Error('Arquivo oficial sem digest SHA-256 verificável; download recusado')
    return asset


def _verified_asset(release, name, limit):
    asset = _asset(release, name)
    if type(asset.get('size')) is not int or not 0 < asset['size'] <= limit:
        raise Error('Tamanho do arquivo oficial inválido')
    payload = _download(asset['browser_download_url'], limit)
    if (len(payload) != asset['size']
            or 'sha256:' + hashlib.sha256(payload).hexdigest() != asset['digest']):
        raise Error('Checksum do arquivo oficial divergente; download recusado')
    return payload


def _directory(root, version):
    root = Path(root).absolute()
    directory = root / 'downloads' / version
    if directory.resolve() != directory:
        raise Error('Diretório de download não pode conter links simbólicos')
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    return directory


def discover(root, version=None):
    """Download and validate a release manifest, tag commit, and official image digests."""
    release = select(version)
    selected = release['tag_name'].lstrip('v')
    payload = _verified_asset(release, 'release-manifest.json', MAX_JSON)
    directory = _directory(root, selected)
    with tempfile.NamedTemporaryFile(dir=directory, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(payload)
    try:
        try:
            data = manifest(temporary)
        except (ValueError, KeyError, TypeError, AttributeError):
            raise Error('Manifesto oficial inválido') from None
        source = data.get('source', {})
        if not isinstance(source, dict):
            raise Error('Manifesto: commit de origem inválido')
        commit = source.get('commit', '')
        if data['version'] != selected or not isinstance(commit, str) or not SHA.fullmatch(commit):
            raise Error('Manifesto: versão ou commit de origem inválido')
        tag = _json(API + '/commits/' + quote(release['tag_name'], safe=''))
        if not isinstance(tag, dict) or tag.get('sha') != commit:
            raise Error('Commit do manifesto diverge da tag oficial; instalação recusada')
        for key, suffix in (('backend', 'backend'), ('solr', 'solr'), ('frontend', 'angular')):
            image = data['images'][key]
            if image.split('@')[0] != 'ghcr.io/kevintestegit/dspace-pcirn-' + suffix:
                raise Error('Manifesto contém imagem fora do projeto oficial')
        target = directory / 'release-manifest.json'
        if target.is_symlink():
            raise Error('Manifesto armazenado não pode ser link simbólico')
        if target.exists() and target.read_bytes() != payload:
            raise Error('Manifesto da mesma versão mudou; preserve a instalação e investigue a release')
        os.replace(temporary, target)
        return target
    finally:
        temporary.unlink(missing_ok=True)


def download_manager(root, version=None):
    """Download a manager release asset only when its published SHA-256 is available."""
    release = select(version)
    payload = _verified_asset(release, 'dspacepcirn-manager.tar.gz', 32 * 1024 * 1024)
    directory = _directory(root, release['tag_name'].lstrip('v'))
    with tempfile.NamedTemporaryFile(dir=directory, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(payload)
    try:
        target = directory / 'dspacepcirn-manager.tar.gz'
        if target.is_symlink():
            raise Error('Pacote do gerenciador não pode ser link simbólico')
        if target.exists() and target.read_bytes() != payload:
            raise Error('Pacote da mesma versão mudou; atualização recusada')
        os.replace(temporary, target)
        return target, hashlib.sha256(payload).hexdigest()
    finally:
        temporary.unlink(missing_ok=True)


def docker_architecture(run):
    """Detect supported Linux architecture from the Docker daemon."""
    try:
        info = json.loads(run(['docker', 'info', '--format', '{{json .}}'], timeout=TIMEOUT))
        arch = {'x86_64': 'amd64', 'aarch64': 'arm64'}.get(info['Architecture'], info['Architecture'])
        if info['OSType'] != 'linux' or arch not in ('amd64', 'arm64'):
            raise Error('Docker precisa executar Linux AMD64 ou ARM64')
        return arch
    except (ValueError, KeyError, TypeError):
        raise Error('Docker retornou arquitetura inválida') from None


def _descriptors(run, image, arch):
    if arch not in ('amd64', 'arm64'):
        raise Error('Arquitetura suportada: AMD64 ou ARM64')
    try:
        entries = json.loads(run(['docker', 'manifest', 'inspect', '--verbose', image], timeout=TIMEOUT))
    except Error:
        raise Error('Imagem indisponível: verifique rede e acesso ao registro; para GHCR privado, '
                    'configure autenticação nas configurações avançadas') from None
    except (ValueError, TypeError):
        raise Error('Registro retornou manifesto de imagem inválido') from None
    if isinstance(entries, dict):
        entries = [entries]
    if not isinstance(entries, list):
        raise Error('Registro retornou manifesto de imagem inválido')
    matches = []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get('Descriptor'), dict):
            raise Error('Registro retornou descritor de imagem inválido')
        descriptor = entry['Descriptor']
        platform = descriptor.get('platform', {})
        if not isinstance(platform, dict):
            raise Error('Registro retornou plataforma de imagem inválida')
        digest = descriptor.get('digest', '')
        if (platform.get('os') == 'linux' and platform.get('architecture') == arch
                and isinstance(digest, str) and DIGEST.fullmatch(digest)):
            matches.append(descriptor)
    if not matches:
        raise Error(f'Imagem oficial indisponível para Linux {arch}')
    return matches


def postgres_image(run, arch, major=16):
    """Pin the official supported PostgreSQL image to its architecture's digest."""
    if major != 16:
        raise Error('PostgreSQL Docker suportado pelo instalador: versão 16')
    descriptors = _descriptors(run, 'docker.io/library/postgres:16', arch)
    if len(descriptors) != 1:
        raise Error('Registro retornou imagens PostgreSQL ambíguas para a arquitetura')
    return 'postgres@' + descriptors[0]['digest']


def validate_images(run, release, arch):
    """Validate that every immutable release image supports the Docker platform."""
    for image in release['images'].values():
        _descriptors(run, image, arch)

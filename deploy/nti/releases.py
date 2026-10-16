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
            raise Error('Download refused: redirect outside GitHub')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


urlopen = build_opener(_OfficialRedirect()).open


def _download(url, limit=MAX_JSON):
    """Read bounded HTTPS data from official GitHub hosts; hide raw network errors."""
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.hostname not in ('api.github.com', 'github.com')
            or parsed.username or parsed.password):
        raise Error('Download requires the official GitHub source')
    request = Request(url, headers={'Accept': 'application/vnd.github+json',
                                   'User-Agent': 'dspacepcirn-installer'})
    try:
        with urlopen(request, timeout=TIMEOUT) as response:
            final = urlsplit(response.geturl())
            if final.scheme != 'https' or final.hostname not in (
                    'api.github.com', 'github.com', 'release-assets.githubusercontent.com'):
                raise Error('Download refused: redirect outside GitHub')
            payload = response.read(limit + 1)
    except HTTPError as exc:
        if exc.code in (401, 403, 429):
            raise Error('GitHub denied or rate-limited the request; retry later') from None
        if exc.code == 404:
            raise Error('Release or asset not found on GitHub') from None
        raise Error('GitHub unavailable; retry later') from None
    except (URLError, TimeoutError, OSError):
        raise Error('Cannot reach GitHub; check DNS/HTTPS and retry') from None
    if len(payload) > limit:
        raise Error('Download exceeds its size limit')
    return payload


def _json(url):
    try:
        return json.loads(_download(url))
    except (ValueError, UnicodeError):
        raise Error('GitHub returned invalid JSON') from None


def select(version=None):
    """Choose the highest stable SemVer, otherwise the highest release candidate."""
    if version is not None:
        if not VERSION.fullmatch(version):
            raise Error('Invalid version: use X.Y.Z or X.Y.Z-rcN')
        result = _json(API + '/releases/tags/' + quote('v' + version.lstrip('v'), safe=''))
        if not isinstance(result, dict) or result.get('draft'):
            raise Error('Official release unavailable')
        if result.get('tag_name') != 'v' + version.lstrip('v'):
            raise Error('GitHub returned a different release')
        return result
    candidates = []
    for page in range(1, 6):
        entries = _json(API + f'/releases?per_page=100&page={page}')
        if not isinstance(entries, list):
            raise Error('Invalid official release list')
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
        raise Error('Too many releases; select a version in Advanced')
    if not candidates:
        raise Error('No official stable or RC release available')
    return max(candidates, key=lambda item: item[:3])[3]


def _asset(release, name):
    assets = [asset for asset in release.get('assets', []) if asset.get('name') == name]
    if len(assets) != 1:
        raise Error(f'Release must contain exactly one {name}; select another release')
    asset = assets[0]
    expected = 'https://github.com/' + REPOSITORY + '/releases/download/' + release['tag_name'] + '/' + name
    if asset.get('browser_download_url') != expected:
        raise Error('Asset does not belong to the selected official release')
    digest = asset.get('digest', '')
    if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
        raise Error('Official asset has no verifiable SHA-256; download refused')
    return asset


def _verified_asset(release, name, limit):
    asset = _asset(release, name)
    if type(asset.get('size')) is not int or not 0 < asset['size'] <= limit:
        raise Error('Invalid official asset size')
    payload = _download(asset['browser_download_url'], limit)
    if (len(payload) != asset['size']
            or 'sha256:' + hashlib.sha256(payload).hexdigest() != asset['digest']):
        raise Error('Official asset checksum mismatch; download refused')
    return payload


def _directory(root, version):
    root = Path(root).absolute()
    directory = root / 'downloads' / version
    if directory.resolve() != directory:
        raise Error('Download directory cannot contain symlinks')
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
            raise Error('Invalid official manifest') from None
        source = data.get('source', {})
        if not isinstance(source, dict):
            raise Error('Manifest: invalid source commit')
        commit = source.get('commit', '')
        if data['version'] != selected or not isinstance(commit, str) or not SHA.fullmatch(commit):
            raise Error('Manifest: invalid version or source commit')
        tag = _json(API + '/commits/' + quote(release['tag_name'], safe=''))
        if not isinstance(tag, dict) or tag.get('sha') != commit:
            raise Error('Manifest commit differs from the official tag; installation refused')
        for key, suffix in (('backend', 'backend'), ('solr', 'solr'), ('frontend', 'angular')):
            image = data['images'][key]
            if image.split('@')[0] != 'ghcr.io/kevintestegit/dspace-pcirn-' + suffix:
                raise Error('Manifest contains an image outside the official project')
        target = directory / 'release-manifest.json'
        if target.is_symlink():
            raise Error('Cached manifest cannot be a symlink')
        if target.exists() and target.read_bytes() != payload:
            raise Error('Manifest for the same version changed; review the release')
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
            raise Error('Manager package cannot be a symlink')
        if target.exists() and target.read_bytes() != payload:
            raise Error('Package for the same version changed; update refused')
        os.replace(temporary, target)
        return target, hashlib.sha256(payload).hexdigest()
    finally:
        temporary.unlink(missing_ok=True)


def download_data_source(version):
    """Read a verified data descriptor from the selected official release."""
    from remote_data import validate_source
    release = select(version)
    if not any(asset.get('name') == 'data-package.json' for asset in release.get('assets', [])):
        raise Error('This release has no data package. Use --data-package for a local export')
    payload = _verified_asset(release, 'data-package.json', 16 * 1024)
    try:
        return validate_source(json.loads(payload))
    except (ValueError, UnicodeError):
        raise Error('Invalid release data descriptor') from None


def docker_architecture(run):
    """Detect supported Linux architecture from the Docker daemon."""
    try:
        info = json.loads(run(['docker', 'info', '--format', '{{json .}}'], timeout=TIMEOUT))
        arch = {'x86_64': 'amd64', 'aarch64': 'arm64'}.get(info['Architecture'], info['Architecture'])
        if info['OSType'] != 'linux' or arch not in ('amd64', 'arm64'):
            raise Error('Docker must run Linux AMD64 or ARM64')
        return arch
    except (ValueError, KeyError, TypeError):
        raise Error('Docker returned an invalid architecture') from None


def _descriptors(run, image, arch):
    if arch not in ('amd64', 'arm64'):
        raise Error('Supported architecture: AMD64 or ARM64')
    try:
        entries = json.loads(run(['docker', 'manifest', 'inspect', '--verbose', image], timeout=TIMEOUT))
    except Error:
        raise Error('Image unavailable; check network and registry access. For private GHCR, '
                    'configure login in Advanced') from None
    except (ValueError, TypeError):
        raise Error('Registry returned an invalid image manifest') from None
    if isinstance(entries, dict):
        entries = [entries]
    if not isinstance(entries, list):
        raise Error('Registry returned an invalid image manifest')
    matches = []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get('Descriptor'), dict):
            raise Error('Registry returned an invalid image descriptor')
        descriptor = entry['Descriptor']
        platform = descriptor.get('platform', {})
        if not isinstance(platform, dict):
            raise Error('Registry returned an invalid image platform')
        digest = descriptor.get('digest', '')
        if (platform.get('os') == 'linux' and platform.get('architecture') == arch
                and isinstance(digest, str) and DIGEST.fullmatch(digest)):
            matches.append(descriptor)
    if not matches:
        raise Error(f'Official image unavailable for Linux {arch}')
    return matches


def postgres_image(run, arch, major=16):
    """Pin the official supported PostgreSQL image to its architecture's digest."""
    if major != 16:
        raise Error('Managed PostgreSQL version: 16')
    descriptors = _descriptors(run, 'docker.io/library/postgres:16', arch)
    if len(descriptors) != 1:
        raise Error('Registry returned ambiguous PostgreSQL images for this architecture')
    return 'postgres@' + descriptors[0]['digest']


def validate_images(run, release, arch):
    """Validate that every immutable release image supports the Docker platform."""
    for image in release['images'].values():
        _descriptors(run, image, arch)

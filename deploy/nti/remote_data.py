"""Download a checksum-pinned export package without touching the target database."""
import hashlib
import ipaddress
import os
from pathlib import Path
import re
import shutil
import socket
import tarfile
import tempfile
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from pcirn import Error, checksum, read_json, secure_ancestors

GIB = 1024 ** 3
CHUNK = 1024 ** 2


def validate_source(source):
    """Require a direct HTTPS URL and exact archive size and SHA-256."""
    if (not isinstance(source, dict) or set(source) != {'url', 'sha256', 'size'}
            or not isinstance(source['url'], str)
            or not isinstance(source['sha256'], str)
            or not re.fullmatch(r'[a-f0-9]{64}', source['sha256'])
            or type(source['size']) is not int or source['size'] <= 0):
        raise Error('Data package requires an HTTPS URL, SHA-256 and byte size')
    validate_url(source['url'])
    return source


def validate_url(url, resolve=False):
    """Reject insecure URLs and private destinations, including redirects."""
    try:
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username
                or parsed.password or parsed.fragment or parsed.port not in (None, 443)
                or any(c.isspace() or ord(c) < 32 for c in url)):
            raise ValueError
        if resolve:
            addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
            if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
                raise ValueError
    except (ValueError, OSError):
        raise Error('Data source must be a public HTTPS download on port 443') from None


class PublicRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl, resolve=True)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


urlopen = build_opener(PublicRedirect()).open


def validate_package(directory):
    from data_migration import PACKAGE_FILES
    allowed = PACKAGE_FILES | {'checksums.json', 'source-identity.json'}
    if directory.is_symlink():
        raise Error('Cached data package contains unexpected files or links')
    files = {p.name for p in directory.iterdir()}
    if (files not in (PACKAGE_FILES | {'checksums.json'}, allowed)
            or any(p.is_symlink() or not p.is_file() for p in directory.iterdir())):
        raise Error('Cached data package contains unexpected files or links')
    if any((directory / name).stat().st_size > 2 * CHUNK
           for name in ('checksums.json', 'release.json', 'source-report.json', 'source-identity.json')
           if (directory / name).exists()):
        raise Error('Data package metadata exceeds its size limit')
    hashes = read_json(directory / 'checksums.json')
    provided = set(hashes) if isinstance(hashes, dict) else set()
    if (provided not in (PACKAGE_FILES, PACKAGE_FILES | {'source-identity.json'})
            or files != provided | {'checksums.json'}
            or any(not isinstance(hashes[name], str) or checksum(directory / name) != hashes[name]
                   for name in provided)):
        raise Error('Data package is incomplete or its checksums do not match')
    if 'source-identity.json' in provided:
        identity = read_json(directory / 'source-identity.json')
        containers = identity.get('containers') if isinstance(identity, dict) else None
        if (not isinstance(containers, dict)
                or identity.get('schema_version') != 1 or identity.get('project') != 'd9'
                or identity.get('release_equivalence') is not False
                or set(containers) != {'dspace', 'dspacedb', 'dspacesolr', 'dspace-angular'}
                or any(not isinstance(container, dict)
                       or not all(isinstance(container.get(field), str) and container[field]
                                  for field in ('id', 'image_id', 'configured_image'))
                       for container in containers.values())):
            raise Error('Invalid local source identity')


def download_package(root, source):
    """Stream, verify and extract a flat export-data archive into a private cache."""
    from data_migration import PACKAGE_FILES
    source = validate_source(source)
    directory = Path(root).absolute() / 'downloads' / source['sha256']
    secure_ancestors(directory)
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    directory.chmod(0o700)
    archive_path = directory / 'data-package.tar.gz'
    target = directory / 'package'
    if target.exists():
        if (archive_path.is_symlink() or archive_path.stat().st_size != source['size']
                or checksum(archive_path) != source['sha256']):
            raise Error('Cached data archive changed; import refused')
        validate_package(target)
        return target
    if archive_path.exists():
        if (archive_path.is_symlink() or archive_path.stat().st_size != source['size']
                or checksum(archive_path) != source['sha256']):
            raise Error('Cached data archive changed; import refused')
    else:
        if shutil.disk_usage(directory).free < 30 * GIB + 2 * source['size']:
            raise Error('Not enough disk space to download the data package')
        validate_url(source['url'], resolve=True)
        temporary = None
        try:
            request = Request(source['url'], headers={'User-Agent': 'dspacepcirn-installer'})
            with urlopen(request, timeout=30) as response, tempfile.NamedTemporaryFile(
                    dir=directory, prefix='.download-', delete=False) as stream:
                temporary = Path(stream.name)
                validate_url(response.geturl(), resolve=True)
                if response.headers.get_content_type() == 'text/html':
                    raise Error('Data source returned a web page; use a direct file download URL')
                digest, size = hashlib.sha256(), 0
                while chunk := response.read(CHUNK):
                    size += len(chunk)
                    if size > source['size']:
                        raise Error('Data download exceeds its declared size')
                    digest.update(chunk)
                    stream.write(chunk)
                if size != source['size'] or digest.hexdigest() != source['sha256']:
                    raise Error('Data download checksum or size does not match')
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, archive_path)
        except (OSError, TimeoutError):
            raise Error('Data download failed; check HTTPS connectivity and retry') from None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.package-', dir=directory))
    try:
        seen, size = set(), 0
        budget = shutil.disk_usage(directory).free - 30 * GIB
        with tarfile.open(archive_path, 'r|gz') as archive:
            for member in archive:
                if (member.name not in PACKAGE_FILES | {'checksums.json'} or not member.isfile()
                        or member.name in seen
                        or (member.name.endswith('.json') and member.size > 2 * CHUNK)):
                    raise Error('Data archive contains unexpected files, paths or links')
                seen.add(member.name)
                size += member.size
                if size > budget:
                    raise Error('Not enough disk space to extract the data package')
                with archive.extractfile(member) as src, (staging / member.name).open('xb') as dst:
                    os.chmod(dst.name, 0o600)
                    shutil.copyfileobj(src, dst, CHUNK)
            if seen != PACKAGE_FILES | {'checksums.json'}:
                raise Error('Data archive is incomplete')
        validate_package(staging)
        staging.rename(target)
        return target
    except (tarfile.TarError, ValueError, KeyError):
        raise Error('Invalid data package archive or checksums') from None
    finally:
        # Failed staging contains downloaded files only, never repository data.
        if staging.exists():
            shutil.rmtree(staging)

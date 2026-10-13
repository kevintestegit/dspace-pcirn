"""Verified code-only updates of the standalone manager, retaining previous files."""
import ctypes
import fcntl
import os
from pathlib import Path
import tarfile
import tempfile
import subprocess

from pcirn import Error, checksum, secure_ancestors

FILES = {'pcirn.py', 'wizard.py', 'preflight.py', 'data_migration.py', 'host_setup.py',
         'releases.py', 'manager_update.py', 'dspacepcirn', 'compose.template.yml', 'smtp.env.example',
         'install-manager.sh'}
MAX_SIZE = 8 * 1024 * 1024


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def exchange(active, staging):
    """Atomically exchange two directories on the same Linux filesystem."""
    libc = ctypes.CDLL(None, use_errno=True)
    rename = getattr(libc, 'renameat2', None)
    if rename is None:
        raise Error('Sistema sem renameat2; gerenciador atual preservado')
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(active), -100, os.fsencode(staging), 2) != 0:
        raise Error('Ativação atômica indisponível; gerenciador atual preservado')


def update(package, expected_sha256, library=None):
    """Install a digest-verified flat manager package; never touch deployment data."""
    library = Path(library or Path(__file__).resolve().parent).absolute()
    secure_ancestors(library)
    if (library.name != 'dspacepcirn' or library.resolve() != library
            or library.parent.name != 'lib' or not library.is_dir()
            or library.stat().st_mode & 0o022
            or library.stat().st_uid != os.geteuid()
            or library.parent.stat().st_mode & 0o022
            or any(p.is_symlink() for p in library.iterdir())):
        raise Error('Atualização exige o gerenciador global em prefixo/lib/dspacepcirn seguro')
    if (len(expected_sha256) != 64 or any(c not in '0123456789abcdef' for c in expected_sha256)
            or checksum(package) != expected_sha256):
        raise Error('Checksum do pacote do gerenciador divergente')
    unexpected = {p.name for p in library.iterdir()} - FILES - {'__pycache__'}
    if unexpected:
        raise Error('Arquivos desconhecidos no gerenciador; atualização recusada')
    with (library.parent / '.dspacepcirn-update.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise Error('Outra atualização do gerenciador está em execução') from exc
        staging = Path(tempfile.mkdtemp(prefix='.dspacepcirn-update-', dir=library.parent))
        with tarfile.open(package, 'r:gz') as archive:
            members = archive.getmembers()
            if (len(members) != len(FILES) or {m.name for m in members} != FILES
                    or any(not m.isfile() or m.size > MAX_SIZE for m in members)
                    or sum(m.size for m in members) > MAX_SIZE):
                raise Error('Pacote do gerenciador inválido; links e caminhos externos recusados')
            for member in members:
                with archive.extractfile(member) as stream:
                    contents = stream.read(MAX_SIZE + 1)
                if len(contents) != member.size:
                    raise Error('Pacote do gerenciador truncado')
                path = staging / member.name
                if path.suffix == '.py':
                    try:
                        compile(contents, member.name, 'exec')
                    except (SyntaxError, ValueError) as exc:
                        raise Error('Código Python inválido no pacote do gerenciador') from exc
                with path.open('wb') as destination:
                    destination.write(contents)
                    destination.flush()
                    path.chmod(0o755 if path.name in ('dspacepcirn', 'install-manager.sh') else 0o644)
                    os.fsync(destination.fileno())
                if path.name in ('dspacepcirn', 'install-manager.sh'):
                    parsed = subprocess.run(['bash', '-n', str(path)], capture_output=True, timeout=30)
                    if parsed.returncode:
                        raise Error('Código Bash inválido no pacote do gerenciador')
        staging.chmod(0o755)
        sync_directory(staging)
        saved = library.with_name('dspacepcirn.previous-' + expected_sha256[:12])
        if saved.exists():
            raise Error('Atualização já preparada; diretório anterior preservado para revisão')
        exchange(library, staging)
        sync_directory(library.parent)
        # After the exchange both versions are reachable, even if interrupted here.
        staging.rename(saved)
        sync_directory(library.parent)
        print('Gerenciador atualizado. Versão anterior preservada em ' + str(saved))

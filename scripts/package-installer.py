#!/usr/bin/env python3
"""Package only public installer inputs with deterministic archive metadata."""
import argparse
import gzip
import hashlib
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = (
    'install.sh', 'docker-compose.yml', 'docker-compose.dev.yml', 'smtp.env.example',
    'deploy/nti/*.py', 'deploy/nti/*.md', 'deploy/nti/dspacepcirn',
    'deploy/nti/provision-database.sql', 'deploy/nti/tests/e2e_homolog.py',
    'deploy/nti/tests/test_*.py',
    'deploy/nti/tests/fixtures/probe.sql', 'deploy/nti/tests/fixtures/probe.txt',
    'deploy/nti/homolog/release-a.json', 'deploy/nti/homolog/release-b.json',
    'deploy/nti/homolog/registry-verification.json', 'deploy/nti/homolog/build-verification.json',
    'deploy/nti/homolog/README.md', 'deploy/nti/homolog/VALIDATION.md',
    'scripts/package-installer.py', 'scripts/release-manifest.sh',
    'scripts/backup-dspace.sh',
    'scripts/flyway-history.json', 'scripts/flyway-fresh-history.json',
    '.github/workflows/publish-images.yml',
)


def package(output, root=ROOT):
    files = sorted({path for pattern in PATTERNS for path in root.glob(pattern)})
    required = ['install.sh', 'deploy/nti/pcirn.py', 'deploy/nti/tests/e2e_homolog.py',
                'deploy/nti/homolog/release-a.json', 'deploy/nti/homolog/release-b.json']
    if any(root / name not in files for name in required):
        raise ValueError('Required installer input is missing')
    if any(path.is_symlink() or not path.is_file() for path in files):
        raise ValueError('Installer inputs must be regular files')
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('wb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode='w', format=tarfile.PAX_FORMAT) as archive:
            for path in files:
                info = tarfile.TarInfo('dspacepcirn-installer/' + path.relative_to(root).as_posix())
                info.size = path.stat().st_size
                info.mode = 0o755 if path.suffix == '.sh' or path.name == 'dspacepcirn' else 0o644
                with path.open('rb') as source:
                    archive.addfile(info, source)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_name(output.name + '.sha256').write_text(f'{digest}  {output.name}\n')
    return digest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(package(args.output))

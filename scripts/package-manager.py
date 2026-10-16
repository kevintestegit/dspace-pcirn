#!/usr/bin/env python3
"""Create the standalone manager release asset without Git or runtime dependencies."""
import argparse
import hashlib
from pathlib import Path
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'deploy/nti'))
from manager_update import FILES

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=Path('dspacepcirn-manager.tar.gz'))
args = parser.parse_args()
with tarfile.open(args.output, 'w:gz') as archive:
    for name in sorted(FILES):
        source = (ROOT / 'docker-compose.yml' if name == 'compose.template.yml' else
                  ROOT / 'smtp.env.example' if name == 'smtp.env.example' else ROOT / 'deploy/nti' / name)
        archive.add(source, arcname=name, recursive=False)
digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
args.output.with_suffix(args.output.suffix + '.sha256').write_text(digest + '  ' + args.output.name + '\n')
print(args.output.name + ' sha256:' + digest)

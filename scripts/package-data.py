#!/usr/bin/env python3
"""Package a completed export-data directory for a direct HTTPS download."""
import argparse
import os
from pathlib import Path
import sys
import tarfile
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'deploy/nti'))
from pcirn import Error, checksum, secure_ancestors, write_json
from remote_data import validate_package, validate_source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', required=True, type=Path)
    parser.add_argument('--url', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    validate_package(args.package)
    validate_source({'url': args.url, 'sha256': '0' * 64, 'size': 1})
    output = args.output.absolute()
    descriptor = output.with_name(output.name + '.json')
    if output.parent.resolve().is_relative_to(args.package.resolve()):
        raise Error('Output must be outside the export directory')
    secure_ancestors(output.parent)
    if output.exists() or output.is_symlink() or descriptor.exists() or descriptor.is_symlink():
        raise Error('Output already exists; nothing overwritten')
    with tempfile.NamedTemporaryFile(dir=output.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            with tarfile.open(fileobj=stream, mode='w:gz') as archive:
                for source in sorted(args.package.iterdir()):
                    archive.add(source, arcname=source.name, recursive=False)
            stream.flush()
            os.fsync(stream.fileno())
            os.link(temporary, output)
        finally:
            temporary.unlink(missing_ok=True)
    write_json(descriptor, {'url': args.url, 'sha256': checksum(output), 'size': output.stat().st_size})
    print(f'Package: {output}\nRelease descriptor: {descriptor}')


if __name__ == '__main__':
    try:
        main()
    except (Error, OSError, ValueError, KeyError) as error:
        print(str(error) if isinstance(error, Error) else type(error).__name__, file=sys.stderr)
        sys.exit(1)

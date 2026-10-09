#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ $# -eq 0 ]]; then
    exec "${SCRIPT_DIR}/deploy/nti/dspacepcirn"
fi
exec python3 "${SCRIPT_DIR}/deploy/nti/pcirn.py" install --wizard "$@"

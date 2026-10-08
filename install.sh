#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python3 "${SCRIPT_DIR}/deploy/nti/preflight.py" "$@"
exec python3 "${SCRIPT_DIR}/deploy/nti/pcirn.py" install "$@"

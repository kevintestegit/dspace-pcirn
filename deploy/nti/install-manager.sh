#!/usr/bin/env bash
set -Eeuo pipefail
umask 022
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="${1:-/usr/local}"
if [[ $# -gt 1 || "$PREFIX" != /* || "$(realpath -m -- "$PREFIX")" != "$PREFIX" ]]; then
    echo 'Use um prefixo absoluto sem links simbólicos.' >&2
    exit 1
fi
LIB="$PREFIX/lib/dspacepcirn"
COMMAND="$PREFIX/bin/dspacepcirn"
if [[ "$(realpath -m -- "$LIB")" != "$LIB" || "$(realpath -m -- "$COMMAND")" != "$COMMAND" ]]; then
    echo 'Diretórios do gerenciador não podem conter links simbólicos.' >&2
    exit 1
fi
if [[ -e "$COMMAND" || -L "$COMMAND" || -e "$LIB" || -L "$LIB" ]]; then
    echo 'Gerenciador/comando existente: nada sobrescrito.' >&2
    exit 1
fi
mkdir -p -- "$PREFIX/bin" "$PREFIX/lib"
mkdir -- "$LIB"
install -m 644 -- "$SCRIPT_DIR"/{pcirn.py,wizard.py,preflight.py,data_migration.py} "$LIB/"
install -m 755 -- "$SCRIPT_DIR/dspacepcirn" "$LIB/dspacepcirn"
install -m 644 -- "$SCRIPT_DIR/../../docker-compose.yml" "$LIB/compose.template.yml"
install -m 644 -- "$SCRIPT_DIR/../../smtp.env.example" "$LIB/smtp.env.example"
(set -o noclobber; cat > "$COMMAND" <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/../lib/dspacepcirn/pcirn.py" "$@"
EOF
)
chmod 755 -- "$COMMAND"
echo "Gerenciador instalado: $COMMAND"

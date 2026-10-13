#!/usr/bin/env bash
set -Eeuo pipefail
umask 022
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="${1:-/usr/local}"
if [[ $# -gt 1 || "$PREFIX" != /* || "$(realpath -m -- "$PREFIX")" != "$PREFIX" ]]; then
    echo 'Use an absolute prefix without symlinks.' >&2
    exit 1
fi
LIB="$PREFIX/lib/dspacepcirn"
COMMAND="$PREFIX/bin/dspacepcirn"
for location in "$PREFIX" "$PREFIX/bin" "$PREFIX/lib"; do
    ancestor="$location"
    while [[ "$ancestor" != / ]]; do
        if [[ -e "$ancestor" ]]; then
            owner="$(stat -c %u -- "$ancestor")"
            permissions="$(stat -c %a -- "$ancestor")"
            mode=$((8#$permissions))
            if [[ "$owner" != "$EUID" && "$owner" != 0 ]] ||
               (( (mode & 0022) != 0 && !(owner == 0 && (mode & 01000) != 0) )); then
                echo 'Administrative prefix has unsafe ownership or permissions.' >&2
                exit 1
            fi
        fi
        ancestor="$(dirname -- "$ancestor")"
    done
done
if [[ "$(realpath -m -- "$LIB")" != "$LIB" || "$(realpath -m -- "$COMMAND")" != "$COMMAND" ]]; then
    echo 'Manager directories cannot contain symlinks.' >&2
    exit 1
fi
if [[ -e "$COMMAND" || -L "$COMMAND" || -e "$LIB" || -L "$LIB" ]]; then
    echo 'Manager/command already exists; nothing overwritten.' >&2
    exit 1
fi
mkdir -p -- "$PREFIX/bin" "$PREFIX/lib"
mkdir -- "$LIB"
install -m 644 -- "$SCRIPT_DIR"/{pcirn.py,wizard.py,preflight.py,data_migration.py,host_setup.py,releases.py,manager_update.py,remote_data.py} "$LIB/"
install -m 755 -- "$SCRIPT_DIR/dspacepcirn" "$LIB/dspacepcirn"
install -m 755 -- "$SCRIPT_DIR/install-manager.sh" "$LIB/install-manager.sh"
COMPOSE_SOURCE="$SCRIPT_DIR/compose.template.yml"
SMTP_SOURCE="$SCRIPT_DIR/smtp.env.example"
if [[ ! -f "$COMPOSE_SOURCE" ]]; then COMPOSE_SOURCE="$SCRIPT_DIR/../../docker-compose.yml"; fi
if [[ ! -f "$SMTP_SOURCE" ]]; then SMTP_SOURCE="$SCRIPT_DIR/../../smtp.env.example"; fi
install -m 644 -- "$COMPOSE_SOURCE" "$LIB/compose.template.yml"
install -m 644 -- "$SMTP_SOURCE" "$LIB/smtp.env.example"
(set -o noclobber; cat > "$COMMAND" <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/../lib/dspacepcirn/dspacepcirn" "$@"
EOF
)
chmod 755 -- "$COMMAND"
echo "Manager installed: $COMMAND"

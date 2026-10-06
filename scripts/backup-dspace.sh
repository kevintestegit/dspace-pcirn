#!/usr/bin/env bash
# Backup of the two things that cannot be regenerated: the PostgreSQL database
# and the assetstore.
#
# Two deployment shapes are supported and detected automatically:
#
#   development  docker-compose.dev.yml, PostgreSQL in the dspacedb container
#   production   docker-compose.yml, PostgreSQL administered by the NTI
#
# Usage:
#   scripts/backup-dspace.sh [destino]
#
# Development reads .env; production reads .env.production, or the DB_* values
# already exported in the environment.
set -Eeuo pipefail

umask 077

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backup_root="${1:-${ROOT}/backups}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_dir="${backup_root%/}/dspace-${timestamp}"
tmp_dir="${backup_dir}/.incomplete"

mode=
compose() {
  case "${mode}" in
    development)
      docker compose --project-directory "${ROOT}" \
        -f "${ROOT}/docker-compose.dev.yml" --env-file "${ROOT}/.env" "$@" ;;
    *)
      docker compose --project-directory "${ROOT}" \
        -f "${ROOT}/docker-compose.yml" --env-file "${ROOT}/.env.production" "$@" ;;
  esac
}

# A dump or archive that failed halfway is worse than no backup, because it
# looks usable. Everything is written under .incomplete and only moved into
# place after it has been verified.
cleanup() { rm -rf "${tmp_dir}"; }
trap cleanup ERR

mkdir -p "${tmp_dir}"

# The deployment shape follows from which stack is actually running: only the
# development stack has a database container. BACKUP_MODE overrides the
# detection when both files or neither are present.
case "${BACKUP_MODE:-auto}" in
  development|production) mode="${BACKUP_MODE}" ;;
  auto)
    if docker compose --project-directory "${ROOT}" \
         -f "${ROOT}/docker-compose.dev.yml" --env-file "${ROOT}/.env" \
         ps --services --status running 2>/dev/null | grep -qx dspacedb; then
      mode=development
    else
      mode=production
    fi
    ;;
  *)
    echo "BACKUP_MODE deve ser 'auto', 'development' ou 'production'" >&2
    exit 2
    ;;
esac

if [[ "${mode}" == production && -f "${ROOT}/.env.production" ]]; then
  # shellcheck disable=SC1091
  set -a; . "${ROOT}/.env.production"; set +a
fi

if [[ "${mode}" == development ]]; then
  # The dspace image has no PostgreSQL client, so the dump runs in the
  # database container itself.
  compose exec -T dspacedb pg_dump -U dspace -d dspace --format=custom \
    > "${tmp_dir}/dspace.dump"
else
  : "${DB_URL:?DB_URL nao definido: exporte-o ou use .env.production}"
  : "${DB_PASSWORD:?DB_PASSWORD nao definido: exporte-o ou use .env.production}"

  # jdbc:postgresql://host:port/database[?params] -> host port database
  rest="${DB_URL#jdbc:postgresql://}"
  rest="${rest%%\?*}"
  host_port="${rest%%/*}"
  db_name="${rest#*/}"
  db_host="${host_port%%:*}"
  db_port="${host_port##*:}"
  [[ "${db_port}" == "${db_host}" ]] && db_port=5432

  # A throwaway client, so the host and the backend image need no psql.
  # --network host is what lets it reach a database on the host or the LAN.
  docker run --rm --network host \
    --user "$(id -u):$(id -g)" \
    -e "PGPASSWORD=${DB_PASSWORD}" \
    -v "${tmp_dir}:/out" \
    "postgres:${POSTGRES_VERSION:-15}" \
    pg_dump -h "${db_host}" -p "${db_port}" \
      -U "${DB_USERNAME:-dspace}" -d "${db_name}" \
      --format=custom -f /out/dspace.dump
fi

# Bind mount in production, named volume in development. In production the
# location is explicit in .env.production, so nothing needs to be guessed; in
# development the assetstore lives in the volume mounted into the backend.
if [[ "${mode}" == development ]]; then
  compose exec -T dspace tar -C /dspace -czf - assetstore \
    > "${tmp_dir}/assetstore.tar.gz"
else
  : "${ASSETSTORE_PATH:?ASSETSTORE_PATH nao definido: exporte-o ou use .env.production}"
  [[ -d "${ASSETSTORE_PATH}" ]] \
    || { echo "ASSETSTORE_PATH nao existe: ${ASSETSTORE_PATH}" >&2; exit 1; }
  tar -C "$(dirname "${ASSETSTORE_PATH}")" -czf "${tmp_dir}/assetstore.tar.gz" \
    "$(basename "${ASSETSTORE_PATH}")"
fi

# Verify before publishing: pg_restore -l reads the archive table of contents
# without touching a database.
docker run --rm --user "$(id -u):$(id -g)" -v "${tmp_dir}:/out" \
  "postgres:${POSTGRES_VERSION:-15}" \
  pg_restore -l /out/dspace.dump > /dev/null
tar -tzf "${tmp_dir}/assetstore.tar.gz" > /dev/null

mv "${tmp_dir}/dspace.dump" "${backup_dir}/dspace.dump"
mv "${tmp_dir}/assetstore.tar.gz" "${backup_dir}/assetstore.tar.gz"
rmdir "${tmp_dir}"
# pg_dump runs in a container with its own umask, so the mode is set here
# rather than assumed: a dump carries every password hash in the repository.
chmod 600 "${backup_dir}/dspace.dump" "${backup_dir}/assetstore.tar.gz"

(
  cd "${backup_dir}"
  sha256sum dspace.dump assetstore.tar.gz > SHA256SUMS
)

trap - ERR

printf 'Backup (%s) criado em %s\n' "${mode}" "${backup_dir}"
printf '  dspace.dump        %s\n' "$(du -h "${backup_dir}/dspace.dump" | cut -f1)"
printf '  assetstore.tar.gz  %s\n' "$(du -h "${backup_dir}/assetstore.tar.gz" | cut -f1)"

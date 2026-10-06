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

compose() {
  if [[ -f "${ROOT}/.env" ]]; then
    docker compose --project-directory "${ROOT}" --env-file "${ROOT}/.env" "$@"
  else
    docker compose --project-directory "${ROOT}" --env-file "${ROOT}/.env.production" "$@"
  fi
}

# A dump or archive that failed halfway is worse than no backup, because it
# looks usable. Everything is written under .incomplete and only moved into
# place after it has been verified.
cleanup() { rm -rf "${tmp_dir}"; }
trap cleanup ERR

mkdir -p "${tmp_dir}"

if compose ps --services --status running 2>/dev/null | grep -qx dspacedb; then
  mode=development
else
  mode=production
fi

if [[ "${mode}" == development ]]; then
  # The dspace image has no PostgreSQL client, so the dump runs in the
  # database container itself.
  compose exec -T dspacedb pg_dump -U dspace -d dspace --format=custom \
    > "${tmp_dir}/dspace.dump"
else
  if [[ -f "${ROOT}/.env.production" ]]; then
    # shellcheck disable=SC1091
    set -a; . "${ROOT}/.env.production"; set +a
  fi
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
    -e "PGPASSWORD=${DB_PASSWORD}" \
    -v "${tmp_dir}:/out" \
    "postgres:${POSTGRES_VERSION:-15}" \
    pg_dump -h "${db_host}" -p "${db_port}" \
      -U "${DB_USERNAME:-dspace}" -d "${db_name}" \
      --format=custom -f /out/dspace.dump
fi

# Bind mount in production, named volume in development.
assetstore_bind="$(compose config 2>/dev/null \
  | awk '/source: \//{print $2; exit}')"
if [[ -n "${assetstore_bind}" && -d "${assetstore_bind}" ]]; then
  tar -C "$(dirname "${assetstore_bind}")" -czf "${tmp_dir}/assetstore.tar.gz" \
    "$(basename "${assetstore_bind}")"
else
  compose exec -T dspace tar -C /dspace -czf - assetstore \
    > "${tmp_dir}/assetstore.tar.gz"
fi

# Verify before publishing: pg_restore -l reads the archive table of contents
# without touching a database.
docker run --rm -v "${tmp_dir}:/out" "postgres:${POSTGRES_VERSION:-15}" \
  pg_restore -l /out/dspace.dump > /dev/null
tar -tzf "${tmp_dir}/assetstore.tar.gz" > /dev/null

mv "${tmp_dir}/dspace.dump" "${backup_dir}/dspace.dump"
mv "${tmp_dir}/assetstore.tar.gz" "${backup_dir}/assetstore.tar.gz"
rmdir "${tmp_dir}"

(
  cd "${backup_dir}"
  sha256sum dspace.dump assetstore.tar.gz > SHA256SUMS
)

trap - ERR

printf 'Backup (%s) criado em %s\n' "${mode}" "${backup_dir}"
printf '  dspace.dump        %s\n' "$(du -h "${backup_dir}/dspace.dump" | cut -f1)"
printf '  assetstore.tar.gz  %s\n' "$(du -h "${backup_dir}/assetstore.tar.gz" | cut -f1)"

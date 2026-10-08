#!/usr/bin/env bash
# Backup of the state that cannot be regenerated: the PostgreSQL database, the
# assetstore and the Solr statistics core.
#
# Two deployment shapes are supported and detected automatically:
#
#   development  docker-compose.dev.yml, PostgreSQL in the dspacedb container
#   production   docker-compose.yml, PostgreSQL administered by the NTI
#
# Usage:
#   scripts/backup-dspace.sh [destino]
#
# Development reads .env; production reads .env.production through Compose, so
# the dump connects with exactly the values the stack uses.
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
# place after it has been verified; any exit before that — including an explicit
# `exit 1` — removes the partial work and the directory that held it, so a
# failed run leaves nothing that could be mistaken for a backup.
cleanup() {
  rm -rf "${tmp_dir}"
  rmdir "${backup_dir}" 2>/dev/null || true
}
trap cleanup EXIT

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

# .env.production is a Compose env file, not a shell script. Sourcing it would
# expand $, run command substitutions and split unquoted values on spaces, so
# the dump could authenticate with a value the stack never uses — or execute
# whatever the file contains. Compose is the parser that starts the stack, so it
# is also the one that reports the values used here.
env_value() {
  local line
  while IFS= read -r line; do
    case "${line}" in
      "$1="*) printf '%s' "${line#"$1="}"; return 0 ;;
    esac
  done < "${tmp_dir}/environment"
}

db_url= db_user= db_password= assetstore= postgres_version=
if [[ "${mode}" == production ]]; then
  [[ -f "${ROOT}/.env.production" ]] \
    || { echo "Producao exige ${ROOT}/.env.production" >&2; exit 1; }
  compose config --environment > "${tmp_dir}/environment" \
    || { echo "Nao foi possivel ler .env.production com o Compose" >&2; exit 1; }
  db_url="$(env_value DB_URL)"
  db_user="$(env_value DB_USERNAME)"
  db_password="$(env_value DB_PASSWORD)"
  assetstore="$(env_value ASSETSTORE_PATH)"
  postgres_version="$(env_value POSTGRES_VERSION)"
  : "${db_url:?DB_URL nao definido em .env.production}"
  : "${db_password:?DB_PASSWORD nao definido em .env.production}"
  : "${assetstore:?ASSETSTORE_PATH nao definido em .env.production}"
fi

if [[ "${mode}" == development ]]; then
  # The dspace image has no PostgreSQL client, so the dump runs in the
  # database container itself.
  compose exec -T dspacedb pg_dump -U dspace -d dspace --format=custom \
    > "${tmp_dir}/dspace.dump"
else
  # jdbc:postgresql://host:port/database[?params] -> host port database
  rest="${db_url#jdbc:postgresql://}"
  query=
  if [[ "${rest}" == *\?* ]]; then
    query="${rest#*\?}"
    rest="${rest%%\?*}"
  fi
  host_port="${rest%%/*}"
  db_name="${rest#*/}"
  db_host="${host_port%%:*}"
  db_port="${host_port##*:}"
  [[ "${db_port}" == "${db_host}" ]] && db_port=5432

  # libpq reads its connection parameters from the environment, and the JDBC
  # parameters are the ones the application connects with: dropping them here
  # would make the backup connect differently from the stack — sslmode=require
  # silently becoming "prefer", for example. A parameter the client cannot use
  # is an error, not something to ignore.
  client_args=(-v "${tmp_dir}:/out" -e "PGPASSWORD=${db_password}")
  while IFS='=' read -r key value; do
    [[ -n "${key}" ]] || continue
    case "${key}" in
      sslmode) client_args+=(-e "PGSSLMODE=${value}") ;;
      sslrootcert|sslcert|sslkey)
        [[ -f "${value}" ]] \
          || { echo "${key} nao existe neste servidor: ${value}" >&2; exit 1; }
        case "${key}" in
          sslrootcert) variable=PGSSLROOTCERT ;;
          sslcert) variable=PGSSLCERT ;;
          sslkey) variable=PGSSLKEY ;;
        esac
        # The client is a container, so the file must be visible inside it at
        # the same path; libpq reads it read-only.
        client_args+=(-e "${variable}=${value}" -v "${value}:${value}:ro") ;;
      *)
        echo "Parametro JDBC nao suportado pelo cliente PostgreSQL: ${key}" >&2
        exit 1 ;;
    esac
  done < <(tr '&' '\n' <<< "${query}")

  # A throwaway client, so the host and the backend image need no psql.
  # --network host is what lets it reach a database on the host or the LAN.
  docker run --rm --network host \
    --user "$(id -u):$(id -g)" \
    "${client_args[@]}" \
    "postgres:${postgres_version:-15}" \
    pg_dump -h "${db_host}" -p "${db_port}" \
      -U "${db_user:-dspace}" -d "${db_name}" \
      --format=custom -f /out/dspace.dump
fi

# Bind mount in production, named volume in development. In production the
# location is explicit in .env.production, so nothing needs to be guessed; in
# development the assetstore lives in the volume mounted into the backend.
if [[ "${mode}" == development ]]; then
  compose exec -T dspace tar -C /dspace -czf - assetstore \
    > "${tmp_dir}/assetstore.tar.gz"
else
  [[ -d "${assetstore}" ]] \
    || { echo "ASSETSTORE_PATH nao existe: ${assetstore}" >&2; exit 1; }
  tar -C "$(dirname "${assetstore}")" -czf "${tmp_dir}/assetstore.tar.gz" \
    "$(basename "${assetstore}")"
fi

# Usage statistics cannot be rebuilt: index-discovery -b rebuilds the search,
# authority, OAI and suggestion cores from the database, never the statistics
# core, which is the only record of views and downloads. The rest of the Solr
# data is derived, so only this core is archived. `run` instead of `exec` so the
# archive is produced whether or not Solr is up; --entrypoint skips the core
# seeding of the service and streams the archive straight to stdout.
if ! compose run --rm --no-deps --entrypoint tar dspacesolr \
     -C /var/solr/data -czf - statistics > "${tmp_dir}/solr-statistics.tar.gz"; then
  echo "core 'statistics' ausente no Solr: nada foi publicado" >&2
  exit 1
fi

# Verify before publishing: pg_restore -l reads the archive table of contents
# without touching a database.
docker run --rm --user "$(id -u):$(id -g)" -v "${tmp_dir}:/out" \
  "postgres:${postgres_version:-15}" \
  pg_restore -l /out/dspace.dump > /dev/null
tar -tzf "${tmp_dir}/assetstore.tar.gz" > /dev/null
tar -tzf "${tmp_dir}/solr-statistics.tar.gz" > /dev/null

mv "${tmp_dir}/dspace.dump" "${backup_dir}/dspace.dump"
mv "${tmp_dir}/assetstore.tar.gz" "${backup_dir}/assetstore.tar.gz"
mv "${tmp_dir}/solr-statistics.tar.gz" "${backup_dir}/solr-statistics.tar.gz"
# The rendered environment holds the database password: it is deleted before
# rmdir, which also fails loudly if anything unexpected is still there.
rm -f "${tmp_dir}/environment"
rmdir "${tmp_dir}"
# pg_dump runs in a container with its own umask, so the mode is set here
# rather than assumed: a dump carries every password hash in the repository,
# and the statistics core carries the activity of every reader.
chmod 600 "${backup_dir}/dspace.dump" "${backup_dir}/assetstore.tar.gz" \
  "${backup_dir}/solr-statistics.tar.gz"

(
  cd "${backup_dir}"
  sha256sum dspace.dump assetstore.tar.gz solr-statistics.tar.gz > SHA256SUMS
)


printf 'Backup (%s) criado em %s\n' "${mode}" "${backup_dir}"
printf '  dspace.dump            %s\n' "$(du -h "${backup_dir}/dspace.dump" | cut -f1)"
printf '  assetstore.tar.gz      %s\n' "$(du -h "${backup_dir}/assetstore.tar.gz" | cut -f1)"
printf '  solr-statistics.tar.gz %s\n' "$(du -h "${backup_dir}/solr-statistics.tar.gz" | cut -f1)"

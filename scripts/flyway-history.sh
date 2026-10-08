#!/usr/bin/env bash
# Writes the Flyway history recorded in public.schema_version as a JSON array,
# for the database.migrations field of a release manifest.
#
# The release contract requires the history the image produces, not a value
# derived from the SQL files: Flyway computes its own checksums and Java
# migrations carry -1, so hashing the scripts would produce a manifest the
# installer correctly rejects.
#
# Usage:
#   scripts/flyway-history.sh --database-url URL [--output FILE]
#
# URL forms accepted:
#   jdbc:postgresql://host:port/dbname     (as used in DB_URL)
#   postgresql://host:port/dbname
#
# Credentials come from PGUSER and PGPASSWORD in the environment.
set -Eeuo pipefail

database_url=
output=
while [[ $# -gt 0 ]]; do
  case "$1" in
    --database-url) database_url="$2"; shift 2 ;;
    --output)       output="$2";       shift 2 ;;
    -h|--help)      sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "argumento desconhecido: $1" >&2; exit 2 ;;
  esac
done

[[ -n "${database_url}" ]] || { echo "--database-url e obrigatorio" >&2; exit 2; }

# jdbc:postgresql://host:port/db[?params] -> host port db
rest="${database_url#jdbc:postgresql://}"
rest="${rest#postgresql://}"
rest="${rest%%\?*}"
host_port="${rest%%/*}"
db_name="${rest#*/}"
db_host="${host_port%%:*}"
db_port="${host_port##*:}"
[[ "${db_port}" == "${db_host}" ]] && db_port=5432

: "${PGUSER:?PGUSER nao definido}"
: "${PGPASSWORD:?PGPASSWORD nao definido}"

# The columns are quoted explicitly and the objects built by hand instead of
# row_to_json, so the field order and the null handling match the contract
# exactly. Failed rows are excluded, which the installer treats as fatal
# separately.
query="
SELECT COALESCE(json_agg(json_build_object(
         'version', version,
         'script', script,
         'checksum', checksum
       ) ORDER BY installed_rank), '[]'::json)
FROM public.schema_version
WHERE success IS TRUE
  AND version IS NOT NULL;
"

history="$(PGPASSWORD="${PGPASSWORD}" psql \
  --host="${db_host}" --port="${db_port}" --username="${PGUSER}" \
  --dbname="${db_name}" --no-psqlrc --tuples-only --no-align \
  --command="${query}")"

[[ -n "${history}" ]] || { echo "historico vazio ou banco inacessivel" >&2; exit 1; }

# Fail loudly rather than emit a manifest the installer will reject later.
count="$(printf '%s' "${history}" | jq 'length')"
[[ "${count}" -gt 0 ]] || { echo "nenhuma migration versionada encontrada" >&2; exit 1; }
printf '%s' "${history}" | jq -e 'all(.[]; (.version | test("^[0-9]+(\\.[0-9]+)*$")))' >/dev/null \
  || { echo "historico contem version fora do formato esperado" >&2; exit 1; }

if [[ -n "${output}" ]]; then
  printf '%s\n' "${history}" | jq '.' > "${output}"
  printf '%s migrations escritas em %s\n' "${count}" "${output}" >&2
else
  printf '%s\n' "${history}" | jq '.'
fi

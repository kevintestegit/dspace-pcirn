#!/usr/bin/env bash
# Writes the release manifest consumed by the NTI installer.
#
# The contract is defined in deploy/nti/README.md and enforced by that CLI:
#
#   {
#     "schema_version": 1,
#     "version": "1.0.0",
#     "images": {
#       "backend":  "ghcr.io/ORG/NAME@sha256:<64 hex>",
#       "solr":     "ghcr.io/ORG/NAME@sha256:<64 hex>",
#       "frontend": "ghcr.io/ORG/NAME@sha256:<64 hex>"
#     },
#     "database": { "migrations": [ { "version", "script", "checksum" } ] }
#   }
#
# Images are referenced by digest only; a tag is never accepted. version is
# SemVer without the leading "v" of the git tag.
#
# source and createdAt are extra keys: the installer ignores what it does not
# know, and they let a deployment record which commit produced the images.
#
# Usage:
#   scripts/release-manifest.sh \
#     --version 1.0.0 \
#     --commit <sha> \
#     --angular-commit <sha> \
#     --backend-digest sha256:<64 hex> \
#     --angular-digest sha256:<64 hex> \
#     --solr-digest sha256:<64 hex> \
#     --migrations scripts/flyway-history.json \
#     [--repository-owner ORG] \
#     [--output release-manifest.json]
set -Eeuo pipefail

version=
commit=
angular_commit=
backend_digest=
angular_digest=
solr_digest=
migrations=
registry=ghcr.io
owner=
output=release-manifest.json

die() { printf 'erro: %s\n' "$*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)        version="$2";        shift 2 ;;
    --commit)         commit="$2";         shift 2 ;;
    --angular-commit) angular_commit="$2"; shift 2 ;;
    --backend-digest) backend_digest="$2"; shift 2 ;;
    --angular-digest) angular_digest="$2"; shift 2 ;;
    --solr-digest)    solr_digest="$2";    shift 2 ;;
    --migrations)     migrations="$2";     shift 2 ;;
    --registry)       registry="$2";       shift 2 ;;
    --repository-owner) owner="$2";        shift 2 ;;
    --output)         output="$2";         shift 2 ;;
    -h|--help)        sed -n '2,30p' "$0"; exit 0 ;;
    *) die "argumento desconhecido: $1" ;;
  esac
done

[[ -n "${version}" ]]        || die "--version e obrigatorio"
[[ -n "${commit}" ]]         || die "--commit e obrigatorio"
[[ -n "${backend_digest}" ]] || die "--backend-digest e obrigatorio"
[[ -n "${angular_digest}" ]] || die "--angular-digest e obrigatorio"
[[ -n "${solr_digest}" ]]    || die "--solr-digest e obrigatorio"
[[ -n "${migrations}" ]]     || die "--migrations e obrigatorio"

# The manifest carries SemVer; the git tag may be v-prefixed.
version="${version#v}"
printf '%s' "${version}" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.]+)?$' \
  || die "'${version}' nao e SemVer"

for pair in "backend:${backend_digest}" "angular:${angular_digest}" "solr:${solr_digest}"; do
  name="${pair%%:*}"
  value="${pair#*:}"
  printf '%s' "${value}" | grep -Eq '^sha256:[0-9a-f]{64}$' \
    || die "digest de ${name} invalido: ${value}"
done

# The installer resolves each image as ghcr.io/<owner>/<name>@sha256:<digest>,
# so the repository name has to be lower case.
if [[ -z "${owner}" ]]; then
  owner="$(git config --get remote.origin.url 2>/dev/null \
    | sed -E 's#.*[:/]([^/]+)/[^/]+(\.git)?$#\1#')"
  [[ -n "${owner}" ]] || die "nao foi possivel inferir o owner; use --repository-owner"
fi
owner="$(printf '%s' "${owner}" | tr '[:upper:]' '[:lower:]')"

[[ -f "${migrations}" ]] || die "arquivo de migrations nao encontrado: ${migrations}"
history="$(jq '.' "${migrations}")"
count="$(printf '%s' "${history}" | jq 'length')"
[[ "${count}" -gt 0 ]] || die "database.migrations esta vazio"

# Reject anything the installer would refuse, so a broken manifest never ships.
printf '%s' "${history}" | jq -e '
  all(.[];
    (keys | sort) == ["checksum","script","version"]
    and (.version | test("^[0-9]+(\\.[0-9]+)*$"))
    and (.script | type == "string")
    and (.checksum == null or (.checksum | type == "number"))
  )' >/dev/null || die "database.migrations invalido"
[[ "$(printf '%s' "${history}" | jq '[.[].version] | unique | length')" == "${count}" ]] \
  || die "database.migrations tem version repetida"

jq -n \
  --arg version "${version}" \
  --arg commit "${commit}" \
  --arg angularCommit "${angular_commit}" \
  --arg createdAt "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg backendRef "${registry}/${owner}/dspace-pcirn-backend@${backend_digest}" \
  --arg solrRef "${registry}/${owner}/dspace-pcirn-solr@${solr_digest}" \
  --arg frontendRef "${registry}/${owner}/dspace-pcirn-angular@${angular_digest}" \
  --argjson migrations "${history}" \
  '{
     schema_version: 1,
     version: $version,
     images: {
       backend: $backendRef,
       solr: $solrRef,
       frontend: $frontendRef
     },
     database: { migrations: $migrations },
     source: {
       commit: $commit,
       angularCommit: (if $angularCommit == "" then null else $angularCommit end)
     },
     createdAt: $createdAt
   }' > "${output}"

printf 'Manifesto %s escrito em %s (%s migrations)\n' "${version}" "${output}" "${count}"

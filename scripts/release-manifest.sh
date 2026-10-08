#!/usr/bin/env bash
# Writes the release manifest for a published version.
#
# The manifest is the contract between a published version and a deployment:
# it records which commit produced the images and the digest each image
# resolved to, so a deployment can pin the exact bytes it runs even if a tag is
# later moved.
#
# Usage:
#   scripts/release-manifest.sh \
#     --version v1.0.0 \
#     --commit <sha> \
#     --angular-commit <sha> \
#     --backend-digest sha256:<...> \
#     --angular-digest sha256:<...> \
#     --solr-digest sha256:<...> \
#     [--registry ghcr.io] \
#     [--repository-owner kevintestegit] \
#     [--output release-manifest.json]
set -Eeuo pipefail

version=
commit=
angular_commit=
backend_digest=
angular_digest=
solr_digest=
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
    --registry)       registry="$2";       shift 2 ;;
    --repository-owner) owner="$2";        shift 2 ;;
    --output)         output="$2";         shift 2 ;;
    -h|--help)        sed -n '2,20p' "$0"; exit 0 ;;
    *) die "argumento desconhecido: $1" ;;
  esac
done

[[ -n "${version}" ]]        || die "--version e obrigatorio"
[[ -n "${commit}" ]]         || die "--commit e obrigatorio"
[[ -n "${backend_digest}" ]] || die "--backend-digest e obrigatorio"
[[ -n "${angular_digest}" ]] || die "--angular-digest e obrigatorio"

# A version tag is immutable and must look like one.
printf '%s' "${version}" | grep -Eq '^v[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.]+)?$' \
  || die "'${version}' nao e uma versao (esperado vMAIOR.MENOR.CORRECAO)"

# A digest that is not a digest would silently make the manifest useless.
for pair in "backend:${backend_digest}" "angular:${angular_digest}"; do
  name="${pair%%:*}"
  value="${pair#*:}"
  printf '%s' "${value}" | grep -Eq '^sha256:[0-9a-f]{64}$' \
    || die "digest de ${name} invalido: ${value}"
done
if [[ -n "${solr_digest}" ]]; then
  printf '%s' "${solr_digest}" | grep -Eq '^sha256:[0-9a-f]{64}$' \
    || die "digest de solr invalido: ${solr_digest}"
fi

# Owner defaults to the repository the script runs in, which is what the
# workflow needs; the explicit flag exists for local runs.
if [[ -z "${owner}" ]]; then
  owner="$(git config --get remote.origin.url 2>/dev/null \
    | sed -E 's#.*[:/]([^/]+)/[^/]+(\.git)?$#\1#')"
  [[ -n "${owner}" ]] || die "nao foi possivel inferir o owner; use --repository-owner"
fi

jq -n \
  --arg version "${version}" \
  --arg commit "${commit}" \
  --arg angularCommit "${angular_commit}" \
  --arg registry "${registry}" \
  --arg owner "${owner}" \
  --arg backendDigest "${backend_digest}" \
  --arg angularDigest "${angular_digest}" \
  --arg solrDigest "${solr_digest}" \
  --arg createdAt "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  '{
     version: $version,
     source: {
       commit: $commit,
       angularCommit: (if $angularCommit == "" then null else $angularCommit end)
     },
     createdAt: $createdAt,
     images: (
       [
         { name: "backend", repository: ($registry + "/" + $owner + "/dspace-pcirn-backend"), digest: $backendDigest },
         { name: "angular", repository: ($registry + "/" + $owner + "/dspace-pcirn-angular"), digest: $angularDigest }
       ]
       + (if $solrDigest == "" then []
          else [{ name: "solr", repository: ($registry + "/" + $owner + "/dspace-pcirn-solr"), digest: $solrDigest }]
          end)
       | map(. + { reference: (.repository + "@" + .digest), tag: ($version) })
     ),
     platforms: ["linux/amd64", "linux/arm64"]
   }' > "${output}"

printf 'Manifesto escrito em %s\n' "${output}"

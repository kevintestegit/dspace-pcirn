#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MAVEN_REPO="${HOME}/.cache/dspace-maven-repo"
MAVEN_IMAGE="maven:3-eclipse-temurin-17"
DEFAULT_MODULES=(dspace-services dspace-api dspace-server-webapp dspace/modules/additions dspace/modules/server dspace-oai dspace-rdf dspace-sword dspace-swordv2 dspace-iiif dspace-saml2)

mkdir -p "$MAVEN_REPO"
for m in "${DEFAULT_MODULES[@]}"; do mkdir -p "${ROOT}/${m}/target/classes"; done

mvn_in_docker() {
  docker run --rm \
    -u "$(id -u):$(id -g)" \
    -e HOME=/tmp \
    -e MAVEN_OPTS="-Duser.home=/tmp" \
    -v "${ROOT}:/app" \
    -v "${MAVEN_REPO}:/m2" \
    -w /app \
    "${MAVEN_IMAGE}" \
    mvn --no-transfer-progress -Dmaven.repo.local=/m2 "$@"
}

if [[ "${1:-}" == "init" ]]; then
  mvn_in_docker -DskipTests -P-assembly -P-test-environment \
    -Denforcer.skip=true -Dcheckstyle.skip=true -Dlicense.skip=true -Dxml.skip=true \
    -pl dspace-services,dspace-api,dspace-server-webapp,dspace/modules/additions,dspace/modules/server \
    -am install
  echo "init ok. Use scripts/backend-dev.sh apos alterar codigo Java."
  exit 0
fi

modules=("$@")
if [[ ${#modules[@]} -eq 0 ]]; then
  modules=("${DEFAULT_MODULES[@]}")
fi

mvn_in_docker -DskipTests -Denforcer.skip=true -Dcheckstyle.skip=true -Dlicense.skip=true \
  compile -pl "$(IFS=,; echo "${modules[*]}")"

docker compose up -d --no-build --force-recreate dspace

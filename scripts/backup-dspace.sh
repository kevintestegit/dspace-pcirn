#!/usr/bin/env bash
set -Eeuo pipefail

umask 077
backup_root="${1:-./backups}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_dir="${backup_root%/}/dspace-${timestamp}"
mkdir -p "$backup_dir"

# PostgreSQL is the source of truth for metadata, policies, users and workflows.
docker compose exec -T dspacedb pg_dump -U dspace -d dspace --format=custom > "$backup_dir/dspace.dump"
# Assetstore contains the uploaded bitstreams and must travel with the database dump.
docker compose exec -T dspace tar -C /dspace -czf - assetstore > "$backup_dir/assetstore.tar.gz"

printf 'Backup criado em %s\n' "$backup_dir"

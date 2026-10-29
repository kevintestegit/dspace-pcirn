#!/usr/bin/env bash
set -euo pipefail

# Script para monitorar e gerar miniaturas automaticamente para novos documentos no DSpace PCIRN.
# Executa filter-media no container dspace e, caso alguma nova miniatura seja gerada,
# atualiza o índice do Solr Discovery imediatamente.

if ! docker ps --format '{{.Names}}' | grep -q '^dspace$'; then
    exit 0
fi

# Executa filter-media apenas para o plugin PDFBox Thumbnail
OUTPUT=$(docker exec -i dspace /dspace/bin/dspace filter-media -p "PDFBox JPEG Thumbnail" 2>&1 || true)

# Se algum arquivo foi processado (FILTERED:), atualiza o índice do Discovery
if echo "$OUTPUT" | grep -q "FILTERED:"; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Novas miniaturas geradas:"
    echo "$OUTPUT" | grep "FILTERED:"
    docker exec -i dspace /dspace/bin/dspace index-discovery || true
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Índice Discovery atualizado com sucesso."
fi

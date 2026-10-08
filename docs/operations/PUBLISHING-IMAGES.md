# Publicação de imagens

As imagens de produção são construídas e publicadas pelo workflow
`.github/workflows/publish-images.yml`. O servidor não compila nada: ele baixa
uma versão publicada.

## O que é publicado

| Imagem | Origem | Dockerfile |
|---|---|---|
| `ghcr.io/<owner>/dspace-pcirn-backend` | raiz do repositório | `Dockerfile` |
| `ghcr.io/<owner>/dspace-pcirn-angular` | submódulo `dspace-angular/source` | `Dockerfile.dist` |
| `ghcr.io/<owner>/dspace-pcirn-solr` | `dspace/src/main/docker/dspace-solr` | `Dockerfile` |

Cada uma é publicada como **manifest list** com `linux/amd64` e `linux/arm64`.
O servidor escolhe a arquitetura sozinho ao fazer o pull.

O Solr é publicado por nós, e não consumido direto de
`dspace/dspace-solr`, porque a imagem carrega os configsets deste repositório
(`dspace/solr/`). Usar a imagem de terceiros exigiria montar os configsets no
servidor, o que tira do versionamento uma parte do que a busca depende.

## O que dispara

Somente tags que casam com `vMAJOR.MINOR.PATCH`, opcionalmente com sufixo
(`v1.0.0`, `v1.2.3-rc1`). Push em branch não publica nada: quem decide quando
uma versão entra em produção é o NTI, executando o pull da versão escolhida.

Também pode ser disparado manualmente (`workflow_dispatch`) informando uma tag
que já exista. O job `validate` resolve a tag para `refs/tags/<tag>` e todos os
jobs fazem checkout **desse** ref, nunca do topo do branch em que o workflow foi
iniciado; o manifesto registra o commit que foi construído, não o `GITHUB_SHA`
do evento. Publicar manualmente uma tag antiga não pode, portanto, etiquetar
código novo com a versão antiga.

## Portões antes da publicação

O job `validate` roda antes de qualquer build. Ele falha e nada é publicado se:

- a tag não tiver o formato de versão;
- o commit do submódulo Angular gravado pelo superprojeto não estiver
  alcançável a partir de um branch do fork (a URL é lida de `.gitmodules`, não
  dos remotes do submódulo, que em clone novo apontam para o upstream);
- o build ou os testes unitários do Maven falharem.

Cada imagem só recebe a tag de versão depois que **as duas arquiteturas** foram
construídas e enviadas. As arquiteturas são enviadas primeiro por digest
(`push-by-digest=true`); um job separado cria o manifest list. Se uma
arquitetura falhar, nenhuma tag é criada e a versão não existe para consumo.

## Imutabilidade e digests

Uma tag como `v1.0.0` é um ponteiro mutável; o que identifica os bytes é o
digest. O `release-manifest.json`, anexado à release, é o **contrato consumido
pelo instalador do NTI** (`deploy/nti/README.md`, seção "Contrato esperado do
pipeline GHCR"):

```json
{
  "schema_version": 1,
  "version": "1.0.0",
  "images": {
    "backend":  "ghcr.io/<owner>/dspace-pcirn-backend@sha256:<64 hex>",
    "solr":     "ghcr.io/<owner>/dspace-pcirn-solr@sha256:<64 hex>",
    "frontend": "ghcr.io/<owner>/dspace-pcirn-angular@sha256:<64 hex>"
  },
  "database": {
    "migrations": [
      { "version": "9.4.2026.09.23",
        "script": "V9.4_2026.09.23__pcirn_memoria_institucional_collection.sql",
        "checksum": 20958078 }
    ]
  }
}
```

Pontos que a CLI do instalador verifica e que o pipeline precisa respeitar:

- `version` é SemVer **sem** o `v` da tag; `images` só aceita
  `ghcr.io/<minusculas>/<nome>@sha256:<64 hex>`, nunca tag ou `latest`;
- as três chaves — `backend`, `solr`, `frontend` — são obrigatórias;
- `database.migrations` traz o histórico Flyway completo, com `version` em
  pontos, `script` e `checksum` como persistidos em `public.schema_version`.
  Checksum **não** é derivável de SHA-256 do SQL: o Flyway usa o próprio
  algoritmo e migrations Java valem `-1`. Por isso o histórico é extraído do
  banco por `scripts/flyway-history.sh` e versionado em
  `scripts/flyway-history.json`;
- a CLI compara esse histórico linha a linha contra o banco do NTI e **recusa a
  atualização** se divergir. Logo, alterar uma migration já aplicada quebra a
  instalação — e é por isso que as nove migrações PCIRN estão congeladas.

O job `validate` falha se alguma migration listada em `flyway-history.json`
tiver desaparecido do repositório. Ao adicionar uma migration nova, regenere o
arquivo:

```bash
scripts/flyway-history.sh \
  --database-url "jdbc:postgresql://HOST:5432/dspace" \
  --output scripts/flyway-history.json
```

Para fixar a versão exata em produção, use `repository@sha256:...` no lugar da
tag. É isso que torna o rollback confiável: o manifesto diz qual digest foi
publicado para cada versão.

`source` e `createdAt` são chaves extras; a CLI ignora o que não conhece e elas
servem para registrar qual commit produziu as imagens. O `source.commit` é o
commit do ref publicado — o `HEAD` do checkout da tag.

As imagens também levam proveniência e SBOM (`provenance: true`, `sbom: true`),
consultáveis com:

```bash
docker buildx imagetools inspect ghcr.io/<owner>/dspace-pcirn-backend:v1.0.0
```

## Publicar a primeira versão

Pré-requisitos, uma única vez:

1. O commit do submódulo Angular precisa estar no fork. Enquanto não estiver, o
   job `validate` bloqueia — de propósito.
2. Os pacotes no GHCR nascem privados. Se o servidor não for autenticado, torne
   os três pacotes públicos em *Package settings*, ou configure um token de
   leitura no servidor.

```bash
# 1. o submodulo primeiro
cd dspace-angular/source
git push fork codex/pcirn-repository-structure

# 2. o backend
cd ../..
git push origin main

# 3. a tag, que dispara a publicacao
git tag -a v1.0.0 -m "PCIRN 1.0.0"
git push origin v1.0.0
```

Acompanhe em *Actions*. Ao final, a release `v1.0.0` existe com o
`release-manifest.json` anexado.

## Usar uma versão no servidor

```bash
docker compose -f docker-compose.yml --env-file .env.production pull
docker compose -f docker-compose.yml --env-file .env.production up -d
```

Para fixar por digest, preencha em `.env.production`:

```
DSPACE_IMAGE=ghcr.io/<owner>/dspace-pcirn-backend@sha256:...
ANGULAR_IMAGE=ghcr.io/<owner>/dspace-pcirn-angular@sha256:...
SOLR_IMAGE=ghcr.io/<owner>/dspace-pcirn-solr@sha256:...
```

## Uma versão publicada por engano

Uma tag não deve ser movida: o digest já pode estar em uso em algum servidor.
Para corrigir, publique a próxima versão (`v1.0.1`). Se for imprescindível
remover, apague a tag e o pacote pelo GitHub — mas trate como incidente e
verifique se algum servidor já fez o pull.

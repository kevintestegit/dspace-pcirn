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
que já exista.

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

Uma tag como `v1.0.0` é um ponteiro mutável. O que identifica os bytes é o
digest. O `release-manifest.json`, anexado à release, registra:

```json
{
  "version": "v1.0.0",
  "source": { "commit": "...", "angularCommit": "..." },
  "images": [
    { "name": "backend", "repository": "ghcr.io/<owner>/dspace-pcirn-backend",
      "digest": "sha256:...", "reference": "ghcr.io/<owner>/dspace-pcirn-backend@sha256:..." }
  ],
  "platforms": ["linux/amd64", "linux/arm64"]
}
```

Para fixar a versão exata em produção, use `repository@sha256:...` no lugar da
tag. É isso que torna o rollback confiável: o manifesto diz qual digest foi
publicado para cada versão.

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

# Operação de produção

Desenvolvimento e produção usam arquivos Compose distintos:

| | arquivo | PostgreSQL |
|---|---|---|
| Desenvolvimento | `docker-compose.dev.yml` | container `dspacedb` |
| Produção | `docker-compose.yml` | instância administrada pelo NTI |

A stack de produção não contém serviço de banco. O DSpace conecta por JDBC à
instância do NTI, que precisa estar acessível a partir do servidor antes de a
stack subir.

## Preparação do servidor

```bash
cp .env.production.example .env.production
cp smtp.env.example smtp.env
chmod 600 .env.production smtp.env
```

Preencher em `.env.production`, no mínimo: `DB_URL`, `DB_USERNAME`,
`DB_PASSWORD`, `PUBLIC_UI_URL`, `PUBLIC_REST_URL`, `PUBLIC_REST_HOST`,
`ASSETSTORE_PATH` e as três imagens versionadas. A stack se recusa a subir se
qualquer uma delas faltar. `DSPACE_IMAGE`, `SOLR_IMAGE` e `ANGULAR_IMAGE` não
podem apontar para `latest`: fixe a versão que está sendo publicada.

O `ASSETSTORE_PATH` é onde os bitstreams ficam no servidor. É estado, não
artefato de build: precisa sobreviver a toda atualização de imagem e entrar no
backup.

O arquivo `dspace/config/local.cfg` é montado somente leitura. Ele precisa
existir no servidor antes de subir a stack; use `dspace/config/local.cfg.EXAMPLE`
como base.

```bash
docker compose -f docker-compose.yml --env-file .env.production up -d
```

UI e REST ficam ligados a `127.0.0.1`; um proxy TLS encaminha o tráfego público
para as portas `4000` e `8501`. Use `deploy/nginx/pcirn.conf.example` como base,
substituindo o hostname e os caminhos do certificado. `PUBLIC_UI_URL` e
`PUBLIC_REST_URL` devem ser as URLs HTTPS do proxy, sem as portas internas: o
backend recusa iniciar com URL que não seja `https://`.

A faixa `TRUSTED_PROXY_NETWORK` precisa ser coerente com `DSPACE_NETWORK_SUBNET`.
O REST só honra `X-Forwarded-*` vindo dessa faixa.

## Migração de schema

O schema **não** é migrado na inicialização do container. Uma migração que falha
deve aparecer como erro legível, não como um container reiniciando em loop.
Depois de publicar uma versão que altera o schema:

```bash
docker compose -f docker-compose.yml --env-file .env.production \
  run --rm dspace /dspace/bin/dspace database info
docker compose -f docker-compose.yml --env-file .env.production \
  run --rm dspace /dspace/bin/dspace database migrate
```

Toda migração já aplicada é imutável: alterar o conteúdo de um script muda o
checksum gravado em `schema_version` e o Flyway passa a recusar a próxima
migração. As nove migrações PCIRN anteriores aos cabeçalhos de licença estão
congeladas e excluídas da checagem de cabeçalho em `dspace-api/pom.xml`.

### Um banco novo não é criado por `database migrate`

As migrações PCIRN não são apenas de schema: elas ajustam permissões de
comunidades e coleções que precisam existir. Em um banco vazio, `database
migrate` para na primeira delas com erros de dado:

```
ERROR: The dc.title metadata field is missing          (V9.4_2026.08.15)
ERROR: PCIRN sector community not found: Gestão ...    (V9.4_2026.08.16)
```

`dc.title` vem do `registry-loader`, e as comunidades vêm do conteúdo do
repositório. A ordem de bootstrap seria schema → registries → estrutura de
comunidades e coleções → migrações, e ainda assim as migrações PCIRN foram
escritas contra os dados já existentes.

Por isso, a instalação no servidor do NTI parte de um **restore** do dump da
instância atual, e não de um banco vazio:

```bash
# no servidor, com o banco do NTI já criado e vazio
pg_restore -h HOST -U dspace -d dspace --no-owner --no-privileges dspace.dump
```

O dump carrega o schema completo e a tabela `schema_version` na versão
9.4.2026.09.23, de modo que `database info` reporta o schema em dia e nenhuma
migração precisa rodar. Só depois disso a stack sobe.

## Tarefas administrativas

Dentro de um container existente:

```bash
docker compose -f docker-compose.yml --env-file .env.production \
  exec dspace /dspace/bin/dspace <comando>
```

Ou em um container descartável, sem afetar o que está em execução:

```bash
docker compose -f docker-compose.yml --env-file .env.production \
  run --rm dspace /dspace/bin/dspace <comando>
```

Reconstrução do índice de busca, necessária quando a configuração de descoberta
muda:

```bash
docker compose -f docker-compose.yml --env-file .env.production \
  exec dspace /dspace/bin/dspace index-discovery -b
```

## Login OIDC

O login começa em `/server/api/authn/oidc/login`. O callback exige o estado de
uso único da sessão que iniciou a navegação. O cookie de sessão é Secure,
HttpOnly e SameSite=Lax; esse fluxo exige HTTPS e afinidade de sessão caso haja
mais de uma instância REST.

## Segredos e contexto de build

`.env`, `.env.*`, `smtp.env` e `scripts/../backups/` são excluídos do contexto
Docker, inclusive em subdiretórios. Mantenha os arquivos de runtime com
permissão `600`.

A exclusão não remove segredos de snapshots, imagens intermediárias ou caches já
criados. Se houve exposição, revogue e substitua as chaves Brevo/SMTP e coordene
a troca da senha do PostgreSQL com o NTI. Alterar `DB_PASSWORD` no
`.env.production` não muda a senha de um banco já inicializado: a troca precisa
acontecer nos dois lados.

## Harvesting e depósitos ZIP

OAI e ORE usam somente destinos HTTP(S) públicos nas portas 80/443, com validação
DNS em cada conexão e em redirecionamentos. Proxies de saída não são usados por
esse cliente. Respostas OAI têm limite de 16 MiB; recursos ORE, 1 GiB.
Provedores internos e portas alternativas são rejeitados.

Depósitos SimpleZip são descompactados em área temporária antes de criar
bitstreams. Os limites em `swordv2-server.cfg` são positivos: 1.000 entradas,
100 MiB por entrada, 1 GiB total e razão máxima de compressão de 100. A área
temporária precisa de espaço para o limite total configurado.

## Backup

```bash
scripts/backup-dspace.sh /var/backups/dspace
```

O script detecta o modo: com o container `dspacedb` em execução faz o dump pelo
container; sem ele, usa um cliente PostgreSQL descartável contra o banco do NTI,
lendo `DB_URL` e `DB_PASSWORD` de `.env.production`. Grava `dspace.dump`,
`assetstore.tar.gz` e `SHA256SUMS`, validando os dois artefatos antes de
publicá-los.

Guardar os três arquivos juntos. O índice Solr é derivado e pode ser
reconstruído com `index-discovery -b`.

## Aceite antes da publicação

- `docker compose ... ps` sem serviços reiniciando.
- `database info` sem migrações pendentes e `schema_version` sem falhas.
- login, logout, recuperação de senha e cadastro administrativo de usuário.
- usuário de cada setor deposita somente nas coleções do seu setor.
- depósito, devolução, reenvio, exclusão e aprovação NUGECID.
- Handle, busca, filtros e download público do bitstream aprovado.
- SMTP real testado com `/dspace/bin/dspace test-email`.
- backup restaurado em uma instalação de teste.

Ainda dependem de decisão externa: hostname e porta do PostgreSQL, SSL,
hostname público, certificado e servidor SMTP institucional. Nenhum segredo deve
entrar no Git.

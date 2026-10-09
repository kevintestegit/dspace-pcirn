# DSPACEPCIRN

`install.sh` instala uma stack dedicada; `dspacepcirn` administra essa instalação.
O instalador não instala pacotes do sistema. Pré-requisitos: Linux, Bash, Python
3.9+, Docker Engine, Compose >= 2.20 e `psql`, `pg_dump`, `pg_restore` (cliente
PostgreSQL da mesma versão major do servidor), OpenSSL para PostgreSQL em Docker. Execute como usuário
administrativo com acesso ao Docker e leitura/escrita dos dados do Solr, incluindo
arquivos pertencentes ao UID do container; normalmente root no servidor dedicado.
O administrador fornece banco **dedicado**, credenciais, certificados TLS e os privilégios
necessários para Flyway e restore. O banco pode ser externo ou provisionado em Docker pelo wizard.

## Menu e instalação interativa

Em uma VM Ubuntu limpa, instale Bash, Python 3, OpenSSL e os clientes PostgreSQL
do mesmo major do banco (15, 16 ou 17 no modo Docker). Exemplo para PostgreSQL 17,
após configurar o [repositório oficial PostgreSQL](https://www.postgresql.org/download/linux/ubuntu/):

```bash
sudo apt-get update
sudo apt-get install -y bash python3 openssl postgresql-client-17
```

Instale Docker Engine e o plugin Compose pelo
[repositório oficial Docker](https://docs.docker.com/engine/install/ubuntu/#install-using-the-repository).
Não é necessário instalar PostgreSQL Server no host. Confirme `docker compose version`,
`psql --version`, `pg_dump --version` e `pg_restore --version` antes de continuar.

Na cópia revisada da release, instale somente o gerenciador:

```bash
sudo bash deploy/nti/install-manager.sh
cd /
sudo dspacepcirn
```

O comando regular `/usr/local/bin/dspacepcirn` executa a cópia autossuficiente em
`/usr/local/lib/dspacepcirn`, incluindo os módulos Python, templates Compose e SMTP. Depois
desse passo o checkout pode ser removido; nenhum subcomando depende dele ou do
diretório corrente. A instalação recusa comando ou biblioteca preexistentes sem
sobrescrevê-los. Os pré-requisitos do sistema continuam sendo responsabilidade
do administrador; o gerenciador não executa apt nem altera outras stacks.

`./install.sh` sem argumentos abre o mesmo menu. O menu oferece instalação/retomada,
status, diagnóstico, validação dos serviços, backup, exportação e verificação de dados.
Os subcomandos abaixo continuam disponíveis sem interação. Para outra raiz, use
`sudo dspacepcirn --root /srv/outra-instalacao`.

O wizard contém sete etapas, com validação antes de cada avanço:

1. **Diagnóstico do servidor:** Ubuntu, ferramentas, Docker local, Compose, recursos,
   imagens da arquitetura correta, portas livres e conflitos de rede.
2. **Escolha do PostgreSQL:** somente **PostgreSQL em Docker** e **PostgreSQL externo**.
   O modo externo solicita host, porta, banco dedicado vazio, usuário, senha e TLS,
   e verifica conexão, ownership, permissões e versões dos clientes.
3. **Importação de dados:** seleciona um pacote criado por `export-data`, verifica
   SHA-256, relatório de origem e igualdade entre a release do pacote e a instalação.
   A restauração efetiva ocorre na etapa 5, com o backend parado.
4. **Configuração institucional:** nome, sigla, URLs HTTPS da interface e do REST,
   seguida da validação completa de recursos e PostgreSQL.
5. **Instalação:** chama `migrate-data` somente no destino vazio; chama `verify-data`
   antes do deploy existente. O wizard não autoriza Flyway, mesmo se receber
   `--authorize-migrations`: o pacote deve conter o histórico completo da release.
6. **Validação dos serviços:** backend, Solr e interface precisam estar saudáveis,
   e PostgreSQL precisa responder.
7. **Relatório final:** `ROOT/report.json` registra release, modo do PostgreSQL,
   URLs e conclusão das etapas, sem credenciais.

O wizard exige um pacote de dados. Para inicialização de uma base nova sem acervo,
use o comando direto `install --config ... --manifest ... --authorize-migrations`
após revisar e autorizar a inicialização; esse comando permanece disponível para
automação. Para um pacote de release antiga, instale primeiro essa mesma release,
e só depois execute `update` com autorização explícita das migrations necessárias.

### PostgreSQL em Docker

Informe uma imagem oficial `postgres@sha256:DIGEST_REAL_64_HEX`, PostgreSQL 15, 16
ou 17, com o mesmo major dos clientes locais. O instalador confirma a versão antes
de criar o volume. PostgreSQL 18+ usa outro layout de dados e é recusado neste fluxo.
O volume externo persistente e o container têm nome derivado da raiz da instalação.
Um recurso preexistente é recusado; recursos criados pelo wizard só são reutilizados
quando o diário e os rótulos de propriedade coincidem. Nenhum volume é excluído.

A porta escolhida é publicada somente em `127.0.0.1` (padrão 55432). O backend usa
`postgres:5432` na rede privada do Compose. Todas as conexões TCP exigem TLS e SCRAM;
o certificado local é verificado por `verify-ca`. A senha administrativa é aleatória,
lida de arquivo protegido, e o usuário da aplicação não recebe superuser, createdb
ou createrole. O certificado e a chave ficam em `ROOT/postgres-tls`; a chave tem
permissão 600 e pertence ao usuário PostgreSQL da imagem. O certificado tem validade
de dez anos; sua substituição exige manutenção planejada antes de expirar.

### Retomada e correção de erros

`ROOT/wizard.json` guarda entradas e etapas concluídas; ele contém credenciais e
recebe permissão 600, dentro de uma raiz 700. A senha é digitada sem eco. Configurações,
credenciais temporárias e relatórios também usam 600. A CLI não retransmite stderr
de ferramentas, que poderia revelar senhas. Mantenha todos esses arquivos privados.

Em erro recuperável, corrija o problema e escolha tentar novamente, ou saia e execute
`sudo dspacepcirn` para retomar na etapa pendente. Em automação, repita o mesmo comando,
com a mesma configuração, manifesto e pacote. Antes do provisionamento do banco,
é possível corrigir as credenciais em `--config`; após essa etapa, mudanças de
configuração são recusadas para proteger o destino. Uma importação já verificada não é
executada de novo; manifesto ou pacote alterados bloqueiam a retomada.

Se houver `operation.json` (restauração/deploy interrompido) ou `postgres.json` com
estado `creating`, a retomada fica bloqueada para revisão manual. Não remova o diário
para forçar nova importação, não limpe a base e não execute `down -v`. Examine o diário,
o staging e os backups, preserve os recursos e determine quais operações concluíram.
Para falha durante a primeira restauração, use uma nova raiz e um novo banco vazio
após preservar o destino interrompido; o wizard não reinicializa esse destino.
Recuperação de instalação já existente continua pelos comandos explícitos de
restore/rollback documentados abaixo, com autorização própria.

As portas HTTP internas não validam a publicação HTTPS. Configure o proxy reverso
conforme [exemplo existente](../nginx/pcirn.conf.example), certificados e SMTP antes
de liberar acesso aos usuários. O relatório confirma os serviços internos.

### Automação das sete etapas

```bash
sudo dspacepcirn install --wizard --root /srv/dspacepcirn \
  --config /etc/dspacepcirn/config.json --manifest /backup/release.json \
  --data-package /backup/pacote
# Equivalente:
sudo ./install.sh --root /srv/dspacepcirn \
  --config /etc/dspacepcirn/config.json --manifest /backup/release.json \
  --data-package /backup/pacote
```

Para Docker, acrescente `PG_MODE: "docker"` e `PG_IMAGE` à configuração abaixo,
e use `DB_URL` com host `127.0.0.1`, porta explícita, `sslmode=verify-ca` e
`sslrootcert=/srv/dspacepcirn/postgres-tls/server.crt` (ajuste à raiz escolhida).
Esse certificado é criado pelo wizard. Para externo, `PG_MODE: "external"` é opcional.
`DSPACE_NAME` e `DSPACE_SHORTNAME` são opcionais na automação. Nenhuma senha deve
ser passada na linha de comando.

## Configuração inicial

Crie `/etc/dspacepcirn/config.json`, com permissão 600 (diretório 700):

```json
{
  "DB_URL": "jdbc:postgresql://postgres.example:5432/pcirn?sslmode=verify-full&sslrootcert=/etc/ssl/repository-ca.pem",
  "DB_USERNAME": "pcirn",
  "DB_PASSWORD": "SUBSTITUA_PELA_SENHA",
  "PUBLIC_UI_URL": "https://repositorio.example",
  "PUBLIC_REST_URL": "https://repositorio.example/server",
  "PUBLIC_REST_HOST": "repositorio.example"
}
```

Os seis campos abaixo são obrigatórios; os campos opcionais são documentados acima. Não há interpolação nem execução de shell.
`sslmode` explícito aceita require, verify-ca ou verify-full; os parâmetros JDBC
adicionais aceitos são sslrootcert, sslcert e sslkey. Com verify-ca ou verify-full
o `sslrootcert` é obrigatório. Cada caminho precisa ser um **arquivo absoluto e
legível no host**: a CLI o monta somente leitura no backend, no mesmo caminho, de
modo que psql, pg_dump, pg_restore e o driver JDBC leiam o mesmo material. Um
diretório de CAs é recusado de propósito — o driver JDBC lê um único arquivo PEM,
então aceitá-lo funcionaria para o psql e quebraria a aplicação.
Nunca empacote chaves privadas nas imagens. Use require apenas quando autorizado
pelo administrador; verify-full verifica também a identidade do servidor.

Faça login no GHCR previamente com Docker, quando as imagens forem privadas. Sob
`sudo`, o login do usuário que invocou é usado automaticamente (`DOCKER_CONFIG`
explícito tem precedência; caso contrário `~/.docker` do `SUDO_USER`); sem login o
pull falha como não autenticado.
Obtenha e revise o manifesto publicado pelo pipeline; não execute curl | bash.

```bash
./install.sh --root /srv/dspacepcirn --config /etc/dspacepcirn/config.json \
  --manifest /tmp/release.json --data-package /backup/pacote
export PATH="/srv/dspacepcirn/bin:$PATH"
dspacepcirn status --root /srv/dspacepcirn
```

Os binários ficam em `ROOT/bin`, a configuração em `ROOT/config.json`, o Compose
em `ROOT/compose.yml`, a configuração complementar em `ROOT/dspace/config/local.cfg`,
o e-mail em `ROOT/smtp.env` e os dados em `ROOT/data/{assetstore,solr}`. O
projeto Compose deriva do hash do caminho absoluto, isolando instalações em
diretórios diferentes. As portas padrão são 127.0.0.1:8501 e 127.0.0.1:4000; o
administrador configura o proxy TLS conforme
[exemplo existente](../nginx/pcirn.conf.example). Em hosts com outra stack usando
essas portas, use outro host ou ajuste o Compose dedicado antes do start,
incluindo portas, subnet e trusted proxy range juntos para evitar sobreposição
de redes Docker (o padrão é 10.250.50.0/24).

O backend carrega `ROOT/smtp.env` como `env_file`. O install cria o arquivo a
partir de `smtp.env.example` — com o envio desabilitado — e nunca o sobrescreve;
preencha o SMTP institucional e remova `mail__P__server__P__disabled` para
habilitar as notificações. O arquivo precisa existir para o Compose subir.

Bancos e volumes existentes nunca são substituídos durante a instalação. A configuração provisória criada pelo próprio wizard é atualizada na etapa institucional; os demais arquivos existentes são preservados. Configuração fornecida
que divergir da existente causa erro. A segunda instalação da mesma release apenas
verifica os pré-requisitos e a saúde, sem backup, migration ou restart. Para outra
release, use update. O diretório deve ser dedicado e não conter links nos caminhos
administrativos. Não aponte a CLI para o checkout, mounts ou banco da stack atual.

## Comandos

| Comando | Operação |
|---|---|
| `install --wizard --config ARQUIVO --manifest ARQUIVO --data-package DIRETÓRIO` | Executa as sete etapas sem prompts |
| `install --config ARQUIVO --manifest ARQUIVO` | Provisionamento direto para automação; migrations exigem autorização explícita |
| `update --manifest ARQUIVO` | Consulta histórico, baixa digests, para stack, faz backup e atualiza |
| `status` | Estado de todos os containers e aviso de operação interrompida |
| `version` | Release registrada (status informa operações ainda pendentes) |
| `doctor` | Ferramentas, daemon, Compose, TLS PostgreSQL e validade da configuração |
| `export-data --output DIRETÓRIO` | Para a stack e exporta dump, assetstore, Solr e checksums; mantém a aplicação parada |
| `migrate-data --data-package DIRETÓRIO` | Restaura dump, assetstore e Solr em banco vazio, sem start ou Flyway |
| `verify-data [--expected RELATÓRIO] [--output ARQUIVO]` | Confere registros, Flyway e integridade dos arquivos |
| `health` | Exige três serviços running/healthy e conexão PostgreSQL |
| `logs [--follow]` | Últimas 200 linhas; saída pode conter dados pessoais da aplicação |
| `backup` | Para stack, cria backup validado, reinicia com healthcheck |
| `restore --backup DIRETÓRIO --authorize-restore` | Faz backup de segurança e restaura banco/dados/release |
| `rollback --authorize-restore` | Restaura backup anterior à última atualização/instalação, incluindo banco |

Todos aceitam `--root` (padrão `/srv/dspacepcirn`). Operações concorrentes são
bloqueadas. Erros retornam 1, argumentos inválidos 2 e interrupção 130.

Para migrar o acervo na instalação inicial, use `install.sh --data-package DIRETÓRIO`.
O [roteiro de migração](MIGRACAO.md) descreve preparação do pacote, configuração TLS,
SQL de provisionamento para o DBA, recusa de banco ocupado e
recuperação de falhas. Nenhuma importação bem-sucedida é marcada como instalação
concluída antes do deploy e healthcheck.

```bash
dspacepcirn update --manifest /tmp/release-nova.json --authorize-migrations
dspacepcirn backup
dspacepcirn rollback --authorize-restore
```

`--authorize-migrations` vale apenas para a operação invocada. A CLI consulta
`public.schema_version` em transação READ ONLY, compara versões/scripts/checksums
com o manifesto e só executa `/dspace/bin/dspace database migrate` se há versões
faltando. Histórico divergente, falho, repetível ou banco não vazio sem histórico
exige avaliação do administrador; não há repair/force automáticos. Nenhuma migration acontece
no startup, e `Context` não executa Flyway: abrir um contexto jamais altera o
schema, então nem a CLI nem a aplicação migram o banco fora deste comando. A flag
não substitui a aprovação administrativa do administrador.

## Backup e recuperação

Toda atualização efetiva e instalação inicial gera backup **antes** de migrations
ou start das novas imagens. A stack inteira fica parada para que banco, assetstore
e Solr sejam consistentes; outros escritores no banco dedicado devem estar
suspensos pelo administrador. O backup contém dump custom PostgreSQL, dois arquivos tar,
manifesto, identificação de origem e SHA-256 de cada arquivo. Dump é validado com
pg_restore --list; archives rejeitam travessia de diretórios, links e dispositivos.
Só backups completos são publicados em `ROOT/backups/backup-*`; `.incomplete-*`
indica falha e nunca é selecionado automaticamente. Sem retenção/exclusão automática.
Copie backups para armazenamento externo protegido. SHA-256 verifica integridade,
não autentica um arquivo recebido de terceiros: restaure somente backups confiáveis.

Restore exige autorização explícita, valida origem e hashes **antes de parar**,
faz um novo backup, extrai os dados em staging e reconstrói o schema public numa
única transação PostgreSQL. DROP SCHEMA CASCADE remove também objetos criados por
migrations posteriores; simples pg_restore --clean não garante esse resultado.
Banco dedicado é obrigatório. Ownership/ACLs originais não são transportados; os
objetos restaurados pertencem ao usuário administrador configurado. Configuração existente,
credenciais e local.cfg são preservados; role grants/certificados continuam sob administração local.
Dados anteriores e SQL ficam em `.restore-*` (permissões privadas) para recuperação;
a CLI não os exclui. Restore/rollback descartam logicamente alterações posteriores
ao backup selecionado, que ficam no backup de segurança criado antes do restore.

Se pull falhar, nada é parado. Se backup falhar numa atualização, a CLI tenta
reiniciar a release anterior. Se o healthcheck falhar sem migration, tenta voltar
às imagens anteriores. Se uma migration foi iniciada, a aplicação permanece parada
em caso de falha, pois não é seguro voltar apenas imagens. `operation.json` registra
release anterior, destino e backup; install/update/backup bloqueiam até recuperar.
SIGTERM/Ctrl-C encerram o subprocesso ativo e seguem o mesmo caminho de recuperação;
um desligamento abrupto deixa o journal para inspeção. Para falhas de restore,
repita restore indicando o backup desejado; o backup de segurança já concluído
é reutilizado e diretórios ausentes por interrupção são reconstruídos. Para falha
de backup avulso antes de qualquer alteração de dados, rollback apenas reinicia
a release anterior, sem exigir autorização de restore. Não apague o journal
para forçar update.

## Contrato esperado do pipeline GHCR — integração pendente

O pipeline paralelo deve publicar um arquivo JSON de release confiável com:

```json
{
  "schema_version": 1,
  "version": "1.0.0",
  "images": {
    "backend": "ghcr.io/ORGANIZACAO/backend@sha256:DIGEST_REAL_64_HEX",
    "solr": "ghcr.io/ORGANIZACAO/solr@sha256:DIGEST_REAL_64_HEX",
    "frontend": "ghcr.io/ORGANIZACAO/frontend@sha256:DIGEST_REAL_64_HEX"
  },
  "database": {
    "migrations": [
      {"version": "1", "script": "V1__exemplo.sql", "checksum": 123456789}
    ]
  }
}
```

**Exemplo estrutural, deliberadamente não instalável.** version é SemVer e imagens
usam apenas nomes GHCR minúsculos + SHA-256 real, nunca tags/latest. O pipeline
versiona as três imagens e fornece o digest do índice/plataforma publicado.
`database.migrations` é o histórico completo esperado após migrate de um banco
vazio de homologação: valores version/script/checksum do Flyway efetivamente usados
pela imagem, incluindo migrations Java (checksum null quando apropriado) e baseline
se existente. Não derive checksum Flyway de SHA-256 do SQL. Entradas são únicas;
version usa pontos, conforme persistida em schema_version. Mudanças em migrations
já aplicadas são rejeitadas. Este contrato v1 admite migrations versionadas; se o
pipeline introduzir repeatables, o contrato deve ser revisto antes da integração.

Backend: /dspace/bin/dspace, server-boot.jar, curl e Java 17; startup sem migration.
Solr: cores DSpace e utilitários init-var-solr/precreate-core/runuser/curl conforme
Compose atual. Frontend: Node SSR porta 4000, configuração DSPACE_* em runtime.
Banco usa schema public; assetstore em /dspace/assetstore. Imagens devem suportar
os envs e healthchecks do Compose existente. A CLI instalada é distribuída junto
com esta árvore, não atualizada implicitamente pelo manifesto de imagens.

Pendente: emissão do manifesto pelo pipeline DeepSeek, digests/versões reais,
permissões GHCR, arquitetura do servidor e ensaio end-to-end em homologação com
PostgreSQL externo (TLS, privilégios, Flyway, backup/restore e healthchecks).
Workflows do GitHub Actions não foram alterados por este instalador.

## Testes isolados

```bash
python3 -m unittest discover -s deploy/nti/tests -v
bash -n install.sh deploy/nti/dspacepcirn
```

Executáveis simulados verificam a CLI por subprocessos, sem daemon Docker ou banco.
Incluem os dois tipos de PostgreSQL, falhas nas sete etapas, retomada sem reimportação,
recusa de volumes existentes, TLS/SCRAM, falhas em pull, dump, migration, conexão, health e restore, corrupção de
backup, autorização, concorrência, proteção de credenciais e travessia de archives.
`test_production_operations.py` cobre a superfície fora da CLI — entrypoint do
Compose, `scripts/backup-dspace.sh`, publicação manual e SMTP — e usa o Docker
apenas para renderizar configurações; sem o CLI do Docker esses casos são pulados.
Referências técnicas: [imagem oficial PostgreSQL](https://hub.docker.com/_/postgres),
[TLS PostgreSQL](https://www.postgresql.org/docs/17/ssl-tcp.html), [Compose up --wait](https://docs.docker.com/reference/cli/docker/compose/up/),
[interpolação Compose](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/)
e [pg_restore](https://www.postgresql.org/docs/current/app-pgrestore.html).

## Homologação numa VM limpa

O [roteiro de homologação](HOMOLOGACAO.md) inclui preflight automático no wizard,
executor E2E opt-in e critérios de aprovação/recuperação. O contrato GHCR acima
permanece inalterado. Testes locais são simulados e não iniciam containers.

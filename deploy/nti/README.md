# DSPACEPCIRN

O comando principal é `sudo dspacepcirn`. Em Ubuntu 24.04 AMD64/ARM64, o gerenciador
prepara as dependências ausentes após uma confirmação, consulta releases oficiais e
provisiona PostgreSQL em Docker por padrão. Os comandos não interativos permanecem
disponíveis com configuração e manifesto explícitos.

A interface é concisa e em inglês. Após configurar o PostgreSQL, pergunta
`Import data? [y/N]`. Ao aceitar, obtém a origem pelo asset oficial `data-package.json`
da RC e baixa um pacote HTTPS verificado, sem pedir URL ou SHA-256 ao administrador.
Consulte [hospedagem e preparação do pacote](DATA-IMPORT.md). Sem importação, inicializa
um repositório vazio numa release compatível. Detalhes internos ficam em `ROOT/installer.log`.

## Primeiro acesso

Use uma cópia revisada deste código ou o pacote `dspacepcirn-manager.tar.gz` da
release oficial de `kevintestegit/dspace-pcirn`. Confira o SHA-256 publicado no
GitHub antes de extrair o pacote. O pacote é autossuficiente e dispensa Git.

```bash
# Na árvore do projeto:
sudo bash deploy/nti/install-manager.sh
# Ou, dentro do pacote verificado e extraído:
sudo bash install-manager.sh
sudo dspacepcirn
```

O gerenciador global fica em `/usr/local/lib/dspacepcirn`; o comando regular fica em
`/usr/local/bin/dspacepcirn`. O instalador do gerenciador recusa caminhos/comandos
preexistentes. Não execute downloads como scripts nem use `curl | bash`.

**A RC4 publicada não contém o pacote novo nem a capacidade de inicialização vazia.**
A seleção automática reconhece RCs pelo nome da tag, mesmo se o GitHub não as marcou
como prerelease. A publicação autorizada da RC6 inclui estas capacidades e é
condicionada aos testes da pipeline. Consulte [o relatório da entrega](RC6.md).

## Menu

1. Instalar DSpace, incluindo retomada de etapas concluídas.
2. Atualizar DSpace, com backup e autorização própria para migrations.
3. Fazer backup.
4. Restaurar backup, com confirmação e backup de segurança.
5. Verificar funcionamento.
6. Configurações avançadas: diagnóstico, status, logs, exportação/verificação de
   dados, seleção de versão, atualização do gerenciador e autenticação GHCR.
0. Sair.

Use `sudo dspacepcirn --root /srv/outra-instalacao` para outra raiz dedicada.

## Instalação

O fluxo tem sete checkpoints privados:

1. Diagnóstico: distribuição, versão, arquitetura, CPU, RAM, disco, rede, Docker,
   Compose, Python, OpenSSL e clientes PostgreSQL. Ubuntu 24.04 exige pelo menos
   2 CPUs, 8 GiB de RAM total, 4 GiB disponíveis e 30 GiB livres. Dependências vêm
   de Ubuntu, Docker e PostgreSQL oficiais, com chaves APT verificadas. Docker só é
   iniciado/habilitado se necessário. Não se instala PostgreSQL Server no host.
   Portas locais e subnet Docker livres são escolhidas automaticamente.
2. Preparação do PostgreSQL: Docker é padrão, PostgreSQL 16 oficial fixado pelo
   digest da arquitetura, cliente major 16, porta local livre, banco/usuário `dspace`
   e senhas aleatórias. No modo externo, informe host, porta, banco e credenciais;
   o padrão é `verify-full` usando CAs do sistema. CA particular ou certificado
   cliente são configurados em `--config`, conforme a seção avançada abaixo.
3. Importação opcional: `Import data? [y/N]`. A importação automática usa o pacote
   publicado para essa release e verifica checksums, versão, histórico e relatório
   antes de restaurar. O destino precisa estar vazio. Pacotes locais continuam
   disponíveis por `--data-package`; não há download ao escolher um repositório vazio.
4. Nome e endereço público HTTPS do repositório. O REST usa o mesmo host em `/server`.
   Configurações avançadas podem definir URLs separadas por `--config`.
5. Instalação: migrations de banco vazio exigem autorização explícita; migração
   utiliza `migrate-data` e `verify-data`, sem autorizar migrations automaticamente.
6. Saúde: backend, Angular, Solr e PostgreSQL precisam responder corretamente.
7. Relatório: `ROOT/report.json`, sem credenciais. Erros deixam `ROOT/diagnostic.json`
   com a etapa pendente e uma mensagem segura.

A release estável mais recente tem preferência; na ausência dela, o administrador
confirma a RC mais recente, identificada como versão de testes. O manifesto é baixado
do asset oficial, conferido com o SHA-256 do GitHub e com o commit da tag. As três
imagens precisam ser dos repositórios oficiais e suportar a arquitetura Docker.
Downloads têm limites e timeout. Falha de rede/autenticação não executa migrations.

### Banco vazio e histórico Flyway

As migrations institucionais históricas não foram alteradas. Elas dependem de
comunidades e metadados existentes. O perfil explícito `DB_PROFILE: "fresh"`
(`db.pcirn.profile=fresh` no backend) carrega as migrations DSpace básicas e a
inicialização dos grupos Anonymous, Administrator, Usuarios_Logados, NUGECID e
PCIRN_Depositantes, sem importar acervo, comunidades,
coleções ou usuários institucionais. O histórico próprio está em
`scripts/flyway-fresh-history.json`; o manifesto deve declarar
`database.fresh_bootstrap=pcirn-fresh-v1` e `database.fresh_migrations`.

O wizard verifica essa declaração e `database fresh-capability` na imagem antes de
iniciar. Imagens RC4 são recusadas para instalação nova. O perfil deve ser preservado
em backups, restaurações e atualizações. Uma base institucional não pode trocar para
`fresh`; o histórico padrão permanece integral. Não se fabricam registros Flyway
para representar SQL que não foi executado.

### PostgreSQL gerenciado e retomada

O banco publica apenas em `127.0.0.1`; o backend usa `postgres:5432` na rede privada.
TCP exige TLS e SCRAM. O usuário da aplicação não recebe superuser, createdb ou
createrole. TLS fica em `ROOT/postgres-tls`; chave privada e senha usam 600, com
ownership adequado à imagem. Certificado local verificado por CA, válido por dez
anos, precisa de manutenção antes de expirar.

O volume externo persistente nunca é apagado. Nome, token e raiz são registrados
em `postgres.json` e nos rótulos do volume. Antes de reutilizar um container, o
instalador confere projeto Compose, imagem e mounts do volume, TLS e senha.
Um diário `creating` só pode terminar o provisionamento se os recursos pertencem
à instalação e os arquivos privados estão completos. Se a criação da função já
concluiu, a conexão/ownership são conferidos sem redefinir senha. Se não concluiu,
só um banco sem objetos pode terminar essa operação, em transação. Recursos
estranhos, desaparecidos ou incompletos exigem revisão; nada é recriado para
contornar a dúvida. Isso inclui instalações RC4 parcialmente provisionadas.

`wizard.json` e configurações usam 600 numa raiz 700. A retomada conserva manifesto,
configuração e pacote. Não remova diários para forçar importação; nunca execute
`down -v`. Uma inicialização nova interrompida confere o histórico antes de continuar:
se migrations já terminaram, apenas retoma serviços; migrations pendentes requerem
nova autorização. Restauração interrompida exige revisão de staging e backups.

Os serviços internos não configuram o DNS/proxy público. Prepare HTTPS usando o
[proxy existente](../nginx/pcirn.conf.example) e configure SMTP antes de abrir acesso.
O relatório de sucesso valida os serviços internos; não comprova publicação HTTPS.

### Automação

```bash
# Migração, contrato existente:
sudo dspacepcirn install --wizard --root /srv/dspacepcirn \
  --config /etc/dspacepcirn/config.json --manifest /backup/release.json \
  --data-package /backup/pacote
# Instalação vazia, somente com imagem/manifesto compatíveis:
sudo dspacepcirn install --wizard --installation-mode new \
  --root /srv/dspacepcirn --config /etc/dspacepcirn/config.json \
  --manifest /backup/release.json --authorize-migrations
```

A automação preserva os argumentos técnicos explícitos e não instala dependências
sem interação. Os clientes major diferentes são selecionados por caminho próprio,
sem mudar alternativas globais. Para Docker, configure `PG_MODE`, `PG_IMAGE`,
`PG_MAJOR` e uma URL local com `sslmode=verify-ca` e CA gerenciada. Para banco externo,
`PG_MODE: "external"` é opcional.

### Atualizar somente o gerenciador

`sudo dspacepcirn update-manager` obtém o pacote oficial e verifica o digest do asset.
Também é possível usar `--manager-package ARQUIVO --manager-sha256 HEX` após conferir
um pacote local. A atualização confere os arquivos permitidos, recusa links/caminhos
externos e mantém a biblioteca anterior. Não executa scripts baixados, não atualiza
imagens DSpace nem acessa banco, documentos ou volumes. Pacotes são gerados por
`python3 scripts/package-manager.py`; a pipeline anexa pacote e checksum à release.
A RC4 não oferece esse asset e a atualização remota é recusada com mensagem clara.

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

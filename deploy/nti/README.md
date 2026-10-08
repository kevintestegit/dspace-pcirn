# Instalação e administração pelo NTI

`install.sh` instala uma stack dedicada; `dspacepcirn` administra essa instalação.
O instalador não instala pacotes do sistema. Pré-requisitos: Linux, Bash, Python
3.9+, Docker Engine, Compose >= 2.20 e `psql`, `pg_dump`, `pg_restore` (cliente
PostgreSQL da mesma versão major do servidor ou mais novo). Execute como usuário
administrativo com acesso ao Docker e leitura/escrita dos dados do Solr, incluindo
arquivos pertencentes ao UID do container; normalmente root no servidor dedicado.
O NTI fornece banco **dedicado**, credenciais, certificados TLS e os privilégios
necessários para Flyway e restore. Não há serviço PostgreSQL nesta stack.

## Configuração inicial

Crie `/etc/dspacepcirn/nti.json`, com permissão 600 (diretório 700):

```json
{
  "DB_URL": "jdbc:postgresql://postgres.nti.example:5432/pcirn?sslmode=verify-full&sslrootcert=/etc/ssl/nti-ca.pem",
  "DB_USERNAME": "pcirn",
  "DB_PASSWORD": "FORNECIDO_PELO_NTI",
  "PUBLIC_UI_URL": "https://repositorio.example",
  "PUBLIC_REST_URL": "https://repositorio.example/server",
  "PUBLIC_REST_HOST": "repositorio.example"
}
```

Os seis campos são obrigatórios. Não há interpolação nem execução de shell.
`sslmode` explícito aceita require, verify-ca ou verify-full; os parâmetros JDBC
adicionais aceitos são sslrootcert, sslcert e sslkey. Certificados precisam existir
no host **e no backend** com os mesmos caminhos: o pipeline deve empacotar a CA
institucional ou o NTI deve configurar mounts no Compose antes do primeiro start.
Nunca empacote chaves privadas nas imagens. Use require apenas quando autorizado
pelo NTI; verify-full verifica também a identidade do servidor.

Faça login no GHCR previamente com Docker, quando as imagens forem privadas.
Obtenha e revise o manifesto publicado pelo pipeline; não execute curl | bash.

```bash
./install.sh --root /srv/dspacepcirn --config /etc/dspacepcirn/nti.json \
  --manifest /tmp/release.json --authorize-migrations
export PATH="/srv/dspacepcirn/bin:$PATH"
dspacepcirn status --root /srv/dspacepcirn
```

Os binários ficam em `ROOT/bin`, a configuração em `ROOT/config.json`, o Compose
em `ROOT/compose.yml`, a configuração complementar em `ROOT/dspace/config/local.cfg`
e os dados em `ROOT/data/{assetstore,solr}`. O projeto Compose deriva do hash do
caminho absoluto, isolando instalações em diretórios diferentes. As portas padrão
são 127.0.0.1:8501 e 127.0.0.1:4000; o NTI configura o proxy TLS conforme
[exemplo existente](../nginx/pcirn.conf.example). Em hosts com outra stack usando
essas portas, use outro host ou ajuste o Compose dedicado antes do start,
incluindo portas, subnet e trusted proxy range juntos para evitar sobreposição
de redes Docker (o padrão é 10.250.50.0/24).

Arquivos existentes nunca são sobrescritos por install. Configuração fornecida
que divergir da existente causa erro. A segunda instalação da mesma release apenas
verifica os pré-requisitos e a saúde, sem backup, migration ou restart. Para outra
release, use update. O diretório deve ser dedicado e não conter links nos caminhos
administrativos. Não aponte a CLI para o checkout, mounts ou banco da stack atual.

## Comandos

| Comando | Operação |
|---|---|
| `install --config ARQUIVO --manifest ARQUIVO` | Provisiona e inicia; autoriza migrations separadamente |
| `update --manifest ARQUIVO` | Consulta histórico, baixa digests, para stack, faz backup e atualiza |
| `status` | Estado de todos os containers e aviso de operação interrompida |
| `version` | Release registrada (status informa operações ainda pendentes) |
| `doctor` | Ferramentas, daemon, Compose, TLS PostgreSQL e validade da configuração |
| `health` | Exige três serviços running/healthy e conexão PostgreSQL |
| `logs [--follow]` | Últimas 200 linhas; saída pode conter dados pessoais da aplicação |
| `backup` | Para stack, cria backup validado, reinicia com healthcheck |
| `restore --backup DIRETÓRIO --authorize-restore` | Faz backup de segurança e restaura banco/dados/release |
| `rollback --authorize-restore` | Restaura backup anterior à última atualização/instalação, incluindo banco |

Todos aceitam `--root` (padrão `/srv/dspacepcirn`). Operações concorrentes são
bloqueadas. Erros retornam 1, argumentos inválidos 2 e interrupção 130.

```bash
dspacepcirn update --manifest /tmp/release-nova.json --authorize-migrations
dspacepcirn backup
dspacepcirn rollback --authorize-restore
```

`--authorize-migrations` vale apenas para a operação invocada. A CLI consulta
`public.schema_version` em transação READ ONLY, compara versões/scripts/checksums
com o manifesto e só executa `/dspace/bin/dspace database migrate` se há versões
faltando. Histórico divergente, falho, repetível ou banco não vazio sem histórico
exige avaliação do NTI; não há repair/force automáticos. Nenhuma migration acontece
no startup. A flag não substitui a aprovação administrativa do NTI.

## Backup e recuperação

Toda atualização efetiva e instalação inicial gera backup **antes** de migrations
ou start das novas imagens. A stack inteira fica parada para que banco, assetstore
e Solr sejam consistentes; outros escritores no banco dedicado devem estar
suspensos pelo NTI. O backup contém dump custom PostgreSQL, dois arquivos tar,
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
objetos restaurados pertencem ao usuário NTI configurado. Configuração existente,
credenciais e local.cfg são preservados; role grants/certificados continuam sob NTI.
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
Incluem falhas em pull, dump, migration, conexão, health e restore, corrupção de
backup, autorização, concorrência, proteção de credenciais e travessia de archives.
Referências técnicas: [Compose up --wait](https://docs.docker.com/reference/cli/docker/compose/up/),
[interpolação Compose](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/)
e [pg_restore](https://www.postgresql.org/docs/current/app-pgrestore.html).

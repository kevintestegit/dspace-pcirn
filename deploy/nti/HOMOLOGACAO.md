# Homologação do dspacepcirn numa VM Ubuntu limpa

Este roteiro prepara a execução; nenhuma imagem ou banco real foi usado nos testes
locais. O executor real tem opt-in e só aceita dois bancos com nomes definidos.
Não execute no host de produção nem aponte configurações para bancos existentes.
O contrato do manifesto em README.md permanece inalterado.

## Responsabilidades e entradas

NTI: VM Ubuntu limpa, Docker local, PostgreSQL externo de homologação com TLS,
usuário proprietário dos bancos e do schema public, certificado e acesso ao GHCR.
DeepSeek: duas releases A/B com versões e pelo menos um digest diferentes, os
manifestos v1 já contratados, imagens para a arquitetura da VM e configuração dos
certificados no backend. A compatibilidade Flyway deve ser real, inclusive checksum.

Fornecer um dump PostgreSQL custom **fictício** compatível com A. Gere-o de uma
instância A nova e sem contas/documentos de pessoas reais; não use dump de produção,
mesmo anonimizado. O dump deve conter o schema DSpace e o histórico Flyway completo,
gerado com pg_dump do mesmo major PostgreSQL do servidor,
sem tabela pcirn_homolog_probe e sem bitstreams ou dependências de outros schemas.
O executor adiciona um registro e um arquivo fictícios pequenos de fixtures/.
Não há dump binário nem credenciais versionados neste repositório.

O NTI cria dois bancos dedicados inicialmente vazios, com schema public:
`pcirn_homolog_restored` e `pcirn_homolog_empty`. Ambos não podem conter objetos de usuário (incluindo funções, sequências, tipos,
extensões em public ou outros schemas). Apenas objetos de sistema são aceitos.
Ambos precisam ser de propriedade
do usuário usado na respectiva configuração; ownership/ACLs de produção não são
transportados. Não se cria, remove ou altera bancos automaticamente pelo roteiro.
O ensaio importa o dump em restored antes de testar install. Em empty, testa a
recusa sem autorização e, se autorizada separadamente, a inicialização Flyway.

## Preparar a VM

1. Use Ubuntu suportado pelo Docker, arquitetura amd64 ou arm64, Docker Engine
   local e Compose >= 2.20. A CLI usa explicitamente o contexto default e o
   preflight exige socket Unix local, impedindo contextos SSH/TCP remotos. Instale Python >= 3.9 e os clientes psql/pg_dump/pg_restore
   com o mesmo major do PostgreSQL externo. Siga as instruções oficiais
   de [Docker para Ubuntu](https://docs.docker.com/engine/install/ubuntu/) e
   [clientes PostgreSQL](https://www.postgresql.org/download/linux/ubuntu/).
   Instalar apenas pacotes; não construir imagens nesta preparação.
2. Reserve, de preferência, 4 vCPU e 16 GiB RAM para o ciclo. O preflight exige
   pelo menos 2 vCPU, 8 GiB reconhecidos pelo daemon e 4 GiB MemAvailable. Esses
   valores são critérios iniciais de homologação, não resultado de benchmark.
3. Exija livre, tanto no filesystem da instalação quanto no DockerRootDir:
   **30 GiB + 3 × (tamanho do banco + arquivos de data)**. Dumps, extração SQL,
   backups de segurança e dados anteriores acumulam; verifique espaço novamente
   durante o ciclo. Nenhuma retenção automática remove evidências.
4. Use uma VM sem serviços nas portas 127.0.0.1:8501 e 4000, sem rede Docker que
   sobreponha 10.250.50.0/24. Não crie redes/containers locais de PostgreSQL.
   GHCR precisa estar acessível com autenticação, se privado; o PostgreSQL externo
   precisa resolver DNS, conectar e negociar TLS. O proxy público HTTPS fica sob NTI.
5. Faça checkout **feat/nti-installer**, registre o commit e faça login Docker no
   GHCR, quando necessário. Copie os artefatos confiáveis para /opt/pcirn-homolog/:
   release-a.json, release-b.json e fictional-a.dump. Não execute docker build.
6. Prepare /etc/dspacepcirn/homolog-restored.json e homolog-empty.json com o mesmo
   formato de configuração do README (seis campos, chmod 600, diretório 700).
   DB_URL identifica os bancos acima e exige sslmode. Certificados indicados pelo
   JDBC precisam existir também no container backend com o mesmo caminho.
7. Tire snapshot da VM e registre que os dois bancos estão vazios. Snapshot de VM
   não inclui PostgreSQL externo: a recuperação do estado inicial desses bancos
   precisa ser combinada separadamente com NTI. Execute como usuário com acesso
   Docker e leitura/escrita dos arquivos do Solr; normalmente root na VM descartável.

## Preflight independente e automático

```bash
python3 deploy/nti/preflight.py \
  --root /srv/dspacepcirn-homolog/restored \
  --config /etc/dspacepcirn/homolog-restored.json \
  --manifest /opt/pcirn-homolog/release-a.json
```

Saída esperada: `preflight: OK`, código 0. Repita para B e para a configuração de
empty. Nenhum pull, migration, container ou diretório de instalação é criado pelo
preflight. As chamadas externas têm prazo de 30 segundos; falha bloqueia instalação.
`install.sh` executa esse preflight antes de provisionar. A chamada direta da CLI
`install` permanece disponível para operação administrada: execute o preflight
separadamente antes dela. O executor de homologação faz essa verificação antes de
qualquer escrita e novamente depois de importar a fixture.

A inspeção de arquitetura usa [docker manifest inspect --verbose](https://docs.docker.com/reference/cli/docker/manifest/inspect/),
sem baixar layers. A conexão PostgreSQL e as permissões são consultadas em transação
READ ONLY usando [pg_stat_ssl](https://www.postgresql.org/docs/current/monitoring-stats.htm)
e [funções de privilégios](https://www.postgresql.org/docs/current/functions-info.html).
Não se prova permissão de DDL criando objetos durante o preflight; o ciclo real
valida migrations/restore. Privilegios para extensões específicas continuam sob NTI.
O subnet/portas verificados são os padrões da stack para esta VM limpa.

## Executar o ciclo real — somente na VM descartável

Este comando **não foi executado localmente**. Ele pode baixar as imagens prontas
e iniciar a stack; não executa builds. O diretório base precisa não existir e ter
nome dspacepcirn-homolog. Configurações para qualquer outro nome de banco são recusadas.

```bash
python3 deploy/nti/tests/e2e_homolog.py \
  --execute-on-disposable-vm \
  --root /srv/dspacepcirn-homolog \
  --restored-config /etc/dspacepcirn/homolog-restored.json \
  --empty-config /etc/dspacepcirn/homolog-empty.json \
  --manifest-a /opt/pcirn-homolog/release-a.json \
  --manifest-b /opt/pcirn-homolog/release-b.json \
  --fixture-dump /opt/pcirn-homolog/fictional-a.dump \
  --authorize-migrations \
  --authorize-empty-migrations
```

`--execute-on-disposable-vm` autoriza o ensaio somente nos alvos delimitados;
`--authorize-migrations` autoriza migrations necessárias de B. Sem ela, a tentativa
de atualização com schema diferente é negada e o ensaio para. A autorização de
restore/rollback faz parte do ciclo solicitado e é explícita em cada chamada CLI.
`--authorize-empty-migrations` autoriza separadamente inicializar empty; omitir
essa flag testa apenas sua recusa e registra authorized_empty=not_run. Para
aprovação dos dois cenários completos, exigir authorized_empty=passed.

O executor começa com a tentativa negada de empty, importa a fixture em restored,
instala A sem migrations desnecessárias, repete install, cria backup, altera registro
fictício/arquivo e cria objeto posterior, testa restore negado e autorizado, atualiza
para B, altera dados, testa rollback negado e autorizado e verifica A novamente.
Antes da inicialização autorizada de empty, executa down **somente na stack restored
criada pelo ensaio**, liberando portas/subnet; mantém seus dados e bancos externos.
Não usa down -v, não remove backups e não manipula serviços anteriores da VM.

Evidências em /srv/dspacepcirn-homolog/homolog-report.json (privado): SHA-256 da
fixture, versões, retorno dos comandos e resultado de cada assert. Não inclui
senhas nem saída bruta de ferramentas. Em falha, preserva o estado para inspeção;
não faz cleanup destrutivo. Repita um ciclo completo numa VM limpa e bancos
reinicializados pelo NTI, não removendo apenas o diretório para contornar os guards.

## Critérios objetivos de aprovação

| Etapa | Aprovar somente se |
|---|---|
| Preflight | Código 0 para ambos os bancos e releases; todos os recursos/acessos acima atendidos |
| Empty sem autorização | Código 1 com mensagem de autorização; zero objetos de usuário antes/depois, sem containers/backups/installed.json/operação mutável |
| Instalação restored | A instalada, registro fictício e hash do arquivo preservados, histórico corresponde ao manifesto A |
| Idempotência | Novo install retorna 0 e config.json conserva SHA-256 |
| Backup | Exatamente um backup novo completo; pg_restore --list, tar e todos os hashes validados |
| Restore negado | Código 1; registro posterior continua intacto |
| Restore autorizado | Registro/bytes originais voltam; objeto criado depois do backup deixa de existir |
| Update | Backup anterior contém A; version informa B; três containers usam exatamente os digests B |
| Rollback | Negado sem flag; autorizado volta para A e seus dados; configuração conserva hash |
| Empty autorizado | Histórico Flyway completo de A, versão A e três containers healthy usando seus digests |
| Saúde | Cada start termina em até 600s e health retorna 0; backend, Solr e frontend running/healthy |
| Evidências | report.passed=true, authorized_empty=passed, nenhum assert false; NTI registra VM/commit/data e aprova |

Healthchecks internos provam o funcionamento da stack. Complemente manualmente com
HTTPS público da UI e /server/api, login de usuário fictício e upload/download de
um documento fictício; esses critérios de proxy e produto não são medidos pelo
executor administrativo. Falha TLS, erro HTTP >=400, bitstream diferente ou versão
incorreta reprovam a homologação. Registre logs protegidos e horários para auditoria.

## Falhas e recuperação

As falhas abaixo já são simuladas pelos testes leves. Injetá-las numa VM real deve
ser combinado com NTI e restrito aos dois bancos e stacks do ensaio; nunca faça
indisponibilidade de PostgreSQL compartilhado, rede de produção ou disco do host.

| Falha | Resultado exigido e recuperação |
|---|---|
| Docker/GHCR/arquitetura/recursos/permissões | Preflight !=0, sem instalação; corrigir pré-requisito e repetir |
| Banco vazio sem autorização | Sem migrations; restaurar fixture ou obter autorização explícita de inicialização |
| Histórico/checksum divergente | Sem migrations; obter artefatos compatíveis, não usar repair/force |
| Pull falha | Release e stack anteriores permanecem; corrigir GHCR e repetir update |
| Dump/validação falha | Update aborta antes da migration e tenta reiniciar release anterior; não usar .incomplete-* |
| Health falha sem migration | Tenta imagens anteriores; se recuperação falhar, journal persiste e exige inspeção |
| Migration iniciada falha | Aplicação parada; journal/backup preservados; restaurar backup com --authorize-restore |
| Backup corrompido | Restore negado antes da parada; selecionar cópia íntegra/confiável |
| Restore falha/interrompe entre renomes | Aplicação parada; repetir restore com mesmo backup e flag; safety backup é reutilizado |
| Backup avulso não reinicia | Journal persiste; corrigir causa e executar rollback para reiniciar release anterior |
| Bootstrap de empty falha | Não aprovar; registrar logs/journal. Recriar o banco vazio com NTI e restaurar snapshot de VM antes de repetir |

Exemplo de recuperação restrita à stack restored do ensaio:

```bash
/srv/dspacepcirn-homolog/restored/bin/dspacepcirn status \
  --root /srv/dspacepcirn-homolog/restored
/srv/dspacepcirn-homolog/restored/bin/dspacepcirn restore \
  --root /srv/dspacepcirn-homolog/restored \
  --backup /srv/dspacepcirn-homolog/restored/backups/BACKUP_VALIDADO \
  --authorize-restore
```

Não apague operation.json para liberar update. Preserve .restore-* e backups de
segurança; restauração substitui alterações posteriores ao backup escolhido.
A recuperação só está aprovada quando dados/hash/versão e health voltam aos valores
esperados e o journal deixa de existir. Para terminar o ensaio, NTI arquiva as
evidências e descarta a VM/bancos dedicados sob seu procedimento; o executor não faz isso.

## Testes leves disponíveis agora

```bash
python3 -m unittest discover -s deploy/nti/tests -v
bash -n install.sh deploy/nti/dspacepcirn
```

Todos usam mocks ou executáveis fictícios em diretórios temporários. O ciclo E2E
simulado roda o mesmo executor da VM e verifica os dados fictícios após restore e
rollback; não apenas códigos de saída. A simulação não comprova execução real de
Flyway, pg_restore, arquitetura das imagens, certificados dentro do backend ou
consumo de memória. Esses pontos exigem imagens A/B e a VM futura.

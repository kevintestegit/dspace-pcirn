# Revisão da integração do instalador interativo

Revisão local de `feat/interactive-installer` (`8d8be29b8e`) sobre `main`
(`2d830ea711`), em 2026-10-09. A integração inclui os commits anteriores
de migração inicial de dados e suas correções, pois são ancestrais da feature.

O worktree principal permanece em `feat/nti-initial-data-migration`, com todas
as alterações locais intactas. Foram comparados o diff binário, o status e o
conteúdo dos arquivos não rastreados antes e depois da revisão. Uma cópia
privada adicional foi guardada em `/tmp/dspace-integration-preserve-34lcky00`.
Nenhum reset, clean, push ou publicação foi executado.

## Bloqueadores corrigidos

- O link global recomendado não encontrava `pcirn.py` e dependia do checkout.
  `deploy/nti/install-manager.sh` agora instala o comando e todos os módulos e
  templates em `/usr/local`, recusando sobrescrever um gerenciador existente.
- Backup e restore agora revalidam o major de `psql`, `pg_dump` e `pg_restore`
  antes de parar serviços ou restaurar dados. Um cliente incompatível também
  não deixa um diário de operação pendente no comando de backup.
- O executável fictício dos testes agora extrai o banco corretamente de URLs
  JDBC com caminhos de certificados, permitindo verificar o modo Docker.

## Banco e persistência

O provisionamento Docker aceita imagens oficiais por digest de PostgreSQL
15–17, exige clientes do mesmo major, TLS e SCRAM, e publica a porta somente
em `127.0.0.1`. O backend usa `postgres:5432`; os clientes administrativos usam
o endereço e a porta publicados no host. O volume externo persistente tem
nome próprio e rótulos de propriedade; recursos preexistentes e inicialização
interrompida são recusados. Backup/restore param somente os três serviços da
aplicação, preservando PostgreSQL. Não há exclusão de volume nesse fluxo.

## Verificação

- Suíte Python: `python3 -m unittest discover -s deploy/nti/tests -p 'test_*.py' -q`.
  149 testes descobertos; 148 executados e um teste opt-in executado separadamente.
- PostgreSQL 15 real: `PCIRN_RUN_POSTGRES15=1 python3 -m unittest discover
  -s deploy/nti/tests -p 'test_data_migration_postgres15.py' -v`.
  Round trip e recusa de destino ocupado aprovados em container descartável,
  sem portas publicadas, usando tmpfs e dados fictícios.
- Testes novos cobrem backup/restore em ambos os modos, bloqueio de clientes
  incompatíveis, volume e JDBC renderizados pelo Compose real, e instalação
  independente do checkout.
- Java 17/Maven 3.9.9: compilação e 22 testes de `ContextTest` e
  `ContextInitializationTest` aprovados. O reactor reduzido gerou inicialmente
  um ambiente incompleto; os testes passaram após extrair o `testEnvironment.zip`
  completo do cache isolado e executar `surefire:test` com
  `-DskipUnitTests=false -Dtest=ContextTest,ContextInitializationTest
  -DsurefireJacoco= -Dagnostic.build.dir=/workspace/dspace-api/target`.
- `mvn -o -Dmaven.repo.local=/cache -Droot.basedir=/workspace -pl dspace-api
  -am checkstyle:check`: aprovado, sem violações.
- Sintaxe Bash e `git diff --check`: aprovados.
- Ubuntu 24.04 limpo em container descartável: instalação dos pré-requisitos
  Python, sudo, OpenSSL e clientes PostgreSQL 16; instalação global; origem
  renomeada; `sudo dspacepcirn --help` e menu em terminal aprovados como usuário
  comum, a partir de `/`. Docker Engine/Compose nessa imagem não foram
  homologados; o roteiro do README aponta para a instalação oficial.

## Parecer e limites

A integração está aprovada para a main local pelos testes direcionados.
Nenhum container ou dado institucional foi alterado. Apenas containers
descartáveis de testes foram criados e removidos.

Ainda é necessária a homologação completa em VM Ubuntu com as três imagens
reais, proxy HTTPS e SMTP. O provisionamento Docker foi revisado e testado com
processos simulados e renderização real do Compose; o round trip real em
PostgreSQL não substitui essa homologação. A suíte Maven completa não foi executada.

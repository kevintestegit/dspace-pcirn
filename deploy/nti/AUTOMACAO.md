# Relatório da automatização do DSPACEPCIRN

Base: `main`, `4fa3a52942cd622218738b1b5ca2d79043d0e7e0`.
Branch de entrega: `feat/automated-installer`, worktree `.worktrees/automated-installer`.

## Implementação

- Preparação automática Ubuntu 24.04 AMD64/ARM64; dependências oficiais, chaves APT
  conferidas, confirmação única, diagnóstico de CPU/RAM/disco/rede e preservação do
  Docker existente. Clientes PostgreSQL usam major correspondente ao servidor.
- Descoberta da release estável mais recente, ou RC identificada como teste;
  manifesto limitado/verificado por digest e commit da tag; imagens oficiais e
  arquitetura conferidas. Seleção manual e login GHCR no menu avançado.
- PostgreSQL 16 gerenciado por padrão, imagem oficial fixada por digest, porta/rede
  automáticas, TLS/SCRAM, credenciais aleatórias privadas e volume persistente.
  Banco externo exige TLS, conectividade e privilégios apropriados.
- Instalação nova separada de migração. Perfil `fresh` mantém histórico próprio
  medido, sem executar as nove migrations institucionais incompatíveis. Os arquivos
  históricos permanecem idênticos à main. Banco vazio inicializa sem acervo.
- Migração mantém comandos existentes, checksums e fingerprints de todos os registros,
  documentos e estatísticas Solr. O perfil de origem é validado antes de restaurar.
- Retomada comprova propriedade do volume/container/mounts; não redefine credenciais
  existentes. Instalação fresh retoma serviços sem repetir migrations concluídas e
  só aceita portas ocupadas pelos containers próprios com imagens fixadas.
- Menu solicitado, relatórios privados, configuração técnica avançada e atualização
  independente do gerenciador. Ativação usa troca atômica de diretórios com fsync;
  a biblioteca anterior permanece acessível mesmo após interrupção.

## Evidências de validação

- Suíte Python completa do instalador: `python3 -m unittest discover -s deploy/nti/tests -p 'test_*.py'`.
  Aprovado: 213 testes, um opt-in pulado; o teste PostgreSQL 15 tem execução real
  separada abaixo. Reexecução: 80,589 segundos,
  `/tmp/automated-installer-delivery-tests.log`. Após fechar o stream de logs,
  os 16 testes focados também passaram: `/tmp/pcirn-stream-final-tests.log`.
- Maven Java 17: `mvn -B -ntp -pl dspace-api -am package -DskipUnitTests=false -Dtest=PcirnFreshProfileTest -Dsurefire.failIfNoSpecifiedTests=false -Dxml.skip -Denforcer.skip`.
  Aprovado: seis testes JDBC, compilação, empacotamento, Checkstyle e licenças.
- Bootstrap final com JAR Maven em PostgreSQL 15 e 16: aprovado, 79 migrations
  idênticas, zero comunidades/coleções/usuários, metadados e grupos internos presentes,
  repetição sem mudança de histórico, validação Flyway e rejeição de troca de perfil.
  Base contendo documento fictício é recusada e o documento permanece intacto.
  A prova usa backend local com o JAR compilado desta alteração, não a imagem RC4
  publicada no GHCR.
- Ubuntu 24.04 descartável: pacotes oficiais AMD64 resolvidos; disponibilidade de
  pacotes ARM64 conferida nos índices oficiais. Fingerprints Docker e PGDG conferidos.
- PostgreSQL 16 real em runner Ubuntu: modos Docker e externo, TLS, clientes, ownership,
  retomada de interrupção e preservação de documentos e hashes de senhas/certificados
  aprovados. Log local: `/tmp/pcirn-host-final.log`.
  Prova adicional aprovada de bootstrap PostgreSQL 16 com usuário `dspace`
  NOSUPERUSER, TLS gerenciado e discovery padrão, incluindo capability, migrations,
  checksums e ownership dos objetos. Log: `/tmp/pcirn-host-bootstrap-default.log`.
- PostgreSQL 15 real: export-data/migrate-data/verify-data, UUIDs, handles, políticas,
  histórico, bitstreams, bytes Solr, destino ocupado e corrupção: aprovado, um teste.
- Consulta real GitHub: RC4, commit da base acima e SHA-256 do manifesto verificados.
- Testes de atualização do gerenciador incluem checksum, archive inseguro, ownership
  e interrupção após troca atômica. Revisão independente das correções sem achados
  importantes pendentes. Sintaxe Bash e `git diff --check` aprovados.
- Comando completo solicitado: `mvn -B -ntp install -DskipUnitTests=false -DskipIntegrationTests=false`.
  Execução em container exclusivo, sem socket Docker nem rede host;
  Serviços: 81 testes aprovados. API: 1417 unitários (9 pulados) e 480 de integração
  (3 pulados); integração bloqueada por S3BitStoreServiceIT sem Docker para
  Testcontainers, com erro no setup e teardown. Log: `/tmp/pcirn-full-validation.log`.
  A continuação `mvn -B -ntp install -rf :modules -DskipUnitTests=false -DskipIntegrationTests=false`
  aprovou os módulos anteriores ao REST e 167 unitários REST (2 pulados).
  Foi interrompida após registrar 1025 testes de integração REST, 43 falhas e
  24 pulados, preservando os arquivos; a suíte completa não está aprovada.
  Log: `/tmp/pcirn-downstream-validation-live.log`.
  Comparação com main exata, API baseline compilada e configurações sem alterações:
  196 testes em 13 classes, 43 falhas, 5 pulados. Os métodos, tipos e mensagens de
  todas as 43 falhas são idênticos nos relatórios XML das duas árvores.
  Logs: `/tmp/pcirn-baseline-rest-configured.log` e
  `/tmp/pcirn-baseline-rest-additional.log`.

## Bloqueadores e limites restantes

1. A RC4 publicada não contém o perfil fresh nem o pacote do novo gerenciador.
   Instalação nova é explicitamente indisponível nessa release; migração continua
   disponível. Uma próxima release precisa incluir este backend, manifesto fresh
   e pacote verificável do gerenciador. Nenhuma publicação foi realizada aqui.
2. Uma VM Ubuntu 24.04 descartável com systemd ainda é necessária para provar o
   comando principal desde um host vazio, incluindo apt e inicialização do Docker.
   O runner Ubuntu prova pacotes e banco reais, mas não simula systemd ou inicializa
   a stack completa com imagens novas. Essa homologação não pode usar a VM Oracle
   parcialmente provisionada como ambiente descartável.
3. Execução nativa ARM64 e fluxo completo backend/Angular/Solr com as novas imagens
   permanecem pendentes. A disponibilidade dos pacotes e a resolução de arquitetura
   foram testadas; não se declara homologação completa ARM64.
4. DNS, certificado HTTPS/proxy público e SMTP dependem da infraestrutura escolhida.
   O wizard solicita o endereço público e valida serviços internos; a publicação
   HTTPS requer o proxy documentado. Banco externo com CA privada exige configuração
   avançada do certificado.
5. O teste S3 exige um Docker exclusivo acessível ao Testcontainers. O socket do
   Docker institucional não foi fornecido; esse teste permanece bloqueado no runner
   isolado. As falhas REST comparadas com main são preexistentes; não houve alteração
   de autorização REST para contornar os testes. A suíte completa exige um ambiente
   adequado e resolução das falhas de baseline antes de aprovação global.

## Preservação

Na implementação inicial não houve acesso/modificação à VM Oracle ou a containers, bancos e volumes
institucionais. Não houve merge na main, push nem release. Recursos descartáveis
criados para prova têm nomes/rótulos exclusivos, foram parados e preservados;
nenhum volume foi apagado. O checkout inicial com alterações locais ficou intacto.
O estado RC4 `creating` pode retomar apenas se propriedade, TLS e credenciais forem
comprovados; recursos incompletos/estranhos continuam exigindo revisão administrativa.

## Interface em inglês e importação HTTPS

O wizard agora pergunta `Import data? [y/N]` após preparar o banco. Ao aceitar,
consulta `data-package.json` na release oficial, verifica o digest do asset e baixa
o pacote de uma URL HTTPS pública usando tamanho e SHA-256 fixados. A origem fica
registrada no checkpoint para retomada. O manifesto do software permanece inalterado,
sem checksum circular; pacote e release continuam precisando corresponder exatamente.

`scripts/package-data.py` empacota uma exportação completa e produz o descritor.
URLs de visualização/login do Drive não são suportadas. Consulte [DATA-IMPORT.md](DATA-IMPORT.md).
Mensagens do gerenciador são em inglês; detalhes internos vão para `ROOT/installer.log`
com permissão 600. Comandos não interativos e pacotes locais continuam disponíveis.

Validação desta extensão: 228 testes, um opt-in pulado, em 70,490 segundos
(`/tmp/pcirn-english-data-delivery.log`); 15 testes focados após a revisão do
empacotador; prova separada PostgreSQL 15 aprovada em 12,806 segundos
(`/tmp/pcirn-remote-data-postgres-final.log`). A prova usa transporte HTTPS simulado,
mas dump/restauração PostgreSQL reais e confere documentos, UUIDs, handles, permissões,
histórico e bytes Solr. Sintaxe Bash, bundle do gerenciador e diff verificados.

Durante a etapa posterior de conexão SSH, o gerenciador da VPS foi atualizado com
a versão inicial desta branch, preservando a versão anterior e os arquivos do banco.
DSpace/migrations não foram iniciados. Esta extensão de importação e idioma não foi
aplicada à VPS; não há pacote real hospedado, novo asset ou RC publicada. Teste de
download com um servidor/Drive real depende da URL e de um pacote autorizado.

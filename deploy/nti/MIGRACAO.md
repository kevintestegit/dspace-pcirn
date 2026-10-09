# Migração inicial para o NTI

A migração usa exclusivamente banco de destino dedicado e vazio, provisionado pelo
DBA conforme [provision-database.sql](provision-database.sql). TLS, roles e GRANTs
PostgreSQL ficam sob responsabilidade do DBA; o pacote preserva as permissões
DSpace, UUIDs, handles, grupos, metadados e histórico Flyway sem renumeração.
Os clientes PostgreSQL devem ter o mesmo major do servidor. Configure os seis
campos de config.json conforme [README.md](README.md), com diretório 700 e arquivo
600. Certificados e chaves privadas ficam fora do pacote; a CLI monta os caminhos
TLS explicitamente configurados no backend somente leitura, exigindo arquivos
absolutos e legíveis (não diretórios) para que psql e o driver JDBC usem o mesmo
material.

## Exportar na origem

Reserve janela autorizada e suspenda jobs e todos os escritores externos. A CLI
para somente a stack identificada por ROOT e a mantém parada, inclusive em falha.
Nunca use os exemplos contra produção sem essa janela. O relatório percorre
consultas separadas, exigindo dados imutáveis durante todo o ciclo.

```bash
umask 077
dspacepcirn export-data --root /srv/dspacepcirn-origem \
  --output /transferencia/pcirn
```

O diretório de saída precisa não existir e ficar fora da instalação. A exportação
usa staging privado e publica o pacote completo por rename somente após dump,
validação e comparação da origem antes/depois. Falhas deixam .export-* para
inspeção e não publicam o destino final nem reiniciam a aplicação.

O pacote contém database.dump (pg_dump custom), assetstore.tar.gz, solr.tar.gz,
source-report.json, release.json e checksums.json. Solr é transportado integralmente,
incluindo statistics; não é substituído por um índice reconstruído. Os checksums
SHA-256 cobrem os cinco arquivos de conteúdo. O relatório guarda hashes e contagens
das tabelas públicas e dos arquivos da assetstore/Solr, sem dados pessoais em claro.
O pacote contém dados e deve ser transportado por canal institucional protegido.
SHA-256 detecta corrupção; não autentica remetentes. Restaure somente dumps confiáveis.

## Restaurar no destino

Suspenda todos os outros acessos ao banco dedicado. ROOT deve ser novo ou já
provisionado com assetstore e Solr vazios. Containers parados são permitidos;
containers running são recusados. Bancos com qualquer objeto de usuário são sempre
recusados, inclusive com --authorize-restore. Não há DROP SCHEMA, limpeza, repair ou
substituição de dados existentes pelo comando migrate-data.

```bash
./deploy/nti/dspacepcirn migrate-data --root /srv/dspacepcirn-destino \
  --config /etc/dspacepcirn/nti.json \
  --manifest /transferencia/pcirn/release.json \
  --data-package /transferencia/pcirn

/srv/dspacepcirn-destino/bin/dspacepcirn verify-data \
  --root /srv/dspacepcirn-destino \
  --expected /transferencia/pcirn/source-report.json
```

A restauração usa pg_restore --single-transaction --exit-on-error, sem owner/ACLs
PostgreSQL da origem. Archives rejeitam caminhos externos, duplicados, links e
arquivos especiais. Dados são extraídos em staging; estatísticas são conferidas
antes do restore. A CLI reconfirma banco vazio e ausência de outras conexões
imediatamente antes da escrita. A importação não inicia containers nem executa
Flyway. Todos os registros e arquivos são comparados com o relatório de origem
antes de publicar data-import.json e mover os diretórios para data/.

Cada bitstream ativo deve corresponder a arquivo local store_number=0, tamanho e
checksum MD5, SHA-1 ou SHA-256. São aceitos o layout 12/34/56/internal_id e caminhos
registrados -R relativos à assetstore. Arquivos órfãos também são transportados e
verificados; arquivos de bitstreams deleted podem estar ausentes.

Depois de verificar a entrega, instale a release compatível:

```bash
./install.sh --root /srv/dspacepcirn-destino \
  --config /etc/dspacepcirn/nti.json --manifest /transferencia/pcirn/release.json
```

Também é possível passar --data-package ao install.sh; a importação ocorre antes
de qualquer start ou migration. Se a release destino tiver migrations novas,
--authorize-migrations autoriza sua execução somente após verificar a importação.

## Falhas e recuperação

Uma falha preserva operation.json e o staging, mantém a aplicação parada e bloqueia
install/update/export-data/migrate-data. O restore PostgreSQL é transacional, mas
banco e filesystem não formam uma única transação: uma falha posterior ao restore
pode deixar o banco preenchido. Preserve as evidências; o DBA deve recriar o banco
vazio e repetir em ROOT novo. Não apague o journal para contornar os guards.
Não há recuperação destrutiva automática nem reimportação após sucesso.

## Testes

Testes leves com executáveis fictícios:

```bash
python3 -B -m unittest discover -s deploy/nti/tests -p test_data_migration.py -v
```

Ensaio real opt-in, requer Docker e OpenSSL, usa a imagem oficial postgres:15:

```bash
PCIRN_RUN_POSTGRES15=1 python3 -B -m unittest discover \
  -s deploy/nti/tests -p test_data_migration_postgres15.py -v
```

O ensaio cria um container com nome aleatório, rede none, sem portas publicadas e
PGDATA em tmpfs. Só um diretório temporário do teste é montado. Usa TLS e bancos
fictícios; executa pg_dump/pg_restore reais e a CLI instalada, mantendo o ciclo de
vida da aplicação simulado. Remove apenas o container criado pelo próprio teste.
Confere identidades, handles, políticas, histórico, sequências, arquivos, recusa de
banco ocupado e detecção de corrupção. Não comprova consultas de estatísticas em
Solr real ou execução do backend; esses pontos ficam para homologação do produto.

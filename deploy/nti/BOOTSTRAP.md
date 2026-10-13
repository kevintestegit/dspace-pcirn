# Inicialização sem dados institucionais

O perfil `db.pcirn.profile=fresh` cria o schema completo do DSpace e os grupos
genéricos PCIRN, sem importar comunidades, coleções, documentos ou usuários.
O perfil precisa permanecer configurado durante toda a vida dessa instalação.
O perfil padrão `institutional` continua carregando os scripts históricos originais.
Nenhum checksum histórico é alterado e nenhum registro de migration é fabricado.

As migrations institucionais existentes exigem setores e coleções anteriores à
instalação do software. Elas não são aplicáveis a um repositório novo. O Maven
empacota um segundo diretório com as migrations do DSpace, excluindo esses scripts,
e acrescenta uma migration exclusiva para os grupos genéricos. O Flyway mantém um
histórico verdadeiro e distinto para cada perfil. O backend recusa a troca para
`fresh` quando encontra histórico institucional ou conteúdo anterior ao perfil.
Trocar uma instalação fresh para o perfil institucional também falha na validação.

A interface consulta `dspace database fresh-capability`. Somente o backend novo
retorna `pcirn-fresh-v1`; uma release antiga, incluindo RC4, não oferece essa
capacidade. O manifesto precisa conter `database.fresh_bootstrap` e
`database.fresh_migrations`, com histórico medido em PostgreSQL vazio. O comando
`scripts/release-manifest.sh --fresh-migrations scripts/flyway-fresh-history.json`
publica esses campos no artefato gerado; sem esse argumento eles ficam ausentes.

## Prova em ambiente descartável

Depois de compilar o módulo `dspace-api`, execute em máquina com Docker:

```bash
python3 deploy/nti/tests/bootstrap_fresh.py \
  --api-jar dspace-api/target/dspace-api-9.4-SNAPSHOT.jar \
  --backend-image IMAGEM_BACKEND_COMPATIVEL \
  --postgres-image postgres:15 \
  --output /tmp/fresh-history.json
```

O teste cria nomes aleatórios para rede e contêineres, sem publicar portas,
sem usar volumes existentes e com dados PostgreSQL em tmpfs. Executa bootstrap,
retomada e validação Flyway; verifica registries, grupos internos, ausência de
conteúdo institucional e recusa de troca de perfil. Para PostgreSQL 16, repita
com uma imagem oficial de major 16 e compare o histórico. Os contêineres são
parados e retidos para inspeção; o script não apaga recursos Docker.

Os logs e o histórico de saída têm permissões 600. Credenciais aleatórias são
redigidas nos logs. A configuração do instalador continua exigindo autorização
explícita para executar migrations, independentemente desse perfil.

Para verificar também o provisionamento gerenciado, TLS e usuário sem superusuário,
use `deploy/nti/tests/e2e_host_postgres.py` num runner Ubuntu 24.04 descartável,
com clientes PostgreSQL 16, OpenSSL e Compose. O diretório novo `/tmp/pcirn-host-postgres-*`
deve ser montado no mesmo caminho do host; o runner precisa de rede host e acesso
a um Docker exclusivo para testes. Nunca use a VM de homologação para essa prova.

```bash
python3 deploy/nti/tests/e2e_host_postgres.py \
  /tmp/pcirn-host-postgres-teste-unico \
  --backend-image IMAGEM_BACKEND_COMPATIVEL \
  --api-jar dspace-api/target/dspace-api-9.4-SNAPSHOT.jar
```

Esse teste mantém discovery padrão, verifica checksums e ownership, exercita banco
externo e retomadas interrompidas, preservando dados sentinela e credenciais.
O PostgreSQL próprio é parado ao terminar; containers e volumes são mantidos.

# Operação e manutenção

Instalação, configuração e comandos: [README](README.md).
Evidências e pendências: [validação da entrega](VALIDACAO.md).

## Importação

Depois de escolher PostgreSQL Docker ou externo, o wizard pergunta
`Import data? [y/N]`. Não importa dados ao escolher No. Yes usa o asset oficial
`data-package.json` da release; se ele não existir, forneça um pacote local.
A RC6 não contém dados publicados. Não inicialize o schema antes de importar:
o destino deve estar completamente vazio, mesmo que não existam itens.

O pacote contém exatamente seis arquivos: `database.dump`, `assetstore.tar.gz`,
`solr.tar.gz`, `source-report.json`, `release.json` e `checksums.json`.
Dump sozinho não transporta documentos nem estatísticas. Manifesto e perfil
precisam corresponder exatamente à release de destino; nunca troque release.json
manualmente. UUIDs, handles, usuários, políticas e histórico são preservados.
Ownership e ACLs PostgreSQL não são transportados; o usuário configurado passa
a ser proprietário dos objetos. Banco externo exige provisionamento pelo DBA:
[provision-database.sql](provision-database.sql).

### Exportar e transferir

Reserve uma janela autorizada; suspenda jobs e outros escritores. Use somente a
raiz dedicada da origem. A exportação normal para sua stack e a mantém parada:

```bash
umask 077
sudo dspacepcirn export-data --root /srv/dspacepcirn-origem \
  --output /transferencia/export
```

A saída não pode existir e deve ficar fora da instalação. O pacote só é publicado
após dump validado e comparação da origem antes/depois. Falhas preservam staging
privado e não reiniciam a stack. Reinicie a origem de forma administrada e verifique
a saúde ao concluir a janela.

Para uma instalação Docker anterior ao gerenciador:

```bash
python3 scripts/export-docker-data.py \
  --manifest /private/release-manifest.json --output /private/new-export
```

Esse helper exige o endpoint Unix local do contexto Docker default, valida o
histórico institucional antes da pausa e usa clientes dentro do container do banco
por socket Unix. PostgreSQL permanece rodando. Backend, frontend e Solr são
reiniciados ao terminar, inclusive após falha; confirme a saúde. Não altera TLS,
credenciais ou schema da origem. Cópias de trabalho incompletas são preservadas.

Transfira os seis arquivos por um canal privado autorizado. Use diretórios 700 e
arquivos 600. Executando como root, os ancestrais e arquivos precisam ser seguros e
pertencer a root: uma pasta sob a home de outro usuário será recusada. Faça staging
em uma raiz dedicada; não altere o ownership da home. Checksums detectam corrupção,
mas não autenticam o remetente: aceite somente dumps de origem confiável.

### Importar pacote local

`--data-package` recebe o diretório dos seis arquivos, não o tar externo:

```bash
sudo dspacepcirn install --wizard --root /srv/dspacepcirn \
  --config /etc/dspacepcirn/config.json --manifest /transferencia/export/release.json \
  --installation-mode migration --data-package /transferencia/export
sudo dspacepcirn verify-data --root /srv/dspacepcirn \
  --expected /transferencia/export/source-report.json
```

A importação verifica hashes, histórico, versão, perfil, ausência de outros acessos
e banco vazio antes da escrita. Usa pg_restore transacional sem owner/ACLs da origem;
archives recusam links, dispositivos, duplicados e caminhos externos. Confere todas
as tabelas e arquivos antes de marcar sucesso. Bitstreams ativos exigem arquivos
locais store_number=0, tamanho e MD5/SHA-1/SHA-256 corretos; órfãos são preservados.
Solr é transportado completo, inclusive statistics. Não há limpeza ou repair.

Banco e filesystem não formam uma transação única. Se uma falha ocorrer após o
restore, preserve operation.json, staging e backups para recuperação administrada.
Não remova checkpoints nem recrie o banco automaticamente para repetir a operação.

### Hospedagem opcional

O mantenedor pode preparar download automático uma vez por release:

```bash
python3 scripts/package-data.py --package /transferencia/export \
  --url https://downloads.example.org/rc6-data.tar.gz \
  --output /transferencia/rc6-data.tar.gz
```

Publique o arquivo em HTTPS e anexe seu JSON gerado à release oficial compatível
como `data-package.json`. O descritor tem URL, SHA-256 e tamanho; o instalador
verifica o digest oficial do descritor e os bytes do download. Não sobrescreve
saídas. Use uma nova release ao trocar o dataset, pois retomadas fixam o descritor.
URLs de preview/login/confirmação do Drive não funcionam; exige download direto.
HTTP, redirects privados, páginas HTML, corrupção e espaço insuficiente são recusados.
Para dados reais, hospedagem/publicação exige autorização separada. Prefira dados
fictícios públicos ou transporte privado para o acervo institucional.

## Banco vazio

O perfil `DB_PROFILE=fresh` corresponde a `db.pcirn.profile=fresh`. Mantém as
migrations DSpace e grupos genéricos sem importar usuários, comunidades ou itens.
Os nove scripts institucionais dependentes de conteúdo anterior são excluídos do
perfil fresh; seus originais não são alterados. O histórico é real e distinto.
Não é permitido trocar perfis em uma instalação existente. Preserve-o em atualizações,
backups e importações. Um repositório vazio ainda precisa de administrador DSpace.

O backend deve responder `database fresh-capability` com `pcirn-fresh-v1` e o
manifesto declarar fresh_bootstrap/fresh_migrations. A RC4 não oferece essa capacidade.
Migrations exigem autorização explícita; startup não as executa.

## Validação

### Rotina leve

```bash
python3 -B scripts/check-installer.py
```

Executa uma seleção sequencial de testes de limites de confiança, dependências,
releases, importação, modos PostgreSQL, bootstrap e higiene Git. Não inicia serviços.
GitHub usa essa seleção em alterações do instalador. Maven unitário roda em PRs que
alteram código/configuração Java e por execução manual. A integração Maven é manual;
os dois jobs são sequenciais. Não execute build/teste na VM de operação.

### Antes de publicar — runner separado

```bash
python3 -B scripts/check-installer.py --full
# Opt-in explícito: cria somente PostgreSQL descartável com dados fictícios.
PCIRN_RUN_POSTGRES15=1 python3 -B scripts/check-installer.py --full
```

Publicação continua exigindo todos os testes do instalador, round trip PostgreSQL
real, Maven unitário e bootstrap nativo AMD64/ARM64. Não se removem os testes de
preservação para tornar a CI verde. Para gerar/checkar histórico fresh:

```bash
python3 deploy/nti/tests/bootstrap_fresh.py \
  --api-jar dspace-api/target/dspace-api-9.4-SNAPSHOT.jar \
  --backend-image IMAGEM_BACKEND_COMPATIVEL --postgres-image postgres:16 \
  --output /tmp/fresh-history.json
```

Requer Docker exclusivo para testes. Cria nomes próprios, PGDATA em tmpfs e nenhuma
porta pública; verifica repetição, registries, grupos, histórico e recusa de dados.
Para TLS, usuário restrito, modo externo e retomada, use `tests/e2e_host_postgres.py
--help` em Ubuntu24.04 descartável. Containers/volumes são parados e retidos;
nunca use a instalação institucional ou a Oracle parcial como ambiente descartável.

### Aceitação pelo NTI

Em VM de homologação, registre commit, release, digests, arquitetura, relatórios e
configuração redigida. Exija:

1. Dependências automáticas e preflight aprovados em Ubuntu24.04 com systemd.
2. Instalação vazia com histórico correto ou importação completa com fingerprints.
3. Repetição/retomada conservando senhas, TLS, dados e histórico.
4. UI e REST via HTTPS público; login, busca e download íntegro de documento.
5. Backup validado, atualização para uma release B e retorno à A em dados fictícios.
6. Recusa sem autorização de migrations/restore e recusa de banco ocupado/corrompido.
7. Backend, frontend, Solr e conexão PostgreSQL saudáveis; logs privados legíveis.

O executor `tests/e2e_homolog.py --help` automatiza backup/update/restore/rollback
com dois bancos externos dedicados: pcirn_homolog_restored e pcirn_homolog_empty,
manifestos A/B e dump fictício. Exige --execute-on-disposable-vm e autorizações
explícitas. Não usa banco institucional. Seu relatório não comprova HTTPS, login
ou funcionamento no navegador; valide-os separadamente.

## Recuperação

Status/doctor/health identificam etapas pendentes. Falha de pull não para serviços;
falha de backup tenta reiniciar a release anterior. Falha de saúde sem migrations
tenta imagens anteriores; depois de migration iniciada, mantém a aplicação parada
para recuperação do banco. Consulte o journal e use restore/rollback autorizado
somente com backup validado. Restore cria backup de segurança e substitui logicamente
alterações posteriores; configuração/credenciais são preservadas.

Não apague operation.json, wizard.json, staging, backups ou volumes para liberar a
instalação. RC4 parcial mantém a release fixada: trocar para RC6 exige um plano de
transição verificado, não limpeza dos checkpoints. Recursos existentes só podem
ser reutilizados com prova de propriedade e integridade.

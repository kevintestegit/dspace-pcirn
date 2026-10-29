# Validação da revisão 2 — 2026-10-18

Preparação realizada localmente; sem acesso, deploy ou limpeza na VPS.
Base local: c9a119e19a, com alterações de trabalho incluídas no tarball.
O SHA-256 identifica os bytes entregues; os arquivos-fonte automáticos do GitHub
continuam associados à tag original e não representam esta revisão do instalador.

## Verificações executadas

- `python3 -m unittest discover -s deploy/nti/tests`: 127 testes esperados; a
  contagem pode variar com testes opcionais. Na última execução: OK, 1 skip
  (integração opcional PostgreSQL). Inclui ciclo E2E simulado, restauração,
  migrações autorizadas/negadas, perfil fresh, TLS, credenciais e empacotamento.
- `PCIRN_RUN_POSTGRES15=1 python3 -m unittest discover -s deploy/nti/tests -p test_data_migration_postgres15.py`:
  1 teste, OK, PostgreSQL 15 local descartável, dados somente sintéticos.
- Sintaxe Python (`compileall`), shell (`bash -n`), leitura YAML/JSON e
  `git diff --check`: aprovadas.
- Builds publicados A/rc4 e B/rc6: conclusão success e commits registrados em
  build-verification.json. Seis índices GHCR consultados por digest: SHA-256
  dos bytes brutos conferido, variantes linux/amd64 e linux/arm64 presentes.
- Tarball gerado duas vezes, inclusive a partir da árvore extraída: bytes iguais.
  Checksum `.sha256` conferido após a geração; ajuda da CLI e do executor E2E
  conferida no pacote extraído. Insumos limitados à lista pública do empacotador.

## Limitações e decisão

Não houve E2E real com DSpace, Flyway fresh, restauração institucional, UI ou
certificados dentro das imagens. O teste PostgreSQL isolado não substitui isso.
Não foi gerado dump: falta uma origem integralmente sintética com o histórico
institucional de A. Não foi fabricado digest, checksum Flyway ou dado institucional.
Leia README.md para os requisitos de fornecimento e revisão do dump.

Não houve novo build/push de imagens; usam-se builds anteriores comprovados.
O workflow foi atualizado nas fontes locais e incluído no pacote, mas sua ativação
no GitHub depende de integrar essas alterações ao repositório de origem e publicar
uma nova tag. Não se executou Maven/Checkstyle: nenhuma fonte Java foi alterada
nesta tarefa. Shellcheck não estava disponível; foi validada a sintaxe shell.

A homologação permanece pendente do dump compatível, VM descartável, PostgreSQL
externo com TLS, configurações privadas e acesso às imagens. Resultado parcial do
executor nunca é aprovação: retorna 2 e passed=false sem o ensaio de banco vazio.

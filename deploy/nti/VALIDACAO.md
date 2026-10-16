# Validação para entrega ao NTI

Data da revisão: 2026-10-14. Branch: `feat/automated-installer`.
Base main: `4fa3a52942cd622218738b1b5ca2d79043d0e7e0`.
**Parecer: candidato disponível para homologação; produção ainda não aprovada.**

## Artefato publicado

[RC6](https://github.com/kevintestegit/dspace-pcirn/releases/tag/v1.0.0-rc6),
tag imutável no commit `45bdcc9f8493569bd3d2f18f1821411aeadb06f9`.
[Publicação aprovada](https://github.com/kevintestegit/dspace-pcirn/actions/runs/38421955489):
237 testes do instalador com PostgreSQL real, Maven unitário, seis builds nativas
e bootstrap AMD64/ARM64. O pacote não contém dados institucionais.

| Asset | SHA-256 |
|---|---|
| release-manifest.json | `5a037d1a2233bafbf7b03b487a8cdfb483076671bea9e00bd6828b61e1761d36` |
| dspacepcirn-manager.tar.gz | `03da3082d110da6029f651645e43f5b32d3b8e97d4e5a528347cbc8e6087526c` |

O manifesto fixa os digests backend, Angular e Solr e registra o commit Angular
`857aa482e5d97b6f75cea5c00e3991a4bff1c7a9`. Discovery verificou os assets, o commit
da tag e as duas arquiteturas. A limpeza de documentação/CI posterior não modifica
os bytes da RC6 publicada. Os ajustes de higiene da árvore estão na branch de
entrega; não reescrevem a main nem a tag já publicada.

## Evidências funcionais existentes

| Verificação | Resultado e limite |
|---|---|
| Banco vazio PG15/16 | 79 migrations medidas, registries/grupos presentes, zero usuários/itens/comunidades; repetição e guards aprovados |
| Bootstrap nativo AMD64/ARM64 | Backend publicado aprovado nas duas arquiteturas; não substitui stack ARM64 completa |
| Docker/external PG16 | TLS, clientes da major correta, ownership, usuário restrito e retomada aprovados em runner descartável |
| Stack RC6 vazia | Ubuntu24.04 AMD64 em container; PostgreSQL16 TLS/NOSUPERUSER, backend/frontend/Solr healthy e HTTP200 |
| Retomada da stack vazia | Falha inicial de mount do runner corrigida; checkpoint retomado sem mudar senhas/TLS/histórico |
| Migração real RC6 | 65 tabelas e 2.256 itens; fingerprints do banco e assetstore iguais após startup; Solr completo validado antes do startup |
| Preservação | UUIDs, handles, quatro usuários, permissões e 87 registros Flyway preservados; origem reiniciada healthy |
| Falhas/recuperação | Testes simulados cobrem autorização, corrupção, arquivos inseguros, concorrência, backups, restore/rollback e recusa de destino ocupado |

Provas privadas locais em `/home/gecid007/dspacepcirn-release-proof-rc6/`:
`verified-release.json`, `full-stack-proof.json`, `data-stack-proof.json`.
Os ensaios não comprovam login/busca no navegador por uma URL pública.

O acervo exportado permanece privado em
`/home/gecid007/dspacepcirn-private-exports/source-rc6-20261013`.
Arquivo de transferência: `source-rc6-20261013.tar.gz`, 520.857.085 bytes,
SHA-256 `3b97490757c3c625429e71d62b919b7b343c9664749a0f8dee9e8e6a146e005d`.
Não foi hospedado nem publicado. A cópia RC4 anterior também foi preservada.

## Revisão de higiene e custo de manutenção

- `.superpowers` tinha sete protótipos/PID rastreados apesar do ignore; retirados
  somente do índice, preservando arquivos locais. `.github`, `.gitmodules`,
  `.dockerignore` e exemplos de configuração são arquivos necessários.
- A busca por tokens/chaves encontrou somente dois fixtures SAML públicos do
  upstream, idênticos à main, e o código que lê PEM. Esses fixtures continuam
  permitidos explicitamente; chaves privadas de operação são ignoradas.
- Ignore cobre caches, dependências, dumps e assets locais. Docker context também
  exclui worktrees, tooling e conteúdo derivado do banco. O ignore não apaga arquivos
  de commits antigos: a RC6/main anteriores continuam com sua árvore original.
- O código rastreado ocupa aproximadamente 37 MB; testes upstream e documentos
  de uso do DSpace não foram removidos por tamanho. Não participam do runtime.
- Documentação específica do instalador consolidada de oito para três arquivos:
  README, OPERACOES e este relatório. Históricos antigos ficam no Git.
- Rotina reduzida a 96 testes sequenciais, aprovada em 3,280 segundos sem iniciar
  serviços (`/tmp/pcirn-final-quick.log`). Publicação mantém o gate completo.
- Build Maven deixa de rodar em cada push: unitários em PRs relevantes/manual,
  integração somente manual explícita, max-parallel=1. Isso reduz execução;
  não corrige nem oculta as falhas conhecidas.

## Bloqueadores de aprovação final

1. **CI geral não está verde.**
   [Build revisada](https://github.com/kevintestegit/dspace-pcirn/actions/runs/38421955521)
   falhou em unitários por OutOfMemory (heap de testes 1 GB), com erros subsequentes
   de beans Matomo/SHERPA. Integração API: 494 testes, uma falha e quatro erros
   (S3Mock bucket 404/create 405 e ConcurrentModification no teardown).
   Logs locais: `/tmp/pcirn-final-unit-github.log` e
   `/tmp/pcirn-final-integration-github.log`. O gate de publicação unitário passou
   em outra execução; isso não torna a build geral aprovada. Não houve supressão.
   Não se reproduziu esta falha de memória nesta revisão nem se alterou runtime
   para contorná-la. Execução Maven local não ocorreu: host sem Java/Maven.
   Antes, 43 falhas REST também foram reproduzidas na main exata em 196 testes
   selecionados; não atribuir automaticamente as novas falhas a esse baseline.
2. **VM limpa com systemd e stack ARM64 completa** ainda precisam de aceitação.
   Pacotes/arquiteturas e backend nativo foram verificados; container Ubuntu não
   comprova instalação desde host cru, apt e inicialização do Docker.
3. **Oracle RC4 parcial** mantém PostgreSQL/checkpoints. A mudança de release
   inacabada está bloqueada pelo pin do wizard; exige transição revisada. O
   gerenciador antigo também pode recusar bundle novo com arquivo adicional.
   Não apague estado, regenere senhas ou volumes para passar. Não houve acesso
   nem alteração da VM nesta revisão.
4. **HTTPS/proxy/DNS, login, busca, documento e SMTP** precisam de ensaio real.
   Banco externo deve ser acessível de dentro do container; localhost do host não
   é o localhost do backend. Uma instalação vazia não cria administrador DSpace.
5. **Importação automática pública** depende de URL/dataset autorizado. Transporte
   privado local está disponível; dump completo não pode ser importado depois de
   inicializar o schema. Escolha importação antes do bootstrap.
6. **Atualização A→B real** e backup/retorno precisam ser comprovados na VM de
   homologação. Há cobertura simulada, mas o ciclo completo publicado RC4→RC6 não
   foi executado; relatório do wizard concluído pode conservar sua release fixada.

## Entrega

Enviar ao NTI a RC6 como candidata, os três documentos e os resultados da CI da
branch de entrega. Transportar o pacote institucional separadamente, com acesso
restrito e aprovação. [OPERACOES](OPERACOES.md#aceitacao-pelo-nti) define os critérios
para aprovação final. Não houve merge na main, nova release, migrations históricas
alteradas ou remoção de dados nesta revisão.

# Resultado do MVP PCIRN

Data da validação: 2026-08-14

## Entregue

- `Usuarios_Logados`, `NUGECID` e `PCIRN_Depositantes` existem no PostgreSQL.
- Os usuários locais existentes estão em `Usuarios_Logados`; `admin@localhost` e `gesiele@localhost.com` estão em NUGECID e PCIRN_Depositantes.
- As políticas de leitura atuais foram transferidas de `Anonymous` para `Usuarios_Logados`; as políticas de depósito foram criadas para `PCIRN_Depositantes`.
- O grupo NUGECID foi associado ao papel nativo `editor` em todas as 22 coleções.
- `authentication-password.login.specialgroup = Usuarios_Logados` habilita membership automático em novos logins por senha.
- O PDF `ESTRUTURA DO SISTEMA.pdf` foi depositado na coleção `Portarias e Atos Normativos Internos`.
- O fluxo NUGECID foi provado: submissão, devolução por `admin@localhost`, correção, reenvio e aprovação.
- Item publicado: Handle `123456789/24`; busca Solr encontrou o item pelo identificador de teste; endpoint de facetas retornou 7 filtros.
- Bitstream PDF validado: 404230 bytes; acesso autenticado retornou HTTP 200 e acesso anônimo retornou HTTP 401.
- SMTP validado com `/dspace/bin/dspace test-email`: envio aceito pelo `smtp.gmail.com`.
- A home permanece protegida por autenticação, conforme a decisão de sistema interno; os testes focados Angular passaram 10/10.

## Setores e sidebar

- Migração versionada `V9.4_2026.08.15__pcirn_sector_access.sql` registrada em `schema_version`.
- Migração `V9.4_2026.08.16__pcirn_sector_membership_reconcile.sql` sincroniza membros de `NUGECID` com `PCIRN_Setor_NUGECID`.
- Grupos criados: `PCIRN_Setor_DG`, `PCIRN_Setor_IC`, `PCIRN_Setor_II`, `PCIRN_Setor_IML` e `PCIRN_Setor_NUGECID`.
- NUGECID foi criado como comunidade visível, sem substituir o grupo curatorial `NUGECID`.
- As leituras PCIRN de `Usuarios_Logados` foram substituídas por políticas dos respectivos setores; `PCIRN_Depositantes` e workflow permaneceram intactos.
- Sidebar Angular consulta comunidades autorizadas pelo REST, aceita múltiplos setores e oculta-se quando a sidebar administrativa está ativa.
- Usuário NUGECID autenticado: comunidade NUGECID retornou `200`; comunidade DG retornou `403`.
- A capacidade de múltiplos setores foi validada em transação SQL com duas memberships e rollback, sem alterar usuário real.
- Os três usuários locais atuais foram associados ao setor `PCIRN_Setor_NUGECID`; nenhum recebeu papel curatorial adicional por essa associação.
- IC, II e IML também expedem Portarias e Atos Normativos Internos: a coleção `Portarias e Atos Normativos Internos` foi adicionada às comunidades de cada instituto pela migração `V9.4_2026.08.17__pcirn_portarias_collections.sql`, com as mesmas políticas de leitura do setor, depósito (`PCIRN_Depositantes`) e curadoria (`NUGECID` editor) das demais coleções.

## Implementação persistida

- Migração idempotente: `dspace-api/src/main/resources/org/dspace/storage/rdbms/sqlmigration/postgres/V9.4_2026.08.14__pcirn_mvp_access.sql`
- Configuração de membership: `dspace/config/modules/authentication-password.cfg`
- Plano e critérios: `docs/goals/pcirn-mvp/PLAN.md` e `docs/goals/pcirn-mvp/GOAL.md`

O backend foi reconstruído uma vez para incorporar a migração e o serviço foi recriado sem rebuild do Angular. Iterações de fonte no modo dev continuam usando `--no-build`.

# MVP do Repositório Institucional PCIRN

**Intent:** fechar o MVP descrito em `ESTRUTURA DO SISTEMA.pdf` com acesso interno, curadoria NUGECID e prova ponta a ponta.
**Current Behavior:** a estrutura de comunidades/coleções e o formulário PCIRN existem; há políticas anônimas remanescentes, nenhum item depositado e o fluxo ainda não foi provado.
**Expected Outcome:** usuários autenticados conseguem depositar; NUGECID consegue devolver, receber reenvio e aprovar; o item publicado possui Handle, indexação, filtros e bitstream protegido.
**Target-Perspective Output:** um responsável deposita um PDF, acompanha a devolução/correção e recebe o documento publicado; um curador valida e publica.
**Truth Owner:** PostgreSQL para grupos, políticas e objetos; `dspace/config/` para o contrato de submissão/workflow; Angular para rotas e experiência.
**Contract Boundary:** DSpace REST/Angular; autenticação JWT; grupos `Usuarios_Logados`, `NUGECID` e `PCIRN_Depositantes`.
**Cutover:** nova migração reconciliará políticas existentes; configuração de senha adicionará usuários autenticados a `Usuarios_Logados`; `/home` passará a exigir autenticação.
**Displaced Path:** políticas `Anonymous` de leitura dos objetos PCIRN e home pública.
**Value Density:** uma migração, uma configuração de grupo e um teste ponta a ponta cobrem o maior risco do MVP.
**Acceptance Evidence:** consultas SQL de políticas/membership, depósito REST, transições de workflow, Handle, busca Solr, acesso autenticado/anônimo ao bitstream e teste SMTP documentado.
**Evidence Lane:** Docker Compose local, PostgreSQL e endpoints REST em `localhost:8501`; nenhuma credencial deve ser registrada neste documento.
**Kill Criteria:** não criar camada paralela de autorização, submissão ou workflow; usar os mecanismos nativos do DSpace.
**Non-goals:** DOI, validação especializada PDF/A, LDAP/OIDC, páginas institucionais completas e modelagem detalhada de cada setor interno.
**Risk if wrong:** uma política anônima residual ou membership ausente deixa documentos internos expostos ou impede o depósito.

## Arquitetura e arquivos

- **Modificar:** `dspace-api/src/main/resources/org/dspace/storage/rdbms/sqlmigration/postgres/V9.4_2026.08.14__pcirn_mvp_access.sql`, `dspace/config/modules/authentication-password.cfg`, `dspace-angular/source/src/app/app-routes.ts`.
- **Usar:** `dspace/config/pcirn/structure.xml`, `dspace/config/item-submission.xml`, `dspace/config/submission-forms.xml`, `dspace/config/spring/api/workflow.xml`.
- **Evitar:** substituir componentes nativos de submissão, autorização, workflow, busca ou Handle.
- **Migration/cutover:** executar `database migrate`; conferir `schema_version`; testar políticas antes e depois.

## Tarefas

1. Criar e aplicar migração idempotente para grupos, membership, políticas de leitura e permissões ADD.
2. Configurar membership automático para `Usuarios_Logados`; colocar o usuário de teste em `NUGECID` e `PCIRN_Depositantes`.
3. Proteger `/home` e rotas de conteúdo; preservar `/login` e recuperação de senha.
4. Depositar `ESTRUTURA DO SISTEMA.pdf` como item de teste via REST.
5. Validar devolução, reenvio e aprovação pelo grupo NUGECID.
6. Confirmar Handle, documento indexado, filtros de metadados e bitstream protegido.
7. Executar `test-email` sem expor credenciais; se o provedor bloquear, registrar o bloqueio como externo.

## Gate de revisão

O MVP só é marcado como concluído quando todas as evidências acima forem capturadas; falha de SMTP externo não bloqueia o restante, mas permanece explicitamente registrada.

# Fluxo de publicação de documentos PCIRN

Análise do fluxo de depósito, revisão e leitura de portarias, POPs e demais documentos do Repositório Institucional PCIRN.

Atualizado em 2026-09-15, após aplicação das migrações `V9.4_2026.08.24` e `V9.4_2026.09.15`.

## 1. Estrutura

Fonte: `dspace/config/pcirn/structure.xml` (import manual com `dspace structure-builder`, ver `docs/pcirn-repository.md`).

23 coleções em 5 comunidades (as 22 do `structure.xml` mais a coleção `Documentos do NUGECID`), handles `123456789/2..27` e `/34`:

| Comunidade | Portarias | POPs | Outras |
|---|---|---|---|
| Gestão Estratégica e Administrativa (DG) | `/2` | — | Manuais `/3`, Relatórios `/4`, Notas `/5` |
| Instituto de Criminalística (IC) | `/25` | Internas `/7`, Externas `/8`, Lab `/9` | Manuais `/10`, Relatórios `/11`, Notas `/12` |
| Instituto de Identificação (II) | `/26` | Biometria/Papiloscopia `/20` | Diretrizes `/21`, Manuais ABIS/CIN `/22`, Notas `/23` |
| Instituto de Medicina Legal (IML) | `/27` | Tanatologia `/14`, Sexologia `/15`, Antropologia `/16` | Manuais `/17`, Notas `/18` |
| NUGECID | — | — | Documentos do NUGECID `/34` |

A comunidade NUGECID e a coleção `Documentos do NUGECID` são criadas por migração (`V9.4_2026.08.15` e `V9.4_2026.08.24`), não pelo `structure.xml`.

## 2. Fluxo de submissão

Toda coleção PCIRN usa a definição `pcirn` (`dspace/config/item-submission.xml:288`). Ordem dos passos (`item-submission.xml:288-294`):

`collection` → `pcirnpageone` → `pcirnpagetwo` → `upload` → `license`

**Página 1** (`dspace/config/submission-forms.xml:24-121`): título*, título alternativo/sigla, autor ou relator, unidade responsável*, data de emissão/aprovação*, identificador oficial, versão, idioma*.

**Página 2** (`submission-forms.xml:123-173`): assunto/palavras-chave, resumo/ementa, **tipo de documento*** (`dc.type`, vocabulário `dspace/config/controlled-vocabularies/pcirn-document-types.xml`: `PORTARIA`, `POP`, `MANUAL_GUIA`, `MANUAL_GESTAO`, `RELATORIO_PRODUTIVIDADE`, `RELATORIO_CONTAS`, `NOTA_TECNICA`, `DIRETRIZ_INSTRUCAO`), período de cobertura.

**Upload**: bitstream PDF com metadados (`bitstream-metadata`).

**Visibilidade**: todo item aprovado é público. Não há passo de condição de acesso (embargo/restrito) no processo `pcirn`; as coleções têm `DEFAULT_ITEM_READ`/`DEFAULT_BITSTREAM_READ` para `Anonymous` (migração `V9.4_2026.09.15`), herdadas no momento em que o item é instalado. Rascunhos e itens em workflow continuam privados.

**Licença**: aceite da licença padrão.

O mesmo formulário vale para portaria, POP e documento comum; o tipo é apenas metadado, sem campos condicionais (`type-bind` está ligado em `dspace.cfg:1041`, mas não há `<type-bind>` nos formulários).

## 3. Workflow de aprovação

- Passo único `editstep`, role `editor` = grupo `NUGECID` (`dspace/config/spring/api/workflow.xml:27-51`).
- Ação `editaction` (`AcceptEditRejectAction`), com quatro opções: **validar** (`submit_approve`), **editar** (`submit_edit_metadata`, abre a página de submissão do item), **retornar ao setor** (`submit_reject`, exige motivo e devolve ao workspace do depositante) e **excluir** (`submit_delete`, apaga definitivamente workflow item, item e arquivos). `return_to_pool` foi removido.
- `cwf_collectionrole editor=NUGECID` existe para as 23 coleções (residual: o papel é `REPOSITORY`, resolvido pelo nome do grupo).
- Curadoria: `dspace/config/spring/api/workflow-curation.xml:12` mapeia tudo para `none`; nenhuma task roda. Virus scan desligado (`dspace/config/modules/submission-curation.cfg:10`). PDF/A é exigência manual, não validada pelo sistema.

## 4. Permissões (estado atual, pós-09.15)

| Grupo | Depositar (ADD) | Revisar | Ler |
|---|---|---|---|
| `PCIRN_Setor_DG` | 4 coleções do DG | não | via pública |
| `PCIRN_Setor_IC` | 7 coleções do IC | não | via pública |
| `PCIRN_Setor_II` | 5 coleções do II | não | via pública |
| `PCIRN_Setor_IML` | 6 coleções do IML | não | via pública |
| `PCIRN_Setor_NUGECID` | coleção `/34` | não | via pública |
| `NUGECID` | não | todas as 23 coleções | via pública |
| `Usuarios_Logados` | não | não | via pública (grupo sem policies próprias) |
| `Anonymous` | não | não | tudo: comunidades, coleções, itens arquivados, bundles e bitstreams |
| `PCIRN_Depositantes` | nenhuma (legado) | não | via pública |
| `Administrator` | bypass nativo | bypass | tudo |

O depósito é autorizado exclusivamente pelo vínculo ao grupo do setor da coleção. Não há vínculo por metadado, e-mail ou domínio; a associação é feita em `epersongroup2eperson`.

Autenticação: apenas senha (`authentication.cfg`); auto-cadastro, OIDC e LDAP desativados. Contas são provisionadas por administrador ou diretório institucional. Login por senha adiciona o usuário a `Usuarios_Logados` (sem efeito de leitura, já pública).

## 5. Como fazer

**Adicionar depositante** (administrador): criar a conta (auto-cadastro desligado) e incluir o usuário no grupo `PCIRN_Setor_<DG|IC|II|IML|NUGECID>` pela administração de grupos. Revisores: incluir em `NUGECID`.

**Depositar**: login → abrir a coleção do setor → Depositar → preencher páginas 1 e 2 → enviar PDF → aceitar licença. O item fica no workspace e segue para o workflow.

**Aprovar (NUGECID)**: login → MyDSpace mostra o aviso "Tarefas de fluxo de trabalho aguardando análise" com a contagem (na fila + assumidas) e o atalho **Analisar tarefas**; o fluxo completo fica em Mostrar → Tarefas de fluxo de trabalho. Assumir → conferir arquivo e metadados → **validar**, **editar**, **retornar ao setor** (com motivo) ou **excluir** (definitivo). Aprovado: item arquivado, Handle gerado, indexado e público.

**Ler**: todo item aprovado é aberto ao anônimo (item, bitstream e busca).

## 6. Pendências e limitações conhecidas

1. Grupos `PCIRN_Setor_DG`, `PCIRN_Setor_IC`, `PCIRN_Setor_II` e `PCIRN_Setor_IML` estão sem membros: ninguém deposita nesses setores até o admin provisionar. `PCIRN_Setor_NUGECID` tem 2 membros; `NUGECID` tem 1 (revisor).
2. As migrações `V9.4_2026.08.14/15/16/17/24` não estão versionadas no git (apenas `08.05` modificada, `08.18` e `09.15` rastreadas).
3. `Usuarios_Logados` e os setores não têm mais policies de leitura; toda leitura vem de `Anonymous` (migração `V9.4_2026.09.15`).
4. Novas migrações exigem rebuild da imagem: `dspace database migrate` lê os jars em `/dspace/lib`, não o diretório de classes montado em `/dspace/overrides`. Alterações em Java (`AcceptEditRejectAction`) também exigem rebuild/restart do container.
5. Handles `123456789/*` e `dc.identifier.uri` com `http://localhost:4000` são placeholders.
6. SMTP ainda não configurado: notificações de workflow não são enviadas.
7. PDF/A e antivírus não são validados automaticamente.
8. OAI-PMH permanece desativado; IIIF e SWORD desativados por configuração.

## 7. Correções aplicadas nesta revisão

A migração `V9.4_2026.08.24__pcirn_sector_submission_and_shared_read.sql` nunca havia sido executada e continha dois erros de SQL, corrigidos para aplicação:

- Coluna inexistente `legacy_membership.epersongroup_id` → `eperson_group_id`.
- `rpname` com 31 caracteres em coluna `varchar(30)` → valor reduzido para `PCIRN sector read`.

A migração foi validada com dry-run em transação com rollback e aplicada com sucesso.

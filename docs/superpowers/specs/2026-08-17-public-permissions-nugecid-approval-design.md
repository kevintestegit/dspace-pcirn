# Acesso público e aprovação obrigatória pelo NUGECID

**Status:** aprovado em 2026-08-17.

## Resultado esperado

O público poderá consultar e baixar somente Portarias aprovadas. POPs e demais documentos internos aprovados ficarão disponíveis apenas para usuários autenticados. Nenhum documento novo será publicado sem aprovação do NUGECID.

## Regras de negócio

- O administrador cria as contas; não existe autocadastro.
- A conta precisa ter e-mail para receber a redefinição de senha.
- Todo usuário autenticado com conta ativa pode enviar documentos.
- O remetente e o NUGECID são os únicos atores do fluxo de análise.
- Enquanto estiver em workspace ou workflow, o documento não é público nem aparece na busca pública.
- O remetente pode consultar o próprio envio; o NUGECID consulta e processa a fila de aprovação.
- O NUGECID pode corrigir, devolver, rejeitar ou aprovar.
- Somente a aprovação instala o item no repositório.
- Administrador gerencia contas e configuração, mas não possui uma publicação direta que contorne o NUGECID.

## Modelo de acesso

| Estado | Remetente | NUGECID | Usuário logado | Público |
|---|---:|---:|---:|---:|
| Pendente, devolvido ou rejeitado | sim | sim | não | não |
| Portaria aprovada | sim | sim | sim | sim |
| POP ou documento interno aprovado | sim | sim | sim | não |

A visibilidade será controlada por `ResourcePolicy` e pelas coleções. A coleção de Portarias receberá leitura anônima somente para itens/bitstreams aprovados. Coleções de POPs e documentos internos receberão leitura para o grupo de usuários autenticados. Grupos setoriais não serão usados como critério de leitura neste modelo.

## Interface pública

Usuários não autenticados não verão a sidebar de setores e não dispararão a consulta de comunidades. Usuários autenticados verão a sidebar conforme suas permissões; a sidebar administrativa continua tendo prioridade quando estiver ativa. Essa regra é de apresentação e não substitui as políticas do backend.

## Fluxo obrigatório

1. Usuário autenticado cria a submissão e envia o arquivo.
2. DSpace mantém o item em workspace/workflow com leitura restrita ao remetente e ao NUGECID.
3. O workflow encaminha toda submissão ao grupo `NUGECID`.
4. Devolução ou rejeição mantém o item fora do arquivo público.
5. Aprovação é a única transição que instala, indexa e aplica a política de leitura conforme a coleção.

## Fechamento de atalhos

- A criação administrativa direta de item arquivado via REST será removida ou bloqueada.
- Importações SAF deverão passar pelo workflow; importação direta sem workflow será recusada.
- SWORD e demais entradas externas não autorizadas permanecerão desativadas.
- Leitura pública continuará dependente das políticas do objeto, inclusive para REST, busca, Handle e bitstreams.
- A camada HTTP permitirá leituras anônimas somente para que as políticas nativas do DSpace decidam o acesso; operações de escrita continuarão protegidas.

## Fonte da verdade e cutover

- PostgreSQL: grupos, memberships, coleções e `ResourcePolicy`.
- `dspace/config/spring/api/workflow.xml`: aprovação e ações do NUGECID.
- `dspace/config/item-submission.xml` e `submission-forms.xml`: entrada dos documentos.
- `WebSecurityConfiguration.java`: autenticação de transporte, sem substituir autorização por objeto.
- Migração nova e idempotente: reconciliar políticas existentes para Portarias públicas e documentos internos autenticados. Migrações já registradas em `schema_version` não serão reescritas.

## Evidência de aceite

- Conta criada pelo administrador recebe redefinição por e-mail; autocadastro falha.
- Usuário autenticado consegue enviar Portaria e POP.
- Remetente e NUGECID conseguem ver o pendente; outro usuário e anônimo recebem negação.
- Aprovação do NUGECID publica a Portaria para anônimo.
- Aprovação do NUGECID mantém o POP invisível para anônimo e disponível para usuário logado.
- Devolução/rejeição não publica nem indexa o item.
- REST, busca, Handle, download direto e qualquer importação respeitam o mesmo estado.
- Tentativas de criação direta arquivada e importação sem workflow falham.
- Usuário anônimo não encontra `#pcirn-sector-sidebar` no HTML e não dispara a consulta de comunidades; usuário autenticado pode visualizar a sidebar.

## Fora do escopo

Novo mecanismo Java de autorização, autocadastro público, aprovação por outro setor, publicação pública de POPs, LDAP/OIDC e redesign visual.

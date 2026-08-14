# PCIRN Sector Sidebar

**Status:** Design approved by requester, pending implementation.

## Intent

Mostrar na sidebar de usuários comuns somente os setores aos quais eles pertencem, usando as comunidades e as políticas nativas do DSpace.

## Setores

Cada setor terá um grupo de membership do DSpace e uma comunidade correspondente:

- Gestão Estratégica e Administrativa (DG)
- Instituto de Criminalística (IC)
- Instituto de Identificação (II)
- Instituto de Medicina Legal (IML)
- Núcleo de Gestão do Conhecimento, Informação, Documentação e Memória (NUGECID)

NUGECID é um setor, não uma categoria de usuário. O grupo `NUGECID` já usado pelo workflow será preservado como papel de curadoria; o membership do setor NUGECID usará `PCIRN_Setor_NUGECID` para não quebrar a curadoria existente.

## Regras de acesso

- Um usuário pode pertencer a um ou vários grupos de setor.
- Cada grupo de setor recebe `READ` somente na comunidade correspondente e em suas coleções filhas.
- `Administrator` mantém acesso global.
- Nenhum grupo de usuário genérico deve conceder `READ` global aos setores quando a segregação estiver ativa.
- Usuário sem setor não visualiza setores nem documentos desses setores.

## Interface

- A sidebar comum exibirá a seção **Setores**.
- Cada item será uma comunidade autorizada para o usuário atual.
- A lista será carregada pelo endpoint nativo de comunidades, respeitando as políticas REST do DSpace.
- Usuários com múltiplos setores verão todos os setores atribuídos.
- A sidebar administrativa continuará restrita a permissões administrativas.

## Fonte de verdade

Memberships, comunidades, coleções e `ResourcePolicy` do DSpace são a única fonte de verdade. Não será criado cadastro paralelo de setores no Angular.

## Administração

Administradores poderão adicionar ou remover um usuário de qualquer quantidade de grupos de setor pela gestão de grupos/usuários existente.

## Aceitação

1. Kevin associado a um único setor vê apenas esse setor e suas coleções.
2. Kevin associado a dois setores vê ambos.
3. Kevin não consegue listar ou abrir comunidade/coleção de setor ao qual não pertence.
4. Usuário sem setor não recebe módulos de setor.
5. Usuário membro de `PCIRN_Setor_NUGECID` vê o módulo NUGECID, salvo quando também for membro de outro setor.
6. Administrator continua vendo todos os setores.
7. O fluxo de depósito e curadoria existente continua funcionando nas coleções permitidas.

## Não objetivos

- Criar uma nova tabela ou API de setores.
- Transformar NUGECID em papel global de administrador.
- Alterar a sidebar administrativa existente.

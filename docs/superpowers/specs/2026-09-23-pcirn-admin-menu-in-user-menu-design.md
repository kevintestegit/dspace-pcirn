# Menu de administração dentro do menu do usuário

## Objetivo

Repor o acesso a todos os itens que antes ficavam na barra lateral de administração. A barra foi removida e hoje o menu do usuário só oferece um link solto para `/admin`. A solução escolhida (D2 no companion visual) coloca os itens no próprio menu do usuário, agrupados por seção em grupos recolhíveis.

## Contexto confirmado

- A barra lateral foi removida no working tree: `custom/app/admin/admin-sidebar/*` está deletado e `src/app/root/root.component.ts` não importa mais `ThemedAdminSidebarComponent` nem `ThemedSectorSidebarComponent`.
- O menu do usuário custom já tem o gancho: `administrationAvailable$` observa `MenuService.isMenuVisibleWithVisibleSections(MenuID.ADMIN)` e `ngOnInit` chama `showMenu(MenuID.ADMIN)` no login (`custom/app/shared/auth-nav-menu/user-menu/user-menu.component.ts:45-54`).
- `MenuID.ADMIN = 'admin-sidebar'`. Para uma conta administradora o menu tem 40 nós: 17 seções de topo (15 visíveis, 7 delas com filhos) e 17 itens, totalizando 32 nós visíveis.
- O painel em `/admin` (`custom/app/admin/admin-dashboard/admin-dashboard.component.html`, ainda não versionado) estava quebrado: `groups$` nunca emitia. Causa raiz: `MenuService.getSubSectionsByParentID` monta `combineLatest([])` quando a seção não tem filhos; dentro de um `switchMap` cujo store nunca completa, o resultado nem emite nem completa, então `defaultIfEmpty` também não dispara. Qualquer seção de topo sem filhos (Pesquisa administrativa, Histórico de e-mails, Governança, Fluxo, Saúde, Alertas, Processos, Tarefas) travava a lista inteira.
- Mockups e escolha: `.superpowers/brainstorm/1695879-1790167796/content/admin-menu-placement.html` (A–D) e `admin-menu-user-variants.html` (D1–D3). O usuário escolheu **D2**.

## Decisão

D2: o item "Administração" do menu do usuário vira um grupo recolhível com todos os itens visíveis do `MenuID.ADMIN`. Fechado, mostra apenas as seções; aberto, revela os itens. O menu já é renderizado dentro do dropdown do avatar e no acordeão da navbar em telas pequenas, então o mesmo markup serve os dois casos.

## Arquitetura

Mudança restrita ao tema custom:

- `custom/app/shared/auth-nav-menu/user-menu/user-menu.component.ts` — expõe `adminSections$` e o estado/controles dos grupos.
- `custom/app/shared/auth-nav-menu/user-menu/user-menu.component.html` — substitui o link único `/admin` pelo bloco "Administração" com grupos e itens.
- `custom/app/shared/auth-nav-menu/user-menu/user-menu.component.scss` — estilos dos grupos, itens e setas, reusando os tokens `--pcirn-menu-*` já definidos.
- `src/app/shared/menu/menu.service.ts` — correção na raiz: `getSubSectionsByParentID` devolve `of([])` quando o pai não tem filhos, em vez de um observable que nunca emite. Vale para o menu novo, para o painel e para qualquer consumidor futuro.
- `src/app/shared/menu/menu.service.spec.ts` — expectativa do caso "sem filhos" passa de "não emite" para "emite lista vazia".

Nenhuma rota, componente, provider de menu, permissão ou serviço novo.

## Fluxo de dados

- `adminSections$` parte de `menuService.getMenuTopSections(MenuID.ADMIN)` (já filtra visibilidade) e, para cada seção, combina `menuService.getSubSectionsByParentID(MenuID.ADMIN, section.id).pipe(defaultIfEmpty([]))` em `{ section, items }`.
- Render por tipo de `section.model.type`:
  - `LINK` → `<a [routerLink]>` com `(click)="onMenuItemClick()"`.
  - `ONCLICK` → `<button type="button">` que chama `onMenuItemClick()` (fecha o dropdown) e em seguida executa `(model as OnClickMenuItemModel).function()`.
  - `TEXT` com itens → cabeçalho de grupo recolhível (ícone `section.icon`, texto traduzido, `aria-expanded`).
  - `TEXT` sem itens → não renderiza.
- Grupos começam fechados. Estado local `expanded: Set<string>`; `toggleSection(id, $event)` chama `$event.stopPropagation()` para o clique não fechar o dropdown.
- Primeiro item do bloco é "Painel administrativo" (`admin.dashboard.title` → `/admin`).

## Inventário dos itens (visíveis para administrador)

Seções com filhos:

| Seção | Itens |
| --- | --- |
| `menu.section.new` | Nova comunidade (ação), Nova coleção (ação), Novo item (ação), Novo processo (`/processes/new`) |
| `menu.section.edit` | Editar comunidade, Editar coleção, Editar item (ações) |
| `menu.section.import` | Importar metadados (`/admin/metadata-import`), Importar lote (`/admin/batch-import`) |
| `menu.section.export` | Exportar metadados, Exportar lote (ações) |
| `menu.section.notifications` | Reivindicações de publicação (`/admin/notifications/publication-claim`) |
| `menu.section.access_control` | Pessoas (`/access-control/epeople`), Grupos (`/access-control/groups`), Permissões (`/access-control/bulk-access`) |
| `menu.section.registries` | Metadados (`/admin/registries/metadata`), Formatos (`/admin/registries/bitstream-formats`) |

Seções de topo que são link direto: Pesquisa administrativa (`/admin/search`), Histórico de e-mails (`/admin/email-logs`), Governança (`/admin/governance`), Tarefas de curadoria (`/admin/curation-tasks`), Processos (`/processes`), Fluxo de trabalho (`/admin/workflow`), Saúde (`/health`), Alerta do sistema (`/admin/system-wide-alert`).

Ocultas por permissão (não renderizam): Relatórios e COAR Notify.

## Correção na raiz (MenuService)

Em `menu.service.ts`, no `getSubSectionsByParentID`, trocar o `switchMap` por:

```ts
      switchMap((ids: string[]) => isNotEmpty(ids)
        ? observableCombineLatest(ids.map((id: string) => this.getMenuSection(menuID, id)))
        : of([]),
      ),
```

Sem isso, qualquer seção sem filhos trava a emissão — inclusive no menu novo, que usa o mesmo encadeamento. O painel `/admin` volta a listar todas as seções sem precisar de `defaultIfEmpty` nos consumidores.

## Acessibilidade e i18n

- Cabeçalho de grupo é `<button type="button">` real, com `aria-expanded` e `aria-controls` apontando para a lista de itens; itens mantêm `role="menuitem"` como o restante do menu.
- Foco visível preservado; setas apenas decorativas (`aria-hidden`).
- Nenhuma chave de tradução nova: textos de seção e itens já existem; o rótulo do grupo reusa o próprio texto traduzido.

## Verificação

1. `scripts/pcirn-user-menu-admin.test.mjs` (padrão `node --test` dos demais `pcirn-*.test.mjs`): garante `MenuID.ADMIN`, `getSubSectionsByParentID`, a emissão de lista vazia no `MenuService`, execução de `ONCLICK` com fechamento do dropdown e toggle com `stopPropagation`.
2. Suíte `node --test dspace-angular/source/scripts/pcirn-*.test.mjs` e spec focado `ng test --include='src/app/shared/menu/menu.service.spec.ts'`.
3. Compilação do tema no fluxo Docker do `dspace-angular`.
4. Validação viva com conta administradora temporária (criada e removida ao final): abrir o menu, expandir e recolher grupos, abrir um link, disparar uma ação que abre modal (ex.: Nova comunidade) e conferir o comportamento no layout móvel da navbar.

## Limites

Não serão alterados: permissões e providers de menu, rotas, backend/REST, o conteúdo do painel `/admin` (além da correção da emissão), o menu público da navbar e o restante do menu do usuário.

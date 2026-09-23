# Menu de administração no menu do usuário — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Colocar todos os itens do antigo menu lateral de administração dentro do menu do usuário, agrupados por seção em grupos recolhíveis (variante D2).

**Architecture:** O menu do usuário custom passa a consumir `MenuID.ADMIN` do `MenuService` e renderiza grupos recolhíveis com links e ações. Na raiz, `MenuService.getSubSectionsByParentID` passa a devolver `of([])` para seções sem filhos, destravando o painel `/admin` e o próprio menu.

**Tech Stack:** Angular 19 standalone components, RxJS, ngx-translate, NgRx (menu store), SCSS, node:test para os testes de script.

**Spec:** `docs/superpowers/specs/2026-09-23-pcirn-admin-menu-in-user-menu-design.md`

> Neste ambiente, commits só acontecem se o usuário pedir explicitamente. Os passos de commit abaixo ficam marcados, mas devem ser pulados até haver pedido.

---

### Task 1: Destravar seções sem filhos no MenuService

**Files:**
- Modify: `dspace-angular/source/src/app/shared/menu/menu.service.ts:129-139`
- Modify: `dspace-angular/source/src/app/shared/menu/menu.service.spec.ts:252-260`

- [ ] **Step 1: Corrigir a emissão para pais sem filhos**

Importar `of` e trocar o `switchMap`:

```ts
import {
  combineLatest as observableCombineLatest,
  Observable,
  of,
} from 'rxjs';
```

```ts
      switchMap((ids: string[]) => isNotEmpty(ids)
        ? observableCombineLatest(ids.map((id: string) => this.getMenuSection(menuID, id)))
        : of([]),
      ),
```

Motivo: `observableCombineLatest([])` dentro de um `switchMap` cujo store nunca completa nem emite nem completa; `defaultIfEmpty` nos consumidores não dispara. Uma seção de topo sem filhos travava `groups$` do painel e `adminSections$` do menu.

- [ ] **Step 2: Atualizar a spec do serviço**

Em `menu.service.spec.ts`, o caso "when the subsection list is undefined" passa a esperar lista vazia:

```ts
    describe('when the subsection list is undefined', () => {
      it('should return an observable that emits an empty list', () => {

        const result = service.getSubSectionsByParentID(MenuID.ADMIN, 'fakeId');
        const expected = cold('b', {
          b: [],
        });

        expect(result).toBeObservable(expected);
      });
    });
```

- [ ] **Step 3: Rodar a spec focada**

Run: `CHROME_BIN=/usr/bin/google-chrome npx ng test --source-map=true --watch=false --configuration test --include='src/app/shared/menu/menu.service.spec.ts'` em `dspace-angular/source`
Expected: `TOTAL: 29 SUCCESS`.

- [ ] **Step 4: Confirmar compilação**

Run: `docker logs dspace-angular --since 2m 2>&1 | grep -i "compiled successfully"`
Expected: `Compiled successfully`.

---

### Task 2: Dados e controles no componente do menu do usuário

**Files:**
- Modify: `dspace-angular/source/src/themes/custom/app/shared/auth-nav-menu/user-menu/user-menu.component.ts`

- [ ] **Step 1: Adicionar imports e interface**

```ts
import {
  AsyncPipe,
  NgClass,
} from '@angular/common';
import {
  Component,
  inject,
} from '@angular/core';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import {
  RouterLink,
  RouterLinkActive,
} from '@angular/router';
import { TranslateModule } from '@ngx-translate/core';
import {
  combineLatest,
  Observable,
  of,
} from 'rxjs';
import {
  map,
  switchMap,
  take,
} from 'rxjs/operators';
import { ThemedLoadingComponent } from 'src/app/shared/loading/themed-loading.component';
import { LogOutComponent } from 'src/app/shared/log-out/log-out.component';
import { ThemedCreateItemParentSelectorComponent } from 'src/app/shared/dso-selector/modal-wrappers/create-item-parent-selector/themed-create-item-parent-selector.component';
import { LinkMenuItemModel } from 'src/app/shared/menu/menu-item/models/link.model';
import { OnClickMenuItemModel } from 'src/app/shared/menu/menu-item/models/onclick.model';
import { MenuItemType } from 'src/app/shared/menu/menu-item-type.model';
import { MenuID } from 'src/app/shared/menu/menu-id.model';
import { MenuSection } from 'src/app/shared/menu/menu-section.model';
import { MenuService } from 'src/app/shared/menu/menu.service';
import { UserSectorsService } from 'src/app/shared/user-sectors/user-sectors.service';

import { Community } from '../../../../../../app/core/shared/community.model';
import { UserMenuComponent as BaseComponent } from '../../../../../../app/shared/auth-nav-menu/user-menu/user-menu.component';

export interface AdminMenuGroup {
  section: MenuSection;
  items: MenuSection[];
}
```

- [ ] **Step 2: Expor os grupos e os controles**

Substituir o corpo da classe `UserMenuComponent` por:

```ts
export class UserMenuComponent extends BaseComponent {

  readonly userSectors = inject(UserSectorsService);
  private readonly menuService = inject(MenuService);
  private readonly modalService = inject(NgbModal);
  readonly administrationAvailable$ = this.menuService.isMenuVisibleWithVisibleSections(MenuID.ADMIN);

  adminMenuOpen = false;
  readonly expandedAdminSections = new Set<string>();

  readonly adminSections$: Observable<AdminMenuGroup[]> = this.menuService.getMenuTopSections(MenuID.ADMIN).pipe(
    switchMap((sections) => sections.length === 0
      ? of([] as AdminMenuGroup[])
      : combineLatest(sections.map((section) =>
        this.menuService.getSubSectionsByParentID(MenuID.ADMIN, section.id).pipe(
          map((items) => ({ section, items })),
        ),
      ))),
  );

  override ngOnInit(): void {
    super.ngOnInit();
    this.authService.isAuthenticated().pipe(take(1)).subscribe((authenticated) => {
      if (authenticated) {
        this.menuService.showMenu(MenuID.ADMIN);
      }
    });
  }

  trackCommunity(_: number, community: Community): string {
    return community.id;
  }

  trackAdminSection(_: number, group: AdminMenuGroup | MenuSection): string {
    return group.section ? group.section.id : (group as MenuSection).id;
  }

  toggleAdminMenu(event: Event): void {
    event.preventDefault();
    event.stopPropagation();
    this.adminMenuOpen = !this.adminMenuOpen;
  }

  toggleAdminSection(section: MenuSection, event: Event): void {
    event.preventDefault();
    event.stopPropagation();
    if (this.expandedAdminSections.has(section.id)) {
      this.expandedAdminSections.delete(section.id);
    } else {
      this.expandedAdminSections.add(section.id);
    }
  }

  isAdminSectionExpanded(section: MenuSection): boolean {
    return this.expandedAdminSections.has(section.id);
  }

  getAdminSectionText(section: MenuSection): string {
    return 'text' in section.model ? section.model.text : '';
  }

  getAdminSectionLink(section: MenuSection): string | undefined {
    return section.model.type === MenuItemType.LINK
      ? (section.model as LinkMenuItemModel).link
      : undefined;
  }

  isAdminSectionAction(section: MenuSection): boolean {
    return section.model.type === MenuItemType.ONCLICK;
  }

  executeAdminSection(section: MenuSection): void {
    this.onMenuItemClick();
    if (this.isAdminSectionAction(section)) {
      (section.model as OnClickMenuItemModel).function();
    }
  }

  openSubmission(): void {
    this.onMenuItemClick();
    this.modalService.open(ThemedCreateItemParentSelectorComponent);
  }
}
```

- [ ] **Step 3: Confirmar compilação**

Run: `docker logs dspace-angular --since 2m 2>&1 | grep -i "compiled successfully"`
Expected: `Compiled successfully` (o template ainda aponta para o link antigo, então nada quebra).

---

### Task 3: Template do menu

**Files:**
- Modify: `dspace-angular/source/src/themes/custom/app/shared/auth-nav-menu/user-menu/user-menu.component.html:35-43`

- [ ] **Step 1: Substituir o bloco de administração**

Trocar o bloco `@if (administrationAvailable$ | async) { ... }` por:

```html
    @if (administrationAvailable$ | async) {
      <li class="ds-menu-item-wrapper pcirn-user-menu-admin" role="presentation">
        <button type="button"
          class="ds-menu-item pcirn-user-menu-admin-toggle"
          [attr.aria-expanded]="adminMenuOpen"
          aria-controls="pcirn-user-menu-admin-list"
          (click)="toggleAdminMenu($event)">
          <i class="fas fa-shield-halved fa-fw" aria-hidden="true"></i>
          <span>{{ 'user-menu.administration' | translate }}</span>
          <i class="fas" [ngClass]="adminMenuOpen ? 'fa-chevron-up' : 'fa-chevron-down'" aria-hidden="true"></i>
        </button>
        @if (adminMenuOpen) {
          <ul id="pcirn-user-menu-admin-list" class="pcirn-user-menu-admin-list" role="menu">
            <li role="presentation">
              <a class="ds-menu-item pcirn-user-menu-admin-item pcirn-user-menu-admin-direct" role="menuitem"
                [routerLink]="['/admin']" (click)="onMenuItemClick()">
                <i class="fas fa-gauge-high fa-fw" aria-hidden="true"></i>
                <span>{{ 'admin.dashboard.title' | translate }}</span>
              </a>
            </li>
            @for (group of (adminSections$ | async); track trackAdminSection($index, group)) {
              <li role="presentation">
                @if (group.items.length > 0) {
                  <button type="button"
                    class="ds-menu-item pcirn-user-menu-admin-group"
                    [attr.aria-expanded]="isAdminSectionExpanded(group.section)"
                    [attr.aria-controls]="'pcirn-admin-group-' + group.section.id"
                    (click)="toggleAdminSection(group.section, $event)">
                    <i class="fas fa-{{ group.section.icon ?? 'cog' }} fa-fw" aria-hidden="true"></i>
                    <span>{{ getAdminSectionText(group.section) | translate }}</span>
                    <i class="fas" [ngClass]="isAdminSectionExpanded(group.section) ? 'fa-chevron-up' : 'fa-chevron-down'" aria-hidden="true"></i>
                  </button>
                  @if (isAdminSectionExpanded(group.section)) {
                    <ul [attr.id]="'pcirn-admin-group-' + group.section.id" class="pcirn-user-menu-admin-items" role="menu">
                      @for (item of group.items; track trackAdminSection($index, item)) {
                        <li role="presentation">
                          @if (getAdminSectionLink(item); as link) {
                            <a class="ds-menu-item pcirn-user-menu-admin-item" role="menuitem"
                              [routerLink]="link" (click)="onMenuItemClick()">
                              {{ getAdminSectionText(item) | translate }}
                            </a>
                          } @else if (isAdminSectionAction(item)) {
                            <button type="button" class="ds-menu-item pcirn-user-menu-admin-item pcirn-user-menu-admin-action"
                              role="menuitem" (click)="executeAdminSection(item)">
                              {{ getAdminSectionText(item) | translate }}
                            </button>
                          }
                        </li>
                      }
                    </ul>
                  }
                } @else if (getAdminSectionLink(group.section); as link) {
                  <a class="ds-menu-item pcirn-user-menu-admin-item pcirn-user-menu-admin-direct" role="menuitem"
                    [routerLink]="link" (click)="onMenuItemClick()">
                    <i class="fas fa-{{ group.section.icon ?? 'cog' }} fa-fw" aria-hidden="true"></i>
                    <span>{{ getAdminSectionText(group.section) | translate }}</span>
                  </a>
                } @else if (isAdminSectionAction(group.section)) {
                  <button type="button" class="ds-menu-item pcirn-user-menu-admin-item pcirn-user-menu-admin-action"
                    role="menuitem" (click)="executeAdminSection(group.section)">
                    <i class="fas fa-{{ group.section.icon ?? 'cog' }} fa-fw" aria-hidden="true"></i>
                    <span>{{ getAdminSectionText(group.section) | translate }}</span>
                  </button>
                }
              </li>
            }
          </ul>
        }
      </li>
    }
```

Regras: grupos fechados por padrão; o toggle não fecha o dropdown (`stopPropagation`); ação fecha o dropdown e só então executa o modal; links fecham o dropdown.

- [ ] **Step 2: Confirmar compilação**

Run: `docker logs dspace-angular --since 2m 2>&1 | grep -i "compiled successfully"`
Expected: `Compiled successfully` sem erro de template.

---

### Task 4: Estilos

**Files:**
- Modify: `dspace-angular/source/src/themes/custom/app/shared/auth-nav-menu/user-menu/user-menu.component.scss`

- [ ] **Step 1: Ajustar o bloco de administração**

Substituir a regra `.pcirn-user-menu-admin` existente (linhas 135-157) por:

```scss
  .pcirn-user-menu-admin {
    margin: .78rem .9rem .7rem !important;
  }

  .pcirn-user-menu-admin-toggle,
  .pcirn-user-menu-admin-group,
  .pcirn-user-menu-admin-direct,
  .pcirn-user-menu-admin-action {
    display: flex;
    align-items: center;
    gap: .48rem;
    width: 100%;
    padding: .55rem .6rem;
    border: 0;
    border-radius: .5rem;
    background: #eaf4f7;
    color: var(--pcirn-menu-ink);
    font: inherit;
    font-size: .76rem;
    font-weight: 800;
    text-align: left;

    > i:first-child { color: var(--pcirn-menu-blue); flex: 0 0 auto; }
    > span { flex: 1; min-width: 0; }
    > i:last-child { color: var(--pcirn-menu-gold); font-size: .66rem; }

    &:hover,
    &:focus-visible {
      background: #dceef3;
      color: var(--pcirn-menu-ink);
    }
  }

  .pcirn-user-menu-admin-list {
    margin: .35rem 0 0;
    padding: 0;
    list-style: none;
    max-height: min(60vh, 30rem);
    overflow-y: auto;
  }

  .pcirn-user-menu-admin-group,
  .pcirn-user-menu-admin-direct,
  .pcirn-user-menu-admin-action {
    background: #f4f8fc;
    border: 1px solid #e4edf3;
    font-size: .73rem;
    font-weight: 700;
  }

  .pcirn-user-menu-admin-items {
    margin: .18rem 0 .3rem .85rem;
    padding: 0;
    list-style: none;
    border-left: 2px solid #e1edf3;
  }

  .pcirn-user-menu-admin-item {
    display: block;
    width: 100%;
    margin: 0;
    padding: .42rem .55rem;
    border: 0;
    border-radius: .38rem;
    background: transparent;
    color: #245c79;
    font: inherit;
    font-size: .71rem;
    font-weight: 600;
    text-align: left;
    text-decoration: none;

    &:hover,
    &:focus-visible {
      background: var(--pcirn-menu-mist);
      color: var(--pcirn-menu-blue);
    }
  }

  .pcirn-user-menu-admin-action {
    cursor: pointer;
  }
```

- [ ] **Step 2: Confirmar compilação**

Run: `docker logs dspace-angular --since 2m 2>&1 | grep -i "compiled successfully"`
Expected: `Compiled successfully`.

---

### Task 5: Teste de script e verificação final

**Files:**
- Create: `dspace-angular/source/scripts/pcirn-user-menu-admin.test.mjs`

- [ ] **Step 1: Escrever o teste**

```js
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const scriptDir = dirname(fileURLToPath(import.meta.url));
const srcDir = join(scriptDir, '..', 'src');
const userMenuDir = join(srcDir, 'themes', 'custom', 'app', 'shared', 'auth-nav-menu', 'user-menu');

function read(...parts) {
  return readFileSync(join(...parts), 'utf8');
}

test('user menu builds the admin tree from MenuID.ADMIN without hanging', () => {
  const component = read(userMenuDir, 'user-menu.component.ts');

  assert.match(component, /MenuID\.ADMIN/);
  assert.match(component, /getMenuTopSections\(MenuID\.ADMIN\)/);
  assert.match(component, /getSubSectionsByParentID\(MenuID\.ADMIN, section\.id\)/);
  assert.match(component, /sections\.length === 0/);
});

test('user menu renders collapsible groups with links and actions', () => {
  const template = read(userMenuDir, 'user-menu.component.html');

  assert.match(template, /pcirn-user-menu-admin-list/);
  assert.match(template, /adminMenuOpen/);
  assert.match(template, /aria-expanded/);
  assert.match(template, /toggleAdminSection\(group\.section, \$event\)/);
  assert.match(template, /isAdminSectionExpanded\(group\.section\)/);
  assert.match(template, /executeAdminSection\(item\)/);
  assert.match(template, /\[routerLink\]="link"/);
  assert.match(template, /'admin\.dashboard\.title' \| translate/);
  assert.match(template, /adminMenuInstanceId/);
});

test('toggling a group does not close the dropdown and actions close it first', () => {
  const component = read(userMenuDir, 'user-menu.component.ts');

  assert.match(component, /toggleAdminSection\(section: MenuSection, event: Event\)[\s\S]*?event\.stopPropagation\(\)/);
  assert.match(component, /executeAdminSection\(section: MenuSection\)[\s\S]*?this\.onMenuItemClick\(\)[\s\S]*?\.function\(\)/);
});

test('menu service emits an empty list for sections without children', () => {
  const service = read(srcDir, 'app', 'shared', 'menu', 'menu.service.ts');

  assert.match(
    service,
    /switchMap\(\(ids: string\[\]\) => isNotEmpty\(ids\)\s*\?\s*observableCombineLatest\(ids\.map\(\(id: string\) => this\.getMenuSection\(menuID, id\)\)\)\s*:\s*of\(\[\]\),/,
  );
});

test('user menu styles cover the admin groups', () => {
  const styles = read(userMenuDir, 'user-menu.component.scss');

  assert.match(styles, /\.pcirn-user-menu-admin-list/);
  assert.match(styles, /\.pcirn-user-menu-admin-items/);
  assert.match(styles, /\.pcirn-user-menu-admin-group/);
});
```

- [ ] **Step 2: Rodar o teste**

Run: `node --test scripts/pcirn-user-menu-admin.test.mjs` em `dspace-angular/source`
Expected: `pass 5`.

- [ ] **Step 3: Rodar a suíte completa**

Run: `node --test scripts/pcirn-*.test.mjs` em `dspace-angular/source`
Expected: todos passando, sem regressão nos 102 anteriores.

- [ ] **Step 4: Validação viva**

Com uma conta administradora temporária (criada via `dspace create-administrator` e removida ao final):
1. Abrir o menu do avatar em `/home`, expandir "Administração".
2. Expandir "Editar" e confirmar os três itens.
3. Clicar em "Histórico de e-mails" (link direto) e confirmar navegação.
4. Clicar em "Nova comunidade" (ação) e confirmar que o dropdown fecha e o modal abre.
5. Conferir em viewport móvel (390px) que o acordeão do menu funciona sem overflow horizontal.
6. Abrir `/admin` e confirmar que os cards das seções agora renderizam.

---

## Self-review

- Cobertura do spec: grupos D2 (Tasks 2-4), correção do painel (Task 1), acessibilidade/i18n (Task 3: `aria-expanded`/`aria-controls`, chaves existentes), verificação (Task 5), limites respeitados (nenhuma rota/permissão alterada).
- Sem placeholders: todos os passos trazem código completo.
- Consistência de tipos: `AdminMenuGroup`, `adminSections$`, `expandedAdminSections`, `toggleAdminSection`, `isAdminSectionExpanded`, `getAdminSectionText`, `getAdminSectionLink`, `isAdminSectionAction`, `executeAdminSection` usados de forma idêntica em ts, html, scss e teste.

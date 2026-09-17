# PCIRN Página de Ajuda / FAQ Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar a nova página institucional de Ajuda / FAQ no frontend Angular da PCIRN (`/info/ajuda`) e corrigir o link correspondente no rodapé, eliminando a rota indevida de sugestões.

**Architecture:** Componente standalone `AjudaComponent` com suporte a temas `ThemedAjudaComponent` sob `src/app/info/ajuda/`, registrado no roteamento de informações (`info-routes.ts`), internacionalizado em `pt-BR.json5` e `en.json5`, e referenciado no `footer.component.html`.

**Tech Stack:** Angular 19/20, SCSS, TypeScript, DSpace ThemedComponent pattern, Node test runner (`node:test`).

---

### Task 1: Atualização dos Testes do Rodapé (TDD)

**Files:**
- Modify: `dspace-angular/source/scripts/pcirn-home.test.mjs`

- [ ] **Step 1: Atualizar asserções de navegação institucional no teste**

Modificar `scripts/pcirn-home.test.mjs` para verificar que o rodapé aponta para `/info/ajuda` e não mais para `/info/feedback`:

```javascript
assert.match(footerTemplate, /routerLink="\/info\/ajuda">Ajuda<\/a>/);
assert.doesNotMatch(footerTemplate, /routerLink="\/info\/feedback">Ajuda<\/a>/);
```

- [ ] **Step 2: Executar o teste e verificar a falha esperada**

Run: `node scripts/pcirn-home.test.mjs`  
Expected: FAIL indicando que `routerLink="/info/ajuda">Ajuda</a>` ainda não foi encontrado no template.

---

### Task 2: Atualização do Rodapé

**Files:**
- Modify: `dspace-angular/source/src/app/footer/footer.component.html:18-20`

- [ ] **Step 1: Ajustar o link no template do rodapé**

Substituir `<a routerLink="/info/feedback">Ajuda</a>` por `<a routerLink="/info/ajuda">Ajuda</a>`.

- [ ] **Step 2: Executar o teste para verificar aprovação**

Run: `node scripts/pcirn-home.test.mjs`  
Expected: PASS no teste do rodapé.

---

### Task 3: Criação do Componente de Ajuda / FAQ

**Files:**
- Create: `dspace-angular/source/src/app/info/ajuda/ajuda.component.ts`
- Create: `dspace-angular/source/src/app/info/ajuda/ajuda.component.html`
- Create: `dspace-angular/source/src/app/info/ajuda/ajuda.component.scss`
- Create: `dspace-angular/source/src/app/info/ajuda/themed-ajuda.component.ts`

- [ ] **Step 1: Criar `ajuda.component.ts`**

Componente standalone com `TranslatePipe`.

- [ ] **Step 2: Criar `ajuda.component.html`**

Estrutura institucional com cabeçalho (`pcirn-list-header`), card principal (`pcirn-about-card`), e as 5 seções de FAQ com numeração destacada e canais de contato com o NUGECID.

- [ ] **Step 3: Criar `ajuda.component.scss`**

Estilos alinhados à identidade visual PCIRN, consistentes com `politica-acesso.component.scss` e `about.component.scss`.

- [ ] **Step 4: Criar `themed-ajuda.component.ts`**

Componente que estende `ThemedComponent<AjudaComponent>` e resolve o componente pelo tema ativo ou tema padrão.

---

### Task 4: Configuração de Rotas e Internacionalização

**Files:**
- Modify: `dspace-angular/source/src/app/info/info-routing-paths.ts`
- Modify: `dspace-angular/source/src/app/info/info-routes.ts`
- Modify: `dspace-angular/source/src/assets/i18n/pt-BR.json5`
- Modify: `dspace-angular/source/src/assets/i18n/en.json5`

- [ ] **Step 1: Definir constantes de rota em `info-routing-paths.ts`**

Adicionar `AJUDA_PATH = 'ajuda'` e `getAjudaPath()`.

- [ ] **Step 2: Registrar rota em `info-routes.ts`**

Adicionar rota para `AJUDA_PATH` com componente `ThemedAjudaComponent`, resolver de breadcrumb e títulos i18n (`info.ajuda.title` e `info.ajuda.breadcrumbs`).

- [ ] **Step 3: Adicionar traduções em `pt-BR.json5` e `en.json5`**

Adicionar:
`"info.ajuda.title": "Ajuda",`
`"info.ajuda.breadcrumbs": "Ajuda",`

---

### Task 5: Validação e Testes Finais

**Files:**
- Test: `dspace-angular/source/scripts/pcirn-home.test.mjs`

- [ ] **Step 1: Executar suíte completa de testes unitários da home/footer**

Run: `node scripts/pcirn-home.test.mjs`  
Expected: PASS com 100% de sucesso.

- [ ] **Step 2: Validar resposta HTTP do container Angular**

Realizar requisição HTTP para a nova rota e verificar retorno 200 e renderização correta.

- [ ] **Step 3: Finalizar sessão do Brainstorm Companion**

Encerrar o servidor do brainstorm e registrar a entrega.

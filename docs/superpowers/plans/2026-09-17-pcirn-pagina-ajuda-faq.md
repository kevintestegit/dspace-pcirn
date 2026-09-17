# PCIRN Página de Ajuda / FAQ Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar a nova página institucional de Ajuda / FAQ no frontend Angular da PCIRN (`/info/ajuda`) e corrigir o link correspondente no rodapé, eliminando a rota indevida de sugestões.

**Architecture:** Componente standalone `AjudaComponent` com suporte a temas `ThemedAjudaComponent` sob `src/app/info/ajuda/`, registrado no roteamento de informações (`info-routes.ts`), internacionalizado em `pt-BR.json5` e `en.json5`, e referenciado no `footer.component.html`.

**Tech Stack:** Angular 19/20, SCSS, TypeScript, DSpace ThemedComponent pattern, Node test runner (`node:test`).

---

### Task 1: Atualização dos Testes do Rodapé (TDD)

**Files:**
- Modify: `dspace-angular/source/scripts/pcirn-home.test.mjs`

- [x] **Step 1: Atualizar asserções de navegação institucional no teste**
- [x] **Step 2: Executar o teste e verificar a falha esperada**

---

### Task 2: Atualização do Rodapé

**Files:**
- Modify: `dspace-angular/source/src/app/footer/footer.component.html:18-20`

- [x] **Step 1: Ajustar o link no template do rodapé**
- [x] **Step 2: Executar o teste para verificar aprovação**

---

### Task 3: Criação do Componente de Ajuda / FAQ

**Files:**
- Create: `dspace-angular/source/src/app/info/ajuda/ajuda.component.ts`
- Create: `dspace-angular/source/src/app/info/ajuda/ajuda.component.html`
- Create: `dspace-angular/source/src/app/info/ajuda/ajuda.component.scss`
- Create: `dspace-angular/source/src/app/info/ajuda/themed-ajuda.component.ts`

- [x] **Step 1: Criar `ajuda.component.ts`**
- [x] **Step 2: Criar `ajuda.component.html`**
- [x] **Step 3: Criar `ajuda.component.scss`**
- [x] **Step 4: Criar `themed-ajuda.component.ts`**

---

### Task 4: Configuração de Rotas e Internacionalização

**Files:**
- Modify: `dspace-angular/source/src/app/info/info-routing-paths.ts`
- Modify: `dspace-angular/source/src/app/info/info-routes.ts`
- Modify: `dspace-angular/source/src/assets/i18n/pt-BR.json5`
- Modify: `dspace-angular/source/src/assets/i18n/en.json5`

- [x] **Step 1: Definir constantes de rota em `info-routing-paths.ts`**
- [x] **Step 2: Registrar rota em `info-routes.ts`**
- [x] **Step 3: Adicionar traduções em `pt-BR.json5` e `en.json5`**

---

### Task 5: Validação e Testes Finais

**Files:**
- Test: `dspace-angular/source/scripts/pcirn-home.test.mjs`

- [x] **Step 1: Executar suíte completa de testes unitários da home/footer**
- [x] **Step 2: Validar compilação e resposta da aplicação Angular**
- [x] **Step 3: Atualizar documentação e registrar entrega**

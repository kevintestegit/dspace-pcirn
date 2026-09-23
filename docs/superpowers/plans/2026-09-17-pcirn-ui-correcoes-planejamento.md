# Plano de Implementação: Correções de UI, Identidade Visual e Páginas do Repositório PCIRN

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sanar as inconsistências de interface, erros de idioma, lacunas de personalização e bloqueios indevidos de navegação identificados na auditoria global do sistema, alinhando todas as páginas públicas e de autenticação à identidade visual oficial da **Polícia Científica do Rio Grande do Norte (PCIRN)**.

**Architecture:**
1. **Navegação & Rótulos Globais:** Ajustar as chaves de tradução em `pt-BR.json5` e `en.json5` e os templates do cabeçalho e rodapé para exibir `"Coleções"` no plural, `"Todo o Acervo"` no seletor de escopo da busca e `"Publicações"` no breadcrumb de pesquisa.
2. **Identidade Visual de Autenticação (`/login` e `/logout`):** Customizar os componentes temáticos em `src/themes/custom/app/login-page/` e `logout-page/`, substituindo o logotipo verde nativo do DSpace pelo Brasão da PCIRN e encapsulando os formulários em cards institucionais elevados.
3. **Adequação Jurídica & LGPD (`/info/privacy` e `/info/end-user-agreement`):** Substituir os textos de modelo genérico americano em inglês por políticas institucionais em português, alinhadas à LGPD (Lei nº 13.709/2018) e à missão da PCIRN, com o padrão de cards já adotado em `about`, `ajuda` e `politica-acesso`.
4. **Desbloqueio da Navegação Pública por Índices (`/browse`):** Remover a guarda de autenticação compulsória da rota `/browse` em `src/app/app-routes.ts`, permitindo que cidadãos e pesquisadores naveguem pelas listagens de documentos por título, autor e data sem redirecionamento para o login.
5. **Páginas de Erro Amigáveis (`/404` e `/403`):** Customizar os componentes `ThemedPageNotFoundComponent` e `ThemedForbiddenComponent` com leiaute institucional, ícones ilustrativos e atalhos rápidos de navegação.

**Tech Stack:** Angular 19 / DSpace Angular, Bootstrap 5 / SCSS tokens PCIRN, `@ngx-translate/core`, Node.js `node:test`, JSON5.

---

### Tarefa 1: Correção de Rótulos na Navbar, Rodapé e Busca

**Arquivos:**
- Modificar: `dspace-angular/source/src/themes/custom/app/navbar/navbar.component.html`
- Modificar: `dspace-angular/source/src/app/footer/footer.component.html`
- Modificar: `dspace-angular/source/src/assets/i18n/pt-BR.json5`
- Modificar: `dspace-angular/source/src/assets/i18n/en.json5`
- Modificar: `dspace-angular/source/src/app/search-page/search-page-routes.ts`
- Teste: `scripts/pcirn-navbar-i18n.test.mjs`

- [x] **Passo 1: Escrever teste de regressão para validar os rótulos de navegação**
  - Verificar que o link para `/collection-list` não utiliza o rótulo singular `"Coleção"`.
  - Verificar que a chave `search.form.scope.all` não contém `"DSpace"` no catálogo pt-BR.
  - Verificar que o breadcrumb de `/search` corresponde a `"Publicações"`.

- [x] **Passo 2: Executar o teste e confirmar as falhas**
  - Executar: `node --test scripts/pcirn-navbar-i18n.test.mjs`

- [x] **Passo 3: Corrigir os templates e catálogos de tradução**
  - Em `navbar.component.html`, trocar `collection.listelement.badge` por `item.page.collections` (`"Coleções"`).
  - Em `footer.component.html`, alinhar o link da coluna de navegação para `item.page.collections`.
  - Em `pt-BR.json5`, alterar `"search.form.scope.all"` de `"Todo o DSpace"` para `"Todo o Acervo"`.
  - Em `en.json5`, manter `"All of Repository"`.
  - Em `search-page-routes.ts`, atualizar `breadcrumbKey` para `publicacoes.search.title` ou garantir exibição consistente de `"Publicações"`.

- [x] **Passo 4: Executar os testes e validar aprovação**
  - Executar: `node --test scripts/pcirn-navbar-i18n.test.mjs scripts/pcirn-i18n.test.mjs`

---

### Tarefa 2: Personalização Institucional das Telas de Login e Logout

**Arquivos:**
- Criar/Modificar: `dspace-angular/source/src/themes/custom/app/login-page/login-page.component.html`
- Criar/Modificar: `dspace-angular/source/src/themes/custom/app/login-page/login-page.component.scss`
- Criar/Modificar: `dspace-angular/source/src/themes/custom/app/logout-page/logout-page.component.html`
- Criar/Modificar: `dspace-angular/source/src/themes/custom/app/logout-page/logout-page.component.scss`
- Teste: `dspace-angular/source/scripts/pcirn-login.test.mjs`

- [x] **Passo 1: Escrever teste de asserção da identidade visual de login**
  - Assegurar que o template de login não referencia `dspace-logo.svg`.
  - Assegurar que referencia `brasao-policia-cientifica-rn.png` ou `brasao-estado-rn.svg`.
  - Assegurar a presença do container/card estilizado `.pcirn-login-card`.

- [x] **Passo 2: Implementar o template e estilo temático de login**
  - Substituir a logo padrão pela marca da Polícia Científica do RN.
  - Estruturar o card centralizado com `border-radius: 12px`, elevação sutil e espaçamento adequado.
  - Estilizar os inputs e o botão de acesso com a cor primária PCIRN (`#07345f`).

- [x] **Passo 3: Implementar o template e estilo de logout**
  - Exibir mensagem de encerramento seguro de sessão com o brasão institucional e botão de retorno à página inicial.

- [x] **Passo 4: Validar compilação e teste**
  - Executar: `node --test dspace-angular/source/scripts/pcirn-login.test.mjs`

---

### Tarefa 3: Adequação Institucional da Política de Privacidade e Termos de Uso

**Arquivos:**
- Criar/Modificar: `dspace-angular/source/src/themes/custom/app/info/privacy/privacy.component.html`
- Criar/Modificar: `dspace-angular/source/src/themes/custom/app/info/privacy/privacy.component.scss`
- Criar/Modificar: `dspace-angular/source/src/themes/custom/app/info/end-user-agreement/end-user-agreement.component.html`
- Criar/Modificar: `dspace-angular/source/src/themes/custom/app/info/end-user-agreement/end-user-agreement.component.scss`
- Modificar: `dspace-angular/source/src/assets/i18n/pt-BR.json5`
- Modificar: `dspace-angular/source/src/assets/i18n/en.json5`
- Teste: `dspace-angular/source/scripts/pcirn-info-legal.test.mjs`

- [x] **Passo 1: Escrever teste para validação de conteúdo legal e ausência de placeholders em inglês**
  - Verificar que o componente de privacidade não contém termos corporativos em inglês como `"Children under the age of 13"`, `"Company" or "We"`.
  - Verificar que o contrato de usuário não contém notas soltas `[a]`.

- [x] **Passo 2: Implementar a Política de Privacidade em Português (LGPD)**
  - Redigir os tópicos: Controladoria de dados da PCIRN, finalidade institucional, tratamento de logs de acesso de acordo com o Marco Civil da Internet e LGPD, transparência e canal da encarregada/DPO via NUGECID.
  - Estruturar em cards com ícones e títulos limpos, seguindo o padrão já consolidado em `about` e `politica-acesso`.

- [x] **Passo 3: Implementar os Termos de Uso Institucionais**
  - Reestruturar as regras de uso do repositório, direitos autorais dos atos e laudos periciais, deveres de integridade da informação e preservação digital.

- [x] **Passo 4: Validar testes**
  - Executar: `node --test dspace-angular/source/scripts/pcirn-info-legal.test.mjs`

---

### Tarefa 4: Desbloqueio da Navegação Pública por Índices (`/browse`)

**Arquivos:**
- Modificar: `dspace-angular/source/src/app/app-routes.ts`
- Teste: `scripts/pcirn-public-read.test.mjs`

- [x] **Passo 1: Atualizar o teste de acesso público**
  - Adicionar asserção em `scripts/pcirn-public-read.test.mjs` verificando que a rota `browse` não possui `authenticatedGuard`.

- [x] **Passo 2: Remover `authenticatedGuard` da rota `browse`**
  - Em `app-routes.ts` (linhas 149–153), remover a restrição para permitir a consulta anônima por título, autor, assunto e data.

- [x] **Passo 3: Validar teste**
  - Executar: `node --test scripts/pcirn-public-read.test.mjs`

---

### Tarefa 5: Telas de Erro Institucionais (404, 403, 500 e Erro Geral)

**Arquivos:**
- Criar/Modificar: `dspace-angular/source/src/themes/custom/app/pagenotfound/pagenotfound.component.html`
- Criar/Modificar: `dspace-angular/source/src/themes/custom/app/pagenotfound/pagenotfound.component.scss`
- Criar/Modificar: `dspace-angular/source/src/themes/custom/app/forbidden/forbidden.component.html`
- Criar/Modificar: `dspace-angular/source/src/themes/custom/app/forbidden/forbidden.component.scss`
- Criar/Modificar: `dspace-angular/source/src/themes/custom/app/page-internal-server-error/page-internal-server-error.component.html`
- Criar/Modificar: `dspace-angular/source/src/themes/custom/app/page-internal-server-error/page-internal-server-error.component.scss`
- Criar/Modificar: `dspace-angular/source/src/themes/custom/app/page-internal-server-error/page-internal-server-error.component.ts`
- Criar/Modificar: `dspace-angular/source/src/themes/custom/app/page-error/page-error.component.html`
- Criar/Modificar: `dspace-angular/source/src/themes/custom/app/page-error/page-error.component.scss`
- Criar/Modificar: `dspace-angular/source/src/themes/custom/app/page-error/page-error.component.ts`
- Teste: `dspace-angular/source/scripts/pcirn-errors.test.mjs`

- [x] **Passo 1: Escrever teste de regressão das páginas de erro**
  - Validar que as páginas 404, 403, 500 e Erro Geral possuem cards estilizados e links úteis de retorno e busca.

- [x] **Passo 2: Implementar templates temáticos com card PCIRN**
  - Inserir badge/ícone institucional, mensagem explicativa acolhedora em português e grupo de botões:
    - *"Ir para o Início"*
    - *"Pesquisar no Acervo"*
    - *"Fale Conosco"*

- [x] **Passo 3: Executar a suíte de testes de erro**
  - Executar: `node --test dspace-angular/source/scripts/pcirn-errors.test.mjs`

---

### Verificação Final e Aceite

- [x] Executar toda a suíte de testes de interface:
  `node --test scripts/pcirn-*.test.mjs dspace-angular/source/scripts/pcirn-*.test.mjs`
- [x] Validar compilação sem erros no contêiner `dspace-angular`.
- [x] Gerar capturas de tela finais das páginas corrigidas via Google Chrome headless para conferência visual.

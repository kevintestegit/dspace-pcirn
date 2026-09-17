# Internacionalização (i18n) do Repositório PCIRN e Localização de Itens

Data: 2026-09-17  
Status: Aprovado pelo solicitante  
Escopo: Frontend Angular (`dspace-angular`), tema customizado PCIRN e exibição de itens do acervo

---

## 1. Objetivo

Garantir que a troca de idioma no seletor do DSpace (`ds-lang-switch`) seja aplicada de forma consistente em todo o sistema:
1. Eliminar textos fixos (*hardcoded*) em português nos componentes customizados da interface (Página Inicial, Rodapé Institucional, Menu do Usuário e cabeçalho de busca).
2. Sincronizar os catálogos de tradução [pt-BR.json5](file:///dados/apps/dspace/dspace-angular/source/src/assets/i18n/pt-BR.json5) e [en.json5](file:///dados/apps/dspace/dspace-angular/source/src/assets/i18n/en.json5), evitando que chaves customizadas sejam exibidas como texto bruto de código.
3. Ativar fallback global no `ngx-translate` para proteger os mais de 30 idiomas padrão mantidos ativos no DSpace, impedindo a quebra de layout quando qualquer idioma adicional for selecionado.
4. Localizar a exibição dos itens e publicações do acervo, traduzindo rótulos de metadados e os tipos documentais (`dc.type`), mantendo integralmente o conteúdo original (título, ementa, resumo) em português.

---

## 2. Decisões de Arquitetura

### 2.1. Fallback Global no `ngx-translate`
- Em [`InitService.initI18n()`](file:///dados/apps/dspace/dspace-angular/source/src/app/init.service.ts), ativar explicitamente `this.translate.setDefaultLang(environment.fallbackLanguage || 'en')`.
- [en.json5](file:///dados/apps/dspace/dspace-angular/source/src/assets/i18n/en.json5) passa a conter todas as chaves existentes no tema PCIRN com cobertura de 100%. Assim, qualquer seleção de idioma no seletor que não tenha a chave customizada traduzida recorrerá automaticamente ao idioma padrão sem falhas ou chaves cruas na tela.

### 2.2. Componentes da Interface Customizada
- **Página Inicial ([`home-page.component.html`](file:///dados/apps/dspace/dspace-angular/source/src/themes/custom/app/home-page/home-page.component.html)):**
  - Hero: substituir strings literais por `pcirn.home.hero.title.*` e `pcirn.home.hero.lead`.
  - Busca e Chips: substituir rótulos por `pcirn.home.search.heading` e `pcirn.home.search.chip.*`.
  - Acesso Rápido: atualizar [`buildQuickAccess()`](file:///dados/apps/dspace/dspace-angular/source/src/themes/custom/app/home-page/pcirn-home-data.service.ts) para fornecer `titleKey` e `descriptionKey`, traduzidos via pipe `translate`.
  - Coleções em Destaque & Métricas: traduzir título de seção, botão "Explorar coleção", mensagens de erro e contadores de *Documentos*, *Coleções* e *Comunidades*.
  - Últimas Publicações: traduzir título, link "Ver todas as publicações", mensagens de lista vazia e erro.
- **Rodapé Institucional ([`footer.component.html`](file:///dados/apps/dspace/dspace-angular/source/src/app/footer/footer.component.html)):**
  - Slogan institucional, títulos de colunas (*Navegação*, *Ajuda e informações*, *Plataforma*), direitos autorais e indicação de desenvolvimento pelo NUGECID extraídos para chaves i18n.
  - Links reaproveitando chaves padrão do DSpace (`home.breadcrumbs`, `communityList.breadcrumbs`, `collection.listelement.badge`, `search.title`, `info.about.title`, etc.).
- **Menu do Usuário ([`user-menu.component.html`](file:///dados/apps/dspace/dspace-angular/source/src/themes/custom/app/shared/auth-nav-menu/user-menu/user-menu.component.html)):**
  - Sincronização obrigatória de `user-menu.add-document`, `user-menu.sectors` e `user-menu.administration` em `en.json5`.
  - Sincronização das 119 chaves presentes em `pt-BR.json5` ausentes no `en.json5`.

### 2.3. Localização de Itens e Tipos Documentais
- **Pipe de Tradução de Tipos Documentais (`PcirnDocumentTypePipe`):**
  - Criar um pipe reutilizável (`dsPcirnDocumentType`) para normalizar e traduzir o valor de `dc.type` (ou `dcterms.type`) via `ngx-translate`.
  - Mapear chaves sob `pcirn.document-type.<KEY>`:
    - `PORTARIA` / `Portaria` → *Portaria* (pt-BR) / *Ordinance* (en)
    - `DECRETO` → *Decreto* (pt-BR) / *Decree* (en)
    - `LEI` → *Lei* (pt-BR) / *Law* (en)
    - `POP` / `Procedimento Operacional Padrão (POP)` → *Procedimento Operacional Padrão (POP)* (pt-BR) / *Standard Operating Procedure (SOP)* (en)
    - `NOTA_TECNICA` / `Nota Técnica` → *Nota Técnica* (pt-BR) / *Technical Note* (en)
    - `Texto` → *Texto* (pt-BR) / *Text* (en)
    - `default` → *Documento* (pt-BR) / *Document* (en)
    - Fallback: se o valor não estiver mapeado no catálogo, o pipe retorna o valor textual original do banco sem lançar erro.
- **Página do Item ([`pcirn-document-item.component.html`](file:///dados/apps/dspace/dspace-angular/source/src/themes/custom/app/item-page/pcirn-document-item/pcirn-document-item.component.html)):**
  - Aplicar o pipe no badge principal de tipo documental e no metadado lateral "Tipo de documento".
  - Substituir `aria-label` fixos por chaves i18n (`pcirn.item.viewer.aria`, `pcirn.item.info.aria`).
  - Preservar o conteúdo textual cadastrado (títulos, resumos, citações e autores em português, conforme deliberado).
- **Últimas Publicações e Busca:**
  - Aplicar o pipe na tag de tipo dos itens exibidos na página inicial e nos resultados de busca.

---

## 3. Fluxo de Dados

1. O usuário seleciona um idioma no dropdown `ds-lang-switch`.
2. [`LocaleService.useLang()`](file:///dados/apps/dspace/dspace-angular/source/src/app/core/locale/locale.service.ts) persiste a escolha no cookie `dsLanguage` e atualiza `TranslateService.use(lang)`.
3. Para cada elemento de tela:
   - Se a chave existir no catálogo do idioma selecionado, renderiza a tradução correspondente.
   - Se a chave não existir no catálogo (ex.: idioma padrão do DSpace sem customização PCIRN), o `ngx-translate` recorre a `setDefaultLang('en')` e renderiza a chave correspondente em inglês.
4. Para itens do repositório:
   - O `dc.type` original do banco é processado por `PcirnDocumentTypePipe`, que busca a tradução no catálogo ativo.
   - Metadados textuais (`dc.title`, `dc.description.abstract`) permanecem com os valores armazenados no banco de dados.

---

## 4. Fora de Escopo

- Tradução automática por IA/serviço externo do corpo do texto ou PDF dos documentos arquivados.
- Desativação dos mais de 30 idiomas padrão do DSpace (requisito do solicitante de mantê-los disponíveis).
- Tradução integral dos textos normativos das páginas institucionais `/info/about` e `/info/politica-acesso`.
- Alterações no schema do banco de dados PostgreSQL ou reindexação do Solr.

---

## 5. Estratégia de Testes e Aceite

1. **Integridade de Catálogos (`scripts/pcirn-i18n.test.mjs`):**
   - Script automatizado em Node.js verificando:
     - Ausência de chaves órfãs PCIRN entre `pt-BR.json5` e `en.json5`.
     - Ausência de texto hardcoded em português nos templates do tema (`home-page`, `footer`, `pcirn-document-item`).
     - Tradução e fallback do pipe `PcirnDocumentTypePipe`.
     - Ativação de `setDefaultLang` no `InitService`.
2. **Validação no Navegador:**
   - Em `pt-BR`: interface totalmente em português, tipos documentais corretos (*Portaria*, *Decreto*, etc.).
   - Em `en`: interface (home hero, quick access, featured collections, metrics, latest publications, footer, user menu, item labels e badge) totalmente em inglês (*Ordinance*, *Decree*, etc.).
   - Em outros idiomas (`es`, `fr`): interface sem chaves quebradas `pcirn.*`, utilizando o fallback configurado.
   - Conteúdo de itens e metadados arquivados mantidos íntegros.

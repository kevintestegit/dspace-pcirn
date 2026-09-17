# Especificação de Design — Página de Ajuda / FAQ PCIRN

Data: 2026-09-17  
Status: Aprovado pelo solicitante (Opção B — Central de Dúvidas Frequentes / FAQ)  
Escopo: Frontend Angular (`dspace-angular`)

---

## 1. Contexto e Diagnóstico

- O link *"Ajuda"* presente no rodapé institucional (`src/app/footer/footer.component.html`) apontava para a rota `/info/feedback`.
- No DSpace padrão com internacionalização em português brasileiro (`pt-BR.json5`), a rota `/info/feedback` corresponde ao formulário nativo de comentários e sugestões, intitulado *"Sugestão"*, com a mensagem *"Obrigado por compartilhar suas sugestões sobre o sistema DSpace. Seus comentários são apreciados!"*.
- Além de causar confusão aos usuários em busca de instruções e suporte, o formulário duplicava a função do link *"Fale conosco"* (`/info/fale-conosco`) localizado ao lado.
- O solicitante optou pela implementação de uma página de Ajuda própria, no formato de **Dúvidas Frequentes (FAQ Direto)**, com orientações claras sobre busca, acesso público x sigiloso, cópia de citações/Handle, depósito por servidores e canais de suporte.

---

## 2. Decisões de Design

1. **Rota e Módulos:**
   - Nova constante de rota: `AJUDA_PATH = 'ajuda'` em `src/app/info/info-routing-paths.ts`.
   - Função auxiliar: `getAjudaPath()` retornando `${getInfoModulePath()}/ajuda`.
   - Registro em `src/app/info/info-routes.ts` mapeando para `ThemedAjudaComponent` com resolver de breadcrumb e títulos i18n (`info.ajuda.title` e `info.ajuda.breadcrumbs`).

2. **Componentes:**
   - Diretório: `src/app/info/ajuda/`
   - `ajuda.component.ts`: Componente standalone importando módulos comuns e de tradução (`TranslatePipe`).
   - `themed-ajuda.component.ts`: Componente herdando de `ThemedComponent` para permitir customização por tema caso necessário.
   - `ajuda.component.html`: Template contendo cabeçalho institucional (`pcirn-list-header`), card principal (`pcirn-about-card`) e seções de FAQ destacadas (`pcirn-about-section`).
   - `ajuda.component.scss`: Estilos alinhados à identidade PCIRN com suporte a design responsivo e ícones de identificação.

3. **Conteúdo das Perguntas e Respostas (FAQ):**
   - **Q1: Como encontrar uma portaria, POP ou documento específico?**  
     Busca por termos, números de portaria e filtros facetados na aba Publicações.
   - **Q2: Qual a diferença entre acesso público e documento com restrição?**  
     Transparência ativa (livre sem login) vs sigilo pericial/LGPD (acesso restrito institucional).
   - **Q3: Como copiar a citação ou o identificador permanente (Handle)?**  
     Uso das ações rápidas "Copiar citação" e "Copiar URI" na página do item.
   - **Q4: Sou servidor da PCIRN. Como faço para submeter documentos?**  
     Autenticação institucional, envio de PDF/A, fluxo de homologação pelo NUGECID e bloco informativo orientando servidores sem acesso ativo a solicitarem a liberação junto ao NUGECID.
   - **Q5: Não encontrei o documento ou preciso de suporte adicional. O que fazer?**  
     Contatos diretos do NUGECID/Arquivo Geral (e-mail e telefone) e link para o Fale Conosco.

4. **Rodapé e Testes:**
   - Atualizar `src/app/footer/footer.component.html`: substituir `<a routerLink="/info/feedback">Ajuda</a>` por `<a routerLink="/info/ajuda">Ajuda</a>`.
   - Manter `<a routerLink="/info/fale-conosco">Fale conosco</a>` intacto para mensagens/sugestões.
   - Atualizar `scripts/pcirn-home.test.mjs` para verificar a presença de `routerLink="/info/ajuda"` no rodapé.

---

## 3. Arquitetura de Arquivos

- **Arquivos novos:**
  - `src/app/info/ajuda/ajuda.component.ts`
  - `src/app/info/ajuda/ajuda.component.html`
  - `src/app/info/ajuda/ajuda.component.scss`
  - `src/app/info/ajuda/themed-ajuda.component.ts`
- **Arquivos modificados:**
  - `src/app/info/info-routing-paths.ts`
  - `src/app/info/info-routes.ts`
  - `src/app/footer/footer.component.html`
  - `src/assets/i18n/pt-BR.json5`
  - `src/assets/i18n/en.json5`
  - `scripts/pcirn-home.test.mjs`

---

## 4. Critérios de Aceite e Testes

- [ ] Acessar `/info/ajuda` renderiza a página de Ajuda com o cabeçalho institucional e as 5 seções de perguntas e respostas.
- [ ] O rodapé exibe o link "Ajuda" apontando para `/info/ajuda`.
- [ ] O link "Fale conosco" permanece apontando para `/info/fale-conosco`.
- [ ] Os testes de regressão em `scripts/pcirn-home.test.mjs` passam com 100% de sucesso.
- [ ] Nenhuma quebra de build ou erro de compilação no Angular.

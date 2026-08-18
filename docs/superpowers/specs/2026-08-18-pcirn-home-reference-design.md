# Design: Home institucional PCIRN com dados reais

**Data:** 2026-08-18  
**Status:** aprovado visualmente; aguardando revisão desta especificação

## Objetivo

Refazer a home pública do repositório para reproduzir a composição aprovada na referência: header institucional claro, hero fotográfica azul, busca sobreposta, acessos rápidos, coleções em destaque, métricas, últimas publicações e rodapé institucional.

A home deve continuar pública e não deve mostrar a sidebar para usuários anônimos.

## Regras de acesso

- Normas e Portarias: conteúdo público, exibido e acessível sem login.
- POPs e Procedimentos: card visível na home, conteúdo protegido; acesso direciona para login.
- Produção Científica: card visível na home, conteúdo protegido; acesso direciona para login.
- Relatórios Técnicos: card visível na home, conteúdo protegido; acesso direciona para login.
- Usuários autenticados podem visualizar as áreas autorizadas conforme as políticas já existentes.
- A home não exibirá dados fictícios. Quando anônimo, listas e métricas devem considerar somente recursos públicos.

## Estrutura visual

### Header

- Fundo branco, logo da Polícia Científica e texto “Repositório Institucional da PCIRN”.
- Navegação: Início, Comunidades, Coleções e Publicações.
- Início recebe estado ativo com sublinhado amarelo.
- Busca e botão Entrar permanecem visíveis para anônimos.
- Estatísticas não aparecem para anônimos.
- A sidebar permanece restrita a usuários autenticados.

### Hero e busca

- Reaproveitar `hero-pcirn.webp` como imagem de fundo.
- Fundo azul escuro com overlay para contraste.
- Título editorial: “Documentos institucionais da PCIRN.”, com “PCIRN” destacado em amarelo.
- Texto institucional curto e sublinhado amarelo.
- Busca ampla sobreposta à base da hero.
- Campo e botão usam o `ThemedSearchFormComponent` existente.
- Atalhos de busca na caixa: Normas e Portarias, POPs e Procedimentos, Produção Científica e Relatórios Técnicos.

### Conteúdo

1. **Acesso rápido:** quatro cards, cada um com ícone, título, descrição e seta. Os cards protegidos permanecem visíveis, mas usam o guard de login no destino.
2. **Coleções em destaque:** três comunidades ou coleções reais retornadas pelo DSpace, com nome, descrição e link. A seleção deve ser determinística e não depender de texto fixo.
3. **Métricas:** documentos, coleções e comunidades, calculados a partir de respostas reais da API e limitados ao universo visível para o usuário.
4. **Últimas publicações:** três itens reais ordenados por data de publicação/acesso, com título, tipo, responsável e data. Para anônimos, somente portarias e documentos públicos.

Estados de carregamento, ausência de dados e erro devem ser tratados sem quebrar a home. Uma falha em um bloco não deve ocultar os demais.

### Rodapé

Manter a identidade visual institucional em azul escuro, com brasão, navegação, ajuda e informações da plataforma. Reaproveitar os assets existentes (`brasao-policia-cientifica-rn.png` e `footer-bg-pcirn.webp`) quando aplicável.

## Dados e integração

Reaproveitar os serviços DSpace existentes no Angular:

- `CommunityDataService` para comunidades públicas/destaques.
- `CollectionDataService` para coleções e contagens.
- `ItemDataService` ou `SearchService` para últimas publicações.
- `SiteDataService` e informações paginadas da API para o site e métricas.

Não criar endpoint paralelo nem manter arrays de conteúdo de exemplo no componente.

O diagnóstico atual mostrou que `/api/core/sites` responde anonimamente, mas comunidades, coleções e itens retornam `401`. Antes da home consumir esses dados publicamente, o backend deve garantir políticas públicas somente para as comunidades/coleções/itens de Normas e Portarias. Os demais recursos permanecem protegidos. Se as contagens públicas não puderem ser obtidas pelos endpoints existentes, deverá ser exposto apenas o mínimo necessário por uma consulta pública de leitura, sem abrir os documentos restritos.

## Componentes e responsabilidades

- `HomePageComponent`: orquestra carregamento, autorização, estados e dados dos blocos.
- Template da home: somente estrutura e bindings; sem lógica de busca ou filtragem complexa.
- Estilos da home: layout responsivo, tokens de cor, hierarquia tipográfica e estados de interação.
- Serviços DSpace existentes: origem dos dados e cache HTTP/NgRx já adotado pelo projeto.
- Políticas/migrações backend: delimitação do acervo público de portarias.

## Responsividade e acessibilidade

- Desktop segue a composição da referência.
- Tablet reduz a navegação e reorganiza cards em duas colunas.
- Mobile empilha hero, busca, cards, coleções, métricas e publicações.
- Todos os cards navegáveis terão foco visível, texto alternativo quando houver imagem e rótulos sem depender apenas de cor ou ícone.
- A busca continuará utilizável por teclado e leitor de tela.

## Validação

- Teste de contrato da home confirma header, hero, quatro blocos, estados de acesso e ausência de conteúdo fictício.
- Testes do componente confirmam carregamento real, filtragem pública para anônimos, conteúdo autorizado para logados e falhas isoladas por bloco.
- Verificação REST anônima confirma que portarias públicas respondem e POPs/produção/relatórios continuam protegidos.
- Verificação visual em `http://10.9.233.96:4000/home` após recompilação do container Angular.
- `git diff --check` e build/teste Angular focalizado antes da entrega.

## Fora do escopo

- Alterar o fluxo de aprovação NUGECID já definido.
- Criar novas contas, papéis ou telas administrativas.
- Liberar POPs, produção científica ou relatórios para anônimos.
- Gerar novas imagens bitmap quando os assets institucionais existentes atenderem à referência.

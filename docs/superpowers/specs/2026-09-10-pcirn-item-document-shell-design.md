# Shell institucional PCIRN para visualização pública de Items

## Objetivo

Aplicar a identidade visual do mockup PCIRN a todas as visualizações públicas de documentos em `/items/:uuid`, incluindo a visualização simples, a visualização completa (`/full`), Items sem thumbnail, Items com um ou vários arquivos e Items com conjuntos diferentes de metadados.

O comportamento funcional do DSpace permanece a fonte de verdade: o shell não fixa UUID, título, autor, arquivo, URI ou conteúdo de metadado. Páginas administrativas, edição, submissão, workflow e entidades que não sejam visualizações públicas de documentos permanecem fora do escopo.

## Contexto confirmado

- O projeto efetivo está em `/dados/apps/dspace`.
- O tema ativo possui sobrescritas em `dspace-angular/source/src/themes/custom`.
- Os wrappers customizados de `ItemPageComponent` e `FullItemPageComponent` ainda apontam para templates base; os templates customizados de Item genérico e Publication estão vazios.
- A seleção pública atual usa `UntypedItemComponent` para Items genéricos e `PublicationComponent` para Publications.
- Os componentes nativos já fornecem thumbnail, visualizador de mídia, arquivos/downloads, autores relacionados, data, resumo, URI, coleções, menu administrativo e retorno aos resultados.
- Existem assets PCIRN em `dspace-angular/source/src/assets/pcirn/images`, incluindo o brasão institucional.

## Direção visual

O shell seguirá uma direção de portal institucional editorial: branco dominante, azul-marinho para hierarquia e navegação, teal para ações de arquivo, dourado apenas como linha/acento, superfícies claras azuladas, bordas suaves e sombra baixa. A composição será densa o suficiente para consulta de documento, sem aparência de dashboard.

Estrutura visual:

1. Header compacto com marca PCIRN à esquerda, navegação funcional existente ao centro e busca/idioma/autenticação à direita.
2. Breadcrumb em faixa clara, com ícone inicial, separadores discretos e truncamento seguro.
3. Área pública de Item em duas colunas no desktop: cartão de arquivo/metadados laterais e cartão principal de conteúdo.
4. Cartão principal com badge de tipo, título, resumo, palavras-chave, URI e citação somente quando houver dados reais.
5. Em mobile, uma coluna com título e tipo antes do arquivo, seguida pelos blocos disponíveis.

## Arquitetura

### Shell compartilhado

Criar um componente de apresentação no tema `custom`, referido nesta especificação como `PcirnDocumentItemComponent`. Ele receberá o `Item` já carregado pela página pública e estenderá o comportamento do componente base de Item para manter `showBackButton$`, `back`, rota do Item, configuração de mídia e estado IIIF.

O componente renderizará o layout visual e reutilizará componentes DSpace existentes para as partes que possuem lógica funcional:

- `ThemedThumbnailComponent` para preview e placeholder nativo;
- `ThemedMediaViewerComponent` e Mirador quando a configuração/Item exigirem;
- `ThemedFileSectionComponent`/`ThemedFileDownloadLinkComponent` para arquivos, paginação e políticas de acesso;
- `ItemPageDateFieldComponent`, `ThemedMetadataRepresentationListComponent`, `ItemPageAbstractFieldComponent`, `GenericItemPageFieldComponent` e `ItemPageUriFieldComponent` para os metadados;
- `ThemedResultsBackButtonComponent` e `DsoEditMenuComponent` para navegação e ações autorizadas.

O shell não duplicará chamadas REST nem implementará autorização paralela. A ausência de thumbnail, resumo, assunto, URI, citação ou qualquer outro campo fará o bloco correspondente desaparecer ou compactar o espaço sem texto substituto inventado. A seção de arquivos continuará mostrando todos os bitstreams autorizados; o primeiro arquivo poderá receber tratamento visual de destaque, sem remover arquivos adicionais.

### Wrappers públicos

Os templates customizados de `UntypedItemComponent` e `PublicationComponent` serão reduzidos a adaptadores do shell compartilhado, preservando seus decorators de seleção de componente e o registro do tema. Assim, Items genéricos e Publications usarão exatamente a mesma estrutura pública sem alterar rotas ou APIs.

O template customizado de `FullItemPageComponent` usará o mesmo shell quando a rota for uma visualização pública normal. Estados originados de workspace/workflow continuarão protegidos pelo fluxo nativo e não serão transformados em tela pública de documento.

### Header e breadcrumb

As sobrescritas atuais de Header e Breadcrumbs passarão a possuir templates próprios no tema `custom`, mantendo os componentes funcionais existentes para busca, idioma, autenticação, menu responsivo e navegação. O footer customizado não será alterado.

O header usará o asset real `brasao-policia-cientifica-rn.png`, se compatível com o uso atual, com fallback apenas entre assets PCIRN já existentes caso a inspeção final de dimensões exija outro arquivo. Nenhum asset externo será adicionado.

### Traduções e conteúdo

Textos de interface novos usarão chaves de tradução existentes quando houver correspondência e chaves do tema custom quando necessário. Valores exibidos no documento virão do `Item`, de relações e de bitstreams reais. Labels genéricos como “Documento” só serão usados como rótulo de interface quando não houver tipo; não serão usados para fabricar metadados ausentes.

## Dados e regras de exibição

- Título: nome do Item por `dsoNameService`/campo nativo.
- Tipo: metadado de tipo real, quando disponível; badge genérico de interface somente quando não houver valor.
- Preview: thumbnail/visualizador nativo, com cartão de ausência natural quando não houver thumbnail.
- Download: bitstreams do bundle `ORIGINAL`, usando o link nativo para respeitar `READ`, autenticação e tokens.
- Tamanho e formato: dados do bitstream/metadado real, sem valores do mockup.
- Data: `dc.date.issued` através do componente nativo de data.
- Autores: `dc.contributor.author`/`dc.creator` através da representação nativa.
- Resumo: `dc.description.abstract`; descrição adicional somente se o componente nativo já a disponibilizar como campo configurado.
- Palavras-chave: valores reais de `dc.subject`, apresentados com wrap visual.
- URI: `dc.identifier.uri`/componente nativo; nenhum handle será inventado.
- Citação: `dc.identifier.citation` quando existir; botão de copiar somente para valor efetivamente renderizado.
- Campos adicionais: continuam acessíveis através dos componentes nativos e/ou da visualização completa, sem apagar metadados que não cabem no mockup.

## Acessibilidade e responsividade

Manter elementos semânticos, links e botões reais, labels, texto alternativo do thumbnail, foco visível, contraste adequado e navegação por teclado. O grid usará os breakpoints Bootstrap existentes: duas colunas em desktop/tablet largo, redução proporcional em tablet e uma coluna em mobile. Títulos e breadcrumbs usarão quebra/truncamento controlado sem overflow horizontal.

## Estados e riscos

- Loading e erro continuarão no wrapper público nativo.
- Alertas, versões e ações administrativas permanecerão no fluxo da página pública sem expor ações para usuários não autorizados.
- Bitstream restrito continuará usando o componente de download existente; a nova aparência não fará requisições sem autorização.
- Vários arquivos serão mantidos, mesmo que o mockup mostre um botão principal.
- Items sem dados opcionais não exibirão seções vazias.
- Tipos especiais não-documentais, como entidades de pessoa/periódico, não serão redirecionados para o shell documental.

## Verificação

1. Teste focalizado de templates/tema e `git diff --check`.
2. Build Angular do tema customizado no fluxo Docker já usado pelo projeto.
3. Validação da rota de exemplo e de Items com: PDF com thumbnail, sem thumbnail, vários arquivos, metadados parciais e arquivo restrito.
4. Verificação em desktop, tablet e mobile, incluindo header, breadcrumb, download, links, copiar URI/citação quando implementado, foco e ausência de erros no console.
5. Regressão visual rápida de Home, comunidade, coleção, login e footer, sem alterar seus contratos funcionais.

## Limites da implementação

Não serão alterados backend Java, REST, banco, schema de metadados, permissões, workflow, configuração de submissão, bibliotecas externas ou componentes do tema padrão quando uma sobrescrita do `custom` for suficiente.

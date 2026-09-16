# PCIRN header zoom stability

## Objetivo

Manter o bloco de marca da PCIRN alinhado dentro da faixa azul quando o usuário reduzir o zoom da página.

## Desenho

- Ajustar somente `header-navbar-wrapper.component.scss`.
- Usar `80px` como altura do masthead em larguras desktop a partir de `768px`, removendo a transição `80px -> 64px` ao cruzar `1599.98px`.
- Preservar brasão, textos, navegação, busca, idioma, autenticação e layout mobile.
- Atualizar `pcirn-home.test.mjs` para proteger a altura desktop contra o salto para `64px`.

## Validação

- O teste focado deve falhar antes da alteração e passar depois.
- Executar build Angular e `git diff --check`.
- Conferir visualmente a header em 100% e 67% de zoom.

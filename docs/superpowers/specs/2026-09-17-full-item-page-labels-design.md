# Full item page: rótulos amigáveis + deploy fix divs invisíveis

Data: 2026-09-17
Status: aprovado pelo usuário (3/3 seções)

## Contexto

1. Simple item page renderizava `div.simple-view-element.d-none` vazias com `h2` (Título da Revista, ISSN da Revista, Título do Volume, Avaliação) para itens sem esses metadados. Causa: `publication.component.html` declara campos incondicionalmente; `item-page-field.component.html` e `metadata-values.component.html` sem guarda; `metadata-field-wrapper` só aplica `d-none` via CSS.
   Fix aplicado (working tree submódulo `dspace-angular/source`): `@if (item?.allMetadata(fields)?.length > 0)` em `item-page-field.component.html` e `uri/item-page-uri-field.component.html`. Host `<ds-generic-item-page-field>` vazio permanece (Angular não remove próprio host de dentro) — sem filhos, sem label.
2. Full item page (`/full`, "Metadados completos") faz dump cru `{{mdEntry.key}} | {{mdValue.value}} | {{mdValue.language}}` (`full-item-page.component.html:21-35`). Comportamento stock, não bug. Decisão: exibir rótulos amigáveis via i18n.

## Mudanças

### 1. Template full page (1 edit)

`dspace-angular/source/src/app/item-page/full/full-item-page.component.html:27`:

```html
<td>{{ ('metadata.' + mdEntry.key) | translate }}</td>
```

Colunas valor/idioma inalteradas. Vale para todos os tipos de item/entidade.

### 2. Entradas i18n (2 edits: `en.json5`, `pt-BR.json5`)

Chaves `metadata.<campo>` (tabela en/pt-BR na seção 2 aprovada: author, coverage.temporal, date.accessioned, date.issued, description.abstract, format.extent, identifier.other, identifier.uri, language, publisher, rights, source, subject, title, type).

Regra fallback: chave sem tradução → ngx-translate devolve a chave `metadata.dc.*` crua... NOTA: pipe `translate` retorna a própria string `metadata.dc.x` quando ausente, NÃO `dc.x`. Template precisa normalizar: se traduzido começa com `metadata.`, mostra `mdEntry.key` cru. Implementação trata isso (pipe dedicado ou comparação no template). Outros idiomas sem tradução caem no fallback cru sem quebrar. Novos campos futuros aparecem crus até traduzidos.

### 3. Deploy + verificação

- Rebuild imagem Angular + restart (edits presos no working tree do submódulo, deploy pendente — causa do "ainda continua").
- Hard-refresh (cache browser).
- Inspector item sem `journal.*`: sem `div.simple-view-element.d-none` / `h2` desses campos.
- Full page pt-BR: rótulos; idioma sem tradução: fallback cru.

## Fora de escopo

- Guardas por campo em `publication/untyped-item.component.html` (host vazio aceito).
- Esconder campos da full page; remover coluna idioma; suite nova de testes (specs existentes cobrem caso com-valor).

## Riscos

- `keyvalue` pipe não garante ordem das linhas — inalterado por este design.
- `metadata.` + chave com caracteres especiais: chaves DSpace são `[a-z.]+`, seguro para lookup i18n.

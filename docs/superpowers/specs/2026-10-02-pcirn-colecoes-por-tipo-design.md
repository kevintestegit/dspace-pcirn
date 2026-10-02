# Coleções PCIRN organizadas por tipo documental

## Objetivo

A página **Coleções** deve apresentar somente sete categorias documentais. Ao abrir uma categoria, a pessoa verá os itens daquele tipo em uma busca global, independentemente da comunidade de origem, respeitando a visibilidade já aplicada pelo DSpace.

## Categorias

1. Portarias e Atos Normativos
2. Procedimento Operacional Padrão (POP)
3. Procedimento Administrativo Padrão (PAP)
4. Guias e Manuais
5. Notas Técnicas
6. Relatório de Produtividade e Prestação de Contas
7. Memória Institucional

## Desenho

A página de Coleções deixará de enumerar coleções reais e exibirá sete links para páginas de busca por configuração (`/search/<configuração>`). As buscas usarão o campo `itemtype`, sem escopo de comunidade ou coleção, e conservarão os filtros comuns para exibir apenas itens atuais, não retirados e descobríveis.

As configurações existentes de POP e Relatórios serão reutilizadas. A busca de Portarias e Atos Normativos será ampliada para incluir `PORTARIA`, `PORTARIA_E_ATO_NORMATIVO_INTERNO`, `DECRETO` e `LEI`. Serão acrescentadas configurações para PAP, Guias e Manuais, Notas Técnicas e Memória Institucional. Guias e Manuais incluirá `MANUAL_GUIA` e `MANUAL_GESTAO`; Notas Técnicas usará `NOTA_TECNICA`; a categoria PAP usará o novo valor `PAP`; e Memória Institucional usará o novo valor `MEMORIA_INSTITUCIONAL`.

Os dois novos valores serão incluídos no vocabulário controlado PCIRN para que possam ser selecionados no cadastro de documentos, com rótulos em português e inglês. Os itens existentes não serão reclassificados automaticamente: só aparecerão nessas buscas após receberem o tipo correspondente. O restante do processo de submissão não muda.

## Componentes e arquivos

- `dspace-angular/source/src/themes/custom/app/collection-list-page/`: substituir a obtenção e exibição de coleções por links às sete buscas globais.
- `dspace/config/controlled-vocabularies/pcirn-document-types.xml`: cadastrar PAP e Memória Institucional.
- `dspace/config/spring/api/discovery.xml`: registrar buscas e filtros globais por categoria.
- `dspace-angular/source/src/assets/i18n/pt-BR.json5` e `en.json5`: rótulos das sete categorias e dos novos tipos.

## Permissões e comportamento

O DSpace continua responsável por excluir itens retirados ou não descobríveis. A pesquisa sem escopo permite combinar itens de comunidades distintas; o acesso individual aos itens segue as permissões atuais. Paginação, filtros e ordenação são fornecidos pela página de busca configurada existente.

## Validação

- Confirmar as sete entradas e seus destinos na página de Coleções.
- Confirmar os novos valores PAP e Memória Institucional no vocabulário usado para submissão.
- Confirmar que cada busca usa os tipos previstos, não restringe por comunidade e mantém os filtros globais de visibilidade e versão.
- Executar validação de compilação Angular e verificação de configuração Spring/XML aplicável.

## Critérios de aceite

- A página Coleções mostra apenas as sete categorias acima, na ordem definida.
- Abrir uma categoria mostra todos os itens classificados com os tipos associados, provenientes de todas as comunidades acessíveis.
- PAP e Memória Institucional podem ser atribuídos em novas submissões.
- Itens antigos sem esses valores permanecem fora das buscas até serem classificados.
- Nenhuma coleção ou item tem permissões alteradas por essa mudança.

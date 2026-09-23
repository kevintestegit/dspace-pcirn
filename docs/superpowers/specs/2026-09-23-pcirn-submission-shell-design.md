# Shell PCIRN para criação e revisão de documentos

## Objetivo

Aplicar a identidade visual PCIRN à página de criar/editar documento (submissão), hoje renderizada com a UI padrão do DSpace. O shell cobre as duas rotas que usam o mesmo componente:

- `/workspaceitems/:id/edit` — depósito do servidor/gestor setorial.
- `/workflowitems/:id/edit` — revisão pelo NUGECID.

O comportamento funcional permanece o do DSpace: criação do workspaceitem, autosave, seções configuradas em `item-submission.xml`, upload, licença, workflow e permissões não são alterados.

## Contexto confirmado

- O tema ativo é `dspace-angular/source/src/themes/custom`.
- Existem 8 componentes de submissão registrados no tema custom, mas todos com os templates custom vazios e `templateUrl`/`styleUrls` apontando para o template base (`custom/app/submission/form/submission-form.component.ts:15-18`, `custom/app/submission/submit/submission-submit.component.ts:7-10`, `custom/app/submission/sections/container/section-container.component.ts:16-19`, `custom/app/submission/form/footer/submission-form-footer.component.ts:11-14`, `custom/app/submission/edit/submission-edit.component.ts:8-11`, `custom/app/submission/sections/upload/file/section-upload-file.component.ts:12-15`, `custom/app/submission/form/submission-upload-files/submission-upload-files.component.ts:8-9`, `custom/app/submission/import-external/submission-import-external.component.ts:16-19`).
- `custom/styles/_global-styles.scss` não importa nenhum partial de submissão; o único estilo relacionado é `_pcirn-workflow.scss`, que estiliza apenas os cards de tarefa do MyDSpace.
- O fluxo PCIRN (`dspace/config/item-submission.xml:288-294`) tem as seções: `pcirnpageone`, `pcirnpagetwo`, `upload` e `license`, além da etapa especial de coleção.
- As duas rotas de edição usam `ThemedSubmissionEditComponent` (`workspaceitems-edit-page-routes.ts:35`, `workflowitems-edit-page-routes.ts:37`).
- O padrão visual PCIRN já consolidado usa cards brancos, borda `#dfe6ec`, radius `.45–.85rem`, azul `#07345f`, teal para ações de arquivo, tipografia `--pcirn-fs-*` e partials `_pcirn-*.scss` importados em `_global-styles.scss`.
- Não há estilo PCIRN para `ds-uploader` nem para os campos de `ds-form` da submissão.

## Direção visual

Mesma linguagem editorial do restante do sistema: fundo claro, superfícies brancas, azul-marinho para hierarquia e ação primária, teal para arquivos, dourado apenas como acento. A página é um formulário denso: cabeçalho institucional, card de upload, acordeão de seções e barra de ações fixa. Sem aparência de dashboard e sem barra lateral.

Estrutura visual:

1. Cabeçalho da página com título, coleção selecionada e estado de salvamento.
2. Card de upload com dropzone nativa.
3. Linha de contexto com o seletor de coleção (quando modificável) e o botão "Adicionar mais".
4. Acordeão de seções, cada seção como card com título, ícone de estado e ação de remover quando não obrigatória.
5. Barra de ações fixa com descartar, salvar, salvar para depois e depositar.
6. Em mobile, coluna única; a barra de ações continua acessível e os botões quebram linha em vez de estourar a largura.

## Arquitetura

### Princípio

Nenhuma lógica muda. Os templates custom preservam exatamente os bindings, eventos, diretivas, `id` e `data-test` dos templates base; a mudança é de estrutura e classes. Os componentes continuam estendendo as classes base e sendo resolvidos pelo mecanismo de tema existente (`getComponentName()`), sem alterar seletores de registro.

### Componentes

**`custom/app/submission/edit/submission-edit.component.html|scss`** — shell da página. Envolve o `<ds-submission-form>` com os mesmos inputs do template base (`collectionId`, `sections`, `selfUrl`, `submissionDefinition`, `submissionErrors`, `item`, `collectionModifiable`, `submissionId`) e adiciona o cabeçalho institucional. Não duplica lógica de carregamento, que permanece no `SubmissionEditComponent` base.

**`custom/app/submission/form/submission-form.component.html|scss`** — formulário. Mantém `isLoading$`, `uploadEnabled$`, `submissionSections$`, `uploadFilesOptions`, `collectionId`, `submissionId` e os componentes `ds-submission-upload-files`, `ds-submission-form-collection`, `ds-submission-form-section-add`, `ds-submission-section-container` e `ds-submission-form-footer`. Reorganiza o cabeçalho em card de upload + linha de contexto, mantém o `ds-loading` e o loop de seções.

**`custom/app/submission/sections/container/section-container.component.html|scss`** — acordeão. Mantém a diretiva `dsSection`, `ngb-accordion` com `activeIds` e `destroyOnHide`, o título traduzido, os quatro estados de ícone (warning, erro, válido, info), a remoção de seção não obrigatória, os alertas de erro genérico e o `ngComponentOutlet`. Muda apenas a apresentação do painel.

**`custom/app/submission/form/footer/submission-form-footer.component.html|scss`** — barra de ações. Mantém `submissionId`, os botões `discard`, `save`, `saveForLater`, `deposit`, os estados `processingSaveStatus`, `processingDepositStatus`, `hasUnsavedModification`, `showDepositAndDiscard`, os `data-test`, a barra de progresso e o modal de confirmação de descarte.

**`custom/app/submission/sections/upload/file/section-upload-file.component.html|scss`** — linha de arquivo. Mantém o switch de bitstream primário, `ds-submission-section-upload-file-view`, `ds-file-download-link`, os botões de editar/excluir, os estados de processamento e o modal de exclusão.

**`custom/styles/_pcirn-submission.scss`** — estilos que não podem ser encapsulados nos componentes: dropzone e lista do `ds-uploader`, campos e grupos do `ds-form`, modais e detalhes do acordeão que dependem de `::ng-deep`. Importado por `_global-styles.scss`.

### Dados

Nenhuma fonte de dados nova. Título, coleção, arquivos, tamanhos, metadados, erros e permissões continuam vindo do `SubmissionService`, do store e da configuração de submissão. Nenhum texto de seção ou metadado é inventado no template.

### i18n

Reutilizar as chaves existentes (`submission.general.*`, `submission.sections.*`, `submission.sections.upload.*`, `submission.edit.title`). Nenhuma chave nova nesta entrega. Se o wording do título precisar mudar para "Depósito de documento", isso vira uma chave PCIRN em iteração separada.

## Acessibilidade e responsividade

- Preservar `aria-label`, `role`, `title`, `tabindex`, foco visível e navegação por teclado dos templates base.
- Ícones de estado mantêm `role="img"` e `aria-label` traduzidos.
- Botões continuam `<button>` reais; nenhum clique em `div`.
- Grid com os breakpoints Bootstrap existentes: uma coluna em mobile, barra de ações com wrap e alvos de toque adequados.
- A barra de ações fixa não pode cobrir o último campo: reservar espaçamento inferior no conteúdo.

## Estados e riscos

- Loading, erros de seção, "nenhum arquivo enviado", botões desabilitados durante save/deposit e a barra de progresso continuam nativos.
- Risco: cópia de templates base envelhece em upgrade do DSpace. Mitigação: templates finos, só estrutura e classes; qualquer regra de negócio permanece no componente base.
- Risco: encapsulamento de estilo do `ds-uploader` e `ds-form`. Mitigação: partial global `_pcirn-submission.scss` em vez de `::ng-deep` espalhado.
- Risco: o mesmo shell atende depósito e revisão; nenhum texto pode assumir "novo documento" quando é revisão. Mitigação: usar chaves neutras já existentes.

## Verificação

1. Script `dspace-angular/source/scripts/pcirn-submission.test.mjs` (padrão `node --test` dos demais `pcirn-*.test.mjs`) garantindo que os templates custom são referenciados localmente, que os bindings essenciais e `data-test` foram preservados e que os marcadores PCIRN existem.
2. Executar a suíte `node --test dspace-angular/source/scripts/pcirn-*.test.mjs`.
3. Compilar o tema no fluxo Docker do `dspace-angular` sem erros.
4. Validação manual: depósito novo, rascunho retomado, revisão NUGECID, desktop e mobile, incluindo barra de ações, acordeão, upload e modais.

## Limites da implementação

Não serão alterados backend Java, REST, banco, `item-submission.xml`, `submission-forms.xml`, permissões, workflow, bibliotecas externas nem componentes do tema padrão quando uma sobrescrita do `custom` for suficiente.

# Tutoriais PCIRN

A página pública `/info/tutoriais` reúne os cinco PDFs. O link fica na coluna **Navegação** do rodapé. Os documentos e seus originais editáveis estão nesta entrega. O layout aprovado pelo usuário foi aplicado à interface em uso em 06/10/2026. Atualizações dos procedimentos devem ser conferidas pelo NUGECID.

## Materiais

- Consulta e download de documentos.
- Acesso ao repositório.
- Submissão de documentos.
- Revisão e publicação pelo NUGECID.
- Fluxo de depósito institucional.

Os PDFs distribuídos pelo frontend estão em `dspace-angular/source/src/assets/pcirn/tutoriais/`. Os arquivos `.odp` nesta pasta podem ser abertos e editados no LibreOffice Impress. O formato é horizontal 4:3, com texto selecionável, capturas descritas, estrutura marcada no PDF e contato clicável.

## Atualizar os manuais

1. Revise `conteudo.json`, incluindo versão e data. Confirme os procedimentos na interface instalada.
2. Atualize as imagens em `capturas/` quando a interface mudar. Use contas e documentos de demonstração em ambiente isolado. Não capture dados pessoais reais, senhas ou documentos de acesso restrito.
3. Confira as dimensões, legendas e retângulos de marcação em `captures` no arquivo de conteúdo. As coordenadas são medidas em pixels na captura original.
4. Execute, na raiz do repositório:

```bash
python3 docs/tutoriais/build.py
node --test dspace-angular/source/scripts/pcirn-tutoriais.test.mjs
```

O gerador requer LibreOffice, o módulo Python `uno` e os utilitários `pdfinfo` e `pdftotext`. Não há novas dependências do aplicativo. Ele exporta os cinco originais ODP e PDFs, verifica o texto/estrutura marcada e atualiza o catálogo com a quantidade de páginas e o tamanho real dos arquivos.

`conteudo.json` e as capturas são as fontes do gerador. Se você editar um ODP diretamente, transporte também as alterações para essas fontes antes de regenerar; a geração substitui os ODPs.

5. Se título ou descrição mudar, atualize as chaves correspondentes em `src/assets/i18n/pt-BR.json5` e `en.json5` no frontend. Os manuais permanecem em português; a página em inglês informa esse idioma.
6. Revise os PDFs exportados no visualizador e após impressão. Confirme que nenhuma ação ou campo foi cortado e que texto e capturas são legíveis.
7. Após revisão editorial pelo NUGECID, publique os arquivos junto com o frontend. Teste o endereço direto da página, o rodapé e cada PDF sem login.

## Critérios editoriais

- Usar os nomes atuais dos controles da PCIRN, sem instruções de SIGAA ou fluxos acadêmicos da UFRN.
- Mostrar seleção da coleção autorizada, rascunho, depósito, devolução, correção, reenvio e validação pelo NUGECID.
- Não afirmar que o sistema valida PDF/A, preserva sigilo ou concede permissões automaticamente sem verificar essa funcionalidade.
- Conferir a finalidade e a adequação para divulgação antes do depósito. O tutorial não altera políticas de acesso ou concede autorização para publicar conteúdo.
- Identificar explicitamente contas e arquivos de demonstração.
- A data do material indica a versão documentada; não representa aprovação editorial ainda não realizada.

## Verificações desta entrega

A compilação de desenvolvimento do Angular e o lint dos arquivos dos tutoriais passaram. Os três testes de `pcirn-tutoriais.test.mjs` passaram. Na suíte relacionada, 19 de 20 testes passaram; permanece uma divergência no teste de tradução de POP: o teste espera “Procedimento Operacional Padrão (POP)” e a tradução atual contém “Procedimento Operacional Padrão”. Essa chave não foi alterada nesta entrega.

No navegador, foram conferidos acesso direto sem login, os cinco PDFs, o link em Navegação, larguras de 320, 768, 1024 e 1440 pixels, foco por teclado e abertura em nova aba. A auditoria automatizada WCAG da página de tutoriais não encontrou violações; isso não equivale a uma certificação de acessibilidade do repositório inteiro.

Em uma cópia isolada dos serviços, com contas e arquivo de demonstração, foram executados depósito, devolução com justificativa, correção, salvamento para continuar depois, reenvio e validação. O item publicado foi consultado e baixado sem login, e a cópia da URI permanente foi conferida. Os documentos originais e as contas da instalação existente não foram modificados.

Os cinco PDFs totalizam 40 páginas. Foram conferidos texto de todas as instruções, limites de página, estrutura marcada e integridade dos originais ODP. A aplicação à interface em uso foi autorizada pelo usuário após a conferência da prévia.

## Referência

Organização inspirada em https://repositorio.ufrn.br/tutoriais: lista pública de PDFs, guias por responsabilidade, passos numerados e fluxograma. Textos, identidade e capturas foram preparados para a PCIRN.

## Aplicação à interface em uso

Em 06/10/2026, a página, o link do rodapé e os cinco PDFs foram aplicados ao contêiner `dspace-angular`. A imagem local `itep/dspace-angular:tutoriais-20261006` registra a atualização; a configuração de execução existente foi atualizada para usá-la nas próximas recriações. A página publicada é `http://10.9.233.96:4000/info/tutoriais`. Foram conferidos acesso sem login, PDFs, Navegação, teclado, responsividade e auditoria de acessibilidade da página.

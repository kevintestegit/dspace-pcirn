# Personalização dos e-mails institucionais da PCIRN

## Objetivo

Aplicar aos e-mails enviados pelo DSpace a identidade visual da PCIRN, inspirada na referência aprovada: fundo azul institucional, cabeçalho com as marcas DSpace, Polícia Científica do RN e Governo do RN, chamada principal, CTA destacado, imagem arquitetônica e rodapé institucional.

O primeiro fluxo será `change_password`, usado para o usuário cadastrar a senha inicial. Em seguida, o mesmo shell será aplicado aos demais e-mails, inclusive notificações de tarefas de workflow.

## Decisão de arquitetura

O backend terá um shell HTML comum, gerado pelo mecanismo de e-mail do DSpace. Os templates individuais continuarão em `dspace/config/emails/`, contendo o assunto e o conteúdo específico de cada evento.

Cada mensagem será enviada como `multipart/alternative`, com uma versão HTML visual e uma versão texto simples. O conteúdo específico, variáveis Velocity, links de ação e dados de workflow serão preservados por template.

As imagens institucionais serão disponibilizadas na configuração de e-mail e incorporadas como recursos inline, evitando dependência de URL pública do frontend e reduzindo falhas de carregamento em clientes de e-mail.

## Estrutura visual

- cabeçalho centralizado com as três marcas;
- nome do Repositório Institucional da PCIRN e identificação da instituição;
- separador azul;
- área de conteúdo específica por evento;
- CTA único e destacado quando houver ação;
- texto de segurança ou orientação contextual;
- imagem do footer da home como faixa institucional;
- rodapé com nome, contato e identificação da PCIRN;
- layout baseado em tabelas e CSS compatível com clientes de e-mail, sem dependência de JavaScript.

O texto não usará elementos específicos de cadastro, como “cancelar inscrição”, em mensagens nas quais eles não façam sentido. O shell é compartilhado; título, corpo, CTA e orientações variam conforme o evento.

## Fluxo de dados

1. O serviço existente seleciona o template do evento e injeta `params` e configurações permitidas.
2. O template produz o assunto e o conteúdo específico.
3. O renderer comum monta as partes HTML e texto simples.
4. O `Email` cria a mensagem MIME e anexa as imagens inline.
5. O SMTP existente envia a mensagem sem alteração no fluxo de autenticação ou entrega.

## Escopo inicial

1. Alterar o renderer `org.dspace.core.Email` para suportar o shell HTML e partes alternativas.
2. Adicionar os assets institucionais à configuração do backend.
3. Migrar `dspace/config/emails/change_password` e validar o cadastro inicial de senha.
4. Migrar os demais templates existentes, preservando parâmetros, links, assuntos e semântica de cada evento.
5. Adicionar testes para MIME, renderização, variáveis e presença do shell.

## Validação

- verificar `Content-Type` HTML e texto simples na mensagem MIME;
- verificar imagens inline e referências CID;
- renderizar a mensagem em desktop e viewport estreito;
- testar o link de cadastro/redefinição com token real de teste;
- validar ao menos uma notificação de tarefa de workflow;
- executar os testes unitários dos módulos alterados e a validação frontend somente se houver alteração de asset/build.

## Fora do escopo

- alteração do fluxo de autenticação, tokens ou SMTP;
- criação de um editor administrativo de templates;
- dependência de imagens hospedadas externamente;
- mudança de permissões, workflows ou destinatários.

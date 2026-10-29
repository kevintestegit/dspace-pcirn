# Entrega do PCIRN ao Núcleo de Tecnologia

Para exportar o banco desta instalação e importar no NTI, siga o
[roteiro de migração](MIGRACAO.md). A exportação da stack de desenvolvimento
também usa `dspacepcirn export-data`; não há mais um caminho separado por SQL.

## O que entregar

- Código: <https://github.com/kevintestegit/dspace-pcirn>, com uma tag ou commit
  definido para a entrega. O frontend é um submódulo de
  <https://github.com/kevintestegit/dspace-angular>; o NTI precisa acessar ambos.
- Banco e arquivos: dump PostgreSQL, assetstore (documentos e demais bitstreams)
  e dados Solr, incluindo estatísticas. O Git não contém o acervo.
- Configurações privadas: conexão PostgreSQL, certificados e SMTP, por canal
  institucional protegido, separados do Git e dos pacotes públicos.
- Manifesto da release com as imagens correspondentes e acesso ao GHCR,
  quando a instalação usar as imagens publicadas.

Clonagem pelo NTI:

```bash
git clone --recurse-submodules https://github.com/kevintestegit/dspace-pcirn.git
cd dspace-pcirn
git checkout TAG_OU_COMMIT_DA_ENTREGA
git submodule update --init --recursive
```

Antes de informar a versão ao NTI, revisar e publicar as alterações necessárias
do backend e do frontend, incluindo o commit do submódulo. Alterações locais não
chegam ao destinatário por meio do endereço Git. Nunca incluir `.env`,
`smtp.env`, senhas, dumps ou chaves privadas nos commits.

## Banco na instância do NTI

O script existente [provision-database.sql](provision-database.sql) cria o usuário,
o banco dedicado e as permissões. O DBA deve revisar nomes e executar com `psql`,
conectado inicialmente ao banco administrativo `postgres`, fora de uma transação:

```bash
psql -X -v ON_ERROR_STOP=1 -h HOST_POSTGRES -U USUARIO_DBA -d postgres \
  -f deploy/nti/provision-database.sql
```

O script solicita a senha do novo usuário interativamente. É para banco novo;
não executá-lo como atualização de um banco já existente. TLS e autorização de
acesso ao PostgreSQL devem seguir as regras do NTI.

Criar o banco não importa o acervo. A importação do dump, assetstore e Solr já
existe no instalador; seguir [MIGRACAO.md](MIGRACAO.md) e [README.md](README.md).
O destino deve estar vazio e o pacote precisa pertencer à release entregue.

O comando `export-data` desse roteiro exige uma origem administrada pela CLI
`dspacepcirn`. Se a origem usa o Compose de desenvolvimento, não apontar a CLI
para o checkout: preparar a exportação dessa instalação e validar o formato antes
de usar `--data-package`. O backup de `scripts/backup-dspace.sh` possui outro
formato e não é diretamente um pacote de `migrate-data`.

A exportação final exige janela sem escrita para manter banco e arquivos
consistentes. Não desligar a origem definitivamente antes de validar o destino.

## Domínio e HTTPS

O NTI deve configurar DNS para o servidor, certificado TLS e proxy reverso;
há um [exemplo Nginx](../nginx/pcirn.conf.example). Na configuração do instalador,
usar as URLs definitivas, por exemplo:

```json
{
  "PUBLIC_UI_URL": "https://repositorio.instituicao.br",
  "PUBLIC_REST_URL": "https://repositorio.instituicao.br/server",
  "PUBLIC_REST_HOST": "repositorio.instituicao.br"
}
```

Esse trecho complementa os campos de banco exigidos no README; não é uma
configuração completa. As URLs definitivas também permitem que os links de
cadastro e recuperação de senha apontem para o endereço correto.

## E-mail Brevo

A configuração local verificada em 20/10/2026 usa `smtp-relay.brevo.com`, porta
587, STARTTLS obrigatório e envio habilitado. A mudança de servidor permite
continuar usando Brevo, desde que o NTI configure:

- Saída de rede e resolução DNS para `smtp-relay.brevo.com:587`.
- Login SMTP e chave SMTP válidos, obtidos na Brevo e enviados por canal privado.
- Remetente autorizado e domínio de envio autenticado conforme a conta Brevo.
- Envio habilitado e URLs públicas corretas no DSpace.

No instalador, ajustar `ROOT/smtp.env`. O arquivo de exemplo atual usa Resend e
envio desabilitado; copiar o exemplo sem ajustes não configura Brevo. Exemplo
sem credenciais reais, a preencher no destino:

```dotenv
mail__P__server=smtp-relay.brevo.com
mail__P__server__P__port=587
mail__P__server__P__username=LOGIN_SMTP_BREVO
mail__P__server__P__password=CHAVE_SMTP_BREVO
mail__P__from__P__address=REMETENTE_AUTORIZADO
mail__P__admin=EMAIL_ADMINISTRATIVO
mail__P__extraproperties=mail.smtp.starttls.enable=true,mail.smtp.starttls.required=true
mail__P__server__P__disabled=false
```

Proteger o arquivo com permissão 600. Após configurar, recriar o serviço backend
para carregar o ambiente atualizado e testar um envio real. A chave SMTP não é
a senha de acesso à conta nem a chave API. Trocar apenas o domínio do site não
exige trocar o remetente; se o domínio do remetente mudar, autenticá-lo na Brevo.

Referência: [envio transacional por SMTP na Brevo](https://help.brevo.com/hc/en-us/articles/7924908994450-Send-transactional-emails-using-Brevo-SMTP).

## Aceite antes da transferência definitiva

Conferir login, permissões, busca, download de documentos, estatísticas e um
fluxo de e-mail com links no domínio final. Comparar os dados com a origem.
Consultar as pendências de homologação em
[homolog/VALIDATION.md](homolog/VALIDATION.md); os testes registrados ali não
comprovam o funcionamento completo no servidor do NTI.

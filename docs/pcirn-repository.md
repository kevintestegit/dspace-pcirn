# Repositório institucional PCIRN

## Aplicação da estrutura

O arquivo `dspace/config/pcirn/structure.xml` é a fonte da hierarquia inicial de comunidades e coleções. Execute-o uma única vez em uma instância vazia ou após confirmar que os nomes ainda não existem:

```bash
docker compose exec dspace \
  /dspace/bin/dspace structure-builder \
  -e admin@localhost \
  -f /dspace/config/pcirn/structure.xml \
  -o /tmp/pcirn-structure-result.xml
```

O comando retorna os Handles criados em `/tmp/pcirn-structure-result.xml`. Não execute novamente sobre uma instância já populada: o `structure-builder` não é idempotente.

## Fluxo operacional

1. O responsável da unidade deposita o PDF, preenche o formulário PCIRN e seleciona a condição de acesso na etapa nativa `itemAccessConditions`.
2. A coleção encaminha o item ao workflow nativo para o grupo de revisão `NUGECID`.
3. O NUGECID confere arquivo, metadados, acesso e dados sensíveis; aprova ou devolve com parecer.
4. Após aprovação, o DSpace instala o item, gera o Handle e indexa título, autor, data, assunto, tipo e coleção.

O grupo de revisor global `NUGECID` é criado pela migração; o administrador inicial deve permanecer como curador de bootstrap e os demais curadores devem ser adicionados pelo administrador. O cadastro automático por senha, OIDC e LDAP está desativado; novas contas são provisionadas por administrador ou diretório institucional. O SMTP deve ser configurado antes de validar notificações. PDF/A é requisito de curadoria; esta configuração não substitui uma validação especializada do formato.

## Acesso

O sistema é interno. A migração `V9.4_2026.08.05__make_site_private.sql` troca as permissões de leitura anônimas pelo grupo `Usuarios_Logados`. O OAI-PMH permanece desativado; IIIF e SWORD já estão desativados por configuração padrão. Novas contas devem ser provisionadas por administrador ou diretório institucional.

## Validação mínima

- `xmllint --noout dspace/config/pcirn/structure.xml`
- `xmllint --noout dspace/config/controlled-vocabularies/pcirn-document-types.xml`
- `xmllint --noout dspace/config/item-submission.xml`
- `xmllint --noout dspace/config/spring/api/discovery.xml`
- testar depósito, devolução, aprovação, Handle, busca por tipo e acesso anônimo negado

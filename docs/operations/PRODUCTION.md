# Operação de produção

O Compose atual permanece dev. Para preparar um servidor, use o override de produção:

```bash
cp .env.production.example .env.production
cp smtp.env.example smtp.env
chmod 600 .env.production smtp.env
# preencher URLs, senha do PostgreSQL e SMTP antes de iniciar
# para habilitar o histórico administrativo de e-mails, preencher BREVO_API_KEY
docker compose --env-file .env.production \
  -f docker-compose.yml \
  -f dspace/src/main/docker-compose/docker-compose-angular.yml \
  -f docker-compose.production.yml \
  up -d --build
```

O banco e o Solr ficam somente na rede Docker. UI e REST ficam ligados a `127.0.0.1`; um proxy TLS deve encaminhar o tráfego público para as portas `4000` e `8501`.
Use `deploy/nginx/pcirn.conf.example` como base do proxy e, quando o endereço público existir, ajuste `PUBLIC_UI_URL` e `PUBLIC_REST_URL` para as URLs do proxy (sem as portas internas).

## Backup

```bash
./scripts/backup-dspace.sh /var/backups/dspace
```

Guardar juntos `dspace.dump` e `assetstore.tar.gz`. O índice Solr é derivado e pode ser reconstruído.

## Aceite antes da publicação

- `docker compose ... ps` sem serviços reiniciando.
- `database migrate` concluída e `schema_version` sem falhas.
- login, logout, recuperação de senha e cadastro administrativo de usuário.
- usuário de cada setor deposita somente nas coleções do seu setor.
- depósito, devolução, reenvio, exclusão e aprovação NUGECID.
- Handle, busca, filtros e download público do bitstream aprovado.
- SMTP real testado com `/dspace/bin/dspace test-email`.
- backup restaurado em uma instalação de teste.

Ainda dependem de decisão externa: URL pública/TLS e servidor SMTP institucional. Nenhum segredo deve entrar no Git.

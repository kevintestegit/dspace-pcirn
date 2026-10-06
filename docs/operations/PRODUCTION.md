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
Use `deploy/nginx/pcirn.conf.example` como base do proxy. Instale um certificado válido e substitua
`SERVER_ADDRESS` no hostname e nos caminhos do certificado antes de ativar o Nginx. Ajuste
`PUBLIC_UI_URL` e `PUBLIC_REST_URL` para URLs HTTPS do proxy, sem as portas internas.
O exemplo redireciona HTTP para HTTPS e aplica HSTS apenas no servidor HTTPS.

O login OIDC começa em `/server/api/authn/oidc/login`. O callback exige o estado de uso único
da sessão que iniciou a navegação. O cookie de sessão é Secure, HttpOnly e SameSite=Lax;
esse fluxo exige HTTPS e afinidade de sessão caso haja mais de uma instância REST.

## Segredos e contexto de build

Arquivos `.env`, `.env.*` e `smtp.env` são excluídos do contexto Docker, inclusive em subdiretórios.
Mantenha os arquivos usados no runtime com permissão `600`, fora de artefatos distribuídos.
Essa exclusão não remove segredos de snapshots, imagens intermediárias ou caches já criados.
Restrinja o acesso a esses artefatos e verifique se foram compartilhados. Se houve exposição,
revogue e substitua as chaves Brevo/SMTP e coordene a troca da senha PostgreSQL com a atualização
dos consumidores. Alterar apenas `POSTGRES_PASSWORD` não muda a senha de um banco já inicializado.

## Harvesting e depósitos ZIP

OAI e ORE usam somente destinos HTTP(S) públicos nas portas 80/443, com validação DNS em cada
conexão e em redirecionamentos. Proxies de saída não são usados por esse cliente. Respostas OAI
têm limite de 16 MiB; recursos ORE, 1 GiB. Provedores internos e portas alternativas são rejeitados.

Depósitos SimpleZip são descompactados em área temporária antes de criar bitstreams. Os limites
em `swordv2-server.cfg` são positivos: 1.000 entradas, 100 MiB por entrada, 1 GiB total e razão
máxima de compressão de 100. A área temporária precisa de espaço para o limite total configurado.

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

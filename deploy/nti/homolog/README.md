# Insumos de homologação — revisão 2, 2026-10-18

O pacote atende ao fluxo com PostgreSQL **externo**, TLS e configuração explícita.
Não oferece o wizard nem o PostgreSQL gerenciado presentes no tarball original.
Use-o para uma instalação nova em ambiente descartável; não substitua o gerenciador
de uma instalação existente. Os assets originais da release permanecem disponíveis.

## Manifestos reais A/B

`release-a.json` e `release-b.json` são cópias integrais dos manifestos publicados
nas releases `v1.0.0-rc4` e `v1.0.0-rc6` de `kevintestegit/dspace-pcirn`.
`build-verification.json` registra os commits e os builds concluídos com sucesso.
`registry-verification.json` registra os seis índices consultados no GHCR em
2026-10-18; cada SHA-256 do JSON bruto corresponde ao digest do manifesto.
As imagens têm variantes linux/amd64 e linux/arm64; entradas unknown são atestações.
Nenhuma imagem nova foi construída ou publicada nesta revisão do instalador.

Para obter novamente os originais, com GitHub CLI autenticado se necessário:

```bash
mkdir -p /tmp/pcirn-a /tmp/pcirn-b
gh release download v1.0.0-rc4 -R kevintestegit/dspace-pcirn \
  -p release-manifest.json -D /tmp/pcirn-a
gh release download v1.0.0-rc6 -R kevintestegit/dspace-pcirn \
  -p release-manifest.json -D /tmp/pcirn-b
cmp /tmp/pcirn-a/release-manifest.json deploy/nti/homolog/release-a.json
cmp /tmp/pcirn-b/release-manifest.json deploy/nti/homolog/release-b.json
```

O README principal explica a geração de novos manifestos pelo workflow com digests
obtidos dos builds. Não troque tags por digests copiados de exemplos. Para conferir
um índice, use `docker buildx imagetools inspect REFERENCIA_COMPLETA --raw` e
calcule seu SHA-256, preservando exatamente os bytes retornados.

## Perfis diferentes e bloqueio do dump

A possui somente `database.migrations`: o histórico institucional, 87 entradas.
B tem esse histórico e também `fresh_bootstrap=pcirn-fresh-v1` com 79 entradas
em `fresh_migrations`. Para o ciclo restaurado A → B → rollback A, a configuração
usa `DB_PROFILE: institutional` (ou omite esse campo). Para o banco vazio, use
`DB_PROFILE: fresh` e **B** como `--empty-manifest`.

Não foi gerado dump binário: não há uma origem sintética comprovadamente compatível
com o histórico institucional de A neste ambiente. Inicializar B no perfil fresh
não produz o histórico institucional de A. Fabricar schema_version, copiar checksums
ou executar Flyway repair invalidaria o ensaio.

O responsável deve fornecer `fictional-a.dump`, gerado numa instância isolada e
compatível com A, sem importar dados de produção, nem mesmo anonimizados. Caso não
consiga produzir essa instância, deve fornecer outro par A/B com builds verificáveis
e histórico sintético compatível; a homologação completa permanece bloqueada.

Verificações exigidas antes do uso:

1. Origem e procedimento documentados; somente conteúdo e identidades fictícias,
   nenhuma credencial, token, pessoa real ou documento institucional.
2. Dump custom de PostgreSQL do mesmo major do servidor alvo; `pg_restore --list`
   deve funcionar. Arquivo e origem devem ser confiáveis: dumps podem executar SQL.
3. Schema DSpace completo e histórico Flyway (version/script/checksum/success)
   exatamente compatível com A; sem extensões/dependências externas, outros schemas,
   tabela pcirn_homolog_probe ou bitstreams. Não edite o histórico para fazê-lo passar.
4. Gere com `pg_dump --format=custom --no-owner --no-acl --file=fictional-a.dump`
   usando conexão TLS obtida de arquivo privado, sem senha na linha de comando.
   Registre versão dos clientes, origem, SHA-256 e resultado da inspeção de conteúdo.
5. O executor verifica formato, major, bancos vazios e histórico durante o ciclo.
   Essas verificações não comprovam que os dados são sintéticos: a revisão de origem
   e conteúdo é responsabilidade de quem fornece o dump.

As fixtures `../tests/fixtures/probe.sql` e `probe.txt` são inteiramente fictícias;
elas testam persistência e restauração, mas não substituem um schema DSpace válido.

## Execução e reprodução do pacote

Siga `../HOMOLOGACAO.md`. Forneça dois bancos externos dedicados, configurações
privadas chmod 600, certificados TLS e login GHCR do usuário executor, se exigido.
Nada disso pertence aos assets ou ao repositório. Use os manifestos deste diretório
e acrescente `--empty-manifest CAMINHO/release-b.json` ao comando E2E. O resultado
só é aprovado com todas as etapas, incluindo banco vazio autorizado; omitir essa
etapa retorna código 2 e `passed=false`. A VPS não foi acessada nesta preparação.

Para reproduzir a partir desta árvore de fontes:

```bash
python3 scripts/package-installer.py --output /tmp/dspacepcirn-installer-r2.tar.gz
cd /tmp
sha256sum -c dspacepcirn-installer-r2.tar.gz.sha256
```

Metadados do tar e gzip são fixos; nomes, bytes e permissões dos insumos determinam
o resultado. O script inclui somente uma lista explícita de arquivos públicos,
incluindo seu próprio código e o workflow. Ele não inclui configurações locais,
credenciais, dumps nem fontes automáticas do GitHub. Os testes unitários completos
são executados no repositório (alguns conferem fontes Java e Compose de desenvolvimento);
o pacote também contém esses testes para revisão, o executor E2E e suas fixtures.

# Revisão remota — 19/10/2026

## Escopo e integração

Repositório: https://github.com/kevintestegit/dspace-pcirn.
Base revisada: `origin/main` em `7797f2a408`. As 19 branches remotas existentes
(incluindo `main`) foram incorporadas na branch `codex/remote-security-integration`.
Conflitos foram resolvidos preservando as proteções e funcionalidades da `main`.
O checkout original, com alterações locais, não foi modificado.

As propostas de dependências foram conciliadas: Hibernate permanece em
`6.4.10.Final` e Error Prone em `2.42.0`. Hibernate `6.6.58.Final` apresentou
regressão nos testes de persistência; Error Prone `2.50.0` não suporta o Java 17
usado pelo projeto. Incorporar o histórico não significa manter versões quebradas.

## Arquivos indevidos

| Arquivo | Situação |
|---|---|
| `.env`, `.env.bak`, `docker-compose.yml.bak` | Presentes nas pontas de `codex/pcirn-email-branding` e `codex/pcirn-search-ui`; já removidos da `main` e excluídos da integração. |
| `dspace/config/emails/assets/dspace-logo-mini.svg` | Reintroduzido por branch antiga, sem referência; removido novamente na integração. |
| `.env.example`, `.env.production.example`, ZIPs e chaves privadas em testes | Exemplos e fixtures necessários; mantidos. |

Não foram encontrados dumps de produção, instaladores gerados ou credenciais de
produção confirmadas na árvore integrada. Os backups antigos usam senha padrão
de desenvolvimento; não devem ser usados na instalação de produção.
A varredura Gitleaks 8.30.1 percorreu 17.832 commits alcançáveis por `origin`:
62 ocorrências, triadas como exemplos, fixtures, marcadores ou falsos positivos.
Validade de tokens de fixtures não foi consultada em serviços externos.
As branches antigas e o histórico permanecem disponíveis; este trabalho não
reescreve o histórico nem elimina branches.

## Falhas do DSpace corrigidas

Aplicados os patches oficiais da versão 9.4, preservando as validações locais mais
restritivas de ZIP, rede e autorização:

| Aviso oficial | Correção |
|---|---|
| [GHSA-fc3c-5p62-2cx7](https://github.com/DSpace/DSpace/security/advisories/GHSA-fc3c-5p62-2cx7) | Escrita arbitrária no importador REST (`-z`). |
| [GHSA-758x-q228-3vqp](https://github.com/DSpace/DSpace/security/advisories/GHSA-758x-q228-3vqp) | Autorização antes da exposição de informações de bitstreams por token. |
| [GHSA-qff6-8wrh-2frw](https://github.com/DSpace/DSpace/security/advisories/GHSA-qff6-8wrh-2frw) | SSRF no harvesting ORE; validação adicional de host ausente e caixa do hostname. |
| [GHSA-4ppv-j692-84v9](https://github.com/DSpace/DSpace/security/advisories/GHSA-4ppv-j692-84v9) | Validação de token no PATCH de registro. |
| [GHSA-5xvx-grf4-4p7w](https://github.com/DSpace/DSpace/security/advisories/GHSA-5xvx-grf4-4p7w) | Travessia de diretórios em nomes de arquivos exportados. |
| [GHSA-4783-qprq-45x8](https://github.com/DSpace/DSpace/security/advisories/GHSA-4783-qprq-45x8) | Autorização na exclusão de processos, incluindo ajuste oficial posterior. |

## Pendências de segurança

A consulta de versões ao OSV/GitHub Advisory Database detecta bibliotecas afetadas;
não comprova que todos os caminhos vulneráveis estejam expostos nesta aplicação.
Dependências usadas somente em testes foram separadas das de execução.

### Backend

Foram consultadas 444 combinações de biblioteca/versão com escopo `compile` ou
`runtime` nas árvores resolvidas de todos os módulos. O inventário de componentes
com avisos e seus módulos está em
[revisao-dependencias-2026-10-19.csv](revisao-dependencias-2026-10-19.csv).
Os componentes de execução afetados incluem os seguintes. Atualizações maiores precisam de validação de compatibilidade com
Solr, Tika, Handle e Java 17; não foram aplicadas indiscriminadamente.

| Componente | Versão encontrada | Encaminhamento |
|---|---|---|
| Jetty servlets / HTTP2 | 9.4.15.v20190215; servlets também 9.4.53 | Alinhar a família Jetty e tratar avisos de DoS e servlets. |
| Jetty server / HTTP | 9.4.58.v20250814 | Verificar exposição pelo Handle; há avisos de parsing HTTP e autoridade. |
| Jetty security | 9.4.53.v20231009 / 9.4.58.v20250814 | Corrigir autenticação Digest se usada; migração da família necessária. |
| Apache Thrift | 0.19.0 | Avaliar 0.24.0 ou superior compatível. |
| Commons Lang antigo | 2.6 | Remover dependência legada via atualização do componente que a introduz. |
| Netty codec/common/handler/epoll | 4.1.99.Final | Atualizar a família em conjunto; avisos de DoS/TLS/filtros. Parte dos avisos é específica de Windows. |
| ZooKeeper | 3.6.2 | Atualizar componente de origem; avisos de autorização e watchers. |
| snappy-java | 1.1.10.1 | Avaliar 1.1.10.4 ou superior compatível. |
| protobuf-java | 3.15.0 / 3.24.3 | Atualizar para versão corrigida compatível com Solr. |
| jsoup | 1.22.2 | Avaliar 1.23.2 ou superior compatível. |
| junrar | 7.6.0 | Avaliar 7.6.1 ou superior compatível. |
| Tomcat embarcado | 10.1.55 | Avaliar 10.1.58 ou superior; avisos em autenticação Digest/Form e restrições de acesso. |
| Nimbus JOSE JWT | 9.48 | Avaliar 10.0.2 ou superior compatível; DoS por JSON profundamente aninhado. |

Spring Web MVC `6.2.19` também possui
[GHSA-j9f9-w8pj-32f8](https://github.com/advisories/GHSA-j9f9-w8pj-32f8) e
[GHSA-pc63-qcmh-9cmg](https://github.com/advisories/GHSA-pc63-qcmh-9cmg).
Não foram encontrados usos de `XsltView`, `SseEmitter` ou `text/event-stream`
no código da aplicação pesquisado. Isso reduz a evidência de exposição desses
caminhos, mas não substitui a avaliação em execução. Spring 7 exige migração de
plataforma; não é atualização isolada adequada para esta integração.

### Alertas do código no GitHub

O CodeQL registra **19 alertas abertos na `main`**: 6 críticos, 7 altos e
6 médios, segundo a classificação da ferramenta. Inventário com arquivos,
linhas e links: [revisao-codeql-2026-10-19.csv](revisao-codeql-2026-10-19.csv).
Esses números são alertas estáticos, não 19 explorações confirmadas.

- **Prioridade:** `DSpaceControlledVocabulary` interpola IDs recebidos em
  expressões XPath (`getChoicesByParent`, `getParentChoice`, `getNode`).
  Substituir a interpolação por variáveis XPath e testar entradas com aspas.
- **ReDoS:** cinco alertas em expressões de DOI, Handle, Solr e facetas de ano;
  revisar com entradas longas e limites de tamanho.
- **XML:** quatro alertas de XXE passam por fábricas protegidas de `XMLUtils`,
  com DTD desativado. Há indício de falso positivo, mas faltam testes de
  exploração para encerrar os alertas.
- **Brevo:** o host de destino é constante (`api.brevo.com`) e os valores de
  entrada são codificados em query/path. SSRF não foi confirmada na leitura;
  validar também a política de redirecionamento do cliente HTTP.
- **Redirecionamentos/cookie:** quatro fluxos de login já comparam hosts com
  uma lista configurada; o cookie usa `request.isSecure()`. Validar esquema,
  origem completa e cabeçalhos do proxy HTTPS. O redirecionamento OAI também
  requer verificação com caminho iniciado por `//`.
- Dois alertas altos estão em testes (`MockSHERPAService` e script de UI),
  sem evidência de uso em produção.

Os alertas não foram encerrados administrativamente. A nova análise CodeQL
na PR deve ser consultada junto com este inventário.

### Frontend vinculado

O gitlink `dspace-angular/source` aponta para `857aa482e5d9`, na branch
`codex/pcirn-repository-structure` do fork
https://github.com/kevintestegit/dspace-angular.
A `main` desse fork está no DSpace 10.1 e não foi misturada ao backend 9.4.

`npm audit --omit=dev` nesse commit: **37 pacotes afetados**
(1 crítico, 13 altos, 20 moderados, 3 baixos; inclui efeitos transitivos).
O aviso crítico é [GHSA-jqcg-44mw-7w3h](https://github.com/advisories/GHSA-jqcg-44mw-7w3h)
em `proxy-addr` 2.0.7, corrigido em 2.0.8, relacionado a confiança em IPs de proxy.
Há também alertas em Angular, `http-proxy-middleware` e dependências do Mirador.

A tentativa de atualização automática foi descartada: `npm ci` identificou
inconsistência de versões Angular e conflitos de peers do Mirador/React.
O frontend publicado não foi alterado. A atualização deve alinhar toda a família
Angular e resolver esses peers antes de build e testes de SSR/proxy.

## Validação e publicação

- Validação completa do backend em andamento: Java 17 / Maven 3.9.9,
  `mvn -B -ntp install -P-assembly -DskipUnitTests=false -DskipIntegrationTests=false`.
- Resultado final dos testes e merge: pendentes; atualizar esta seção antes da entrega.
- Varreduras: Gitleaks do histórico remoto; OSV das dependências Maven resolvidas;
  auditoria npm do frontend vinculado.
- Não houve teste de invasão, varredura das imagens Docker finais ou validação no
  servidor do NTI. Dependabot Alerts não estava acessível/ativado pela API usada.
- As imagens e o pacote de instalação anteriores precisam ser reconstruídos e
  revalidados para incluir as correções desta revisão.

**Antes da exposição pública:** corrigir e testar o alerta crítico do frontend,
priorizar os demais componentes de execução, validar as imagens finais e concluir
homologação no ambiente do NTI. O merge não certifica ausência de vulnerabilidades.

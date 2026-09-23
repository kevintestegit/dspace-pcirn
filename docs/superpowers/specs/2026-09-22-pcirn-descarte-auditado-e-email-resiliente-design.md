# Descarte auditado e e-mail resiliente — Design

**Data:** 2026-09-22
**Status:** aprovado pelo usuário; aguardando revisão do spec escrito
**Origem:** `docs/pcirn-analise-bugs-2026-09-22.md` (achados A1, A3, A10, A14)
**Base:** fork PCIRN sobre DSpace 9.3 — `42fffa78d0` + working tree não commitada

---

## 1. Problema

Duas falhas independentes, ambas com impacto em produção, mais uma inconsistência de documentação.

### 1.1 Descarte de submissão sem motivo registrado e sem aviso

`AcceptEditRejectAction.processDelete` chama `XmlWorkflowServiceImpl.deleteWorkflowByWorkflowItem`
(`XmlWorkflowServiceImpl.java:969-991`), que faz `turnOffAuthorisationSystem()` e
`itemService.delete(...)`:

- não exige motivo algum;
- não notifica o depositante — o caminho de rejeição notifica (`XmlWorkflowServiceImpl.java:1230-1250`
  envia `submit_reject` com a justificativa);
- não deixa registro durável: o item e a sua `provenance` são apagados junto, e os bitstreams ficam
  órfãos no assetstore.

Para um repositório que publica **atos oficiais** (portarias, POPs, relatórios), apagar uma submissão
sem justificativa registrada e sem ciência do depositante é risco de conformidade.

### 1.2 O shell de e-mail PCIRN derruba notificações críticas

O fork passou a envolver **todo** e-mail do DSpace no shell institucional dentro de `Email.java`
(classe de núcleo). Consequências verificadas:

| # | Defeito | Evidência |
|---|---|---|
| D1 | Asset ou layout ausente lança `IOException` e **nenhum** e-mail sai | `PcirnEmailTemplateRenderer.java:156-163`, consumido por `Email.java:446-450` sem tratamento |
| D2 | E-mail sem `emailTitle` recebe `<h1>` vazio e aviso institucional fora de contexto | `pcirn-layout.html:38-41` × `Email.java:534-537`; ex.: `DailyReportEmailer.java:75` |
| D3 | URL de ação inválida derruba a mensagem inteira em vez de omitir o botão | `PcirnEmailTemplateRenderer.java:139-154` |
| D4 | `<p></p>` no topo de praticamente todo e-mail | `renderBody` (`:119-121`) usa `split("\\n\\s*\\n", -1)` sem filtrar vazios; os templates começam com linhas `#set(...)` cujas quebras sobrevivem ao merge |
| D5 | Layout relido do disco a cada mensagem | `render()` faz `Files.readString(...)` por e-mail |
| D6 | Maquinário de entidades é código morto | `isStructuralEntity` (`:175-179`) cobre exatamente o que `escapeHtml4` produz, logo `unescapeHtml4` (`:174`) nunca executa |

### 1.3 Documentação contradiz o estado real

`docs/pcirn-repository.md:24,28` afirma que "o sistema é interno" e que a migração
`V9.4_2026.08.05__make_site_private.sql` transferiu as leituras anônimas para `Usuarios_Logados`.
O banco em execução diz o contrário (verificado por consulta): 15.624 políticas anônimas, **23/23**
coleções com `READ` anônimo, `READ` anônimo no objeto `site`. As migrações `09.15`/`09.17` tornaram o
acervo público e superaram a `08.05`.

---

## 2. Objetivos

1. Tornar o descarte de submissão **auditável e comunicado**: motivo obrigatório, registro durável e
   e-mail ao depositante.
2. Tornar o shell de e-mail **opt-in e não bloqueante**: nenhuma falha de apresentação pode impedir o
   envio de uma notificação transacional.
3. Alinhar a documentação ao fato de que **a leitura é pública**; o que é restrito é depósito e curadoria.

## 3. Não-objetivos

- Reativar OAI-PMH, IIIF ou SWORD.
- Auditar o fluxo de "depositante excluído" (`ReviewAction.processSubmitterIsDeletedPage`), onde não
  existe destinatário possível.
- Corrigir os demais achados do relatório (A2, A5, A6, A7, A8, A9, A11, A12, A13) — candidatos a um
  plano seguinte.
- Preservar o arquivo descartado: a exclusão continua física (decisão do usuário). O custo — perda do
  conteúdo e dos bitstreams — é explicitamente aceito e fica registrado na auditoria.

## 4. Decisões aprovadas

| Decisão | Escolha |
|---|---|
| Semântica do descarte | **Apagar**, com motivo obrigatório, e-mail ao depositante e registro durável em tabela de auditoria |
| Escopo da correção do e-mail | **Shell resiliente e opt-in**: aplicado só quando o template declara título/CTA; falhas degradam com `WARN` em vez de lançar |

### Premissas (confirmadas com o usuário)

- Motivo: texto livre, **mínimo 10 e máximo 2000 caracteres**.
- Único destinatário: o depositante (`wi.getSubmitter()`); se não houver, `WARN` e o descarte segue.
- Falha de e-mail **não** bloqueia o descarte, mas fica gravada na linha de auditoria.
- A opção de workflow continua se chamando `submit_delete` (não muda o contrato REST existente).

---

## 5. Frente 1 — Descarte auditado

### 5.1 Componentes

| Componente | Responsabilidade |
|---|---|
| `V9.4_2026.09.22__pcirn_discard_audit.sql` | Cria a tabela `pcirn_discard_audit` e a sequência |
| `org.dspace.pcirn.PcirnDiscardAudit` | Entidade JPA; só dados |
| `org.dspace.pcirn.dao.PcirnDiscardAuditDAO` (+`impl`) | Único lugar com acesso a dados da tabela |
| `org.dspace.pcirn.service.PcirnDiscardAuditService` (+`impl`) | `record`, `markNotified`, `markNotificationFailed` |
| `XmlWorkflowService.discardWorkflowItem(Context, T, EPerson, String)` | Orquestra: auditoria → notificação → exclusão |
| `notifyOfDiscard(...)` em `XmlWorkflowServiceImpl` | Espelha `notifyOfReject`; envia o template `submit_delete` |
| `dspace/config/emails/submit_delete` | Template no contrato PCIRN (`emailTitle`/`emailActionLabel`/`emailActionUrl`/`emailPreheader`) |
| `AcceptEditRejectAction.processDelete(Context, XmlWorkflowItem, HttpServletRequest)` | Valida o motivo na borda e delega |
| `ClaimedTaskActionsDeleteComponent` (Angular) | Modal com motivo obrigatório; envia `discard_reason` |

### 5.2 Fluxo

```
Angular: modal exige motivo → createbody() = { submit_delete: 'true', discard_reason: '<texto>' }
   ↓ POST (uriEncodeBody → parâmetros de request)
ClaimedTaskRestRepository.action → valida a opção → doState → AcceptEditRejectAction.execute
   ↓
processDelete: motivo ausente/curto → addErrorField(request, "discard_reason") + TYPE_ERROR
                                   → REST responde 422 "Missing required fields: discard_reason"
   ↓ motivo válido
XmlWorkflowService.discardWorkflowItem(c, wfi, reviewer, reason)
   1. PcirnDiscardAuditService.record(...)        → INSERT (motivo, título, coleção, depositante, revisor)
   2. notifyOfDiscard(...)                        → e-mail ao depositante; sucesso/falha gravados
   3. deleteWorkflowByWorkflowItem(...)           → exclusão física (inalterada)
```

A ordem é obrigatória: depois do passo 3 o item não existe mais e não há como montar o e-mail nem
saber título/coleção.

### 5.3 Contrato

- Opção de workflow: `submit_delete` (inalterada).
- Campo de motivo: **`discard_reason`**. O nome não pode começar com `submit` porque
  `Util.getSubmitButton` (`Util.java:336-348`) devolve o primeiro parâmetro com esse prefixo e o
  motivo seria confundido com o botão.
- Resposta de validação: `422 Unprocessable Entity` com `Missing required fields: discard_reason`
  (comportamento nativo de `ClaimedTaskRestRepository.java:216-219`).

### 5.4 Tratamento de erro

| Situação | Comportamento |
|---|---|
| Motivo ausente, em branco ou < 10 caracteres | 422; **nada** é apagado |
| Motivo > 2000 caracteres | 422; nada é apagado |
| Falha ao gravar a auditoria | exceção sobe; **nada** é apagado (a auditoria precede a destruição) |
| Depositante inexistente | `WARN`, `notified_at` fica nulo, descarte prossegue |
| Falha no envio do e-mail | `WARN`, `notification_error` gravado, descarte prossegue |
| Falha na exclusão | exceção sobe; a linha de auditoria permanece (registro de tentativa) |

### 5.5 Estratégia de teste

- **Unitário (JUnit 4 + Mockito)**, sem contexto Spring:
  - `AcceptEditRejectActionTest`: motivo ausente/curto → `Action.getErrorFields(request)` contém
    `discard_reason` e `xmlWorkflowService` **nunca** é chamado; motivo válido → chamado uma vez com o
    motivo já normalizado (`trim`); `getOptions()` continua expondo `submit_delete`.
  - O campo `xmlWorkflowService` já é `protected` em `ProcessingAction` (`:39-40`), então o teste
    injeta um mock diretamente — não é preciso contexto Spring nem PowerMock.
- **Verificação dinâmica** (tarefa final): o caminho auditoria+notificação+exclusão depende de banco e
  de sessão de e-mail; é verificado ponta a ponta no ambiente em execução (linha na tabela + e-mail
  recebido + item ausente). Isso é declarado como tal: **não** haverá teste unitário fingindo cobrir
  esse caminho.

---

## 6. Frente 2 — Shell de e-mail resiliente e opt-in

### 6.1 Discriminador do shell

O shell é aplicado **se e somente se** o contexto mesclado tiver `emailTitle` não vazio.

Justificativa verificada: os **32/32** arquivos de template em `dspace/config/emails/` definem
`#set($emailTitle = ...)`, enquanto os dois e-mails montados programaticamente não definem nada
(`DailyReportEmailer.java:75` e `Email.java:659`, via `setContent(nome, conteúdo)`). O comportamento
atual é preservado integralmente e apenas esses dois voltam ao texto puro — que é o correto para eles.
Nenhuma propriedade de configuração nova.

### 6.2 Contrato do renderer

`PcirnEmailTemplateRenderer.render(...)` deixa de lançar por motivo de apresentação:

| Situação | Antes | Depois |
|---|---|---|
| Asset ausente/ilegível | `IOException` → nenhum e-mail | Omite aquele `<img src="cid:...">` do HTML, não cria a parte inline, `WARN` |
| URL de ação não-http(s) / malformada | `IOException` → nenhum e-mail | Omite o bloco de CTA, `WARN` |
| Layout ausente | `IOException` | **Continua lançando** (não há shell a renderizar) — e `Email` cai para texto puro |

`RenderedEmail` passa a expor `actionUrl()` (a URL já validada, ou `null`), para que o fallback de
texto puro em `Email` nunca anuncie um link inválido.

### 6.3 `Email.java`

- `emailTitle` vazio → caminho upstream (texto puro, ou `multipart/mixed` quando houver anexos),
  **sem** chamar o renderer.
- `emailTitle` presente → caminho atual (`multipart/alternative` com texto puro + `multipart/related`),
  agora dentro de `try/catch (IOException)`: se o renderer falhar, `WARN` e cai para texto puro. Um
  reset de senha não pode depender de um PNG.
- `renderBody` descarta parágrafos vazios (corrige D4).
- Cache do layout por caminho + `lastModifiedTime` + tamanho (corrige D5); o cache é invalidado quando
  o arquivo muda, para não quebrar o fluxo de edição de template.
- Remover `HTML_ENTITY`, `isStructuralEntity` e o `unescapeHtml4` inalcançável (corrige D6); documentar
  que o corpo do template é **texto puro**.
- Texto puro: o link de ação continua sendo anexado ao final, mas **só** quando a URL foi validada.

### 6.4 Efeito nos testes existentes

`PcirnEmailTemplateRendererTest` codifica o contrato antigo em 6 testes
(`rejectsNonHttpOrHttpsActionUrl`, `rejectsFtpActionUrl`, `rejectsRelativeActionUrl`,
`rejectsNetworkPathActionUrl`, `rejectsRelativeHttpActionUrl`, `rejectsMalformedActionUrl`, via o
helper `assertRejectsInvalidActionUrl`). Esses testes **devem ser reescritos** para o novo contrato
("omite em vez de lançar"), não apenas adicionados. `EmailTest.buildAddsPlainTextActionFallback:135`
também precisa de ajuste (ver 7.1).

---

## 7. Pré-requisito de build (achados A1 e A4)

- `EmailTest.java:135` espera `&#8599;` e o renderer emite `&#8594;` — a suíte está vermelha. Corrigido
  antes de qualquer outra mudança.
- `dspace-api/target/generated-sources` pertence a `nobody`, o que faz `mvn compile` falhar para o
  usuário. Removido antes de rodar qualquer teste.

## 8. Frente 3 — Documentação

| Arquivo | Mudança |
|---|---|
| `docs/pcirn-repository.md` (linhas 24 e 28) | Reescrever: **leitura pública e irrestrita**; restritos são depósito e curadoria; listar os endpoints públicos liberados em `WebSecurityConfiguration`; marcar a `08.05` como superada por `09.15`/`09.17` |
| `docs/operations/PRODUCTION.md` | Refletir leitura pública e incluir smoke test anônimo |
| `docs/goals/pcirn-mvp/PLAN.md` (linha 9) | Marcar a premissa "`/home` passará a exigir autenticação" como superada |
| `docs/pcirn-analise-bugs-2026-09-22.md` | Atualizar A1, A3, A10 e A14 para "resolvido", com referência a este design |

`docs/pcirn-publicacao-analise.md` já descreve o estado público corretamente e serve de referência.

---

## 9. Riscos

| Risco | Mitigação |
|---|---|
| A nova tabela exige registro em `dspace/config/hibernate.cfg.xml`, além dos beans Spring em `core-dao-services.xml`/`core-services.xml` | Incluído como tarefa explícita; verificação por compilação + boot da aplicação |
| Migração aplicada à mão no banco de dev faria o Flyway falhar depois | A validação de sintaxe usa `BEGIN; ... ROLLBACK;` — nada é persistido |
| Mudar o renderer quebra testes que codificam o contrato antigo | Os 6 testes são reescritos na mesma tarefa, com o novo contrato explícito |
| Exclusão física continua irreversível | Fora de escopo por decisão do usuário; a auditoria registra o que foi apagado e por quem |
| `notifyOfDiscard` duplica lógica de `notifyOfReject` | Aceito: são mensagens e parâmetros diferentes; extrair um helper comum só quando houver um terceiro caso (YAGNI) |

## 10. Critérios de sucesso

1. `mvn -pl dspace-api -DskipUnitTests=false -Dtest=EmailTest,PcirnEmailTemplateRendererTest,AcceptEditRejectActionTest test` verde.
2. Um descarte sem motivo é recusado com 422 e **não** apaga nada.
3. Um descarte com motivo grava uma linha em `pcirn_discard_audit` com motivo, revisor e depositante.
4. O depositante recebe o e-mail `submit_delete` com o motivo; falha de envio fica registrada.
5. Um e-mail sem `emailTitle` sai como texto puro; um e-mail com `emailTitle` sai com o shell, **sem**
   `<p></p>` e **sem** quebrar quando um asset falta.
6. `docs/pcirn-repository.md` afirma leitura pública, coerente com o banco.

## 11. Fora de escopo

Demais achados do relatório de análise; reativação de protocolos; auditoria do fluxo de depositante
excluído; preservação do conteúdo descartado.

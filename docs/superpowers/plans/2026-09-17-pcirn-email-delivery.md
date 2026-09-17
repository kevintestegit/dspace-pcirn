# PCIRN Email Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Configure Resend as the PCIRN DSpace SMTP relay, correct the shared HTML/plain-text email contract, and validate every configured email template without introducing a new API client or queue.

**Architecture:** Keep DSpace's existing Velocity, renderer, Jakarta Mail MIME assembly, attachments, and event call sites. Configure Resend through the existing SMTP abstraction using port 587 and STARTTLS. Remove action URLs from HTML body copy while adding a readable plain-text fallback, and keep delivery monitoring at the provider boundary.

**Tech Stack:** Java 17, Maven, Jakarta Mail, Apache Velocity, JUnit 4, Docker Compose, Resend SMTP.

---

## File map

- Modify `dspace-api/src/main/java/org/dspace/core/Email.java` — preserve MIME construction and add a separate plain-text action fallback.
- Modify `dspace-api/src/main/java/org/dspace/core/PcirnEmailTemplateRenderer.java` only if a focused renderer contract test requires it; keep escaping and URL validation unchanged otherwise.
- Modify `dspace-api/src/test/java/org/dspace/core/EmailTest.java` — MIME, action fallback, template smoke, attachment, and charset coverage.
- Modify `dspace-api/src/test/java/org/dspace/core/PcirnEmailTemplateRendererTest.java` — renderer and asset contract coverage.
- Modify `dspace-services/src/test/java/org/dspace/services/email/EmailServiceImplTest.java` — authenticated STARTTLS session configuration.
- Modify `dspace/config/emails/pcirn-layout.html` — final shared shell dimensions and compatibility corrections.
- Modify all event files under `dspace/config/emails/` except `pcirn-layout.html` — copy, metadata, and action-link cleanup.
- Modify `smtp.env.example` — document Resend SMTP keys without a real credential.
- Do not commit `smtp.env`, API keys, generated MIME previews, or build artifacts.
- Create `docs/superpowers/plans/2026-09-17-pcirn-email-delivery.md` — this plan.

---

### Task 1: Establish failing regression tests

**Files:**
- Modify: `dspace-api/src/test/java/org/dspace/core/EmailTest.java`
- Modify: `dspace-api/src/test/java/org/dspace/core/PcirnEmailTemplateRendererTest.java`

- [ ] **Step 1: Add the failing HTML/plain-text action test.**

Extend the existing `change_password` test with assertions that the URL remains in the plain part, appears exactly once in the HTML fallback link, and is not present as ordinary body text.

Use a deterministic token and inspect the first related part:

```java
String token = "https://example.org/reset?token=pcirn-test";
String plainText = (String) alternative.getBodyPart(0).getContent();
String html = (String) ((Multipart) alternative.getBodyPart(1).getContent())
        .getBodyPart(0).getContent();

assertThat(plainText, containsString(token));
assertThat(html, containsString("href=\"" + token + "\""));
assertThat(countOccurrences(html, token), is(2));
assertThat(html, not(containsString("acesse o link abaixo:</p><p>" + token)));
```

Add a private `countOccurrences(String, String)` helper that counts non-overlapping occurrences and returns an integer.

- [ ] **Step 2: Add a failing test for plain-text fallback when the template has no visible URL.**

Add an `EmailTest` using `setContent`:

```java
email.setContent("action-fallback",
        "#set($emailTitle = 'Teste')\n"
        + "#set($emailActionLabel = 'Abrir')\n"
        + "#set($emailActionUrl = 'https://example.org/task')\n"
        + "Conteúdo sem URL visível.");
```

Assert the plain part contains `Abrir: https://example.org/task` and the HTML contains the CTA and one visible fallback link.

- [ ] **Step 3: Run only the new tests and confirm failure.**

Run:

```bash
mvn -pl dspace-api -Dtest=EmailTest#buildRendersRealChangePasswordTemplateAsTextAndHtml,EmailTest#buildAddsPlainTextActionFallback test
```

Expected: the test run fails because the current HTML still renders the action URL in the body and the plain fallback is not generated independently.

- [ ] **Step 4: Commit the test contract.**

```bash
git add dspace-api/src/test/java/org/dspace/core/EmailTest.java
git commit -m "test: define email action fallback contract"
```

---

### Task 2: Normalize event templates

**Files:**
- Modify: `dspace/config/emails/batch_import_error`
- Modify: `dspace/config/emails/batch_import_success`
- Modify: `dspace/config/emails/change_password`
- Modify: `dspace/config/emails/coar_notify_accepted`
- Modify: `dspace/config/emails/coar_notify_endorsed`
- Modify: `dspace/config/emails/coar_notify_rejected`
- Modify: `dspace/config/emails/coar_notify_rejected_resubmission`
- Modify: `dspace/config/emails/coar_notify_relationship`
- Modify: `dspace/config/emails/coar_notify_reviewed`
- Modify: `dspace/config/emails/doi_maintenance_error`
- Modify: `dspace/config/emails/export_error`
- Modify: `dspace/config/emails/export_success`
- Modify: `dspace/config/emails/feedback`
- Modify: `dspace/config/emails/flowtask_notify`
- Modify: `dspace/config/emails/harvesting_error`
- Modify: `dspace/config/emails/healthcheck`
- Modify: `dspace/config/emails/internal_error`
- Modify: `dspace/config/emails/orcid`
- Modify: `dspace/config/emails/qaevent_admin_notification`
- Modify: `dspace/config/emails/register`
- Modify: `dspace/config/emails/registration_notify`
- Modify: `dspace/config/emails/request_item.admin`
- Modify: `dspace/config/emails/request_item.author`
- Modify: `dspace/config/emails/request_item.granted`
- Modify: `dspace/config/emails/request_item.granted_token`
- Modify: `dspace/config/emails/request_item.rejected`
- Modify: `dspace/config/emails/submit_archive`
- Modify: `dspace/config/emails/submit_reject`
- Modify: `dspace/config/emails/submit_task`
- Modify: `dspace/config/emails/subscriptions_content`
- Modify: `dspace/config/emails/validation_orcid`
- Modify: `dspace/config/emails/welcome`

- [ ] **Step 1: Preserve and record every parameter contract before editing.**

Run:

```bash
rg -n '\\$params\\[[0-9]+\\]|#if|#end|^#set\\(\\$subject' dspace/config/emails --glob '!pcirn-layout.html'
```

Expected: a complete inventory of parameter indexes, branches, and subjects used by each event template. Do not renumber or remove any listed parameter.

- [ ] **Step 2: Remove raw action URLs from HTML-bearing action templates.**

Update the body copy of `change_password`, `register`, `submit_task`, and `submit_reject` so the action is described without printing its URL. Keep the URL in the existing parameter and metadata assignment:

```
#set($emailActionUrl = $params[0])
```

The plain-text fallback will be added by `Email.java`. Do not remove the parameter from the template or its production caller.

- [ ] **Step 3: Add metadata only for real user actions.**

Use these exact mappings:

```
change_password       -> $params[0]  / Cadastrar minha senha
register              -> $params[0]  / Confirmar meu cadastro
orcid                 -> $params[0]  / Concluir cadastro com ORCID
validation_orcid      -> $params[0]  / Confirmar e-mail ORCID
submit_task           -> $params[4]  / Acessar minhas tarefas
submit_reject         -> $params[4]  / Acessar minhas submissões
request_item.author   -> $params[6]  / Responder solicitação
request_item.granted_token -> $params[6] / Acessar arquivos
export_success        -> $params[0]  / Baixar arquivo
```

Do not turn informational URLs into CTAs unless the event requires the recipient to act.

- [ ] **Step 4: Normalize Velocity assignments.**

Replace the nested configuration form:

```
#set($phone = ${config.get('mail.message.helpdesk.telephone')})
```

with:

```
#set($phone = $config.get('mail.message.helpdesk.telephone'))
```

Apply this to `change_password`, `register`, `orcid`, and `validation_orcid`.

- [ ] **Step 5: Review visible copy in PT-BR without changing event data.**

Translate remaining user-facing English prose while preserving:
- every `$params[n]`;
- every `#if`, `#else`, and `#end`;
- every subject value unless translation is explicitly required by the PCIRN copy review;
- existing URLs, handles, identifiers, stack traces, and diagnostic values.

- [ ] **Step 6: Run static template checks.**

Run:

```bash
for f in dspace/config/emails/*; do
  [ -f "$f" ] || continue
  [ "$(basename "$f")" = "pcirn-layout.html" ] && continue
  rg -q '^#set\\(\\$emailTitle' "$f" || echo "missing title: $f"
  rg -q '^#set\\(\\$emailPreheader' "$f" || echo "missing preheader: $f"
done
rg -n '\\$email(Title|ActionLabel|ActionUrl|Preheader)|#set\\(' dspace/config/emails \
  --glob '!pcirn-layout.html' | rg -v '^.*:#set' || true
```

Expected: no missing metadata and no unresolved presentation directives printed as body text.

- [ ] **Step 7: Commit the template normalization.**

```bash
git add dspace/config/emails
git commit -m "fix: normalize PCIRN email templates"
```

---

### Task 3: Separate HTML body from plain-text action fallback

**Files:**
- Modify: `dspace-api/src/main/java/org/dspace/core/Email.java`
- Test: `dspace-api/src/test/java/org/dspace/core/EmailTest.java`

- [ ] **Step 1: Add the fallback helper test case before implementation.**

The test from Task 1 must require this exact behavior:

```
private String appendPlainTextActionFallback(
        String body, String actionLabel, String actionUrl) {
    if (actionLabel == null || actionLabel.isBlank()
            || actionUrl == null || actionUrl.isBlank()) {
        return body;
    }
    return body + "\n\n" + actionLabel + ": " + actionUrl + "\n";
}
```

- [ ] **Step 2: Render and validate HTML before mutating the plain body.**

In `Email.build()`, retain the merged template in `mergedBody`, render HTML from that body, then append the fallback only to the plain body:

```
String mergedBody = writer.toString();
String emailTitle = getContextValue(vctx, "emailTitle");
String emailActionLabel = getContextValue(vctx, "emailActionLabel");
String emailActionUrl = getContextValue(vctx, "emailActionUrl");
String emailPreheader = getContextValue(vctx, "emailPreheader");

PcirnEmailTemplateRenderer.RenderedEmail rendered =
        new PcirnEmailTemplateRenderer(Paths.get(
                getConfigurationService().getProperty("dspace.dir"),
                "config", "emails"))
        .render(mergedBody, emailTitle, emailActionLabel,
                emailActionUrl, emailPreheader);

body = appendPlainTextActionFallback(
        mergedBody, emailActionLabel, emailActionUrl);
```

Use `body` for the existing disabled-mail log and the `text/plain` part. Use `rendered.html()` for the HTML part.

- [ ] **Step 3: Keep MIME behavior unchanged.**

Do not change:
- `multipart/alternative` ordering;
- `multipart/related` nesting;
- five CID resources;
- user attachments in outer `multipart/mixed`;
- `message.saveChanges()`;
- subject, recipients, reply-to, or charset behavior.

- [ ] **Step 4: Run the focused Email tests.**

Run:

```bash
mvn -pl dspace-api -Dtest=EmailTest test
```

Expected: PASS, including real `change_password`, attachment, null-argument, charset, and all-template smoke tests.

- [ ] **Step 5: Commit the MIME/body separation.**

```bash
git add dspace-api/src/main/java/org/dspace/core/Email.java \
        dspace-api/src/test/java/org/dspace/core/EmailTest.java
git commit -m "fix: separate email HTML and text action content"
```

---

### Task 4: Finalize the shared HTML shell and renderer tests

**Files:**
- Modify: `dspace/config/emails/pcirn-layout.html`
- Modify: `dspace-api/src/test/java/org/dspace/core/PcirnEmailTemplateRendererTest.java`
- Modify: `dspace-api/src/main/java/org/dspace/core/PcirnEmailTemplateRenderer.java` only if a test exposes a renderer defect.

- [ ] **Step 1: Align the shell with the approved email reference.**

Keep table layout, inline styles, CID images, alt text, preheader, CTA, and visible fallback link. Set the main card to the approved fluid maximum width of `680px`, keep content readable at 390px, and retain the PCIRN institutional labels and footer.

Do not add JavaScript, external fonts, CSS-only background images, or remote image URLs.

- [ ] **Step 2: Add renderer assertions for the final shell.**

Assert:
- five inline resources and their exact content IDs;
- title, preheader, and body HTML escaping;
- action label and URL escaping;
- only `http` and `https` absolute action URLs;
- no action block when either action field is blank;
- `max-width:680px`;
- no unresolved renderer placeholders.

- [ ] **Step 3: Run the renderer suite.**

Run:

```bash
mvn -pl dspace-api -Dtest=PcirnEmailTemplateRendererTest test
```

Expected: PASS with all asset files readable.

- [ ] **Step 4: Commit the shell and renderer contract.**

```bash
git add dspace/config/emails/pcirn-layout.html \
        dspace-api/src/test/java/org/dspace/core/PcirnEmailTemplateRendererTest.java \
        dspace-api/src/main/java/org/dspace/core/PcirnEmailTemplateRenderer.java
git commit -m "test: finalize PCIRN email shell contract"
```

---

### Task 5: Validate authenticated STARTTLS configuration

**Files:**
- Modify: `dspace-services/src/test/java/org/dspace/services/email/EmailServiceImplTest.java`
- Modify: `smtp.env.example`

- [ ] **Step 1: Add the authenticated STARTTLS session test.**

Set temporary configuration values, reset `EmailServiceImpl`, and assert:

```java
assertEquals("smtp.resend.com",
        instance.getSession().getProperty("mail.host"));
assertEquals("587",
        instance.getSession().getProperty("mail.smtp.port"));
assertEquals("true",
        instance.getSession().getProperty("mail.smtp.auth"));
assertEquals("true",
        instance.getSession().getProperty("mail.smtp.starttls.enable"));
assertEquals("true",
        instance.getSession().getProperty("mail.smtp.starttls.required"));
```

Restore every original property and reset the service in a `finally` block.

- [ ] **Step 2: Update the non-secret example configuration.**

Set these example keys without a real secret:

```
mail__P__server=smtp.resend.com
mail__P__server__P__port=587
mail__P__server__P__username=resend
mail__P__server__P__password=REPLACE_WITH_RESEND_API_KEY
mail__P__from__P__address=no-reply@example.org
mail__P__extraproperties=mail.smtp.starttls.enable=true,mail.smtp.starttls.required=true
mail__P__server__P__disabled=true
```

Add a comment that the sending domain must be verified and the API key must remain outside Git.

- [ ] **Step 3: Run the services test.**

Run:

```bash
mvn -pl dspace-services -Dtest=EmailServiceImplTest test
```

Expected: PASS with authenticated and unauthenticated session coverage.

- [ ] **Step 4: Commit configuration documentation and test coverage.**

```bash
git add dspace-services/src/test/java/org/dspace/services/email/EmailServiceImplTest.java \
        smtp.env.example
git commit -m "test: validate Resend SMTP configuration"
```

---

### Task 6: Run the complete focused validation

**Files:**
- Test only; no new production files.

- [ ] **Step 1: Run all email-focused tests.**

```bash
mvn -pl dspace-api,dspace-services \
  -Dtest=EmailTest,PcirnEmailTemplateRendererTest,EmailServiceImplTest test
```

Expected: PASS with no unresolved template metadata and no MIME structure failures.

- [ ] **Step 2: Run the API and services unit suites.**

```bash
mvn -pl dspace-api,dspace-services -DskipUnitTests=false -DskipIntegrationTests=true test
```

Expected: PASS, or a report that separates pre-existing failures from email-related failures.

- [ ] **Step 3: Check the patch.**

```bash
git diff --check
git status --short
git diff --stat HEAD~5..HEAD
```

Expected: no whitespace errors; only intended implementation files are committed; `smtp.env`, credentials, previews, and generated output remain uncommitted.

---

### Task 7: Build and perform controlled operational validation

**Files:**
- Operational only: local `smtp.env`, Resend dashboard, verified DNS.
- Do not commit provider credentials.

- [ ] **Step 1: Configure the local operational secret.**

Set the existing `smtp.env` values to Resend's host, port 587, username `resend`, API key, verified sender, STARTTLS properties, and `mail.server.disabled=false`. Do not print the file or its password.

- [ ] **Step 2: Build the backend image.**

```bash
docker compose build dspace
```

Expected: image build completes with the updated API, services, templates, layout, and assets.

- [ ] **Step 3: Verify the packaged shell and assets.**

```bash
docker compose run --rm dspace test -f /dspace/config/emails/pcirn-layout.html
docker compose run --rm dspace find /dspace/config/emails/assets -maxdepth 1 -type f -printf '%f\n' | sort
```

Expected: shell exists and the five asset names are listed.

- [ ] **Step 4: Send one controlled staging message.**

Use the existing DSpace email test path with `change_password` and a single authorized recipient. Confirm:
- no SMTP exception;
- subject and recipient are correct;
- text/plain contains the action URL;
- HTML contains one CTA and one fallback link;
- all five CID images render;
- Resend records the accepted message.

- [ ] **Step 5: Stop if delivery evidence is incomplete.**

Do not claim delivery based only on application logs. Record relay acceptance, provider event, and inbox receipt separately. Do not send a broad distribution until the single-message test passes.

- [ ] **Step 6: Commit only after validation.**

```bash
git status --short
git diff --check
```

Create the final implementation commit only after the focused tests, build, packaged-asset check, and controlled delivery pass.

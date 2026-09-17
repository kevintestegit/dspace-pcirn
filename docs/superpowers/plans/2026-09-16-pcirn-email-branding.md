# PCIRN Institutional Email Branding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Apply the approved PCIRN institutional email design to every configured DSpace email while preserving each event's dynamic data, links, subject, and plain-text fallback.

**Architecture:** Keep event-specific Velocity templates in dspace/config/emails/, adding explicit presentation metadata: emailTitle, optional emailActionLabel, emailActionUrl, and emailPreheader. A focused renderer will load one table-based shell matching the approved dark-blue reference, escape the rendered text body, and return HTML plus inline assets. Email.build() will send multipart/alternative with a related HTML part and the existing text content.

**Tech Stack:** Java 17, Jakarta Mail, Apache Velocity, Apache Commons Text, Maven, JUnit 4, DSpace configuration/assets.

---

## File map

- Create: dspace-api/src/main/java/org/dspace/core/PcirnEmailTemplateRenderer.java — shared shell renderer, body escaping, asset resolution, and inline-resource descriptors.
- Create: dspace-api/src/test/java/org/dspace/core/PcirnEmailTemplateRendererTest.java — renderer unit tests.
- Modify: dspace-api/src/main/java/org/dspace/core/Email.java — renderer integration and nested MIME construction.
- Modify: dspace-api/src/test/java/org/dspace/core/EmailTest.java — MIME and real-template regression tests.
- Create: dspace/config/emails/pcirn-layout.html — table-based HTML shell with CID image references.
- Create: dspace/config/emails/assets/dspace-logo-white.svg.
- Create: dspace/config/emails/assets/brasao-policia-cientifica-rn.png.
- Create: dspace/config/emails/assets/brasao-estado-rn.png.
- Create: dspace/config/emails/assets/footer-bg-pcirn.webp.
- Create: dspace/config/emails/assets/desenho1.png.
- Modify: every current event template in dspace/config/emails/ — add metadata and PCIRN wording only where needed; preserve params, branches, links, subjects, and event copy.

## Task 1: Define the renderer contract with failing tests

**Files:**
- Create: dspace-api/src/test/java/org/dspace/core/PcirnEmailTemplateRendererTest.java

- [x] **Step 1: Add tests for escaping, paragraphs, metadata, action URL, and five inline resources.**

    @Test
    public void rendersEscapedBodyAndAction() throws Exception {
        PcirnEmailTemplateRenderer renderer = new PcirnEmailTemplateRenderer(
            Paths.get("../dspace/config/emails"));

        PcirnEmailTemplateRenderer.RenderedEmail rendered = renderer.render(
            "Linha <segura>\\n\\nAcesse https://example.org/reset?token=a&b=c",
            "Cadastre sua senha", "Cadastrar minha senha",
            "https://example.org/reset?token=a&b=c", "Ação necessária");

        assertThat(rendered.html(), containsString("&lt;segura&gt;"));
        assertThat(rendered.html(), containsString("Cadastrar minha senha"));
        assertThat(rendered.html(), containsString(
            "href=\"https://example.org/reset?token=a&amp;b=c\""));
        assertThat(rendered.html(), containsString("cid:pcirn-footer-bg"));
        assertThat(rendered.inlineResources(), hasSize(4));
    }

- [x] **Step 2: Run the focused test and verify it fails because the renderer does not exist.**

Run: mvn -pl dspace-api -Dtest=PcirnEmailTemplateRendererTest test

Expected: compilation failure mentioning PcirnEmailTemplateRenderer.

- [x] **Step 3: Commit only the test contract.** Commit was not possible because the workspace `.git` directory is read-only.

    git add dspace-api/src/test/java/org/dspace/core/PcirnEmailTemplateRendererTest.java
    git commit -m "test: define PCIRN email renderer contract"

## Task 2: Implement the renderer, shell, and assets

**Files:**
- Create: dspace-api/src/main/java/org/dspace/core/PcirnEmailTemplateRenderer.java
- Create: dspace/config/emails/pcirn-layout.html
- Create: dspace/config/emails/assets/dspace-logo-mini.svg
- Create: dspace/config/emails/assets/brasao-policia-cientifica-rn.png
- Create: dspace/config/emails/assets/brasao-estado-rn.png
- Create: dspace/config/emails/assets/footer-bg-pcirn.webp

- [x] **Step 1: Copy the approved home assets without modifying the originals.**

    mkdir -p dspace/config/emails/assets
    cp dspace-angular/source/src/assets/images/dspace-logo-mini.svg dspace/config/emails/assets/
    cp dspace-angular/source/src/assets/pcirn/images/brasao-policia-cientifica-rn.png dspace/config/emails/assets/
    cp dspace-angular/source/src/assets/pcirn/images/brasao-estado-rn.png dspace/config/emails/assets/
    cp dspace-angular/source/src/assets/pcirn/images/footer-bg-pcirn.webp dspace/config/emails/assets/

- [x] **Step 2: Create the shell with tables, inline styles, alt text, and these placeholders.**

    <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">
      $emailPreheader
    </div>
    <img src="cid:pcirn-dspace-logo" alt="DSpace">
    <img src="cid:pcirn-policiacientifica"
         alt="Polícia Científica do Rio Grande do Norte">
    <img src="cid:pcirn-estado-rn" alt="Governo do Rio Grande do Norte">
    <h1>$emailTitle</h1>
    $emailActionBlock
    $emailBodyHtml
    <img src="cid:pcirn-footer-bg" alt="">

Use role="presentation" on layout tables and inline styles. Reproduce the approved hierarchy: navy page background, centered dark card, centered three-logo masthead, the exact visible labels “Repositório Institucional da PCIRN” and “POLÍCIA CIENTÍFICA DO RIO GRANDE DO NORTE”, motto separator, envelope icon, centered title/instructions, rounded blue CTA, architectural footer image, and institutional footer. Make the card fluid with a 680px maximum width and usable at 390px. Include a visible fallback text link next to every CTA. Do not use JavaScript, external fonts, CSS-only background images, “PCI” as an isolated brand label, or cadastro-only wording in the shared footer.

- [x] **Step 3: Implement this renderer contract:**

    public final class PcirnEmailTemplateRenderer {
        public record InlineResource(String contentId, File file, String mimeType) { }

    public record RenderedEmail(
            String html, List<InlineResource> inlineResources) { }

    public PcirnEmailTemplateRenderer(Path emailDirectory) { }

        public RenderedEmail render(
            String bodyText,
            String title,
            String actionLabel,
            String actionUrl,
            String preheader) throws IOException;
    }

Read emailDirectory/pcirn-layout.html and the four fixed assets. In production, construct the renderer with Paths.get(configurationService.getProperty("dspace.dir"), "config", "emails"); the test uses ../dspace/config/emails because Maven runs from dspace-api. Escape body and metadata with StringEscapeUtils.escapeHtml4. Convert blank-line-separated text into paragraphs and remaining newlines into <br>. Permit the button only when label and URL are nonblank. Accept only absolute http or https URLs and throw IOException for any other scheme. Return content IDs pcirn-dspace-logo, pcirn-policiacientifica, pcirn-estado-rn, and pcirn-footer-bg.

- [x] **Step 4: Run the renderer tests.**

Run: mvn -pl dspace-api -Dtest=PcirnEmailTemplateRendererTest test

Expected: PASS.

- [x] **Step 5: Commit the renderer and assets.** Commit was not possible because the workspace `.git` directory is read-only.

    git add dspace-api/src/main/java/org/dspace/core/PcirnEmailTemplateRenderer.java \
      dspace-api/src/test/java/org/dspace/core/PcirnEmailTemplateRendererTest.java \
      dspace/config/emails/pcirn-layout.html dspace/config/emails/assets
    git commit -m "feat: add PCIRN email HTML shell"

## Task 3: Make Email produce multipart HTML and text

**Files:**
- Modify: dspace-api/src/main/java/org/dspace/core/Email.java
- Modify: dspace-api/src/test/java/org/dspace/core/EmailTest.java

- [x] **Step 1: Add a MIME-tree test.**

    @Test
    public void buildCreatesHtmlAndPlainTextAlternatives() throws Exception {
        Email email = new Email();
        email.setContent("pcirn-test",
            "#set($emailTitle = 'Teste')\\n"
            + "#set($emailActionLabel = 'Abrir')\\n"
            + "#set($emailActionUrl = 'https://example.org/task')\\n"
            + "Conteúdo de teste.");
        email.addRecipient("recipient@example.org");
        email.build();

        assertThat(email.message.isMimeType("multipart/alternative"), is(true));
        Multipart alternative = (Multipart) email.message.getContent();
        assertThat(alternative.getCount(), is(2));
        assertThat(alternative.getBodyPart(0).isMimeType("text/plain"), is(true));
        assertThat(alternative.getBodyPart(1).isMimeType("multipart/related"), is(true));
        assertThat(((Multipart) alternative.getBodyPart(1).getContent())
            .getCount(), is(5));
    }

- [x] **Step 2: Run the new test and verify it fails because Email still calls message.setText.**

Run: mvn -pl dspace-api -Dtest=EmailTest#buildCreatesHtmlAndPlainTextAlternatives test

Expected: FAIL because the message is text/plain, not multipart/alternative.

- [x] **Step 3: Extract presentation metadata from the same VelocityContext used for the existing merge.**

Read emailTitle, emailActionLabel, emailActionUrl, and emailPreheader after template.merge(). Require emailTitle for migrated templates; treat the remaining values as empty strings. Keep body as the unmodified merged text for disabled-mail logging and the text MIME part.

- [x] **Step 4: Replace only the body branch in build() with nested Jakarta Mail multiparts.**

    MimeMultipart alternative = new MimeMultipart("alternative");

    MimeBodyPart plainPart = new MimeBodyPart();
    plainPart.setText(body, charset);
    alternative.addBodyPart(plainPart);

    PcirnEmailTemplateRenderer.RenderedEmail rendered =
        renderer.render(body, emailTitle, emailActionLabel,
                        emailActionUrl, emailPreheader);
    MimeMultipart related = new MimeMultipart("related");

    MimeBodyPart htmlPart = new MimeBodyPart();
    htmlPart.setContent(rendered.html(), "text/html; charset=" + charset);
    related.addBodyPart(htmlPart);

    for (PcirnEmailTemplateRenderer.InlineResource resource
            : rendered.inlineResources()) {
        MimeBodyPart imagePart = new MimeBodyPart();
        imagePart.attachFile(resource.file());
        imagePart.setHeader("Content-ID", "<" + resource.contentId() + ">");
        imagePart.setDisposition(MimeBodyPart.INLINE);
        related.addBodyPart(imagePart);
    }

    MimeBodyPart relatedPart = new MimeBodyPart();
    relatedPart.setContent(related);
    alternative.addBodyPart(relatedPart);
    message.setContent(alternative);

When regular attachments exist, keep them in an outer multipart/mixed and put the multipart/alternative body first. Do not turn user attachments into inline resources. Preserve subject, recipients, reply-to, charset, disabled-mail logging, and SMTP behavior.

- [x] **Step 5: Run the focused tests.**

Run: mvn -pl dspace-api -Dtest=EmailTest test

Expected: PASS, including the existing null and non-null parameter tests.

- [x] **Step 6: Commit the MIME integration.** Commit was not possible because the workspace `.git` directory is read-only.

    git add dspace-api/src/main/java/org/dspace/core/Email.java dspace-api/src/test/java/org/dspace/core/EmailTest.java
    git commit -m "feat: send PCIRN email alternatives"

## Task 4: Migrate every configured template

**Files:**
- Modify: every current event template in dspace/config/emails/, excluding pcirn-layout.html and assets/
- Test: dspace-api/src/test/java/org/dspace/core/EmailTest.java

- [x] **Step 1: Add presentation metadata to every template.**

Use this exact metadata for action-bearing templates:

    change_password: title "Cadastre sua senha", label "Cadastrar minha senha", URL $params[0]
    register: title "Confirme seu cadastro", label "Confirmar meu cadastro", URL $params[0]
    submit_task: title "Você tem uma nova tarefa", label "Acessar minhas tarefas", URL $params[4]
    submit_reject: title "Sua submissão precisa de atenção", label "Acessar minhas submissões", URL $params[4]

For every other template, declare a Portuguese event-specific emailTitle and emailPreheader, leaving action metadata empty unless that template already contains a verified absolute action URL. Use “Repositório Institucional da PCIRN” in new visible institutional copy. Preserve every existing `$params[n]`, `#if`, subject, and event body.

- [x] **Step 2: Add a template smoke test.**

Load each configured template with its existing representative arguments, call build(), and assert that the message contains a text/plain part, the PCIRN HTML shell marker, and the original body token. For `change_password`, assert `Cadastre sua senha`, `Cadastrar minha senha`, the reset token, and `Se você não solicitou`. For `register`, `submit_task`, and `submit_reject`, assert the title, CTA label, and expected parameter URL.

- [x] **Step 3: Run the complete focused suite.**

Run: `mvn -pl dspace-api -Dtest=EmailTest,PcirnEmailTemplateRendererTest test`

Expected: PASS for every configured template and no missing metadata title.

## Task 5: Migrate every remaining template without changing event contracts

**Files:**
- Modify: every current event template in dspace/config/emails/, excluding pcirn-layout.html and the assets directory.

- [x] **Step 1: Add metadata using existing parameters.**

Use these mappings:

| Template | Title | CTA URL |
|---|---|---|
| register | Confirme seu cadastro | $params[0] |
| submit_task | Você tem uma nova tarefa | $params[4] |
| submit_reject | Sua submissão precisa de atenção | $params[4] |
| change_password | Cadastre sua senha | $params[0] |

For all other templates, set a Portuguese event-specific emailTitle and leave action metadata empty unless the existing body contains a verified action URL. Preserve every $params[n] occurrence and every #if branch. Do not invent URLs from handles, IDs, or action labels.

- [x] **Step 2: Check that every template declares a title and no metadata is printed.**

    for f in dspace/config/emails/*; do
      [ -f "$f" ] || continue
      [ "$(basename "$f")" = "pcirn-layout.html" ] && continue
      rg -q '^#set\\(\\$emailTitle' "$f" || echo "missing title: $f"
    done
    ! rg -n 'emailTitle|emailActionLabel|emailActionUrl|emailPreheader' \
      dspace/config/emails/* | rg -v '^.*:#set'

Expected: no missing title output and no metadata outside #set directives.

- [x] **Step 3: Add a template smoke test.**

Load every migrated template, provide the representative arguments already expected by that template, call build(), and assert the common HTML shell marker plus the original body text in the text part. Keep the argument manifest in the test; do not alter production callers.

- [x] **Step 4: Run and commit the complete migration.** Commit was not possible because the workspace `.git` directory is read-only.

Run: mvn -pl dspace-api -Dtest=EmailTest,PcirnEmailTemplateRendererTest test

Expected: PASS for every configured template.

    git add dspace/config/emails
    git commit -m "feat: apply PCIRN shell to all email templates"

## Task 6: Verify packaging and browser-visible rendering

**Files:**
- Modify only if required: dspace/src/main/docker/*, Compose files, or dspace/config/*
- Create locally, never commit: /tmp/pcirn-email-preview.eml

- [ ] **Step 1: Confirm the backend image contains the shell and assets.**

    docker compose build dspace
    docker compose run --rm dspace test -f /dspace/config/emails/pcirn-layout.html
    docker compose run --rm dspace find /dspace/config/emails/assets -maxdepth 1 -type f -printf '%f\\n' | sort

Expected: the layout exists and all four asset names are listed.

- [ ] **Step 2: Generate a disabled-mail preview from the real change_password template and inspect the MIME structure.**

Use the existing DSpace test path with mail.server.disabled=true. Confirm the application log still records the request and the message contains the token. Delivery is not proven by this step.

- [ ] **Step 3: Render the HTML part at desktop and 390px width.**

Verify the three visible logos, “Repositório Institucional da PCIRN”, “POLÍCIA CIENTÍFICA DO RIO GRANDE DO NORTE”, the motto, envelope icon, event title, readable rounded CTA, architectural footer image, alt text, no horizontal scrolling at 390px, and a visible plain-text URL fallback. Verify `change_password`, `register`, and `submit_task` use the same shell with event-specific title and action label.

- [ ] **Step 4: Run final checks.**

    git diff --check
    mvn -pl dspace-api -DskipUnitTests=false -DskipIntegrationTests=false test

Expected: no whitespace errors and the API module tests pass. Record unrelated pre-existing failures separately.

- [ ] **Step 5: Review the worktree and commit only listed implementation files.**

    git status --short
    git diff --stat
    git commit -m "feat: personalize PCIRN institutional emails"

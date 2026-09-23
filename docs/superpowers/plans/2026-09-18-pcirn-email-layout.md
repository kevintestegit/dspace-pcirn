# PCIRN Email Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render all DSpace HTML emails inside the approved PCIRN institutional layout.

**Architecture:** Keep `Email` as the MIME assembler and `PcirnEmailTemplateRenderer` as the sole shared HTML renderer. Replace only the layout markup and CTA presentation, retaining existing data escaping, URL validation, body rendering, Velocity templates, CID assets, and plain-text alternatives.

**Tech Stack:** Java 17, JavaMail, Apache Velocity, JUnit 4, HTML email tables and inline CSS.

---

### Task 1: Establish the rendered-layout contract

**Files:**
- Modify: `dspace-api/src/test/java/org/dspace/core/PcirnEmailTemplateRendererTest.java`

- [ ] **Step 1: Write the failing assertions for the approved shell**

Add these assertions to `rendersEscapedBodyAndAction()`:

```java
containsString("background-color:#edf4fb"),
containsString("border-radius:12px"),
containsString("NOTIFICAÇÃO DO REPOSITÓRIO"),
containsString("background-color:#0869e8"),
containsString("Se você não reconhece esta mensagem"),
containsString("width=\"72\""),
not(containsString("background-color:#041c34"))
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `mvn -pl dspace-api -Dtest=PcirnEmailTemplateRendererTest test`

Expected: failure because the old dark, centered layout does not contain the new shell markers.

### Task 2: Replace the shared email shell

**Files:**
- Modify: `dspace/config/emails/pcirn-layout.html`

- [ ] **Step 1: Implement the table-based layout**

Replace the dark centered shell with a `max-width:760px` white card. Use a horizontal header for the three existing CID logos, name, police subtitle, and institutional motto; render the neutral `NOTIFICAÇÃO DO REPOSITÓRIO` eyebrow, `$emailTitle`, and `$emailBodyHtml` in the white content area; retain `$emailActionBlock`; add the security notice and use the existing footer illustration/background assets in a light-blue footer.

- [ ] **Step 2: Preserve all renderer placeholders and asset references**

The file must retain each of the following tokens exactly once where applicable:

```html
$emailPreheader
$emailTitle
$emailBodyHtml
$emailActionBlock
cid:pcirn-dspace-logo
cid:pcirn-policiacientifica
cid:pcirn-estado-rn
cid:pcirn-footer-building
cid:pcirn-footer-bg
```

### Task 3: Match the CTA to the approved layout

**Files:**
- Modify: `dspace-api/src/main/java/org/dspace/core/PcirnEmailTemplateRenderer.java`

- [ ] **Step 1: Change only CTA presentation**

In `renderActionBlock`, preserve the two escaped URL occurrences and fallback sentence, but replace the pill styling with the rectangular blue CTA styling:

```java
"padding:17px 34px; background-color:#0869e8; color:#ffffff; "
        + "font-size:18px; line-height:22px; font-weight:bold; text-decoration:none; "
        + "border-radius:7px;"
```

- [ ] **Step 2: Run the focused renderer test**

Run: `mvn -pl dspace-api -Dtest=PcirnEmailTemplateRendererTest test`

Expected: `Tests run: 10` (or the suite's updated count), `Failures: 0`.

### Task 4: Verify MIME integration and template coverage

**Files:**
- Verify: `dspace-api/src/main/java/org/dspace/core/Email.java`
- Verify: `dspace-api/src/test/java/org/dspace/core/EmailTest.java`

- [ ] **Step 1: Run email integration tests**

Run: `mvn -pl dspace-api -Dtest=EmailTest,PcirnEmailTemplateRendererTest test`

Expected: successful test run with multipart alternative/related content and the five CID inline assets unchanged.

- [ ] **Step 2: Inspect the final diff**

Run: `git diff --check -- dspace/config/emails/pcirn-layout.html dspace-api/src/main/java/org/dspace/core/PcirnEmailTemplateRenderer.java dspace-api/src/test/java/org/dspace/core/PcirnEmailTemplateRendererTest.java`

Expected: no whitespace errors.

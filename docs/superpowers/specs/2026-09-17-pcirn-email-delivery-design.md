# PCIRN Email Delivery Design

## Decision

Keep DSpace responsible for Velocity templates, text/plain generation, HTML rendering, MIME assembly, attachments, and the `Email` call sites. Use Resend as the SMTP relay.

Do not introduce the Resend API, Resend SDK, batch endpoint, queue, or outbox in this iteration.

This is the smallest change that improves delivery operations without rewriting DSpace's established email contract. DSpace already supports configurable SMTP host, port, username, password, charset, disabled delivery, and catch-all delivery. Resend supports authenticated SMTP on port 587 with STARTTLS and port 465 with SSL.

## Current behavior

1. A DSpace event loads a file from `dspace/config/emails/`.
2. `Email` merges it with Apache Velocity.
3. `Email.build()` creates a `multipart/alternative` message:
   - `text/plain` from the merged template;
   - `multipart/related` containing the PCIRN HTML shell and five inline images.
4. `Email.send()` calls Jakarta Mail `Transport.send(message)`.
5. The SMTP server accepts or rejects the message synchronously.

The current MIME strategy is valid for transactional mail and attachments. It does not provide an application queue, persistent retry, deduplication, delivery confirmation, or provider-level bounce state.

## Configuration

Operational configuration is kept outside the repository in `smtp.env`, which is already mounted by Compose. Compose environment variables override `local.cfg` and `dspace.cfg`.

Production values:

```properties
mail.server = smtp.resend.com
mail.server.port = 587
mail.server.username = resend
mail.server.password = <secret Resend API key>
mail.from.address = <address on a verified sending domain>
mail.charset = UTF-8
mail.extraproperties = mail.smtp.starttls.enable=true,mail.smtp.starttls.required=true
mail.server.disabled = false
```

The sending domain must be verified in Resend and publish SPF, DKIM, and DMARC records before production delivery. The API key must never be committed or copied into source files.

Development and test environments use `mail.server.disabled = true` or DSpace's catch-all configuration. A real recipient is used only for a controlled staging smoke test.

## Template and rendering contract

`dspace/config/emails/pcirn-layout.html` remains the shared table-based shell. `PcirnEmailTemplateRenderer` remains responsible for:

- loading the shell and fixed assets;
- escaping title, preheader, body, labels, and URLs;
- converting plain text paragraphs and line breaks into safe HTML;
- accepting only absolute `http` and `https` action URLs;
- returning the HTML plus five inline CID resources.

`Email.java` remains responsible for:

- Velocity merge and subject resolution;
- plain-text body;
- nested Jakarta Mail multiparts;
- user attachments;
- SMTP transport.

Action-bearing templates will not print the action URL as ordinary HTML body content. The plain-text part will retain a readable URL fallback, while the HTML part will contain the CTA and one fallback link. This prevents duplicate URLs in `change_password`, `register`, `submit_task`, and `submit_reject`, and applies the same rule to other verified action templates.

All visible template text will be reviewed for PT-BR consistency. Existing `$params[n]` positions, conditional branches, subjects, and event semantics remain unchanged. Action metadata is added only where the URL represents a real user action: password reset, registration, ORCID confirmation, workflow task, submission access, secure file access, or download.

Velocity assignments will use consistent syntax, including configuration lookups without nested `${...}` inside `#set`.

## Testing

Add or update tests for:

1. HTML escaping and safe action URL validation.
2. UTF-8 behavior when the configured charset is absent or overridden.
3. `multipart/alternative` and nested `multipart/related` structure.
4. Inline CID image names, MIME types, and file presence.
5. Regular attachments remaining outside the related part.
6. Every configured template rendering with representative arguments.
7. Preservation of parameters and conditional branches.
8. No leaked metadata directives or unresolved placeholders.
9. No duplicate action URL in rendered HTML.
10. SMTP configuration initialization with authentication and STARTTLS.

Validation order:

1. focused unit tests;
2. local/fake SMTP integration tests;
3. backend build and container packaging;
4. one controlled Resend staging delivery;
5. production rollout with provider dashboard monitoring.

The acceptance boundary is explicit: absence of a `MessagingException` proves relay acceptance only. Resend logs/webhooks prove provider events; the recipient inbox proves receipt.

## Rollout and non-goals

Rollout changes only operational SMTP values, verified-domain DNS, templates, renderer behavior, and tests. No credentials, database data, or generated artifacts are committed.

The following are intentionally deferred:

- Resend API or SDK integration;
- Resend batch sending;
- marketing broadcasts or contact management;
- persistent queue/outbox;
- retry worker and deduplication;
- delivery webhook persistence inside DSpace.

If controlled testing shows that synchronous SMTP blocks event processing, loses messages after process failure, or cannot sustain observed bursts, the next design will introduce an outbox and worker independently of the provider choice.

## References

- DSpace SMTP configuration: https://github.com/DSpace/DSpace/blob/main/dspace/config/dspace.cfg
- DSpace fixed-recipient and disabled-mail controls: https://wiki.lyrasis.org/spaces/DSDOC10x/pages/425330884/Sending%2Be-mails%2Bto%2Bfixed%2Brecipients
- Resend SMTP service and ports: https://resend.com/changelog/smtp-service
- Resend Java integration: https://resend.com/java
- Resend rate and quota limits: https://resend.com/docs/api-reference/rate-limit
- Resend batch API limitations: https://resend.com/blog/introducing-the-batch-emails-api

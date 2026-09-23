# PCIRN Email Layout Design

## Goal

Apply the approved institutional layout to every DSpace HTML email through the existing shared PCIRN renderer.

## Scope

The shared shell uses a white reading area, a horizontal dark-blue institutional header, prominent dark-blue title, the neutral `NOTIFICAÇÃO DO REPOSITÓRIO` eyebrow, optional blue rectangular CTA, security notice, and light-blue footer. Existing plain-text alternatives, Velocity templates, sanitisation, action URL validation, CID assets, and MIME structure remain unchanged.

## Architecture

`PcirnEmailTemplateRenderer` remains the only HTML shell renderer used by `Email`. `pcirn-layout.html` defines presentation; the renderer supplies escaped text and the existing five embedded assets. Templates keep their message-specific text and optional action metadata.

## Acceptance criteria

- Every sent email uses the shared approved visual shell.
- Existing inline assets and their content IDs continue to resolve.
- Emails with and without an action render correctly.
- User-controlled body, title, preheader, action label, and action URL remain escaped/validated.
- Renderer unit tests cover the approved structural contract.

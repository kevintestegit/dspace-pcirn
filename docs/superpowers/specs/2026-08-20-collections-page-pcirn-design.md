# PCIRN collection pages redesign

## Goal

Apply the approved PCIRN visual language to every collection page, based on the reference: institutional breadcrumb, collection identity card, navigation cards, compact filter rail, and search results workspace.

## Scope

- Customize the collection-page theme only.
- Keep the existing collection resolver, DSpace data streams, browse routes, pagination, filters, item links, and administrator actions.
- Preserve the existing global header and footer.
- Apply the same composition to every collection, not only Portarias e Atos Normativos Internos.

## Design

The collection page will use a light institutional canvas with navy typography, gold accents, rounded white surfaces, and restrained borders/shadows.

1. Breadcrumbs remain above the content and gain the same spacing and surface treatment as the reference.
2. The collection identity area becomes a responsive card containing the collection logo or a document fallback icon, a gold vertical rule, collection title, permanent handle, and copy affordance. Introductory/news content remains available below the identity content when present.
3. The browse-by component becomes the “Navegar” row of compact action cards. Existing links and active state remain router-driven; only presentation changes.
4. The browse workspace uses a two-column layout: filters on the left and the routed collection content/results on the right. The existing router outlet remains the source of browse results.
5. Existing loading and error states remain visible, but inherit the new spacing and surface language.

## Responsive behavior

- Desktop: identity card spans the content width; browse actions use a multi-column grid; filters and results remain side by side.
- Tablet: browse actions wrap; filter rail becomes narrower while preserving the results column.
- Mobile: identity content stacks; browse actions use a two-column or single-column layout; filters move above results; all links and controls remain reachable without horizontal scrolling.

## Implementation boundaries

- Primary files: `dspace-angular/source/src/themes/custom/app/collection-page/collection-page.component.html`, `.scss`, and `.ts` only when standalone imports require it.
- Reuse existing base DSpace components instead of duplicating collection data or browse logic.
- Add only collection-scoped styles and selectors; do not change the global header.

## Validation

- Add or update a focused static contract test for the collection composition and preserved native components.
- Run `git diff --check` and the focused Angular test.
- Confirm the Angular container reports `Compiled successfully.`.
- Verify a real collection URL in the browser at desktop and mobile widths: title, handle, browse links, filters, result content, loading/error states, and no horizontal overflow.

## Acceptance criteria

- Every collection page follows the approved visual structure.
- Existing collection navigation and search behavior still works.
- No header regression or global style leak is introduced.
- The collection page is usable at desktop, tablet, and mobile widths.

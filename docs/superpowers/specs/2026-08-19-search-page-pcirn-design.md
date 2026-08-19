# PCIRN search page visual redesign

## Objective

Make `/search` match the approved PCIRN reference: a light institutional search surface with the existing result data and interactions preserved. The header remains unchanged.

## Scope

- Activate the existing custom search-page stylesheet from `dspace-angular/source/src/themes/custom/app/search-page/search-page.component.ts`.
- Implement the approved visual language in `search-page.component.scss`: white cards, navy/gold PCIRN palette, breadcrumb strip, prominent search form, filter sidebar, result list, view controls, export/RSS actions, and responsive behavior.
- Style the existing DSpace search components through page-scoped selectors so search, filters, pagination, CSV export, RSS, view switching, and result links keep their current behavior and translations.
- Use the repository's existing Font Awesome icon set for visible affordances: search, filter, list/grid, download, RSS, info, document, expand/collapse, and navigation actions. Icon-only controls retain accessible labels from their existing components or receive CSS/HTML-safe labels where already supported.
- Preserve the existing header implementation and files. No header markup, behavior, or styling changes are part of this work.

## Component boundaries

The page component remains a thin themed wrapper around the base DSpace search page. The base template and search state stay authoritative; only the custom page stylesheet is enabled. `::ng-deep` is limited to selectors rooted at the themed search page because the visual targets live in nested DSpace components with their own Angular style encapsulation.

## Responsive behavior

Desktop keeps the two-column filter/result composition from the reference. Below the existing DSpace breakpoint, the search controls stack, filter controls remain reachable through the native sidebar toggle, result cards become single-column, and action buttons remain touch-sized. Focus-visible states and reduced-motion behavior are preserved.

## Validation

- `git diff --check`
- Angular build from `dspace-angular/source` using the repository's existing dependencies
- Served `/search` smoke check after the targeted Angular image rebuild
- Browser inspection of `/search` at desktop and narrow widths, confirming the header is unchanged and the search actions/results still operate

## Out of scope

- Header redesign or header icon replacement.
- Search API, routing, authorization, translations, result ordering, or filter semantics.
- New dependencies or new icon libraries.

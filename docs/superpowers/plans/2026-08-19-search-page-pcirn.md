# PCIRN Search Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reproduce the approved PCIRN search-page layout at `/search`, including the visual icon system, while leaving the existing header and search behavior untouched.

**Architecture:** Keep DSpace's base search component, state, translations, and nested search components as the source of behavior. Add a themed wrapper template only to provide a visual root, enable one custom page stylesheet, and use selectors rooted at that wrapper, with `::ng-deep` only where Angular child encapsulation requires it. Add a small Node contract test for the stylesheet activation and the approved visual/icon hooks.

**Tech Stack:** Angular 20 standalone components, SCSS, Bootstrap 5, Font Awesome 6 already bundled by DSpace, Node's built-in test runner.

---

### Task 1: Add the search visual contract test

**Files:**
- Create: `/dados/apps/dspace/scripts/pcirn-search.test.mjs`

- [ ] **Step 1: Write the failing test**

Create a test that reads the themed search component and stylesheet, then asserts the component loads the custom stylesheet and the stylesheet contains the page shell, search controls, filters, result card, responsive breakpoint, and existing icon classes. It must also assert that neither file references header components.

```js
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const sourceRoot = new URL('../dspace-angular/source/', import.meta.url);
const componentPath = new URL('src/themes/custom/app/search-page/search-page.component.ts', sourceRoot);
const templatePath = new URL('src/themes/custom/app/search-page/search-page.component.html', sourceRoot);
const stylePath = new URL('src/themes/custom/app/search-page/search-page.component.scss', sourceRoot);

const [component, template, styles] = await Promise.all([
  readFile(componentPath, 'utf8'),
  readFile(templatePath, 'utf8'),
  readFile(stylePath, 'utf8'),
]);

test('PCIRN search page enables its scoped visual stylesheet', () => {
  assert.match(component, /^\s*styleUrls:\s*\[['"]\.\/search-page\.component\.scss['"]\]/m);
  assert.match(component, /^\s*templateUrl:\s*['"]\.\/search-page\.component\.html['"]/m);
  assert.match(template, /class="pcirn-search-page"/);
  assert.doesNotMatch(component, /header|navbar/i);
  assert.doesNotMatch(template, /header|navbar/i);
});

test('PCIRN search stylesheet exposes the approved visual/icon contract', () => {
  for (const hook of [
    ':host ::ng-deep',
    '#search-form',
    '#search-sidebar',
    '#search-content',
    '.search-button',
    '.scope-button',
    '.fa-search',
    '.fa-filter',
    '.fa-list',
    '.fa-th-large',
    '.fa-file-export',
    '.fa-rss-square',
    '.fa-file-alt',
    '@media (max-width:',
  ]) {
    assert.match(styles, new RegExp(hook.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  }
  assert.doesNotMatch(styles, /header|navbar/i);
});
```

- [ ] **Step 2: Run it before implementation and verify it fails**

Run:

```bash
node --test scripts/pcirn-search.test.mjs
```

Expected: FAIL because the custom search stylesheet is not enabled and is empty.

### Task 2: Enable the custom search page stylesheet

**Files:**
- Modify: `/dados/apps/dspace/dspace-angular/source/src/themes/custom/app/search-page/search-page.component.ts`
- Modify: `/dados/apps/dspace/dspace-angular/source/src/themes/custom/app/search-page/search-page.component.html`

- [ ] **Step 1: Change only the component stylesheet metadata**

Replace the commented template and style entries with:

```ts
  templateUrl: './search-page.component.html',
  styleUrls: ['./search-page.component.scss'],
```

In the custom HTML file, keep the base page behavior and add only the visual root:

```html
<div class="pcirn-search-page">
  <ds-search [showCsvExport]="true" [trackStatistics]="true"></ds-search>
</div>
```

Keep the provider, imports, selector, and class body unchanged. Do not modify any header source file.

- [ ] **Step 2: Run the contract test**

Run:

```bash
node --test scripts/pcirn-search.test.mjs
```

Expected: still FAIL because the stylesheet hooks are not implemented yet.

### Task 3: Implement the approved search visual system

**Files:**
- Modify: `/dados/apps/dspace/dspace-angular/source/src/themes/custom/app/search-page/search-page.component.scss`

- [ ] **Step 1: Add the page-scoped layout and tokens**

Add a `:host` block with `--pcirn-navy: #07345f`, `--pcirn-navy-dark: #062b4f`, `--pcirn-gold: #d79b00`, `--pcirn-ink: #24364b`, `--pcirn-muted: #667587`, and `--pcirn-line: #dfe6ec`. Use `:host ::ng-deep` selectors rooted at the themed page component and target the existing `#search-form`, `#search-sidebar`, and `#search-content` nodes because the base template owns the markup.

The stylesheet must include these concrete visual rules:

```scss
:host {
  --pcirn-navy: #07345f;
  --pcirn-navy-dark: #062b4f;
  --pcirn-gold: #d79b00;
  --pcirn-ink: #24364b;
  --pcirn-muted: #667587;
  --pcirn-line: #dfe6ec;
}

:host ::ng-deep #search-content {
  color: var(--pcirn-ink);
  padding-block: 1.5rem 3rem;
}

:host ::ng-deep #search-form {
  margin-bottom: 1.5rem;
  padding: .75rem;
  border: 1px solid rgba(16, 54, 88, .08);
  border-radius: 1rem;
  background: #fff;
  box-shadow: 0 .65rem 1.5rem rgba(15, 44, 72, .08);
}

:host ::ng-deep #search-form .input-group {
  gap: .75rem;
  margin-bottom: 0 !important;
}
```

- [ ] **Step 2: Style the search controls and existing Font Awesome icons**

Keep the existing form/button DOM and target its classes. Make `.scope-button`, the query input, and `.search-button` at least `3.5rem` high on desktop, set the button background to `var(--pcirn-navy)`, and style `.fa-search`, `.fa-filter`, `.fa-list`, `.fa-th-large`, `.fa-file-export`, `.fa-rss-square`, `.fa-file-alt`, `.fa-info-circle`, `.fa-plus`, and `.fa-minus` with the navy/gold palette. Add `:focus-visible` outlines with `var(--pcirn-gold)` without changing click or submit behavior.

- [ ] **Step 3: Style the sidebar, filters, results, export, RSS, and view controls**

Use nested selectors rooted at `#search-sidebar` and `#search-content` to create the two-column composition: sidebar width `22rem` at desktop, white filter cards with `1px solid var(--pcirn-line)`, navy headings, gold expand/collapse affordances, and result content with a white rounded card, subtle shadow, navy result heading, and light document thumbnail surface. Style `.btn-group` view buttons as a compact list/grid toggle, and style export/RSS buttons as separate bordered icon squares. Preserve the existing RSS/export anchors and their accessible labels.

- [ ] **Step 4: Add responsive behavior and reduced-motion support**

At `max-width: 991.98px`, stack the search form, make the query input full width, keep the native mobile sidebar toggle visible, and make result cards single-column. At `max-width: 575.98px`, reduce page padding and let action groups wrap. Add a `prefers-reduced-motion: reduce` block that disables transitions/animations introduced by this stylesheet.

- [ ] **Step 5: Run the contract test**

Run:

```bash
node --test scripts/pcirn-search.test.mjs
```

Expected: PASS for both tests.

### Task 4: Build and verify the running Angular service

**Files:**
- No additional source files.

- [ ] **Step 1: Check formatting and compile the Angular application**

Run from `/dados/apps/dspace`:

```bash
git diff --check
cd dspace-angular/source
npm run build
```

Expected: `git diff --check` exits cleanly and Angular completes compilation without errors.

- [ ] **Step 2: Rebuild only the Angular image and recreate its service**

Run:

```bash
cd /dados/apps/dspace/dspace-angular/source
docker build -f Dockerfile.dist -t dspace-angular-pcirn-v6:local .
cd /dados/apps/dspace
docker compose up -d --no-build --force-recreate dspace-angular
```

Expected: the existing `dspace-angular` service is recreated from the new local image; backend, Solr, database, volumes, and unrelated containers remain untouched.

- [ ] **Step 3: Verify SSR and browser-visible search markup**

Run:

```bash
docker exec dspace-angular node -e "fetch('http://localhost:4000/search?query=teste').then(async r => { const t = await r.text(); console.log(r.status, t.includes('search-form'), t.includes('search-content')); })"
```

Expected: `200 true true`. Then inspect `/search?query=teste` at desktop and narrow widths; confirm the header is visually unchanged, the search button submits, filter controls remain interactive, view-mode buttons navigate, and export/RSS actions remain present.

- [ ] **Step 4: Review the final diff**

Run:

```bash
git status --short
git diff --check
git diff --stat -- scripts/pcirn-search.test.mjs dspace-angular/source/src/themes/custom/app/search-page/search-page.component.ts dspace-angular/source/src/themes/custom/app/search-page/search-page.component.scss
```

Expected: only the search contract test and the three custom search-page files are part of this implementation change; no header file is modified.

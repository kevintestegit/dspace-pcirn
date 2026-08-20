# PCIRN Collections Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the approved PCIRN collection-page composition to every collection while preserving native DSpace data, routing, browse behavior, and global chrome.

**Architecture:** The custom collection theme owns the page shell and scoped visual system. Existing DSpace components continue to provide collection data, handle, browse navigation, routed results, loading, errors, and admin actions. Only the themed collection page gains a clipboard method.

**Tech Stack:** Angular standalone components, Angular templates, SCSS, Node `node:test`, Docker Angular hot compilation, Chrome CDP browser verification.

---

### Task 1: Add the focused collection visual contract test

**Files:**
- Create: `dspace-angular/source/scripts/pcirn-collection.test.mjs`
- Read: `dspace-angular/source/src/themes/custom/app/collection-page/collection-page.component.html`
- Read: `dspace-angular/source/src/themes/custom/app/collection-page/collection-page.component.scss`

- [ ] **Step 1: Write the failing test**

Read the two custom files and assert that the template contains `pcirn-collection-page`, `pcirn-collection-identity`, `pcirn-collection-navigation`, `pcirn-collection-workspace`, `ds-comcol-page-browse-by`, `router-outlet`, and `copyHandle`; assert the stylesheet contains the identity/workspace selectors and a `max-width: 760px` media query.

- [ ] **Step 2: Run the test and verify it fails**

Run `node --test scripts/pcirn-collection.test.mjs`. Expected: FAIL because the current custom collection template and stylesheet are empty.

- [ ] **Step 3: Commit the red test**

Run `git add scripts/pcirn-collection.test.mjs && git commit -m "test: define collections page contract"`.

### Task 2: Implement the custom collection page shell

**Files:**
- Modify: `dspace-angular/source/src/themes/custom/app/collection-page/collection-page.component.html`
- Modify: `dspace-angular/source/src/themes/custom/app/collection-page/collection-page.component.scss`
- Modify: `dspace-angular/source/src/themes/custom/app/collection-page/collection-page.component.ts`

- [ ] **Step 1: Replace the empty custom template**

Retain `collectionRD$`, `logoRD$`, `dsoNameService`, `ds-comcol-page-browse-by`, `router-outlet`, `ds-dso-edit-menu`, loading, error, copyright, introductory text, and sidebar/news content. Wrap them in `pcirn-collection-page`, `pcirn-collection-identity`, `pcirn-collection-navigation`, and `pcirn-collection-workspace` regions. The identity card contains the existing header/logo/handle components, a gold rule, and a copy button bound to `copyHandle(collection.handle)`. The browse region keeps the existing browse component and routed outlet; do not recreate browse options or result data.

- [ ] **Step 2: Add clipboard behavior**

Add `copyHandle(handle: string): void { if (typeof navigator !== 'undefined' && navigator.clipboard) { void navigator.clipboard.writeText(handle); } }` to the custom themed `CollectionPageComponent`. Do not change collection data services or routes.

- [ ] **Step 3: Add collection-scoped responsive SCSS**

Use navy/gold variables, white rounded identity/result surfaces, a multi-column navigation grid, a two-column workspace, mobile stacking, and `overflow-x: hidden` on the page shell. Keep selectors under `.pcirn-collection-page`; use `::ng-deep` only for presentation overrides of existing child DSpace components.

- [ ] **Step 4: Run the focused test**

Run `node --test scripts/pcirn-collection.test.mjs`. Expected: PASS for the collection visual contract.

- [ ] **Step 5: Commit the themed implementation**

Run `git add src/themes/custom/app/collection-page/collection-page.component.html src/themes/custom/app/collection-page/collection-page.component.scss src/themes/custom/app/collection-page/collection-page.component.ts && git commit -m "feat: redesign PCIRN collection pages"`.

### Task 3: Compile and verify the rendered collection page

**Files:**
- Verify: `dspace-angular/source/src/themes/custom/app/collection-page/collection-page.component.html`
- Verify: `dspace-angular/source/src/themes/custom/app/collection-page/collection-page.component.scss`

- [ ] **Step 1: Run static checks**

Run `node --test scripts/pcirn-collection.test.mjs`, `git diff --check`, and `git diff --check -- src/themes/custom/app/collection-page/collection-page.component.html src/themes/custom/app/collection-page/collection-page.component.scss src/themes/custom/app/collection-page/collection-page.component.ts`. Expected: all pass.

- [ ] **Step 2: Confirm Angular hot compilation**

Run `sleep 10; docker logs dspace-angular 2>&1 | tail -80`. Expected: the latest build ends with `Compiled successfully.` and contains no collection template or Sass errors.

- [ ] **Step 3: Verify desktop and mobile browser geometry**

Open any existing collection from `http://10.9.233.96:4000/community-list` and verify the resulting collection URL. Confirm identity, navigation, workspace, browse links, filters, routed result content, loading/error states, and no horizontal overflow. Desktop must keep filters and results side by side; mobile must stack them.

- [ ] **Step 4: Preserve unrelated worktree changes**

Run `git status --short -- src/themes/custom/app/collection-page scripts/pcirn-collection.test.mjs` and `git log -2 --oneline`. Expected: only intended collection files and the focused test are changed by this work.

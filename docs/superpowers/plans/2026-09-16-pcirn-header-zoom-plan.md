# PCIRN Header Zoom Stability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Keep the PCIRN brand inside the intended masthead band when browser zoom changes the CSS viewport width.

**Architecture:** Preserve the existing two-band header, brand markup, DSpace navigation, search, language selector, and authentication controls. Normalize the desktop masthead height to `80px` from `768px` upward, leaving the existing mobile override intact; add a source-contract regression assertion for the removed height jump.

**Tech Stack:** DSpace Angular, Angular component SCSS, Node.js `node:test`.

---

### Task 1: Add the failing regression contract

**Files:**
- Modify: `dspace-angular/source/scripts/pcirn-home.test.mjs` near the existing header breakpoint tests

- [ ] **Step 1: Add the assertion for a stable desktop masthead height**

Add this test after `header trims the white flap without resizing the blue shape`:

```js
test('header keeps one desktop masthead height across zoom breakpoints', () => {
  assert.match(customHeaderWrapperStyles, /\.pcirn-header-masthead \{[\s\S]*?height: 80px;/);
  assert.match(customHeaderWrapperStyles, /@media \(min-width: 768px\) and \(max-width: 1599\.98px\) \{[\s\S]*?\.pcirn-header-masthead \{ height: 80px; \}/);
  assert.doesNotMatch(customHeaderWrapperStyles, /@media \(min-width: 1200px\) and \(max-width: 1599\.98px\) \{\s*\.pcirn-header-masthead \{ height: 80px; \}\s*\}/);
});
```

- [ ] **Step 2: Run the focused test and confirm the expected failure**

Run from `dspace-angular/source`:

```bash
node --test scripts/pcirn-home.test.mjs
```

Expected: FAIL because the current base masthead is `64px`, the intermediate rule is `90px`, and the dedicated `1200–1599.98px` rule still exists.

### Task 2: Normalize the desktop masthead CSS

**Files:**
- Modify: `dspace-angular/source/src/themes/custom/app/header-nav-wrapper/header-navbar-wrapper.component.scss:28-31,133-148`

- [ ] **Step 1: Set the base desktop height to `80px`**

Change:

```scss
.pcirn-header-masthead {
  color: #fff;
  height: 64px;
  position: relative;
}
```

to:

```scss
.pcirn-header-masthead {
  color: #fff;
  height: 80px;
  position: relative;
}
```

- [ ] **Step 2: Remove the intermediate height jump**

Change the `768–1599.98px` rule from `height: 90px` to `height: 80px`, then remove the now-obsolete `1200–1599.98px` rule. Do not change the mobile `height: 92px` override or any navigation/control markup.

### Task 3: Verify source, build, and visual behavior

**Files:**
- No additional files

- [ ] **Step 1: Run the focused regression test**

```bash
node --test scripts/pcirn-home.test.mjs
```

Expected: PASS.

- [ ] **Step 2: Run formatting validation for the changed files**

```bash
git diff --check -- dspace-angular/source/scripts/pcirn-home.test.mjs dspace-angular/source/src/themes/custom/app/header-nav-wrapper/header-navbar-wrapper.component.scss
```

Expected: no output and exit code `0`.

- [ ] **Step 3: Rebuild the Angular application**

Run from `dspace-angular/source`:

```bash
npm run build
```

Expected: successful Angular compilation with exit code `0`.

- [ ] **Step 4: Inspect the final diff and preserve unrelated work**

```bash
git -C /dados/apps/dspace/dspace-angular/source diff --check
git -C /dados/apps/dspace/dspace-angular/source status --short
```

Expected: only the focused test and header SCSS are changed by this task; all pre-existing dirty files remain untouched.

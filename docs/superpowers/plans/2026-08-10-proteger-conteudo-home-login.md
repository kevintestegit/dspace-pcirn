# Proteger conteúdo da home com login Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Require authentication before the home cards can open `/search` or `/community-list`, while keeping the home public and preserving the existing post-login redirect.

**Architecture:** Reuse `authenticatedGuard` in the root route definitions alongside `endUserAgreementCurrentUserGuard`. Add a small source-level regression test to ensure both protected destinations keep the authentication guard.

**Tech Stack:** Angular routing, TypeScript, Node.js built-in test runner.

---

### Task 1: Add the failing route-protection regression test

**Files:**
- Modify: `dspace-angular/source/scripts/pcirn-home.test.mjs`

- [ ] **Step 1: Add the route source fixture and assertion**

Read `../src/app/app-routes.ts` beside the existing home template and config, then add a test that extracts the `community-list` and `search` route blocks and asserts each contains `authenticatedGuard`.

- [ ] **Step 2: Run the focused test to verify it fails**

Run:

```bash
cd dspace-angular/source
node --test scripts/pcirn-home.test.mjs
```

Expected: the existing home tests pass and the new route-protection test fails because the two route blocks currently contain only `endUserAgreementCurrentUserGuard`.

### Task 2: Apply the existing authentication guard

**Files:**
- Modify: `dspace-angular/source/src/app/app-routes.ts`

- [ ] **Step 1: Add `authenticatedGuard` to both destination routes**

Change only the `canActivate` arrays for the `community-list` and `search` root routes:

```ts
canActivate: [authenticatedGuard, endUserAgreementCurrentUserGuard],
```

Keep the existing import and all other routes unchanged.

- [ ] **Step 2: Run the focused test to verify it passes**

Run:

```bash
cd dspace-angular/source
node --test scripts/pcirn-home.test.mjs
```

Expected: all tests pass.

### Task 3: Validate the Angular checkout

**Files:**
- No additional files.

- [ ] **Step 1: Run TypeScript lint compilation**

Run `npm run build:lint` from `dspace-angular/source` and expect exit code 0.

- [ ] **Step 2: Run the Angular production build**

Run `npm run build` from `dspace-angular/source` and expect exit code 0.

- [ ] **Step 3: Inspect the final diff**

Run `git diff --check` and `git status --short`; confirm only the intended Angular test/route files and the approved design/plan documents are attributable to this task, while preserving unrelated existing worktree changes.

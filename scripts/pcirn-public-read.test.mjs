import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const appRoutes = await readFile(new URL('../dspace-angular/source/src/app/app-routes.ts', import.meta.url), 'utf8');

test('browse route does not require authenticatedGuard', () => {
  // Extract the browse route block from app-routes.ts
  const browseMatch = appRoutes.match(/\{\s*path:\s*'browse'[\s\S]*?\},/);
  assert.ok(browseMatch, 'browse route block should exist in app-routes.ts');
  assert.doesNotMatch(browseMatch[0], /authenticatedGuard/, 'browse route must not require authenticatedGuard');
});

const migration = await readFile(new URL('../dspace-api/src/main/resources/org/dspace/storage/rdbms/sqlmigration/postgres/V9.4_2026.09.15__pcirn_public_items.sql', import.meta.url), 'utf8');
const forms = await readFile(new URL('../dspace/config/submission-forms.xml', import.meta.url), 'utf8');
const action = await readFile(new URL('../dspace-api/src/main/java/org/dspace/xmlworkflow/state/actions/processingaction/AcceptEditRejectAction.java', import.meta.url), 'utf8');

test('public read migration grants Anonymous access to the whole repository', () => {
  assert.match(migration, /Anonymous/);
  assert.match(migration, /FROM community c/);
  assert.match(migration, /FROM collection c/);
  assert.match(migration, /\(VALUES \(0\), \(9\), \(10\)\)/);
  assert.match(migration, /FROM item i/);
  assert.match(migration, /i\.in_archive = true/);
  assert.match(migration, /i\.withdrawn = false/);
  assert.match(migration, /JOIN item2bundle/);
  assert.match(migration, /JOIN bundle2bitstream/);
  assert.match(migration, /RAISE EXCEPTION/);
});

test('public read migration removes the redundant authenticated and sector reads', () => {
  assert.match(migration, /DELETE FROM resourcepolicy/);
  assert.match(migration, /Usuarios_Logados/);
  assert.match(migration, /PCIRN_Setor_%/);
  assert.match(migration, /rp\.action_id IN \(0, 9, 10\)/);
});

test('the submission form no longer asks for an access level', () => {
  assert.doesNotMatch(forms, /Nível de acesso/);
});

test('the reviewer action exposes the four NUGECID decisions and no pool return', () => {
  assert.match(action, /SUBMIT_APPROVE/);
  assert.match(action, /SUBMIT_REJECT/);
  assert.match(action, /SUBMIT_EDIT_METADATA/);
  assert.match(action, /SUBMIT_DELETE = "submit_delete"/);
  assert.match(action, /deleteWorkflowByWorkflowItem/);
  assert.doesNotMatch(action, /options\.add\(RETURN_TO_POOL\)/);
});

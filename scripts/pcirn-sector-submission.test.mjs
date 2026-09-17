import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const migration = await readFile(new URL('../dspace-api/src/main/resources/org/dspace/storage/rdbms/sqlmigration/postgres/V9.4_2026.08.24__pcirn_sector_submission_and_shared_read.sql', import.meta.url), 'utf8');
const submissionConfig = await readFile(new URL('../dspace/config/item-submission.xml', import.meta.url), 'utf8');
const workflowConfig = await readFile(new URL('../dspace/config/spring/api/workflow.xml', import.meta.url), 'utf8');

test('sector submission migration defines the NUGECID authorization contract', () => {
  assert.match(migration, /Documentos do NUGECID/);
  assert.match(migration, /PCIRN_Setor_NUGECID/);
  assert.match(migration, /Usuarios_Logados/);
  assert.match(migration, /PCIRN_Depositantes/);
  assert.match(migration, /action_id\s*=\s*3/);
  assert.match(migration, /action_id\s*=\s*0/);
  assert.match(migration, /cwf_collectionrole/);
  assert.match(migration, /editor/);
  assert.match(migration, /RAISE EXCEPTION/);
});

test('the native PCIRN submission and NUGECID workflow remain configured', () => {
  const pcirnProcess = submissionConfig.match(/<submission-process name="pcirn">([\s\S]*?)<\/submission-process>/)[1];
  assert.match(pcirnProcess, /<step id="collection"\/>/);
  assert.match(pcirnProcess, /<step id="pcirnpageone"\/>/);
  assert.match(pcirnProcess, /<step id="pcirnpagetwo"\/>/);
  assert.match(pcirnProcess, /<step id="upload"\/>/);
  assert.match(pcirnProcess, /<step id="license"\/>/);
  assert.doesNotMatch(pcirnProcess, /itemAccessConditions/);
  assert.match(workflowConfig, /<property name="name" value="NUGECID"\/>/);
  assert.match(workflowConfig, /scope" value="#\{ T\(org\.dspace\.xmlworkflow\.Role\.Scope\)\.REPOSITORY\}"/);
});

import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import assert from 'node:assert/strict';

test('NotifyInfo component uses PCIRN list surface and header hierarchy', () => {
  const html = readFileSync(
    new URL('../dspace-angular/source/src/app/info/notify-info/notify-info.component.html', import.meta.url),
    'utf8',
  );
  assert.match(html, /<main\s+class="pcirn-list pcirn-notify-surface"/);
  assert.match(html, /pcirn-notify-pill-badge/);
  assert.match(html, /pcirn-notify-card/);
  assert.match(html, /pcirn-notify-sidebar/);
  assert.match(html, /'coar-notify-support\.title'/);
  assert.match(html, /'coar-notify-support\.ldn-inbox\.title'/);
  assert.match(html, /'coar-notify-support\.message-moderation\.title'/);
});

test('WorkspaceItems delete page uses PCIRN theme card and header hierarchy', () => {
  const html = readFileSync(
    new URL('../dspace-angular/source/src/themes/custom/app/workspaceitems-edit-page/workspaceitems-delete-page/workspaceitems-delete-page.component.html', import.meta.url),
    'utf8',
  );
  assert.match(html, /<main\s+class="pcirn-list pcirn-workspace-delete-surface"/);
  assert.match(html, /pcirn-workspace-delete-card/);
  assert.match(html, /'workspace-item\.delete\.header'/);
  assert.match(html, /'workspace-item\.delete\.button\.confirm'/);
  assert.match(html, /'workspace-item\.delete\.button\.cancel'/);
});

test('Bitstream download page uses PCIRN theme card and header hierarchy', () => {
  const html = readFileSync(
    new URL('../dspace-angular/source/src/app/bitstream-page/bitstream-download-page/bitstream-download-page.component.html', import.meta.url),
    'utf8',
  );
  assert.match(html, /<main\s+class="pcirn-list pcirn-download-surface"/);
  assert.match(html, /pcirn-download-pill-badge/);
  assert.match(html, /pcirn-download-card/);
  assert.match(html, /pcirn-btn-back/);
  assert.match(html, /'bitstream\.download\.page'/);
});

test('Submission import external page uses PCIRN theme card and header hierarchy', () => {
  const html = readFileSync(
    new URL('../dspace-angular/source/src/app/submission/import-external/submission-import-external.component.html', import.meta.url),
    'utf8',
  );
  assert.match(html, /<main\s+class="pcirn-list pcirn-import-external-surface"/);
  assert.match(html, /pcirn-import-pill-badge/);
  assert.match(html, /pcirn-import-search-card/);
  assert.match(html, /ds-submission-import-external-searchbar/);
});

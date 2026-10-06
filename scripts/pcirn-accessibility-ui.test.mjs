import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import assert from 'node:assert/strict';

const htmlTemplate = readFileSync(
  new URL('../dspace-angular/source/src/app/info/accessibility-settings/accessibility-settings.component.html', import.meta.url),
  'utf8',
);

const scssContent = readFileSync(
  new URL('../dspace-angular/source/src/app/info/accessibility-settings/accessibility-settings.component.scss', import.meta.url),
  'utf8',
);

const tsContent = readFileSync(
  new URL('../dspace-angular/source/src/app/info/accessibility-settings/accessibility-settings.component.ts', import.meta.url),
  'utf8',
);

test('Accessibility component uses PCIRN list surface and header hierarchy', () => {
  assert.match(htmlTemplate, /<main\s+class="pcirn-list pcirn-accessibility-surface"/);
  assert.match(htmlTemplate, /<div\s+class="pcirn-list-inner"/);
  assert.match(htmlTemplate, /<header\s+class="pcirn-accessibility-header"/);
  assert.match(htmlTemplate, /pcirn-accessibility-pill-badge/);
  assert.match(htmlTemplate, /<h1>\{\{\s*'info\.accessibility-settings\.title'\s*\|\s*translate\s*\}\}<\/h1>/);
});

test('Accessibility component preserves all translated keys and bindings', () => {
  const expectedKeys = [
    'info.accessibility-settings.title',
    'info.accessibility-settings.disableNotificationTimeOut.label',
    'info.accessibility-settings.disableNotificationTimeOut.hint',
    'info.accessibility-settings.notificationTimeOut.label',
    'info.accessibility-settings.notificationTimeOut.hint',
    'info.accessibility-settings.notificationTimeOut.invalid',
    'info.accessibility-settings.liveRegionTimeOut.label',
    'info.accessibility-settings.liveRegionTimeOut.hint',
    'info.accessibility-settings.liveRegionTimeOut.invalid',
    'info.accessibility-settings.submit',
    'info.accessibility-settings.reset',
    'info.accessibility-settings.cookie-warning',
  ];

  for (const key of expectedKeys) {
    assert.match(htmlTemplate, new RegExp(key.replace(/\./g, '\\.')));
  }

  assert.match(htmlTemplate, /\(click\)="saveSettings\(\)"/);
  assert.match(htmlTemplate, /\(click\)="resetSettings\(\)"/);
  assert.match(htmlTemplate, /\[id\]="'disableNotificationTimeOutInput'"/);
  assert.match(htmlTemplate, /\[id\]="'notificationTimeOutInput'"/);
  assert.match(htmlTemplate, /\[id\]="'liveRegionTimeOutInput'"/);
  assert.match(htmlTemplate, /\*dsContextHelp=/);
});

test('Accessibility component includes structured card layout and assistive sidebar', () => {
  assert.match(htmlTemplate, /class="[^"]*pcirn-accessibility-card[^"]*"/);
  assert.match(htmlTemplate, /class="[^"]*pcirn-accessibility-sidebar[^"]*"/);
  assert.match(htmlTemplate, /class="[^"]*pcirn-card-badge-icon[^"]*"/);
  assert.match(htmlTemplate, /class="[^"]*pcirn-actions-bar[^"]*"/);
});

test('Accessibility SCSS defines PCIRN variables and responsive grid', () => {
  assert.match(scssContent, /--pcirn-navy-deep:/);
  assert.match(scssContent, /--pcirn-blue:/);
  assert.match(scssContent, /--pcirn-paper:/);
  assert.match(scssContent, /\.pcirn-accessibility-grid/);
  assert.match(scssContent, /\.pcirn-btn-save/);
  assert.match(scssContent, /\.pcirn-btn-reset/);
});

test('Accessibility TypeScript links component stylesheet', () => {
  assert.match(tsContent, /styleUrls:\s*\[\s*'\.\/accessibility-settings\.component\.scss'\s*\]/);
});

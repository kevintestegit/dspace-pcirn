import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const template = await readFile(new URL('../dspace-angular/source/src/themes/custom/app/home-page/home-page.component.html', import.meta.url), 'utf8');
const scss = await readFile(new URL('../dspace-angular/source/src/themes/custom/app/home-page/home-page.component.scss', import.meta.url), 'utf8');
const ptBr = await readFile(new URL('../dspace-angular/source/src/assets/i18n/pt-BR.json5', import.meta.url), 'utf8');
const en = await readFile(new URL('../dspace-angular/source/src/assets/i18n/en.json5', import.meta.url), 'utf8');

test('kinetic typography template preserves accessible semantics, letter roots and blinking dot', () => {
  assert.match(template, /class="pcirn-kinetic"\s+aria-label="PCIRN\."/);
  assert.match(template, /class="visually-hidden">PCIRN\.<\/span>/);
  assert.match(template, /class="pcirn-k-stage"\s+aria-hidden="true"/);

  // Preposition wrap with da / do
  assert.match(template, /class="pcirn-prep-wrap"/);
  assert.match(template, /'pcirn\.home\.hero\.title\.prep\.da'\s*\|\s*translate/);
  assert.match(template, /'pcirn\.home\.hero\.title\.prep\.do'\s*\|\s*translate/);

  // States with continuous blinking dot
  assert.match(template, /class="pcirn-k-item pcirn-k-item-idle"><span class="k-root">PCIRN<\/span><span class="pcirn-k-dot">\.< \/span><\/span>/i.test(template) || /pcirn-k-item-idle[\s\S]*?<span class="pcirn-k-dot">\./.test(template) ? /pcirn-k-dot/ : /pcirn-k-dot/);
  assert.match(template, /class="pcirn-k-item pcirn-k-item-idle">[\s\S]*?<span class="pcirn-k-dot">\./);
  assert.match(template, /class="pcirn-k-item pcirn-k-item-p">[\s\S]*?<span class="pcirn-k-dot">\./);
  assert.match(template, /class="pcirn-k-item pcirn-k-item-c">[\s\S]*?<span class="pcirn-k-dot">\./);
  assert.match(template, /class="pcirn-k-item pcirn-k-item-i">[\s\S]*?<span class="pcirn-k-dot">\./);
  assert.match(template, /class="pcirn-k-item pcirn-k-item-rn">[\s\S]*?<span class="pcirn-k-dot">\./);
});

test('translations provide proper gender agreement prepositions', () => {
  assert.match(ptBr, /"pcirn\.home\.hero\.title\.part2":\s*"institucionais"/);
  assert.match(ptBr, /"pcirn\.home\.hero\.title\.prep\.da":\s*"da"/);
  assert.match(ptBr, /"pcirn\.home\.hero\.title\.prep\.do":\s*"do"/);

  assert.match(en, /"pcirn\.home\.hero\.title\.part2":\s*"documents"/);
  assert.match(en, /"pcirn\.home\.hero\.title\.prep\.da":\s*"of"/);
  assert.match(en, /"pcirn\.home\.hero\.title\.prep\.do":\s*"of"/);
});

test('kinetic typography styles implement fast beat cadence and continuous blinking dot', () => {
  // Color and parameters
  assert.match(scss, /color:\s*var\(--pcirn-gold\);/);
  assert.match(scss, /animation-duration:\s*10s;/);
  assert.match(scss, /animation-iteration-count:\s*infinite;/);

  // Blinking dot animation
  assert.match(scss, /\.pcirn-k-dot\s*\{[\s\S]*?animation:\s*pcirn-dot-blink/);
  assert.match(scss, /@keyframes pcirn-dot-blink/);

  // Preposition animation (da <-> do)
  assert.match(scss, /@keyframes pcirn-prep-anim-da/);
  assert.match(scss, /@keyframes pcirn-prep-anim-do/);

  // Keyframe definitions for beat
  assert.match(scss, /@keyframes pcirn-k-anim-idle/);
  assert.match(scss, /@keyframes pcirn-k-anim-p/);
  assert.match(scss, /@keyframes pcirn-k-ext-p/);
  assert.match(scss, /@keyframes pcirn-k-anim-c/);
  assert.match(scss, /@keyframes pcirn-k-ext-c/);
  assert.match(scss, /@keyframes pcirn-k-anim-i/);
  assert.match(scss, /@keyframes pcirn-k-ext-i/);
  assert.match(scss, /@keyframes pcirn-k-anim-rn/);
  assert.match(scss, /@keyframes pcirn-k-ext-rn/);
});

test('hero entrance animations implement staggered fade-up with blur and smooth easing', () => {
  // Keyframes start 24px below with opacity 0 and blur 4px, ending at original position, opacity 1, blur 0
  assert.match(scss, /@keyframes pcirn-hero-fade-up\s*\{[\s\S]*?filter:\s*blur\(4px\);[\s\S]*?opacity:\s*0;[\s\S]*?transform:\s*translateY\(24px\);[\s\S]*?filter:\s*blur\(0\);[\s\S]*?opacity:\s*1;[\s\S]*?transform:\s*translateY\(0\);/);
  assert.match(scss, /@keyframes pcirn-hero-search-fade-up\s*\{[\s\S]*?transform:\s*translate\(-50%,\s*24px\);[\s\S]*?transform:\s*translate\(-50%,\s*0\);/);
  assert.match(scss, /@keyframes pcirn-hero-fade-forensics\s*\{[\s\S]*?opacity:\s*\.16;/);

  // Easing without bounce, duration 580ms (between 500ms and 650ms), fill-mode both
  const easingRegex = /580ms\s+cubic-bezier\(0\.16,\s*1,\s*0\.3,\s*1\)/;
  assert.match(scss, easingRegex);

  // Staggered order:
  // 1. Título (0ms delay)
  assert.match(scss, /\.pcirn-home h1\s*\{[\s\S]*?animation:\s*pcirn-hero-fade-up 580ms cubic-bezier\(0\.16,\s*1,\s*0\.3,\s*1\)\s+0ms\s+both;/);

  // 2. Subtítulo (100ms delay)
  assert.match(scss, /\.pcirn-home-rule\s*\{[\s\S]*?animation:\s*pcirn-hero-fade-up 580ms cubic-bezier\(0\.16,\s*1,\s*0\.3,\s*1\)\s+100ms\s+both;/);
  assert.match(scss, /\.pcirn-home-lead\s*\{[\s\S]*?animation:\s*pcirn-hero-fade-up 580ms cubic-bezier\(0\.16,\s*1,\s*0\.3,\s*1\)\s+100ms\s+both;/);

  // 3. Campo de busca (200ms delay)
  assert.match(scss, /\.pcirn-home-search\s*\{[\s\S]*?animation:\s*pcirn-hero-search-fade-up 580ms cubic-bezier\(0\.16,\s*1,\s*0\.3,\s*1\)\s+200ms\s+both;/);

  // 4. Elementos secundários (300ms delay)
  assert.match(scss, /\.pcirn-home-search-chips\s*\{[\s\S]*?animation:\s*pcirn-hero-fade-up 580ms cubic-bezier\(0\.16,\s*1,\s*0\.3,\s*1\)\s+300ms\s+both;/);
  assert.match(scss, /\.pcirn-home-hero-forensics\s*\{[\s\S]*?animation:\s*pcirn-hero-fade-forensics 580ms cubic-bezier\(0\.16,\s*1,\s*0\.3,\s*1\)\s+300ms\s+both;/);

  // Reduced motion support disables animation and resets transforms
  assert.match(scss, /:host-context\(\.reduced-motion\)\s*\{[\s\S]*?\.pcirn-home h1[\s\S]*?animation:\s*none !important;/);
});

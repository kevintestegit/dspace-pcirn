import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import { readFileSync, mkdirSync, rmSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const out = join(here, 'out');
const raw = join(out, 'raw');
const GRACE = 2.0;
const TAIL = 0.4;

rmSync(raw, { recursive: true, force: true });
mkdirSync(raw, { recursive: true });

const durations = JSON.parse(readFileSync(join(out, 'durations.json'), 'utf8'));
const anim = durations.reduce((a, b) => a + b, 0) + TAIL;

const browser = await chromium.launch();
const ctx = await browser.newContext({
  viewport: { width: 1280, height: 720 },
  recordVideo: { dir: raw, size: { width: 1280, height: 720 } },
});
const page = await ctx.newPage();
await page.addInitScript(d => { window.__SEGMENT_DURATIONS = d; }, durations);
await page.goto('file://' + join(here, 'scene.html'));
await page.waitForFunction('window.__READY === true');
await page.evaluate('window.start()');
await page.waitForFunction('window.__DONE === true', null, { timeout: (anim + 15) * 1000 });
await page.waitForTimeout(GRACE * 1000);
const video = page.video();
await ctx.close();
await browser.close();

const webm = await video.path();
const vdur = parseFloat(execFileSync('ffprobe', [
  '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', webm
]).toString().trim());
const lead = Math.max(0, vdur - anim - GRACE);
console.log(`raw=${vdur.toFixed(2)}s anim=${anim.toFixed(2)}s lead=${lead.toFixed(2)}s`);

execFileSync('ffmpeg', [
  '-y', '-v', 'error',
  '-ss', lead.toFixed(3), '-i', webm,
  '-i', join(out, 'voice.mp3'),
  '-i', join(out, 'subs.srt'),
  '-map', '0:v', '-map', '1:a', '-map', '2:s',
  '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p',
  '-c:a', 'aac', '-b:a', '192k',
  '-c:s', 'mov_text',
  '-shortest',
  join(out, 'dspace-explainer.mp4'),
], { stdio: 'inherit' });

console.log('ok -> out/dspace-explainer.mp4');

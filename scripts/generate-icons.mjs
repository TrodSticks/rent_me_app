// Renders the Rent Me symbol (Brand Guideline §11 / App Icon Guide) to the PNGs
// referenced by app.json. Run: node scripts/generate-icons.mjs
// Needs Playwright with Chromium available (npm i -g playwright).
import { createRequire } from 'node:module';
import { execSync } from 'node:child_process';
import path from 'node:path';

const require = createRequire(import.meta.url);
const { chromium } = require(
  require.resolve('playwright', { paths: [execSync('npm root -g').toString().trim()] }),
);

const BLUE = '#0D6EFD';
const NAVY = '#0F172A';
const WHITE = '#FFFFFF';

/** The symbol, in a 100×100 box: roof + chimney, pin, four-pane window. */
function mark({ roof, pin, window: win }) {
  const panes = [
    [41.5, 50], [51, 50], [41.5, 59.5], [51, 59.5],
  ].map(([x, y]) => `<rect x="${x}" y="${y}" width="7.5" height="7.5" rx="1.6" fill="${win}"/>`);
  return `
    <path d="M8 50 L50 14 L92 50" stroke="${roof}" stroke-width="9" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
    <rect x="69" y="18" width="9" height="17" rx="1.5" fill="${roof}"/>
    <path d="M50 34 C35.6 34 25 44.6 25 58.5 C25 74 42 87 50 95 C58 87 75 74 75 58.5 C75 44.6 64.4 34 50 34 Z" fill="${pin}"/>
    ${panes.join('')}`;
}

/** Symbol scaled to `scale` of the canvas and centred, on an optional background. */
function svg(size, { bg, scale, colors }) {
  const s = (size * scale) / 100;
  const off = (size - size * scale) / 2;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
    ${bg ? `<rect width="${size}" height="${size}" fill="${bg}"/>` : ''}
    <g transform="translate(${off} ${off - size * 0.02}) scale(${s})">${mark(colors)}</g>
  </svg>`;
}

// White symbol on blue: the pin is white, so its window panes are blue.
const onBlue = { roof: WHITE, pin: WHITE, window: BLUE };

const OUTPUTS = [
  ['icon.png', 1024, { bg: BLUE, scale: 0.66, colors: onBlue }],
  ['android-icon-foreground.png', 1024, { scale: 0.46, colors: onBlue }],
  ['android-icon-background.png', 1024, { bg: BLUE, scale: 0, colors: onBlue }],
  ['android-icon-monochrome.png', 1024, { scale: 0.46, colors: { roof: '#000', pin: '#000', window: 'transparent' } }],
  ['splash-icon.png', 512, { scale: 0.9, colors: { roof: NAVY, pin: BLUE, window: WHITE } }],
  ['favicon.png', 96, { bg: BLUE, scale: 0.72, colors: onBlue }],
];

const outDir = path.resolve(import.meta.dirname, '../assets/images');
const browser = await chromium.launch();
const page = await browser.newPage();
for (const [file, size, opts] of OUTPUTS) {
  await page.setViewportSize({ width: size, height: size });
  await page.setContent(`<html><body style="margin:0;background:transparent">${svg(size, opts)}</body></html>`);
  await page.locator('svg').screenshot({ path: path.join(outDir, file), omitBackground: true });
  console.log('wrote', file);
}
await browser.close();

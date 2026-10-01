// Launch the selected local Chromium and verify its actual version against the pinned profile.
'use strict';
const fs = require('node:fs');
const path = require('node:path');

function compareBrowserVersion(actual, expected) {
  if (typeof expected !== 'string' || !/^\d+\.\d+\.\d+\.\d+$/.test(expected)) throw new Error('Pinned chromium_version must contain four numeric version components');
  if (actual !== expected) throw new Error(`Chromium version mismatch: actual ${actual}, expected ${expected}. Select a matching BROLL_CHROMIUM executable or use the pinned Playwright browser.`);
  return actual;
}

async function checkBrowser(runtimeArgument, profileArgument = path.join(__dirname, 'versions.json'), options = {}) {
  const runtime = path.resolve(runtimeArgument);
  const profile = JSON.parse(fs.readFileSync(profileArgument, 'utf8'));
  const modules = path.join(runtime, 'node_modules');
  const pkg = JSON.parse(fs.readFileSync(path.join(modules, 'playwright/package.json'), 'utf8'));
  if (pkg.version !== profile.playwright) throw new Error(`Playwright version mismatch: actual ${pkg.version}, expected ${profile.playwright}`);
  const browsers = JSON.parse(fs.readFileSync(path.join(modules, 'playwright-core/browsers.json'), 'utf8'));
  if (!browsers.browsers.some(browser => browser.name === 'chromium' && browser.revision === profile.chromium_revision)) throw new Error('Chromium revision mismatch');
  if (!process.env.PLAYWRIGHT_BROWSERS_PATH && fs.existsSync(path.join(runtime, 'browsers'))) process.env.PLAYWRIGHT_BROWSERS_PATH = path.join(runtime, 'browsers');
  const { chromium } = options.playwright || require(path.join(modules, 'playwright'));
  const executablePath = options.executablePath || process.env.BROLL_CHROMIUM;
  const executable = executablePath || chromium.executablePath();
  if (!fs.existsSync(executable) || !fs.statSync(executable).isFile()) throw new Error(`Chromium is missing: ${executable}`);
  let browser;
  try {
    browser = await chromium.launch({ headless: true, timeout: 30000, ...(executablePath ? { executablePath } : {}) });
    const version = compareBrowserVersion(browser.version(), profile.chromium_version);
    return { status: 'passed', browser: 'chromium', version, executable, override: Boolean(executablePath) };
  } finally { if (browser) await browser.close(); }
}

if (require.main === module) {
  const args = process.argv.slice(2);
  if (args.length < 1 || args.length > 2) { console.error('Usage: node browser_check.js runtime_path [versions.json]'); process.exitCode = 1; }
  else checkBrowser(...args).then(result => console.log(JSON.stringify(result)))
    .catch(error => { console.error(`browser-check: ${error.message}`); process.exitCode = 1; });
}
module.exports = { compareBrowserVersion, checkBrowser };

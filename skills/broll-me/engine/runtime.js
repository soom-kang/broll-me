'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { spawn } = require('node:child_process');

function frameRate(value = '30000/1001') {
  const match = /^(\d+)(?:\/(\d+)|\.(\d{1,6}))?$/.exec(String(value).trim());
  if (!match) throw new Error('FPS must be an integer, decimal, or positive rational rate');
  let numerator = Number(match[1]);
  let denominator = Number(match[2] || 1);
  if (match[3]) {
    denominator = 10 ** match[3].length;
    numerator = numerator * denominator + Number(match[3]);
  }
  if (!Number.isSafeInteger(numerator) || !Number.isSafeInteger(denominator) || numerator <= 0 || denominator <= 0 || numerator / denominator > 240) {
    throw new Error('FPS must be positive and at most 240');
  }
  const gcd = (a, b) => b ? gcd(b, a % b) : a;
  const divisor = gcd(numerator, denominator);
  numerator /= divisor; denominator /= divisor;
  return { value: numerator / denominator, text: `${numerator}/${denominator}`, subframes: `${numerator * 4}/${denominator}` };
}

function validateScene(info) {
  if (!info || !Number.isFinite(info.T) || info.T <= 0 || typeof info.alpha !== 'boolean') throw new Error('Scene must define a positive finite DURATION and alpha mode');
  for (const dimension of [info.W, info.H]) {
    if (!Number.isInteger(dimension) || dimension < 2 || dimension > 8192 || dimension % 2) throw new Error('Scene dimensions must be even integers between 2 and 8192');
  }
  return info;
}

function inputFile(value) {
  if (!value || !fs.statSync(value).isFile()) throw new Error(`Input file not found: ${value}`);
  return fs.realpathSync(value);
}

function outputFile(value, extension, inputs = []) {
  if (!value || path.extname(value).toLowerCase() !== extension) throw new Error(`Output must end with ${extension}`);
  const output = path.resolve(value);
  const existing = fs.existsSync(output) ? fs.realpathSync(output) : output;
  if (inputs.includes(existing)) throw new Error('Output must not overwrite an input');
  fs.mkdirSync(path.dirname(output), { recursive: true });
  return output;
}

function timeoutMs() {
  const value = Number(process.env.BROLL_TIMEOUT_MS || 600000);
  if (!Number.isSafeInteger(value) || value < 1000) throw new Error('BROLL_TIMEOUT_MS must be an integer of at least 1000');
  return value;
}

function playwright() {
  const runtime = path.resolve(process.env.BROLL_RUNTIME || 'motion');
  if (!process.env.PLAYWRIGHT_BROWSERS_PATH && fs.existsSync(path.join(runtime, 'browsers'))) process.env.PLAYWRIGHT_BROWSERS_PATH = path.join(runtime, 'browsers');
  const local = path.join(runtime, 'node_modules', 'playwright');
  try { return require(fs.existsSync(local) ? local : 'playwright'); }
  catch (error) { throw new Error(`Playwright is unavailable. Run setup.sh, then set BROLL_RUNTIME or NODE_PATH. ${error.message}`); }
}

async function openScene(html) {
  const { chromium } = playwright();
  const browser = await chromium.launch({ ...(process.env.BROLL_CHROMIUM ? { executablePath: process.env.BROLL_CHROMIUM } : {}) });
  try {
    const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
    page.setDefaultTimeout(30000);
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/*', route => {
      const protocol = new URL(route.request().url()).protocol;
      return ['file:', 'data:', 'about:'].includes(protocol) ? route.continue() : route.abort();
    });
    await page.goto(pathToFileURL(html).href + '?render');
    await page.evaluate(() => document.fonts.ready);
    if (errors.length) throw new Error(`Scene error: ${errors[0]}`);
    const info = validateScene(await page.evaluate(() => {
      if (typeof window.seek !== 'function') throw new Error('Scene does not expose seek(t)');
      const stage = document.getElementById('stage');
      return { T: window.DURATION, W: stage?.offsetWidth, H: stage?.offsetHeight, alpha: document.documentElement.classList.contains('alpha') };
    }));
    await page.setViewportSize({ width: info.W, height: info.H });
    const keyTimes = await page.evaluate(() => window.BROLL_KEY_TIMES || []);
    return { browser, page, info, errors, keyTimes };
  } catch (error) { await browser.close(); throw error; }
}

function encoder(args) {
  const timeout = timeoutMs();
  const child = spawn(process.env.BROLL_FFMPEG || 'ffmpeg', args, { stdio: ['pipe', 'ignore', 'pipe'] });
  let stderr = '';
  let spawnError;
  let settled = false;
  const timer = setTimeout(() => child.kill('SIGKILL'), timeout);
  child.stderr.on('data', chunk => { stderr = (stderr + chunk.toString()).slice(-4000); });
  child.stdin.on('error', () => {}); // write callbacks report pipe failures to the caller.
  const completion = new Promise(resolve => {
    child.on('error', error => { spawnError = error; });
    child.on('close', (code, signal) => {
      settled = true;
      clearTimeout(timer);
      resolve({ code, signal, error: spawnError, stderr });
    });
  });
  const failure = result => new Error(`FFmpeg failed (${result.signal || result.code}): ${result.error?.message || result.stderr}`);
  async function pipeFailure() {
    const result = await completion;
    return failure(result);
  }
  return {
    child,
    async write(buffer) {
      if (settled || child.stdin.destroyed) throw await pipeFailure();
      try {
        await new Promise((resolve, reject) => child.stdin.write(buffer, error => error ? reject(error) : resolve()));
      } catch (error) {
        // Await close to retain the encoder's status and diagnostic instead of EPIPE.
        throw await pipeFailure();
      }
    },
    async finish() {
      child.stdin.end();
      const result = await completion;
      if (result.code !== 0 || result.error) throw failure(result);
    },
    async stop() {
      if (!settled) child.kill('SIGKILL');
      await completion;
    },
  };
}

module.exports = { frameRate, validateScene, inputFile, outputFile, timeoutMs, openScene, encoder };

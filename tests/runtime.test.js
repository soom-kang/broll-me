'use strict';
const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const R = require('../skills/broll-me/engine/runtime');

function mockSceneResources(resources = []) {
  const vm = require('node:vm');
  const { EventEmitter } = require('node:events');
  const page = new EventEmitter();
  const document = { fonts: { ready: Promise.resolve() }, getElementById: () => ({ offsetWidth: 640, offsetHeight: 360 }),
    documentElement: { classList: { contains: () => false } } };
  const window = { seek() {}, DURATION: 1, BROLL_KEY_TIMES: [] };
  const request = (url, errorText) => ({ url: () => url, failure: () => errorText ? { errorText } : null });
  let routeHandler, closeCalls = 0;
  page.setDefaultTimeout = () => {};
  page.route = async (pattern, handler) => { routeHandler = handler; };
  page.goto = async () => {
    for (const [url, errorText] of resources) {
      await routeHandler({ request: () => request(url, errorText),
        continue: async () => { if (errorText) page.emit('requestfailed', request(url, errorText)); },
        abort: async () => page.emit('requestfailed', request(url, 'net::ERR_FAILED')) });
    }
  };
  page.evaluate = async callback => vm.runInNewContext(`(${callback.toString()})()`, { document, window });
  page.setViewportSize = async () => {};
  const browser = { newPage: async () => page, close: async () => { closeCalls++; } };
  const module = { exports: {} };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../skills/broll-me/engine/runtime.js'), 'utf8'), {
    module, process: { env: {} }, URL,
    require: name => name === 'playwright' ? { chromium: { launch: async () => browser } }
      : name === 'node:fs' ? { existsSync: () => false } : require(name),
  });
  return { open: () => module.exports.openScene(path.resolve('scene.html')), page, request, closeCalls: () => closeCalls };
}

test('openScene resources permit successful local and embedded loads', async () => {
  const mock = mockSceneResources([['file:///image.png'], ['file:///font.woff2'], ['data:image/png;base64,fixture']]);
  const scene = await mock.open();
  assert.equal(scene.errors.length, 0);
  assert.equal(scene.info.W, 640);
  assert.equal(mock.closeCalls(), 0);
  await scene.browser.close();
  assert.equal(mock.closeCalls(), 1);
});

test('openScene resources reject missing local images and fonts and close the browser', async () => {
  for (const filename of ['missing.png', 'missing.woff2']) {
    const mock = mockSceneResources([[`file:///${filename}`, 'net::ERR_FILE_NOT_FOUND']]);
    await assert.rejects(mock.open(), error => error.message.includes(filename) && error.message.includes('net::ERR_FILE_NOT_FOUND'));
    assert.equal(mock.closeCalls(), 1);
  }
});

test('openScene resources reject blocked remote loads and close the browser', async () => {
  const mock = mockSceneResources([['https://example.invalid/image.png']]);
  await assert.rejects(mock.open(), /https:\/\/example\.invalid\/image\.png.*net::ERR_FAILED/);
  assert.equal(mock.closeCalls(), 1);
});

test('openScene resources retain late failures in the returned errors array', async () => {
  const mock = mockSceneResources();
  const scene = await mock.open();
  mock.page.emit('requestfailed', mock.request('file:///late.png'));
  assert.equal(scene.errors.length, 1);
  assert.match(scene.errors[0], /file:\/\/\/late\.png.*request failed/);
  await scene.browser.close();
});

test('rational FPS retains exact NTSC rates', () => {
  assert.deepEqual(R.frameRate('30000/1001'), { value: 30000 / 1001, text: '30000/1001', subframes: '120000/1001' });
  assert.equal(R.frameRate('29.97').text, '2997/100');
  for (const invalid of ['0', '30000/0', '-30', 'Infinity', 'abc', '241']) assert.throws(() => R.frameRate(invalid));
});

test('dimensions and scene duration fail before encoding', () => {
  assert.deepEqual(R.validateScene({ W: 1080, H: 1920, T: 2, alpha: true }), { W: 1080, H: 1920, T: 2, alpha: true });
  for (const info of [{ W: 321, H: 180, T: 2, alpha: false }, { W: 320, H: 180, T: NaN, alpha: false }, { W: 9000, H: 180, T: 2, alpha: false }]) assert.throws(() => R.validateScene(info));
});

test('output container and source overwrite are rejected', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'broll-runtime-test-'));
  try {
    const file = path.join(directory, 'source with spaces.mp4');
    fs.writeFileSync(file, 'fixture');
    assert.throws(() => R.outputFile(file, '.mp4', [fs.realpathSync(file)]), /overwrite/);
    assert.throws(() => R.outputFile(path.join(directory, 'panel.mp4'), '.mov'), /\.mov/);
  } finally { fs.rmSync(directory, { recursive: true }); }
});

test('failed encoder is a failed run instead of a success status', async () => {
  const previous = process.env.BROLL_FFMPEG;
  process.env.BROLL_FFMPEG = process.execPath;
  try {
    const encoder = R.encoder(['-e', 'process.stderr.write("fixture encoder failure");process.exit(7)']);
    await assert.rejects(encoder.finish(), /FFmpeg failed \(7\).*fixture encoder failure/);
    await encoder.stop();
  } finally {
    if (previous === undefined) delete process.env.BROLL_FFMPEG; else process.env.BROLL_FFMPEG = previous;
  }
});

test('early encoder exit retains status when writing to a closed pipe', async () => {
  const previous = process.env.BROLL_FFMPEG;
  process.env.BROLL_FFMPEG = process.execPath;
  try {
    const encoder = R.encoder(['-e', 'process.stderr.write("early encoder failure");process.exit(23)']);
    await new Promise(resolve => encoder.child.once('close', resolve));
    await assert.rejects(encoder.write(Buffer.from('frame')), /FFmpeg failed \(23\).*early encoder failure/);
    await encoder.stop();
  } finally {
    if (previous === undefined) delete process.env.BROLL_FFMPEG; else process.env.BROLL_FFMPEG = previous;
  }
});

test('every supplied example has valid inline JavaScript', () => {
  const vm = require('node:vm');
  const directory = path.join(__dirname, '../skills/broll-me/examples');
  for (const file of fs.readdirSync(directory, {recursive:true}).filter(name=>name.endsWith('.html'))) {
    const html = fs.readFileSync(path.join(directory,file),'utf8');
    for(const match of html.matchAll(/<script>([\s\S]*?)<\/script>/g)) new vm.Script(match[1], {filename:file});
  }
});

function sceneEngine(document) {
  const vm = require('node:vm');
  const context = { BROLL_PALETTE: JSON.parse(fs.readFileSync(path.join(__dirname, '../skills/broll-me/palettes/warm-orange.json'), 'utf8')).colors, document, location: { search: '?render' } };
  context.window = context;
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../skills/broll-me/engine/motion.js'), 'utf8'), context);
  return context;
}

function validConfig() {
  return { W: 640, H: 360, T: 1, bg: null, intro: null,
    SH: { card: { w: 400, h: 200, r: 20, cam: 1, bg: '#FFFFFF' } }, start: 'card', SEQ: [],
    layers: [{ el: 'text', tin: null, tout: null, update() {} }], spring: [Infinity, 1], geom(t, g) { return g; } };
}

test('scene configuration rejects invalid references and times before DOM mutation', () => {
  let mutations = 0;
  const nodes = Object.fromEntries(['wrap', 'stage', 'world', 'shape', 'cursor', 'text'].map(id => [id, { style: new Proxy({}, { set(object, key, value) { mutations++; object[key] = value; return true; } }) }]));
  const { M } = sceneEngine({ getElementById: id => nodes[id] });
  const cases = [
    config => { config.start = 'missing'; },
    config => { config.SH.card.w = NaN; },
    config => { config.SEQ = [[0.8, 'card'], [0.2, 'card']]; },
    config => { config.layers[0].el = 'missing'; },
    config => { config.cursor = { keys: [[0, 1, 2], [0, 3, 4]] }; },
    config => { config.cursor = { keys: [[0, 1, 2]], drags: [[0.8, 0.2]] }; },
    config => { config.layers[0].o = { lin: 0 }; },
    config => { config.T = Infinity; },
  ];
  for (const change of cases) {
    const config = validConfig(); change(config);
    assert.throws(() => M.scene(config), /Scene config/);
    assert.equal(mutations, 0);
  }
  const config = validConfig();
  assert.equal(M.validateSceneConfig(config, id => nodes[id]), config);
});

test('legacy example configurations still validate with callbacks and null times', () => {
  const vm = require('node:vm');
  const node = { style: {}, querySelector: () => node, querySelectorAll: () => [], insertAdjacentHTML() {} };
  const directory = path.join(__dirname, '../skills/broll-me/examples');
  for (const file of fs.readdirSync(directory, { recursive: true }).filter(name => name.endsWith('.html'))) {
    const context = sceneEngine({ getElementById: () => node });
    let scenes = 0;
    context.M.scene = config => { context.M.validateSceneConfig(config, () => node); scenes++; };
    const html = fs.readFileSync(path.join(directory, file), 'utf8');
    for (const match of html.matchAll(/<script>([\s\S]*?)<\/script>/g)) vm.runInContext(match[1], context, { filename: file });
    assert.equal(scenes, 1, file);
  }
});

test('draft and default final retain FPS, frame count, codecs and alpha with fewer captures', async () => {
  const { render, parseArguments } = require('../skills/broll-me/engine/render');
  assert.deepEqual(parseArguments(['clip.html', 'clip.mp4', '30000/1001']), ['clip.html', 'clip.mp4', '30000/1001', 'final']);
  assert.deepEqual(parseArguments(['--quality', 'draft', 'clip.html', 'clip.mp4', '25']), ['clip.html', 'clip.mp4', '25', 'draft']);
  assert.throws(() => parseArguments(['clip.html', 'clip.mp4', '--quality', 'unknown']), /Quality/);
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'broll-quality-test-'));
  const source = path.join(directory, 'scene.html'); fs.writeFileSync(source, 'fixture');
  const previous = { openScene: R.openScene, encoder: R.encoder, log: console.log };
  try {
    console.log = () => {};
    for (const alpha of [false, true]) {
      const runs = [];
      for (const quality of ['final', 'draft']) {
        const times = [], screenshots = [];
        let command, closed = false;
        R.openScene = async () => ({ info: { T: 0.1, W: 640, H: 360, alpha }, errors: [],
          page: { evaluate: async (callback, time) => times.push(time), screenshot: async options => { screenshots.push(options); return Buffer.from('frame'); } },
          browser: { close: async () => { closed = true; } } });
        R.encoder = args => { command = args; return { write: async () => {}, finish: async () => fs.writeFileSync(args.at(-1), 'encoded fixture'), stop: async () => {} }; };
        const result = await render(source, path.join(directory, `${quality}-${alpha}${alpha ? '.mov' : '.mp4'}`), '30', quality === 'final' ? undefined : quality);
        assert.equal(result.quality, quality); assert.equal(result.frames, 3); assert.equal(result.fps, '30/1'); assert.equal(result.alpha, alpha);
        assert.equal(times.length, quality === 'final' ? 12 : 3);
        assert.equal(screenshots.every(options => options.omitBackground === alpha), true);
        assert.equal(closed, true);
        if (quality === 'draft') assert.deepEqual(times, [0, 1 / 30, 2 / 30]);
        runs.push(command);
      }
      const codec = command => command.slice(command.lastIndexOf('-c:v'), -1);
      assert.deepEqual(codec(runs[0]), codec(runs[1]));
      assert.match(runs[0][runs[0].indexOf('-vf') + 1], /tmix=frames=4/);
      assert.doesNotMatch(runs[1][runs[1].indexOf('-vf') + 1], /tmix/);
    }
  } finally { R.openScene = previous.openScene; R.encoder = previous.encoder; console.log = previous.log; fs.rmSync(directory, { recursive: true }); }
});

test('scene checker bounds key seeks and flags only visible tagged text', () => {
  const vm = require('node:vm');
  const { seekTimes, visibleTextOverflows } = require('../skills/broll-me/engine/check');
  assert.deepEqual(seekTimes(1, [0.2, 0.8]).times, [0, 0.2, 0.5, 0.8, 1]);
  assert.throws(() => seekTimes(1, [], [-1]), /within scene/);
  const sampled = seekTimes(1, Array.from({ length: 100 }, (_, index) => index / 100));
  assert.equal(sampled.times.length, 64); assert.equal(sampled.sampled, true);
  const rect = { left: 0, top: 0, right: 100, bottom: 30, width: 100, height: 30 };
  const style = { display: 'block', visibility: 'visible', opacity: '1', overflowX: 'visible', overflowY: 'visible' };
  const element = { parentElement: null, style, getBoundingClientRect: () => rect, getAttribute: () => 'title', clientWidth: 100, scrollWidth: 120, clientHeight: 30, scrollHeight: 30 };
  const hidden = { ...element, style: { ...style, opacity: '0' }, getAttribute: () => 'hidden' };
  const context = { document: { getElementById: () => ({ getBoundingClientRect: () => rect }), querySelectorAll: selector => { assert.equal(selector, '[data-broll-text]'); return [element, hidden]; } }, getComputedStyle: element => element.style };
  const result = vm.runInNewContext(`(${visibleTextOverflows.toString()})()`, context);
  assert.equal(result.length, 1); assert.equal(result[0].element, 'title'); assert.equal(result[0].reasons[0], 'horizontal text overflow');
});

test('browser checker rejects actual override mismatch and closes the launched browser', async () => {
  const { compareBrowserVersion, checkBrowser } = require('../skills/broll-me/scripts/runtime/browser_check');
  assert.equal(compareBrowserVersion('151.0.7922.34', '151.0.7922.34'), '151.0.7922.34');
  assert.throws(() => compareBrowserVersion('150.0.0.0', '151.0.7922.34'), /Chromium version mismatch.*BROLL_CHROMIUM/);
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'broll-browser-check-test-'));
  const previousBrowsers = process.env.PLAYWRIGHT_BROWSERS_PATH;
  try {
    for (const [name, content] of Object.entries({ 'node_modules/playwright/package.json': { version: '1.62.1' }, 'node_modules/playwright-core/browsers.json': { browsers: [{ name: 'chromium', revision: '1234' }] }, 'profile.json': { playwright: '1.62.1', chromium_revision: '1234', chromium_version: '151.0.7922.34' } })) {
      const filename = path.join(directory, name); fs.mkdirSync(path.dirname(filename), { recursive: true }); fs.writeFileSync(filename, JSON.stringify(content));
    }
    const executable = path.join(directory, 'override-browser'); fs.writeFileSync(executable, 'fixture');
    let closed = false, options;
    const playwright = { chromium: { launch: async value => { options = value; return { version: () => '150.0.0.0', close: async () => { closed = true; } }; } } };
    await assert.rejects(checkBrowser(directory, path.join(directory, 'profile.json'), { playwright, executablePath: executable }), /Chromium version mismatch/);
    assert.equal(options.executablePath, executable); assert.equal(closed, true);
  } finally { if (previousBrowsers === undefined) delete process.env.PLAYWRIGHT_BROWSERS_PATH; else process.env.PLAYWRIGHT_BROWSERS_PATH = previousBrowsers; fs.rmSync(directory, { recursive: true }); }
});

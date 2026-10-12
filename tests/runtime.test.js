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

test('beats rejects a distinct protected-input hardlink before browser or output writes', async () => {
  const { beats } = require('../skills/broll-me/engine/beats');
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'broll-beats-hardlink-test-'));
  const source = path.join(directory, 'scene.html'), output = path.join(directory, 'sheet.png');
  const previous = { openScene: R.openScene, encoder: R.encoder };
  try {
    fs.writeFileSync(source, '<html>protected scene fixture</html>');
    fs.linkSync(source, output);
    assert.notEqual(fs.realpathSync(source), fs.realpathSync(output));
    let opened = 0, encoded = 0;
    R.openScene = async () => { opened++; throw new Error('browser must not start'); };
    R.encoder = () => { encoded++; throw new Error('encoder must not start'); };
    assert.throws(() => R.validateOutputPath(output, '.png', [source]), /overwrite/);
    assert.throws(() => R.outputFile(output, '.png', [source]), /overwrite/);
    await assert.rejects(beats(source, output, ['0']), /overwrite/);
    assert.equal(opened, 0); assert.equal(encoded, 0);
    assert.equal(fs.readFileSync(source, 'utf8'), '<html>protected scene fixture</html>');
    assert.equal(fs.readFileSync(output, 'utf8'), '<html>protected scene fixture</html>');
    assert.deepEqual(fs.readdirSync(directory).sort(), ['scene.html', 'sheet.png']);
  } finally { R.openScene = previous.openScene; R.encoder = previous.encoder; fs.rmSync(directory, { recursive: true }); }
});

test('beats accepts readable input symlinks and publishes after cleanup without truncating prior hardlinks', async () => {
  const { beats } = require('../skills/broll-me/engine/beats');
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'broll-beats-publish-test-'));
  const source = path.join(directory, 'scene.html'), input = path.join(directory, 'input-link.html');
  const output = path.join(directory, 'sheet.png'), observer = path.join(directory, 'prior-sheet.png');
  const previous = { openScene: R.openScene, encoder: R.encoder, log: console.log };
  try {
    fs.writeFileSync(source, 'protected scene'); fs.symlinkSync(source, input);
    fs.writeFileSync(output, 'previous approved sheet'); fs.linkSync(output, observer);
    let closed = 0, stopped = 0, command, result;
    console.log = value => { result = JSON.parse(value); };
    R.openScene = async html => {
      assert.equal(html, fs.realpathSync(source));
      return { info: { T: 1, W: 640, H: 360, alpha: false }, errors: [],
        page: { evaluate: async () => {}, screenshot: async options => fs.writeFileSync(options.path, 'frame') },
        browser: { close: async () => { closed++; assert.equal(fs.readFileSync(output, 'utf8'), 'previous approved sheet'); } } };
    };
    R.encoder = args => {
      command = args;
      assert.equal(path.dirname(path.dirname(args.at(-1))), path.dirname(output), 'stage stays on the publication filesystem');
      return { finish: async () => fs.writeFileSync(args.at(-1), 'new captured sheet'),
        stop: async () => { stopped++; assert.equal(fs.readFileSync(output, 'utf8'), 'previous approved sheet'); } };
    };
    await beats(input, output, ['0', '1']);
    assert.equal(result.status, 'captured'); assert.deepEqual(result.times, [0, 1]);
    assert.equal(command[command.indexOf('-vf') + 1], 'tile=2x1:padding=4:color=white');
    assert.equal(closed, 1); assert.equal(stopped, 1);
    assert.equal(fs.readFileSync(source, 'utf8'), 'protected scene');
    assert.equal(fs.readFileSync(output, 'utf8'), 'new captured sheet');
    assert.equal(fs.readFileSync(observer, 'utf8'), 'previous approved sheet');
    assert.notEqual(fs.statSync(output).ino, fs.statSync(observer).ino);
    assert.deepEqual(fs.readdirSync(directory).sort(), ['input-link.html', 'prior-sheet.png', 'scene.html', 'sheet.png']);
  } finally { R.openScene = previous.openScene; R.encoder = previous.encoder; console.log = previous.log; fs.rmSync(directory, { recursive: true }); }
});

test('beats rechecks protected-input identity after cleanup before publication', async () => {
  const { beats } = require('../skills/broll-me/engine/beats');
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'broll-beats-late-alias-test-'));
  const source = path.join(directory, 'scene.html'), output = path.join(directory, 'sheet.png');
  const observer = path.join(directory, 'prior-sheet.png');
  const previous = { openScene: R.openScene, encoder: R.encoder, log: console.log };
  try {
    fs.writeFileSync(source, 'protected scene'); fs.writeFileSync(output, 'previous approved sheet'); fs.linkSync(output, observer);
    let closed = 0, stopped = 0, reported = false;
    console.log = () => { reported = true; };
    R.openScene = async () => ({ info: { T: 1, W: 640, H: 360, alpha: false }, errors: [],
      page: { evaluate: async () => {}, screenshot: async options => fs.writeFileSync(options.path, 'frame') },
      browser: { close: async () => { closed++; fs.unlinkSync(output); fs.linkSync(source, output); } } });
    R.encoder = args => ({ finish: async () => fs.writeFileSync(args.at(-1), 'new captured sheet'), stop: async () => { stopped++; } });
    await assert.rejects(beats(source, output, ['0']), /overwrite/);
    assert.equal(closed, 1); assert.equal(stopped, 1); assert.equal(reported, false);
    assert.equal(fs.readFileSync(source, 'utf8'), 'protected scene');
    assert.equal(fs.readFileSync(output, 'utf8'), 'protected scene');
    assert.equal(fs.readFileSync(observer, 'utf8'), 'previous approved sheet');
    assert.deepEqual(fs.readdirSync(directory).sort(), ['prior-sheet.png', 'scene.html', 'sheet.png']);
  } finally { R.openScene = previous.openScene; R.encoder = previous.encoder; console.log = previous.log; fs.rmSync(directory, { recursive: true }); }
});

test('beats capture, encoder and cleanup failures preserve prior output and attempt resource cleanup', async () => {
  const { beats } = require('../skills/broll-me/engine/beats');
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'broll-beats-failure-test-'));
  const source = path.join(directory, 'scene.html'), output = path.join(directory, 'sheet.png');
  const previous = { openScene: R.openScene, encoder: R.encoder, log: console.log };
  try {
    fs.writeFileSync(source, 'protected scene');
    console.log = () => { throw new Error('failed capture must not report success'); };
    for (const phase of ['capture', 'encoder', 'encoder cleanup', 'browser cleanup']) {
      fs.writeFileSync(output, 'previous approved sheet');
      let closed = 0, stopped = 0;
      R.openScene = async () => ({ info: { T: 1, W: 640, H: 360, alpha: false }, errors: [],
        page: { evaluate: async () => {}, screenshot: async options => {
          if (phase === 'capture') throw new Error(`${phase} fixture failure`);
          fs.writeFileSync(options.path, 'frame');
        } }, browser: { close: async () => { closed++; if (phase === 'browser cleanup') throw new Error(`${phase} fixture failure`); } } });
      R.encoder = args => ({ finish: async () => {
        if (phase === 'encoder') throw new Error(`${phase} fixture failure`);
        fs.writeFileSync(args.at(-1), 'new captured sheet');
      }, stop: async () => { stopped++; if (phase === 'encoder cleanup') throw new Error(`${phase} fixture failure`); } });
      await assert.rejects(beats(source, output, ['0']), error => error.message.includes(`${phase} fixture failure`));
      assert.equal(closed, 1, phase); assert.equal(stopped, phase === 'capture' ? 0 : 1, phase);
      assert.equal(fs.readFileSync(source, 'utf8'), 'protected scene', phase);
      assert.equal(fs.readFileSync(output, 'utf8'), 'previous approved sheet', phase);
      assert.deepEqual(fs.readdirSync(directory).sort(), ['scene.html', 'sheet.png'], phase);
    }
  } finally { R.openScene = previous.openScene; R.encoder = previous.encoder; console.log = previous.log; fs.rmSync(directory, { recursive: true }); }
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
      if (alpha) {
        assert.match(runs[0][runs[0].indexOf('-vf') + 1], /premultiply=inplace=1.*tmix.*unpremultiply=inplace=1/);
        assert.equal(runs[0][runs[0].indexOf('-reinit_filter') + 1], '0');
        assert.equal(runs[1].includes('-reinit_filter'), false);
      }
      else assert.doesNotMatch(runs[0][runs[0].indexOf('-vf') + 1], /premultiply/);
    }
  } finally { R.openScene = previous.openScene; R.encoder = previous.encoder; console.log = previous.log; fs.rmSync(directory, { recursive: true }); }
});

test('render cancellation during capture or cleanup retains prior output and releases resources', async () => {
  const { render } = require('../skills/broll-me/engine/render');
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'broll-cancel-test-'));
  const source = path.join(directory, 'scene.html'), output = path.join(directory, 'scene.mp4');
  fs.writeFileSync(source, 'source fixture');
  const previous = { openScene: R.openScene, encoder: R.encoder, log: console.log, error: console.error };
  const termListeners = process.listenerCount('SIGTERM'), intListeners = process.listenerCount('SIGINT');
  try {
    console.log = console.error = () => {};
    for (const phase of ['capture', 'cleanup']) {
      fs.writeFileSync(output, 'previous approved output');
      let closed = false, stopped = false;
      R.openScene = async () => ({ info: { T: 0.1, W: 640, H: 360, alpha: false }, errors: [],
        page: { evaluate: async () => {}, screenshot: async () => {
          if (phase === 'capture') { process.emit('SIGTERM'); return new Promise(() => {}); }
          return Buffer.from('frame');
        } }, browser: { close: async () => { closed = true; if (phase === 'cleanup') process.emit('SIGTERM'); } } });
      R.encoder = args => ({ write: async () => {}, finish: async () => fs.writeFileSync(args.at(-1), 'new video'), stop: async () => { stopped = true; } });
      await assert.rejects(render(source, output, '30'), error => error.exitCode === 124 && /SIGTERM/.test(error.message));
      assert.equal(closed, true); assert.equal(stopped, true);
      assert.equal(fs.readFileSync(output, 'utf8'), 'previous approved output');
      assert.deepEqual(fs.readdirSync(directory).sort(), ['scene.html', 'scene.mp4']);
      assert.equal(process.listenerCount('SIGTERM'), termListeners);
      assert.equal(process.listenerCount('SIGINT'), intListeners);
    }
  } finally { R.openScene = previous.openScene; R.encoder = previous.encoder; console.log = previous.log; console.error = previous.error; fs.rmSync(directory, { recursive: true }); }
});

test('cleanup failures attempt remaining resources and do not report successful cancellation cleanup', async () => {
  const { render } = require('../skills/broll-me/engine/render');
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'broll-cleanup-test-'));
  const source = path.join(directory, 'scene.html'), output = path.join(directory, 'scene.mp4');
  fs.writeFileSync(source, 'source fixture'); fs.writeFileSync(output, 'previous approved output');
  const previous = { openScene: R.openScene, encoder: R.encoder, log: console.log, error: console.error };
  try {
    const diagnostics = []; let closed = false;
    console.log = () => {}; console.error = message => diagnostics.push(message);
    R.openScene = async () => ({ info: { T: 0.1, W: 640, H: 360, alpha: false }, errors: [],
      page: { evaluate: async () => {}, screenshot: async () => { process.emit('SIGTERM'); return new Promise(() => {}); } },
      browser: { close: async () => { closed = true; } } });
    R.encoder = () => ({ write: async () => {}, finish: async () => {}, stop: async () => { throw new Error('encoder close failure'); } });
    await assert.rejects(render(source, output, '30'), error => error.exitCode === 124 && /Render cleanup failed.*encoder close failure/.test(error.message));
    assert.equal(closed, true);
    assert.equal(diagnostics.some(message => message.includes('cleanup completed')), false);
    assert.equal(fs.readFileSync(output, 'utf8'), 'previous approved output');
    assert.deepEqual(fs.readdirSync(directory).sort(), ['scene.html', 'scene.mp4']);
    R.openScene = async () => {
      process.emit('SIGTERM'); const error = new Error('Browser cleanup failed while opening scene'); error.cleanupFailed = true; throw error;
    };
    await assert.rejects(render(source, output, '30'), /Render cleanup failed.*Browser cleanup failed/);
    assert.equal(diagnostics.some(message => message.includes('cleanup completed')), false);
  } finally { R.openScene = previous.openScene; R.encoder = previous.encoder; console.log = previous.log; console.error = previous.error; fs.rmSync(directory, { recursive: true }); }
});

test('real FFmpeg alpha accumulation retains straight color and coverage through ProRes', t => {
  const { spawnSync } = require('node:child_process');
  const { renderFilter, renderInputOptions } = require('../skills/broll-me/engine/render');
  const ffmpeg = process.env.BROLL_FFMPEG || 'ffmpeg';
  const available = spawnSync(ffmpeg, ['-version'], { timeout: 10000 });
  if (available.error?.code === 'ENOENT') { t.skip('FFmpeg is unavailable; real alpha codec check was not run'); return; }
  assert.equal(available.status, 0, available.stderr?.toString() || available.error?.message);
  const fps = R.frameRate('30000/1001');
  const transparent = [0, 0, 0, 0];
  const cases = [
    { frames: [[255, 255, 255, 255], transparent, transparent, transparent], expected: [255, 255, 255, 64] },
    { frames: Array(4).fill([255, 17, 127, 0]), expected: [0, 0, 0, 0] },
    { frames: [[255, 64, 32, 4], transparent, transparent, transparent], expected: [255, 64, 32, 1] },
    { frames: [[255, 0, 0, 128], [0, 255, 0, 64], [0, 0, 255, 32], transparent], expected: [146, 73, 36, 56] },
    { frames: Array(4).fill([250, 80, 40, 255]), expected: [250, 80, 40, 255] },
  ];
  const input = Buffer.concat(cases.flatMap(value => value.frames.map(pixel => Buffer.from(Array(4).fill(pixel).flat()))));
  const filter = renderFilter(true, fps.text);
  const source = ['-v', 'error', '-f', 'rawvideo', '-pixel_format', 'rgba', '-video_size', '2x2', '-framerate', fps.subframes, '-i', '-', '-vf', filter, '-r', fps.text];
  const run = (args, data) => {
    const result = spawnSync(ffmpeg, args, { input: data, timeout: 10000, maxBuffer: 1024 * 1024 });
    assert.equal(result.status, 0, result.stderr?.toString() || result.error?.message);
    return result.stdout;
  };
  const checkPixels = decoded => {
    assert.equal(decoded.length, cases.length * 16, 'the exact rational FPS keeps one output frame per four input samples');
    for (const [frame, value] of cases.entries()) {
      for (let pixel = 0; pixel < 4; pixel++) {
        const actual = decoded.subarray(frame * 16 + pixel * 4, frame * 16 + pixel * 4 + 4);
        actual.forEach((channel, index) => assert.ok(Math.abs(channel - value.expected[index]) <= 2,
          `frame ${frame}, channel ${index}: ${channel} differs from ${value.expected[index]}`));
      }
    }
    const white = decoded.subarray(0, 4);
    assert.ok(Math.abs(white[0] * white[3] / 255 - 64) <= 2, 'quarter coverage keeps its brightness on black');
    assert.deepEqual([...decoded.subarray(16, 20)], [0, 0, 0, 0], 'zero alpha discards hidden RGB');
  };
  checkPixels(run([...source, '-pix_fmt', 'rgba', '-f', 'rawvideo', '-'], input));
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'broll-alpha-test-'));
  try {
    const output = path.join(directory, 'coverage.mov');
    run([...source, '-c:v', 'prores_ks', '-profile:v', '4', '-pix_fmt', 'yuva444p10le', '-vendor', 'apl0', output], input);
    checkPixels(run(['-v', 'error', '-i', output, '-pix_fmt', 'rgba', '-f', 'rawvideo', '-']));
    const png = (pixel, format) => run(['-v', 'error', '-f', 'rawvideo', '-pixel_format', 'rgba', '-video_size', '2x2', '-i', '-',
      '-frames:v', '1', '-pix_fmt', format, '-c:v', 'png', '-f', 'image2pipe', '-'], Buffer.from(Array(4).fill(pixel).flat()));
    const white = png([255, 255, 255, 255], 'rgb24'), clear = png(transparent, 'rgba');
    assert.equal(white[25], 2); assert.equal(clear[25], 6);
    const mixed = Buffer.concat([white, white, clear, clear, clear, white, clear, white, white, white, white, white]);
    const mixedOutput = path.join(directory, 'mixed-png.mov');
    run(['-v', 'error', '-f', 'image2pipe', '-framerate', fps.subframes, '-c:v', 'png', ...renderInputOptions(true), '-i', '-',
      '-vf', filter, '-r', fps.text, '-c:v', 'prores_ks', '-profile:v', '4', '-pix_fmt', 'yuva444p10le', mixedOutput], mixed);
    const decoded = run(['-v', 'error', '-i', mixedOutput, '-pix_fmt', 'rgba', '-f', 'rawvideo', '-']);
    assert.equal(decoded.length, 3 * 16, 'RGB/RGBA PNG changes must not reset accumulation or frame selection');
    for (const [frame, alpha] of [128, 128, 255].entries()) {
      const pixel = decoded.subarray(frame * 16, frame * 16 + 4);
      assert.ok(pixel.subarray(0, 3).every(channel => Math.abs(channel - 255) <= 2));
      assert.ok(Math.abs(pixel[3] - alpha) <= 2);
    }
  } finally { fs.rmSync(directory, { recursive: true }); }
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

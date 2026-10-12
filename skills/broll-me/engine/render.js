// Render deterministic HTML scenes with four subframes and a 180-degree shutter.
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const R = require('./runtime');

function qualitySettings(quality = 'final') {
  if (!['final', 'draft'].includes(quality)) throw new Error('Quality must be final or draft');
  return { quality, samples: quality === 'final' ? 4 : 1 };
}

function renderFilter(alpha, fps, quality = 'final') {
  const timing = `setpts=N/(${fps})/TB`;
  if (qualitySettings(quality).samples === 1) return `format=gbrap,${timing}`;
  // Average coverage-weighted RGB, then restore straight alpha for ProRes.
  // The 16-bit intermediate preserves low-alpha color through both operations.
  const accumulation = alpha
    ? `format=gbrap16le,premultiply=inplace=1,tmix=frames=4:weights='1 1 1 1'`
    : `format=gbrap,tmix=frames=4:weights='1 1 1 1'`;
  const restore = alpha ? 'unpremultiply=inplace=1,' : '';
  return `${accumulation},select='eq(mod(n\\,4)\\,3)',${restore}${timing}`;
}

function renderInputOptions(alpha, quality = 'final') {
  // Chromium PNGs switch between RGB and RGBA as coverage becomes opaque.
  // Keep the accumulator and selection counter across those format changes.
  return alpha && qualitySettings(quality).samples === 4 ? ['-reinit_filter', '0'] : [];
}

function parseArguments(args) {
  const positional = [];
  let quality = 'final', seenQuality = false;
  for (let index = 0; index < args.length; index++) {
    if (args[index] === '--quality') {
      if (seenQuality || index + 1 >= args.length) throw new Error('Provide --quality once with final or draft');
      quality = args[++index]; seenQuality = true;
    } else if (args[index].startsWith('--')) throw new Error(`Unknown option: ${args[index]}`);
    else positional.push(args[index]);
  }
  if (positional.length < 2 || positional.length > 3) throw new Error('Usage: node render.js clip.html output.(mp4|mov) [fps] [--quality final|draft]');
  qualitySettings(quality);
  return [...positional.slice(0, 2), positional[2], quality];
}

async function render(htmlArgument, outputArgument, fpsArgument, quality = 'final') {
  const html = R.inputFile(htmlArgument);
  const fps = R.frameRate(fpsArgument);
  const settings = qualitySettings(quality);
  let scene, ff, temporaryDir, result, primaryError;
  const controller = new AbortController();
  const cancel = signal => {
    const error = new Error(`Render cancelled by ${signal}`);
    error.exitCode = 124;
    controller.abort(error);
    console.error(`render: cancellation requested; cleanup pending${temporaryDir ? '; staging files at ' + temporaryDir : ''}`);
  };
  const terminate = () => cancel('SIGTERM'), interrupt = () => cancel('SIGINT');
  process.once('SIGTERM', terminate);
  process.once('SIGINT', interrupt);
  async function cancellable(action) {
    controller.signal.throwIfAborted();
    let aborted;
    const cancellation = new Promise((_, reject) => {
      aborted = () => reject(controller.signal.reason);
      controller.signal.addEventListener('abort', aborted, { once: true });
    });
    try {
      return await Promise.race([Promise.resolve().then(() => {
        controller.signal.throwIfAborted();
        return action();
      }), cancellation]);
    } finally { controller.signal.removeEventListener('abort', aborted); }
  }
  try {
    scene = await R.openScene(html, { signal: controller.signal });
    controller.signal.throwIfAborted();
    const { page, info, errors } = scene;
    const output = R.outputFile(outputArgument, info.alpha ? '.mov' : '.mp4', [html]);
    temporaryDir = fs.mkdtempSync(path.join(path.dirname(output), '.broll-render-'));
    const temporary = path.join(temporaryDir, path.basename(output));
    const frames = Math.round(info.T * fps.value);
    if (frames < 1) throw new Error('Scene duration is shorter than one output frame');
    const filter = renderFilter(info.alpha, fps.text, settings.quality);
    const codec = info.alpha
      ? ['-c:v', 'prores_ks', '-profile:v', '4', '-pix_fmt', 'yuva444p10le', '-vendor', 'apl0']
      : ['-c:v', 'libx264', '-crf', '14', '-preset', 'medium', '-pix_fmt', 'yuv420p', '-movflags', '+faststart'];
    ff = R.encoder(['-v', 'error', '-nostdin', '-y', '-f', 'image2pipe', '-framerate', settings.samples === 4 ? fps.subframes : fps.text, '-c:v', 'png', ...renderInputOptions(info.alpha, settings.quality), '-i', '-', '-vf', filter, '-r', fps.text, ...codec, temporary]);
    const began = Date.now();
    for (let frame = 0; frame < frames; frame++) {
      for (let subframe = 0; subframe < settings.samples; subframe++) {
        if (Date.now() - began > R.timeoutMs()) throw new Error('Frame capture timed out');
        const time = settings.samples === 4 ? Math.max(0, frame / fps.value + (subframe - 1.5) / (fps.value * 8)) : frame / fps.value;
        await cancellable(() => page.evaluate(t => window.seek(t), time));
        if (errors.length) throw new Error(`Scene error: ${errors[0]}`);
        const screenshot = await cancellable(() => page.screenshot({ type: 'png', omitBackground: info.alpha }));
        await cancellable(() => ff.write(screenshot));
      }
    }
    await cancellable(() => ff.finish());
    controller.signal.throwIfAborted();
    if (!fs.existsSync(temporary) || !fs.statSync(temporary).size) throw new Error('FFmpeg produced no video');
    result = { status: 'rendered', output, frames, fps: fps.text, width: info.W, height: info.H, alpha: info.alpha, quality: settings.quality };
  } catch (error) {
    primaryError = error;
    throw error;
  } finally {
    const failures = primaryError?.cleanupFailed ? [primaryError.message] : [];
    const cleanup = await Promise.allSettled([
      Promise.resolve().then(() => { if (ff) return ff.stop(); }),
      Promise.resolve().then(() => { if (scene) return scene.browser.close(); }),
    ]);
    for (const result of cleanup) if (result.status === 'rejected') failures.push(result.reason.message || String(result.reason));
    // Publish only after resource cleanup, so cancellation during close retains prior output.
    if (result && !controller.signal.aborted && !failures.length) {
      try { fs.renameSync(path.join(temporaryDir, path.basename(result.output)), result.output); }
      catch (error) { failures.push(error.message); }
    }
    try { if (temporaryDir) fs.rmSync(temporaryDir, { recursive: true, force: true }); }
    catch (error) { failures.push(error.message); }
    process.removeListener('SIGTERM', terminate);
    process.removeListener('SIGINT', interrupt);
    if (failures.length) {
      const error = new Error(`Render cleanup failed: ${failures.join('; ')}${temporaryDir ? '; inspect staging path ' + temporaryDir : ''}`);
      error.exitCode = controller.signal.aborted ? 124 : 1;
      throw error;
    }
    if (controller.signal.aborted) {
      console.error('render: cancellation cleanup completed');
      throw controller.signal.reason;
    }
  }
  console.log(JSON.stringify(result));
  return result;
}

if (require.main === module) {
  try { render(...parseArguments(process.argv.slice(2))).catch(error => { console.error(`render: ${error.message}`); process.exitCode = error.exitCode || 1; }); }
  catch (error) { console.error(`render: ${error.message}`); process.exitCode = 1; }
}
module.exports = { render, renderFilter, renderInputOptions, parseArguments, qualitySettings };

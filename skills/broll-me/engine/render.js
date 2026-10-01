// Render deterministic HTML scenes with four subframes and a 180-degree shutter.
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const R = require('./runtime');

function qualitySettings(quality = 'final') {
  if (!['final', 'draft'].includes(quality)) throw new Error('Quality must be final or draft');
  return { quality, samples: quality === 'final' ? 4 : 1 };
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
  let scene, ff, temporaryDir;
  try {
    scene = await R.openScene(html);
    const { page, info, errors } = scene;
    const output = R.outputFile(outputArgument, info.alpha ? '.mov' : '.mp4', [html]);
    temporaryDir = fs.mkdtempSync(path.join(path.dirname(output), '.broll-render-'));
    const temporary = path.join(temporaryDir, path.basename(output));
    const frames = Math.round(info.T * fps.value);
    if (frames < 1) throw new Error('Scene duration is shorter than one output frame');
    const filter = settings.samples === 4
      ? `format=gbrap,tmix=frames=4:weights='1 1 1 1',select='eq(mod(n\\,4)\\,3)',setpts=N/(${fps.text})/TB`
      : `format=gbrap,setpts=N/(${fps.text})/TB`;
    const codec = info.alpha
      ? ['-c:v', 'prores_ks', '-profile:v', '4', '-pix_fmt', 'yuva444p10le', '-vendor', 'apl0']
      : ['-c:v', 'libx264', '-crf', '14', '-preset', 'medium', '-pix_fmt', 'yuv420p', '-movflags', '+faststart'];
    ff = R.encoder(['-v', 'error', '-nostdin', '-y', '-f', 'image2pipe', '-framerate', settings.samples === 4 ? fps.subframes : fps.text, '-c:v', 'png', '-i', '-', '-vf', filter, '-r', fps.text, ...codec, temporary]);
    const began = Date.now();
    for (let frame = 0; frame < frames; frame++) {
      for (let subframe = 0; subframe < settings.samples; subframe++) {
        if (Date.now() - began > R.timeoutMs()) throw new Error('Frame capture timed out');
        const time = settings.samples === 4 ? Math.max(0, frame / fps.value + (subframe - 1.5) / (fps.value * 8)) : frame / fps.value;
        await page.evaluate(t => window.seek(t), time);
        if (errors.length) throw new Error(`Scene error: ${errors[0]}`);
        await ff.write(await page.screenshot({ type: 'png', omitBackground: info.alpha }));
      }
    }
    await ff.finish();
    if (!fs.existsSync(temporary) || !fs.statSync(temporary).size) throw new Error('FFmpeg produced no video');
    fs.renameSync(temporary, output);
    const result = { status: 'rendered', output, frames, fps: fps.text, width: info.W, height: info.H, alpha: info.alpha, quality: settings.quality };
    console.log(JSON.stringify(result));
    return result;
  } finally {
    if (ff) await ff.stop();
    if (scene) await scene.browser.close();
    if (temporaryDir) fs.rmSync(temporaryDir, { recursive: true, force: true });
  }
}

if (require.main === module) {
  try { render(...parseArguments(process.argv.slice(2))).catch(error => { console.error(`render: ${error.message}`); process.exitCode = 1; }); }
  catch (error) { console.error(`render: ${error.message}`); process.exitCode = 1; }
}
module.exports = { render, parseArguments, qualitySettings };

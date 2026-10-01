// Render a contact sheet at selected clip-local times, matching scene dimensions.
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const R = require('./runtime');

async function beats(htmlArgument, outputArgument, timeArguments) {
  const html = R.inputFile(htmlArgument);
  const times = timeArguments.map(Number);
  if (!times.length || times.some(t => !Number.isFinite(t) || t < 0)) throw new Error('Provide at least one finite non-negative beat time');
  let scene, ff, temporaryDir;
  try {
    scene = await R.openScene(html);
    const { page, info, errors } = scene;
    if (times.some(t => t > info.T)) throw new Error('Beat time exceeds scene duration');
    const output = R.outputFile(outputArgument, '.png', [html]);
    temporaryDir = fs.mkdtempSync(path.join(os.tmpdir(), 'broll-beats-'));
    const temporary = path.join(temporaryDir, 'sheet.png');
    if (info.alpha) await page.evaluate(() => { document.documentElement.style.background = '#000000'; document.body.style.background = '#000000'; });
    for (let index = 0; index < times.length; index++) {
      await page.evaluate(t => window.seek(t), times[index]);
      if (errors.length) throw new Error(`Scene error: ${errors[0]}`);
      await page.screenshot({ path: path.join(temporaryDir, `${String(index).padStart(4, '0')}.png`) });
    }
    const columns = Math.min(4, times.length), rows = Math.ceil(times.length / columns);
    ff = R.encoder(['-v', 'error', '-nostdin', '-y', '-i', path.join(temporaryDir, '%04d.png'), '-vf', `tile=${columns}x${rows}:padding=4:color=white`, '-frames:v', '1', temporary]);
    await ff.finish();
    if (!fs.existsSync(temporary) || !fs.statSync(temporary).size) throw new Error('FFmpeg produced no sheet');
    fs.copyFileSync(temporary, output);
    console.log(JSON.stringify({ status: 'captured', output, times, width: info.W, height: info.H }));
  } finally {
    if (ff) await ff.stop();
    if (scene) await scene.browser.close();
    if (temporaryDir) fs.rmSync(temporaryDir, { recursive: true, force: true });
  }
}

if (require.main === module) {
  const [html, output, ...times] = process.argv.slice(2);
  beats(html, output, times).catch(error => { console.error(`beats: ${error.message}`); process.exitCode = 1; });
}
module.exports = { beats };

// Check scene key seeks and visible, explicitly tagged template text without rendering media.
'use strict';
const R = require('./runtime');

const MAX_TIMES = 64;
function seekTimes(duration, keyTimes = [], requested = []) {
  const explicit = requested.length > 0;
  let times = explicit ? requested.map(Number) : [0, duration / 2, duration, ...keyTimes];
  if (times.some(time => !Number.isFinite(time) || time < 0 || time > duration)) throw new Error('Check times must be finite and within scene duration');
  times = [...new Set(times)].sort((a, b) => a - b);
  if (explicit && times.length > MAX_TIMES) throw new Error(`Provide at most ${MAX_TIMES} check times`);
  const total = times.length;
  if (total > MAX_TIMES) times = Array.from({ length: MAX_TIMES }, (_, index) => times[Math.round(index * (total - 1) / (MAX_TIMES - 1))]);
  return { times, sampled: total > MAX_TIMES, total };
}

// Runs in the page. Author-owned arbitrary HTML is deliberately outside this text check.
function visibleTextOverflows() {
  const stage = document.getElementById('stage').getBoundingClientRect();
  const overflows = [];
  for (const element of document.querySelectorAll('[data-broll-text]')) {
    const rect = element.getBoundingClientRect();
    if (!rect.width || !rect.height) continue;
    let visible = true, opacity = 1;
    const clips = [stage];
    for (let node = element; node; node = node.parentElement) {
      const style = getComputedStyle(node);
      opacity *= Number(style.opacity);
      if (style.display === 'none' || ['hidden', 'collapse'].includes(style.visibility) || opacity < 0.002) { visible = false; break; }
      if (node !== element && ['hidden', 'clip'].some(value => style.overflowX === value || style.overflowY === value)) clips.push(node.getBoundingClientRect());
    }
    if (!visible) continue;
    const reasons = [];
    if (element.clientWidth > 0 && element.scrollWidth > element.clientWidth + 1) reasons.push('horizontal text overflow');
    if (element.clientHeight > 0 && element.scrollHeight > element.clientHeight + 1) reasons.push('vertical text overflow');
    if (clips.some(clip => rect.left < clip.left - 1 || rect.top < clip.top - 1 || rect.right > clip.right + 1 || rect.bottom > clip.bottom + 1)) reasons.push('text outside visible frame or clipping ancestor');
    if (reasons.length) overflows.push({ element: element.getAttribute('data-broll-text') || element.id || element.tagName.toLowerCase(), reasons });
  }
  return overflows;
}

async function check(htmlArgument, timeArguments = []) {
  const html = R.inputFile(htmlArgument);
  let scene;
  try {
    scene = await R.openScene(html);
    const { page, info, errors, keyTimes } = scene;
    const selected = seekTimes(info.T, keyTimes || [], timeArguments);
    const overflows = [];
    for (const time of selected.times) {
      await page.evaluate(t => window.seek(t), time);
      if (errors.length) throw new Error(`Scene error: ${errors[0]}`);
      for (const overflow of await page.evaluate(visibleTextOverflows)) overflows.push({ time, ...overflow });
    }
    return { status: overflows.length ? 'failed' : 'passed', source: html, width: info.W, height: info.H, duration: info.T, alpha: info.alpha,
      times: selected.times, sampled: selected.sampled, totalKeyTimes: selected.total, overflows,
      notes: ['Only visible [data-broll-text] elements are checked. This does not replace playback, contrast or human visual review.'] };
  } finally { if (scene) await scene.browser.close(); }
}

if (require.main === module) {
  const [html, ...times] = process.argv.slice(2);
  if (!html) { console.error('Usage: node check.js clip.html [time ...]'); process.exitCode = 1; }
  else check(html, times).then(result => { console.log(JSON.stringify(result)); if (result.status !== 'passed') process.exitCode = 1; })
    .catch(error => { console.error(`check: ${error.message}`); process.exitCode = 1; });
}
module.exports = { check, seekTimes, visibleTextOverflows };

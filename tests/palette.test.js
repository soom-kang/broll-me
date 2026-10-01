/* Deterministic color helpers: run without browser or npm dependencies. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');
const skill = path.resolve(__dirname, '../skills/broll-me');
const source = fs.readFileSync(path.join(skill, 'engine/motion.js'), 'utf8');
const palette = JSON.parse(fs.readFileSync(path.join(skill, 'palettes/warm-orange.json'), 'utf8')).colors;
function engine() {
  const context = { window: { BROLL_PALETTE: {...palette} } };
  vm.runInNewContext(source, context);
  return context.window.M;
}
test('palette is frozen and shared with renderer payload', () => {
  const M = engine();
  assert.equal(M.palette.accent, '#FF5A1F');
  assert.equal(Object.isFrozen(M.palette), true);
});
test('rgba and RGB mixing preserve endpoints and clamp finite inputs', () => {
  const M = engine();
  assert.equal(M.rgba('#FF5A1F', 0.25), 'rgba(255,90,31,0.25)');
  assert.equal(M.rgba('#FF5A1F', 4), 'rgba(255,90,31,1)');
  assert.equal(M.mixColors('#000000', '#FFFFFF', 0.5), '#808080');
  assert.equal(M.mixColors('#000000', '#FFFFFF', -1), '#000000');
  assert.equal(M.mixColors('#000000', '#FFFFFF', 2), '#FFFFFF');
  assert.throws(() => M.rgba('var(--broll-accent)', 1), /#RRGGBB/);
  assert.throws(() => M.mixColors('#fff', '#FFFFFF', 0.5), /#RRGGBB/);
  assert.throws(() => M.rgba('#000000', NaN), /finite/);
  assert.throws(() => M.mixColors('#000000', '#FFFFFF', Infinity), /finite/);
});
test('color tracks are seek-order independent and use exact resolved hex', () => {
  const M = engine();
  const track = M.ctrack(M.palette.surface, [[0.4, M.palette.inverseSurface], [0.8, M.palette.accent]]);
  const first = track(0.65);
  track(0.95); track(0); track(0.2);
  assert.equal(track(0.65), first);
  assert.equal(track(0), 'rgb(255,255,255)');
  assert.throws(() => M.ctrack('var(--broll-surface)', []), /#RRGGBB/);
});

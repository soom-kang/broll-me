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
test('overdamped springs match independent high-precision step-response values', () => {
  const M = engine();
  // Decimal closed-form values, evaluated independently at 700-digit precision.
  const cases = [
    [1, 1, 2, 0.17773657609819048272],
    [0.1, 1, 2, 0.00439144216137045264],
    [1, 6, 2, 0.78415410664593117066],
    [1e-6, 1, 2, 4.99999333333958332867e-13],
    [1, 1, 10, 0.04649431187756466051],
    [1, 1, 1e8, 4.99999996250000027083e-9],
    [10, 1e308, 1e308, 0.99326205300091453290],
    [1e308, 1, 1e308, 0.39346934028736657640],
  ];
  for (const [tau, w, z, expected] of cases) {
    const actual = M.S(tau, w, z);
    assert.ok(Number.isFinite(actual));
    assert.ok(Math.abs(actual - expected) <= Math.abs(expected) * 2e-14,
      `S(${tau}, ${w}, ${z}): ${actual} != ${expected}`);
  }
  assert.equal(M.S(Number.MAX_VALUE, Number.MAX_VALUE, Number.MAX_VALUE), 1);
});
test('overdamped responses remain bounded and meet the critical limit', () => {
  const M = engine();
  for (const z of [1 + Number.EPSILON, 2, 10, 1e8]) {
    let previous = 0;
    for (const tau of [0, 1e-6, 0.001, 0.01, 0.1, 1, 3, 10, 100, 1e6, 1e10]) {
      const value = M.S(tau, 1, z);
      assert.ok(value >= previous && value <= 1, `non-monotone or unbounded z=${z}, t=${tau}`);
      previous = value;
    }
  }
  for (const tau of [0.01, 0.1, 1, 10]) {
    assert.ok(Math.abs(M.S(tau, 1, 1 + Number.EPSILON) - M.S(tau, 1, 1)) < 2e-15);
  }
});
test('legacy presets and reset semantics remain exact', () => {
  const M = engine();
  const values = {
    MORPH: 0.6424353503933824, FAST: 0.9303118718381242,
    SLOW: 0.5128977585896459, SOFT: 0.38340129773057363,
    CAM: 0.25504510171276507, INSTANT: 1,
  };
  for (const [name, value] of Object.entries(values)) assert.equal(M.S(0.13, ...M[name]), value);
  assert.equal(M.S(-1, 1, 2), 0);
  assert.equal(M.S(0, Infinity, 2), 0);
  assert.equal(M.S(Number.MIN_VALUE, Infinity, 2), 1);
  assert.equal(M.S(1, 1, 1), 0.26424111765711533);
});
test('custom overdamping reaches tracks and preserves authored configuration', () => {
  const M = engine();
  const track = M.track(5, [[0, 25], [1, 15, [3, 4]]], [1, 2]);
  const first = track(1.5);
  track(2); track(0); track(0.5);
  assert.equal(track(1.5), first);
  assert.ok(Math.abs(track(0.5) - 6.39410411803918674657) < 2e-14);
  assert.ok(Math.abs(first - 8.99088295817110034607) < 2e-14);
  const color = M.ctrack('#000000', [[0, '#FFFFFF']], [1, 2]);
  const overridden = M.ctrack('#000000', [[0, '#FFFFFF', [1, 10]]], [1, 2]);
  assert.equal(color(1), 'rgb(45,45,45)');
  assert.equal(overridden(1), 'rgb(12,12,12)');
  color(2); color(0);
  assert.equal(color(1), 'rgb(45,45,45)');
  const config = { W: 640, H: 360, T: 2,
    SH: { main: { w: 200, h: 100, r: 10, bg: '#000000', cam: 1 } },
    start: 'main', SEQ: [], spring: [1, 2], camSpring: [1, Number.MAX_VALUE] };
  assert.equal(M.validateSceneConfig(config), config);
});

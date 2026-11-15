// Delayed-response regressions for the real renderer, explore wrapper and pass controller.
// No browser or external services: node web/tests/blink_check.mjs
import assert from 'node:assert/strict';
const noop = () => {};
const gl = new Proxy({}, { get: (t, k) => k in t ? t[k] :
  typeof k === 'string' && k === k.toUpperCase() ? 0 : () => ({}) });
gl.getShaderParameter = gl.getProgramParameter = () => true;
const element = () => ({ style: {}, hidden: false, classList: { add: noop, toggle: noop }, append: noop,
  setAttribute: noop, replaceChildren: noop, addEventListener: noop,
  getContext: (t) => t === 'webgl' ? gl : { setTransform: noop, clearRect: noop },
  getBoundingClientRect: () => ({ left: 0, top: 0, width: 1200, height: 800 }) });
const nodes = new Map();
globalThis.document = { createElement: element, dispatchEvent: noop,
  querySelector: (key) => { if (!nodes.has(key)) nodes.set(key, element()); return nodes.get(key); } };
globalThis.CustomEvent = class { constructor(type, data) { this.type = type; Object.assign(this, data); } };
globalThis.window = { devicePixelRatio: 1 };
globalThis.ResizeObserver = class { observe() {} };
globalThis.requestAnimationFrame = noop;
globalThis.setTimeout = () => 0;
globalThis.clearTimeout = noop;
globalThis.setInterval = () => 0;
const pending = new Map();
const paths = [];
const props = 'hips_order = 7\nhips_tile_format = png\nx_survey_passes = 1 2 3';
const response = () => ({ ok: true, text: async () => props });
globalThis.fetch = async (url) => {
  paths.push(url);
  const gate = pending.get(url);
  if (gate) return new Promise((resolve, reject) => gate.push({ resolve, reject }));
  return response();
};
const hold = (url) => pending.set(url, []);
function release(url) {
  const requests = pending.get(url);
  assert.ok(requests?.length, `request is pending: ${url}`);
  pending.delete(url);
  requests.forEach((r) => r.resolve(response()));
}
const explore = await import('../explore.js');
const sky = await explore.initExplore(element(), { api: 'http://test', ra: 10, dec: 20, fovDeg: .3 });

// A late renderer replacement must not overwrite a newer layer set.
hold('http://test/old/properties');
const old = sky.setOverlays([{ url: 'http://test/old' }]);
await sky.setOverlays([{ url: 'http://test/new1' }, { url: 'http://test/new2' }]);
release('http://test/old/properties');
assert.deepEqual(await old, []);
assert.deepEqual(await sky.addOverlays([{ url: 'http://test/new3' }]), [2], 'newer overlay collection survives');

// Appending a dynamically generated layer belongs to the collection that requested it.
hold('http://test/old-diff/properties');
const addition = sky.addOverlays([{ url: 'http://test/old-diff' }]);
await sky.setOverlays([{ url: 'http://test/replacement' }]);
release('http://test/old-diff/properties');
assert.deepEqual(await addition, []);
assert.deepEqual(await sky.addOverlays([{ url: 'http://test/replacement-diff' }]), [1]);

// Renderer safety alone is insufficient: explore's frame keys/base must also stay current.
hold('http://test/field-old/properties');
const staleField = explore.setFieldLayers([{ url: 'http://test/field-old', epoch: 1 }], [], 'http://test/field-old');
await explore.setFieldLayers([{ url: 'http://test/field-new', epoch: 2 }],
  [{ url: 'http://test/new-frame', frame_id: 'f-new' }], 'http://test/field-new');
release('http://test/field-old/properties');
assert.deepEqual(await staleField, []);
assert.equal(await explore.showLayer('f-new'), true, 'current frame index survives late metadata');
assert.equal(await explore.showLayer('d-f-new-f-other'), true);
assert.ok(paths.includes('http://test/field-new/d-f-new-f-other/properties'), 'dynamic layer uses current field base');
hold('http://test/field-new/d-late/properties');
const staleDiff = explore.showLayer('d-late');
await explore.setFieldLayers([{ url: 'http://test/next-field', epoch: 3 }], [], 'http://test/next-field');
release('http://test/field-new/d-late/properties');
assert.equal(await staleDiff, false);
assert.equal(explore.currentLayer(), null, 'late dynamic layer does not select an unrelated index');
assert.equal(await explore.showLayer('e3'), true);

// Source changes notify synchronously; an old mode load cannot fire a delayed callback.
const passes = await import('../autoblink.js');
const modes = [];
passes.onModeChange((m) => modes.push(m));
await passes.initPasses();
await passes.setMode('epochs');
// The page clears the overlays when the blink turns to field epochs (app.js onBlinkSource -> explore.hideEpochs ->
// sky.setOverlays([])). T143: overlays asked for again keep their layers, so only after that clear is the pass
// metadata fetched again (and can arrive late, as tested here).
await sky.setOverlays([]);
hold('http://test/api/sky/spherex-live-p1/properties');
const slowPasses = passes.setMode('passes');
assert.equal(modes.at(-1), 'passes', 'old epoch timer can be stopped before the pass metadata arrives');
await passes.setMode('epochs');
await explore.setFieldLayers([{ url: 'http://test/current-epoch', epoch: 4 }], [], 'http://test/current-epoch');
release('http://test/api/sky/spherex-live-p1/properties');
await slowPasses;
assert.equal(modes.at(-1), 'epochs', 'late pass response does not announce an obsolete mode');
assert.equal(await explore.showLayer('e4'), true, 'late pass response does not replace the focused field');

// A layer addition which completes after a clear must not restore anything.
hold('http://test/current-epoch/x-pah/properties');
const cleared = explore.showLayer('x-pah');
explore.hideEpochs();
release('http://test/current-epoch/x-pah/properties');
assert.equal(await cleared, false);
assert.equal(explore.currentLayer(), null);
console.log('PASS blink races: late replacements/additions, field indexes, clearing, and immediate source changes');

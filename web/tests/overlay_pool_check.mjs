// T143: overlays asked for again keep their layers (and loaded tiles); dropped ones are freed and made anew.
// The real renderer with a fake WebGL, no browser: node web/tests/overlay_pool_check.mjs
import assert from 'node:assert/strict';
const noop = () => {};
const gl = new Proxy({}, { get: (t, k) => k in t ? t[k] :
  typeof k === 'string' && k === k.toUpperCase() ? 0 : () => ({}) });
gl.getShaderParameter = gl.getProgramParameter = () => true;
const element = () => ({ style: {}, hidden: false, classList: { add: noop, toggle: noop }, append: noop,
  setAttribute: noop, replaceChildren: noop, addEventListener: noop,
  getContext: (t) => t === 'webgl' ? gl : { setTransform: noop, clearRect: noop },
  getBoundingClientRect: () => ({ left: 0, top: 0, width: 1200, height: 800 }) });
globalThis.document = { createElement: element, dispatchEvent: noop, querySelector: () => element() };
globalThis.CustomEvent = class { constructor(type, data) { this.type = type; Object.assign(this, data); } };
globalThis.window = { devicePixelRatio: 1 };
globalThis.ResizeObserver = class { observe() {} };
globalThis.requestAnimationFrame = noop;
globalThis.setTimeout = () => 0;
globalThis.clearTimeout = noop;
globalThis.setInterval = () => 0;
const asked = [];
globalThis.fetch = async (url) => { asked.push(url); return { ok: true, text: async () => 'hips_order = 7\nhips_tile_format = png' }; };
const explore = await import('../explore.js');
const sky = await explore.initExplore(element(), { api: 'http://test', ra: 10, dec: 20, fovDeg: .3 });
const n = (layer) => asked.filter((u) => u === `http://test/${layer}/properties`).length;

await sky.setOverlays([{ url: 'http://test/e1' }, { url: 'http://test/e2' }]);
assert.equal(n('e1') + n('e2'), 2);
// The same field set again (a band step, the colour switch back, a blink decision): nothing fetched again.
const metas = await sky.setOverlays([{ url: 'http://test/e1', epoch: 1 }, { url: 'http://test/e3' }]);
assert.equal(n('e1'), 1, 'a layer asked for again is kept (with its tiles)');
assert.deepEqual(metas.map((m) => m.url), ['http://test/e1', 'http://test/e3']);
assert.equal(metas[0].epoch, 1, 'a kept layer carries what it is asked as now');
// e2 was dropped: freed, so asking for it later makes it anew.
await sky.setOverlays([{ url: 'http://test/e2' }]);
assert.equal(n('e2'), 2, 'a dropped layer is made anew');
// Layers added on demand (A − B, chemistry) are freed with the rest when the set changes.
await sky.addOverlays([{ url: 'http://test/d-a-b' }]);
await sky.setOverlays([{ url: 'http://test/e2' }]);
await sky.setOverlays([{ url: 'http://test/e2' }, { url: 'http://test/d-a-b' }]);
assert.equal(n('d-a-b'), 2, 'an on-demand layer left out of a set is freed');
// Clearing (explore.hideEpochs) frees everything.
await sky.setOverlays([]);
await sky.setOverlays([{ url: 'http://test/e2' }]);
assert.equal(n('e2'), 3);
// A field's single frames are added only when the frame tools show one (T143), once.
const frames = ['f000', 'f001', 'f002'].map((id) => ({ url: `http://test/field/${id}`, frame_id: id, label: id }));
const epochs = await explore.setFieldLayers([{ url: 'http://test/field/e1', epoch: 1 }], frames, 'http://test/field');
assert.deepEqual(epochs.map((l) => l.epoch), [1]);
assert.equal(n('field/f000') + n('field/f001') + n('field/f002'), 0, 'no frame is fetched with the epochs');
assert.equal(await explore.showLayer('f001'), true);
assert.equal(explore.currentLayer(), 'f001');
assert.equal(n('field/f001'), 1, 'a frame is fetched when first shown');
assert.equal(await explore.showLayer('e1'), true);
assert.equal(await explore.showLayer('f001'), true);
assert.equal(n('field/f001'), 1, 'and kept');
assert.equal(await explore.showLayer('f009'), false, 'an unknown frame is not invented');
console.log('PASS overlay pool: kept layers are not fetched again, dropped and on-demand ones are freed; frames are ' +
  'added when first shown');

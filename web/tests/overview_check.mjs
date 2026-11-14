// Offline renderer regression: a direct deep zoom must show the overview while detail stalls or
// fails, then replace it as detail arrives. Run: node web/tests/overview_check.mjs
import assert from 'node:assert/strict';

const noop = () => {};
let texture, positions, uvs, draws = [], frames = [], retries = [], pending = [], mode = 'pending';
const gl = new Proxy({}, { get: (t, k) => k in t ? t[k] :
  typeof k === 'string' && k === k.toUpperCase() ? k : () => ({}) });
gl.getShaderParameter = gl.getProgramParameter = () => true;
gl.createTexture = () => ({});
gl.bindTexture = (_, t) => { texture = t; };
gl.texImage2D = (...args) => { texture.url = args.at(-1).url; };
let buffer;
gl.createBuffer = () => ({});
gl.bindBuffer = (_, b) => { buffer = b; };
gl.bufferData = (_, data) => { buffer.data = Array.from(data); };
gl.getAttribLocation = (_, key) => key;
gl.vertexAttribPointer = (key) => {
  if (key === 'a_pos') positions = buffer.data;
  if (key === 'a_uv') uvs = buffer.data;
};
gl.clear = () => { draws = []; };
gl.drawArrays = () => { draws.push({ url: texture.url, positions, uvs }); };
const el = () => ({ style: {}, classList: { add: noop }, append: noop, addEventListener: noop,
  getContext: (t) => t === 'webgl' ? gl : { setTransform: noop, clearRect: noop },
  getBoundingClientRect: () => ({ left: 0, top: 0, width: 1200, height: 800 }) });
globalThis.document = { createElement: el };
globalThis.window = { devicePixelRatio: 1 };
globalThis.ResizeObserver = class { observe() {} };
globalThis.requestAnimationFrame = (fn) => frames.push(fn);
globalThis.setTimeout = (fn) => retries.push(fn);
globalThis.createImageBitmap = async (blob) => ({ url: blob.url, close: noop });
const props = `hips_order = 7\nhips_tile_width = 512\nhips_tile_format = png\nhips_cube_depth = 102\nhips_cube_firstframe = 1\nx_live_orders = 6 7`;
const response = (url, status = 200) => ({ ok: status === 200, status,
  text: async () => props, blob: async () => ({ url }) });
globalThis.fetch = async (url) => {
  if (url.endsWith('/properties') || url.includes('/Allsky')) return response(url);
  if (mode === 'success') return response(url);
  if (mode === 'error') return response(url, 502);
  return new Promise((resolve) => pending.push(() => resolve(response(url, 502))));
};
async function settle() {
  for (let i = 0; i < 25; i++) {
    await new Promise(setImmediate);
    const batch = frames.splice(0);
    for (const fn of batch) fn();
    if (!batch.length && !frames.length) break;
  }
}
const { createSky } = await import('../sky.js');
const sky = createSky(el(), { ra: 269.4463, dec: 4.7682, fov: 0.25 });
await sky.setBase('http://test/live');
await settle();
assert.equal(sky.stats().order, 7);
assert.ok(sky.stats().loads > 0, 'detail is still loading');
function checkOverview(band) {
  const overview = draws.filter((d) => d.url?.endsWith(`/Allsky_${band}.png`));
  assert.ok(overview.length > 0, 'cached overview draws at deep zoom');
  assert.ok(overview.every((d) => d.uvs.every((v) => v >= 0 && v <= 1)), 'atlas UVs stay inside image');
  assert.ok(overview.every((d) => {
    const us = d.uvs.filter((_, i) => i % 2 === 0), vs = d.uvs.filter((_, i) => i % 2 === 1);
    return Math.abs(Math.max(...us) - Math.min(...us) - 1 / (16 * 27)) < 1e-6 &&
      Math.abs(Math.max(...vs) - Math.min(...vs) - 1 / (16 * 29)) < 1e-6;
  }), 'order-7 mesh samples the correct-sized subrectangle of an order-3 atlas cell');
  assert.ok(overview.some((d) => {
    for (let i = 0; i < d.positions.length; i += 6) {
      const [ax, ay, bx, by, cx, cy] = d.positions.slice(i, i + 6);
      const cross = (x1, y1, x2, y2) => x1 * y2 - y1 * x2;
      const signs = [cross(bx - ax, by - ay, -ax, -ay), cross(cx - bx, cy - by, -bx, -by),
        cross(ax - cx, ay - cy, -cx, -cy)];
      if (signs.every((v) => v >= -1e-8) || signs.every((v) => v <= 1e-8)) return true;
    }
    return false;
  }), 'overview mesh covers the view centre, even when the coarse tile corners are off-screen');
}
checkOverview(1);
assert.ok(sky.stats().blurry > 0, 'overview is reported as blurry, not empty');
mode = 'error';
for (const resolve of pending.splice(0)) resolve();
for (let i = 0; i < 6; i++) {
  await settle();
  for (const retry of retries.splice(0)) retry();
}
await settle();
checkOverview(1);
assert.ok(sky.stats().errors > 0, 'failed detail does not erase overview');
mode = 'success';
// T89/T90: live tiles (orders 6-7) only depend on the detector (17 channels each) and are asked for with the
// detector's first slice: switch to another detector (slice 18 -> live tiles _17, the cube overview _18)
sky.setSlice(18);
await settle();
checkOverview(18);
assert.ok(draws.some((d) => d.url?.includes('/Npix') && d.url.endsWith('_17.png')), 'new-band sharp tiles render');
assert.ok(sky.stats().sharp > 0, 'loaded detail replaces the blurry fallback');
assert.ok(!draws.some((d) => d.url?.includes('/Npix') && /Npix\d+\.png$/.test(d.url)), 'old-band (detector 1) imagery is not drawn after a band switch');
assert.ok(!draws.some((d) => d.url?.endsWith('Allsky_1.png')), 'old-band overview is not drawn after a band switch');
console.log('PASS deep zoom: overview covers centre while detail loads/fails; correct atlas UVs; band switch and sharp replacement');

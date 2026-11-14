// node web/tests/projection_check.mjs : stereographic round trip of sky.js without a browser
// (minimal DOM/WebGL stubs; only the projection is exercised).
const noop = () => {};
const glStub = new Proxy({}, { get: (t, k) => (k in t ? t[k] : typeof k === "string" && k === k.toUpperCase() ? 0 : () => ({})) });
glStub.getShaderParameter = () => true;
glStub.getProgramParameter = () => true;
const el = () => ({ className: "", style: {}, classList: { add: noop }, append: noop, addEventListener: noop,
  getContext: (t) => (t === "webgl" ? glStub : { setTransform: noop, clearRect: noop }),
  getBoundingClientRect: () => ({ left: 0, top: 0, width: 1200, height: 800 }), setPointerCapture: noop });
globalThis.document = { createElement: el };
globalThis.window = { devicePixelRatio: 1 };
globalThis.ResizeObserver = class { observe() {} };
globalThis.requestAnimationFrame = noop;
globalThis.performance = { now: () => 0 };
const { createSky } = await import("../sky.js");
const sky = createSky(el(), { ra: 269.45, dec: 4.77, fov: 2 });
let worst = 0, n = 0;
for (const [ra, dec, fov] of [[269.45, 4.77, 2], [10, 89, 30], [200, -60, 120], [0.1, 0, 200]]) {
  sky.goTo(ra, dec, fov);
  for (let x = 0; x <= 1200; x += 150) for (let y = 0; y <= 800; y += 100) {
    const p = sky.proj.fromScreen(x, y);
    if (!p) continue;
    const s = sky.proj.toScreen(p[0], p[1]);
    worst = Math.max(worst, Math.hypot(s.x - x, s.y - y)); n++;
  }
}
// orientation: east (larger RA) is left, north is up
sky.goTo(100, 20, 1);
const c = sky.proj.toScreen(100, 20), e = sky.proj.toScreen(100.1, 20), nn = sky.proj.toScreen(100, 20.1);
const ok = worst < 1e-6 && e.x < c.x && nn.y < c.y && Math.abs(c.x - 600) < 1e-9;
console.log(`round trip ${n} points, worst ${worst.toExponential(2)} px; east-left ${e.x < c.x}, north-up ${nn.y < c.y}`);
process.exit(ok ? 0 : 1);

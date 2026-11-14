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
// navigation: drag keeps the grabbed sky point under the cursor, anywhere incl. at/over the poles;
// zoom keeps the point under the cursor fixed
let navWorst = 0;
for (const [ra, dec, fov] of [[100, 20, 2], [10, 89.9, 1], [200, -89.5, 5], [0, 0, 60], [45, 88, 30]]) {
  sky.goTo(ra, dec, fov);
  for (const [f, t] of [[[600, 400], [700, 380]], [[300, 200], [320, 650]], [[900, 700], [100, 100]]]) {
    const grabbed = sky.proj.fromScreen(...f);
    sky._dragTo(f, t);
    const s = sky.proj.toScreen(...grabbed);
    navWorst = Math.max(navWorst, Math.hypot(s.x - t[0], s.y - t[1]));
  }
  const under = sky.proj.fromScreen(250, 600);
  sky._zoomAt(0.5, 250, 600);
  const z = sky.proj.toScreen(...under);
  navWorst = Math.max(navWorst, Math.hypot(z.x - 250, z.y - 600));
}
// over the pole: dragging upwards across Dec +90 keeps going instead of sticking
sky.goTo(0, 89, 10);
for (let i = 0; i < 40; i++) sky._dragTo([600, 400], [600, 430]);
const crossed = sky.view().dec < 89 && Math.abs(sky.view().ra - 180) < 1;
console.log(`navigation: worst drift ${navWorst.toFixed(2)} px; over the pole: ${crossed ? "ok" : "STUCK"} (now RA ${sky.view().ra.toFixed(1)} Dec ${sky.view().dec.toFixed(2)})`);
const ok = navWorst < 25 && crossed && worst < 1e-6 && e.x < c.x && nn.y < c.y && Math.abs(c.x - 600) < 1e-9;
console.log(`round trip ${n} points, worst ${worst.toExponential(2)} px; east-left ${e.x < c.x}, north-up ${nn.y < c.y}`);
process.exit(ok ? 0 : 1);

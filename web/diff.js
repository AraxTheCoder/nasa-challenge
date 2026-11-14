// Difference view (T43): show A − B instead of blinking. Grey = unchanged, white = brighter in A,
// black = brighter in B. Steady stars cancel (best for a wavelength-matched pair, T12); anything that
// moved shows as a white/black pair. Official Potential Considerations: "options to ... subtract images
// taken at different times".
//
// The frame PNGs are stretched for display, each on its own, so B is first fitted to A's brightness
// (robust linear fit over pixels valid in both). Pixels with no data in either frame stay transparent
// (the stage shows them hatched). Exclusive with the trail view (T23), switched via its checkbox.

import { $, el, fmtDuration, fmtNum, isTyping } from "./util.js";
import { currentPair, stopBlink } from "./viewer.js";

const st = { on: false, drawnFor: null, token: 0 };
// No data in A or B: its own colour. The stage's dark "no data" hatching would read as "brighter in B".
const NO_DATA = [64, 84, 140];

/** Pure: RGBA pixels of A and B (same size) → RGBA difference image + fit info. */
export function differenceImage(a, b) {
  const n = a.length / 4;
  const valid = new Uint8Array(n);
  let count = 0;
  for (let i = 0; i < n; i++) {
    if (a[4 * i + 3] > 0 && b[4 * i + 3] > 0) { valid[i] = 1; count++; }
  }
  const out = new Uint8ClampedArray(a.length);
  for (let i = 0; i < n; i++) {
    if (valid[i]) continue;
    out[4 * i] = NO_DATA[0]; out[4 * i + 1] = NO_DATA[1]; out[4 * i + 2] = NO_DATA[2]; out[4 * i + 3] = 255;
  }
  if (count < 10) return { data: out, gain: 1, offset: 0, scale: 1, valid: count, p99: 0 };

  // A ≈ g·B + o, least squares; then again without outliers (movers, variable or saturated stars)
  const fit = (use) => {
    let s = 0, sx = 0, sy = 0, sxx = 0, sxy = 0;
    for (let i = 0; i < n; i++) {
      if (!use[i]) continue;
      const x = b[4 * i], y = a[4 * i];
      s++; sx += x; sy += y; sxx += x * x; sxy += x * y;
    }
    const den = s * sxx - sx * sx;
    const g = den > 1e-9 ? (s * sxy - sx * sy) / den : 1;
    const o = (sy - g * sx) / Math.max(s, 1);
    return [g, o];
  };
  let [g, o] = fit(valid);
  let ss = 0;
  for (let i = 0; i < n; i++) if (valid[i]) { const r = a[4 * i] - (g * b[4 * i] + o); ss += r * r; }
  const sigma = Math.sqrt(ss / count) || 1;
  const core = new Uint8Array(n);
  for (let i = 0; i < n; i++) {
    if (valid[i] && Math.abs(a[4 * i] - (g * b[4 * i] + o)) < 2.5 * sigma) core[i] = 1;
  }
  [g, o] = fit(core);

  const res = new Float32Array(n);
  const abs = [];
  for (let i = 0; i < n; i++) {
    if (!valid[i]) continue;
    res[i] = a[4 * i] - (g * b[4 * i] + o);
    abs.push(Math.abs(res[i]));
  }
  abs.sort((x, y) => x - y);
  const p99 = abs[Math.min(abs.length - 1, Math.floor(abs.length * 0.99))];
  const gain = 110 / Math.max(p99, 6); // floor: don't blow pure noise up to full contrast
  for (let i = 0; i < n; i++) {
    if (!valid[i]) continue; // already NO_DATA
    const v = 128 + gain * res[i];
    out[4 * i] = out[4 * i + 1] = out[4 * i + 2] = v;
    out[4 * i + 3] = 255;
  }
  return { data: out, gain, offset: o, scale: g, valid: count, p99 };
}

export async function pixels(url, width, height) {
  const im = new Image();
  im.crossOrigin = "anonymous"; // the Live API sends CORS headers (CONTRACTS v0.3), so pixels are readable
  im.src = url;
  await im.decode();
  const c = document.createElement("canvas");
  c.width = width;
  c.height = height;
  const ctx = c.getContext("2d", { willReadFrequently: true });
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(im, 0, 0, width, height);
  return ctx.getImageData(0, 0, width, height).data;
}

function canvas() {
  let c = $("#diff-canvas");
  if (!c) {
    c = el("canvas", { id: "diff-canvas", class: "diff-canvas", "aria-hidden": "true", hidden: true });
    $("#frame-stack").after(c); // above the frames, below the SVG overlay (paths and names stay on top)
  }
  return c;
}

async function draw() {
  const p = currentPair();
  const c = canvas();
  const note = $("#diff-note");
  $("#stage-label").hidden = st.on && !!p; // the frame label would describe the wrong picture
  if (!st.on || !p) {
    c.hidden = true;
    note.hidden = true;
    $("#stage-diff-label").hidden = true;
    return;
  }
  const key = `${p.a.id}|${p.b.id}|${p.urlA}|${p.urlB}`;
  if (key === st.drawnFor && !c.hidden) return;
  const token = ++st.token;
  try {
    const [a, b] = await Promise.all([pixels(p.urlA, p.width, p.height), pixels(p.urlB, p.width, p.height)]);
    if (token !== st.token || !st.on) return;
    const d = differenceImage(a, b);
    c.width = p.width;
    c.height = p.height;
    c.getContext("2d").putImageData(new ImageData(d.data, p.width, p.height), 0, 0);
    c.hidden = false;
    st.drawnFor = key;
    const dl = Math.abs(p.a.wavelength_um - p.b.wavelength_um);
    $("#stage-diff-label").textContent =
      `A − B · ${p.a.id} − ${p.b.id} · ${fmtDuration(p.b.mjd - p.a.mjd)} apart · Δλ ${fmtNum(dl, 3)} µm`;
    $("#stage-diff-label").hidden = false;
    note.replaceChildren(
      el("span", { class: "diff-key diff-white" }), " brighter in A  ",
      el("span", { class: "diff-key diff-black" }), " brighter in B  ",
      el("span", { class: "diff-key diff-grey" }), " unchanged  ",
      el("span", { class: "diff-key diff-nodata" }), " no data in A or B · ",
      p.matched ? "wavelength-matched pair: steady stars cancel, movers show as a white/black pair " +
        "(small pairs on bright stars are alignment / PSF residuals)"
        : "A and B differ in wavelength: star residuals are expected (try “Match B to A's λ”)",
    );
    note.hidden = false;
  } catch (err) {
    if (token !== st.token) return;
    note.textContent = `Difference view unavailable: ${err.message ?? err}`;
    note.hidden = false;
  }
}

function setOn(on) {
  st.on = on;
  document.dispatchEvent(new CustomEvent("viewer:diff", { detail: { on } }));   // T81: the map follows
  st.drawnFor = null;
  const btn = $("#btn-diff");
  btn.setAttribute("aria-pressed", String(on));
  if (on) {
    stopBlink();
    const trail = $("#trail-on"); // exclusive with the trail view (T23)
    if (trail?.checked) {
      trail.checked = false;
      trail.dispatchEvent(new Event("change"));
    }
  }
  draw();
}

export function initDiff() {
  $("#btn-diff").addEventListener("click", () => setOn(!st.on));
  document.addEventListener("keydown", (e) => {
    if (e.key !== "d" && e.key !== "D") return;
    if (e.altKey || e.ctrlKey || e.metaKey || isTyping(e.target) || !currentPair()) return;
    setOn(!st.on);
  });
  // Turning the trail view on, or starting a blink, ends the difference view.
  document.addEventListener("change", (e) => { if (e.target?.id === "trail-on" && e.target.checked && st.on) setOn(false); });
  document.addEventListener("viewer:blink", (e) => { if (e.detail?.playing && st.on) setOn(false); });
  document.addEventListener("viewer:frame", () => { if (st.on) draw(); }); // A/B may have changed
  document.addEventListener("viewer:target", () => { st.drawnFor = null; if (st.on) draw(); });
}

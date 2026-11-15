// T60: SPHEREx's quality flags on the map. "Quality flags" in the map bar (next to "Unusual spectra", remembered
// per browser) lays a transparent mask over the open field, on top of whatever the map shows or blinks: red where
// the pixels are unreliable in many of the field's frames (saturated stars, dead pixels, afterglow), amber where a
// flag says "look twice" (ghosts, crosstalk, outliers); the more frames, the more opaque. The mask comes from
// GET /api/targets/<id>/flags(.png); the field is small, so the image is drawn with one affine transform through
// its corners (explore.js's public draw hook only). Which flags, in words: click a spot (the spectrum panel lists
// them per exposure).

import { $, el, fmtNum } from "./util.js";
import { targetBase } from "./viewer.js";
import { getSky } from "./explore.js";

const PREF = "spherex.flags";
const st = { on: false, target: null, img: null, info: null, token: 0, hooked: false };
try { st.on = localStorage.getItem(PREF) === "1"; } catch { /* not remembered */ }

function note(text) { const n = $("#flags-note"); if (n) n.textContent = st.on ? text : ""; }

async function load() {
  st.img = null; st.info = null;
  const base = targetBase();
  if (!st.on || !st.target || st.target.synthetic !== false || !base) { note(st.on && !st.target ? "open a field first" : ""); getSky()?.redraw(); return; }
  const token = ++st.token;
  note("reading flags…");
  try {
    const info = await (await fetch(new URL("flags", base), { cache: "no-cache" })).json();
    if (token !== st.token) return;
    if (info.status !== "ready") { note(info.message ?? "no flags"); return; }
    const img = new Image();
    img.crossOrigin = "anonymous";
    await new Promise((ok, bad) => { img.onload = ok; img.onerror = bad; img.src = new URL("flags.png", base).href; });
    if (token !== st.token) return;
    st.img = img; st.info = info;
    const top = Object.keys(info.counts ?? {}).slice(0, 2).map((n) => n.toLowerCase().replace("_", " ")).join(", ");
    note(`${fmtNum(info.bad_fraction * 100, 1)} % unreliable${top ? ` (mostly ${top})` : ""}`);
  } catch { if (token === st.token) note("flags not available"); }
  getSky()?.redraw();
}

function paint(ctx, proj) {
  const t = st.target;
  if (!st.on || !st.img || !t) return;
  const half = (t.image.width * t.image.pixel_scale_arcsec) / 3600 / 2;
  const halfH = (t.image.height * t.image.pixel_scale_arcsec) / 3600 / 2;
  const c = Math.cos(t.center.dec_deg * Math.PI / 180) || 1e-6;
  // grid: north up, east left (CONTRACTS): top-left = north-east corner
  const tl = proj.toScreen(t.center.ra_deg + half / c, t.center.dec_deg + halfH);
  const tr = proj.toScreen(t.center.ra_deg - half / c, t.center.dec_deg + halfH);
  const bl = proj.toScreen(t.center.ra_deg + half / c, t.center.dec_deg - halfH);
  if (!tl.front || !tr.front || !bl.front) return;
  const W = st.img.naturalWidth, H = st.img.naturalHeight;
  ctx.save();
  ctx.imageSmoothingEnabled = false;
  ctx.transform((tr.x - tl.x) / W, (tr.y - tl.y) / W, (bl.x - tl.x) / H, (bl.y - tl.y) / H, tl.x, tl.y);
  ctx.drawImage(st.img, 0, 0);
  ctx.restore();
}

function hook() {
  const sky = getSky();
  if (!sky || st.hooked) return;
  st.hooked = true;
  sky.addDrawHook(paint);
}

function setOn(on) {
  st.on = on;
  try { localStorage.setItem(PREF, on ? "1" : "0"); } catch { /* not remembered */ }
  hook();
  load();
}

function addToggle() {
  if ($("#flags-toggle")) return;
  const after = ($("#outliers-toggle") ?? $("#labels-toggle"))?.closest("label");
  if (!after) return;
  const box = el("label", { title: "SPHEREx's own quality flags over the open field: red = unreliable in many of its frames " +
    "(saturated, dead pixels, afterglow), amber = look twice (ghosts, crosstalk, outliers). Click a spot for the flags by name." },
  el("input", { id: "flags-toggle", type: "checkbox" }), " Quality flags ", el("span", { id: "flags-note", class: "muted small" }));
  after.after(box);
  const input = box.querySelector("input");
  input.checked = st.on;
  input.addEventListener("change", () => setOn(input.checked));
}

addToggle();
document.addEventListener("explore:ready", hook);
hook();
document.addEventListener("viewer:target", (e) => { st.target = e.detail?.target ?? null; load(); });
// for web/tests and the console
globalThis.spherexFlags = { state: () => ({ on: st.on, loaded: Boolean(st.img), info: st.info }) };

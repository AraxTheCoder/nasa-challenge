// T122: the analysed field (the red square) is chosen by the user: "▭ Select region" on the map, then drag a
// rectangle. On release the field is centred on the rectangle and sized by its longer side (5–210′, the API limit)
// and opened the way a shared link does (?ra=&dec=&size=, the page's popstate handler builds it or opens it from
// the cache). While the tool is on, dragging draws instead of moving the map; Esc or the button again cancels.
// A drag shorter than a few pixels is ignored.

import { $, el } from "./util.js";
import * as explore from "./explore.js";

const SIZE_MIN = 5, SIZE_MAX = 210;          // arcmin, as app.js / server parse_size
const st = { on: false, a: null, b: null, id: null, hooked: false };

function button() {
  let b = $("#region-btn");
  if (b) return b;
  const stage = $("#explore");
  if (!stage) return null;
  b = el("button", { id: "region-btn", type: "button", class: "region-btn", "aria-pressed": "false",
    title: "Drag a rectangle on the map to analyse that region (Esc cancels)" }, "▭ Select region");
  b.addEventListener("click", () => setOn(!st.on));
  stage.append(b);
  return b;
}

function hint() {
  let h = $("#region-hint");
  if (!h) {
    h = el("div", { id: "region-hint", class: "region-hint", role: "status" });
    h.hidden = true;
    $("#explore")?.append(h);
  }
  return h;
}

function setOn(on) {
  st.on = on;
  st.a = st.b = null;
  const b = button();
  b?.setAttribute("aria-pressed", String(on));
  b?.classList.toggle("active", on);
  $("#sky")?.classList.toggle("region-drawing", on);
  const h = hint();
  h.textContent = "Drag a rectangle around the region to analyse · Esc cancels";
  h.hidden = !on;
  explore.redraw();
}

function rel(e) {
  const r = $("#sky").getBoundingClientRect();
  return [e.clientX - r.left, e.clientY - r.top];
}

/** Sky size of the rectangle: the longer of its two sky sides through the centre, in arcmin. */
function measure(a, b) {
  const sep = (p, q) => {
    const d = Math.PI / 180;
    const s = Math.sin(((q[1] - p[1]) * d) / 2) ** 2 + Math.cos(p[1] * d) * Math.cos(q[1] * d) * Math.sin(((q[0] - p[0]) * d) / 2) ** 2;
    return (2 * Math.asin(Math.min(1, Math.sqrt(s)))) / d;
  };
  const cx = (a[0] + b[0]) / 2, cy = (a[1] + b[1]) / 2;
  const c = explore.skyAt(cx, cy), l = explore.skyAt(Math.min(a[0], b[0]), cy), r = explore.skyAt(Math.max(a[0], b[0]), cy);
  const t = explore.skyAt(cx, Math.min(a[1], b[1])), btm = explore.skyAt(cx, Math.max(a[1], b[1]));
  if (!c || !l || !r || !t || !btm) return null;
  const side = Math.max(sep(l, r), sep(t, btm)) * 60;
  return { ra: c[0], dec: c[1], raw: side, size: Math.min(SIZE_MAX, Math.max(SIZE_MIN, Math.round(side))) };
}

function label(m) {
  if (!m) return "outside the sky";
  const clamp = m.raw > SIZE_MAX ? ` (largest field: ${SIZE_MAX}′)` : m.raw < SIZE_MIN ? ` (smallest field: ${SIZE_MIN}′)` : "";
  return `${m.size}′ field at RA ${m.ra.toFixed(3)}°, Dec ${m.dec.toFixed(3)}°${clamp}`;
}

function draw(ctx) {
  if (!st.on || !st.a || !st.b) return;
  const [x0, y0] = st.a, [x1, y1] = st.b;
  ctx.save();
  ctx.fillStyle = "rgba(255, 90, 90, 0.10)";
  ctx.strokeStyle = "#ff5a5a";
  ctx.lineWidth = 2;
  ctx.setLineDash([6, 4]);
  ctx.fillRect(Math.min(x0, x1), Math.min(y0, y1), Math.abs(x1 - x0), Math.abs(y1 - y0));
  ctx.strokeRect(Math.min(x0, x1), Math.min(y0, y1), Math.abs(x1 - x0), Math.abs(y1 - y0));
  ctx.restore();
}

function openField(m) {
  const url = new URL(location.href);
  url.searchParams.set("ra", m.ra.toFixed(5));
  url.searchParams.set("dec", m.dec.toFixed(5));
  url.searchParams.set("size", String(m.size));
  url.searchParams.delete("blink");
  history.pushState(null, "", url);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

function init() {
  const sky = $("#sky");
  if (!sky || !button()) return;
  // capture phase on the stage: the map's own drag (on its canvas) never sees these while the tool is on
  sky.addEventListener("pointerdown", (e) => {
    if (!st.on || e.button !== 0) return;
    e.stopPropagation();
    e.preventDefault();
    st.id = e.pointerId;
    sky.setPointerCapture?.(e.pointerId);
    st.a = st.b = rel(e);
    if (!st.hooked) { explore.addDrawHook(draw); st.hooked = true; }
  }, true);
  sky.addEventListener("pointermove", (e) => {
    if (!st.on || st.id !== e.pointerId || !st.a) return;
    e.stopPropagation();
    st.b = rel(e);
    hint().textContent = label(measure(st.a, st.b));
    explore.redraw();
  }, true);
  const end = (e) => {
    if (!st.on || st.id !== e.pointerId || !st.a) return;
    e.stopPropagation();
    st.id = null;
    const [a, b] = [st.a, st.b];
    if (e.type === "pointercancel" || Math.hypot(b[0] - a[0], b[1] - a[1]) < 6) { st.a = st.b = null; explore.redraw(); return; }
    const m = measure(a, b);
    setOn(false);
    if (m) openField(m);
  };
  sky.addEventListener("pointerup", end, true);
  sky.addEventListener("pointercancel", end, true);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && st.on) setOn(false); });
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
else init();
document.addEventListener("explore:ready", () => {
  if (!$("#region-btn")) init();
  if (!st.hooked) { explore.addDrawHook(draw); st.hooked = true; }
});

globalThis.spherexRegion = { on: () => st.on, set: setOn, measure };

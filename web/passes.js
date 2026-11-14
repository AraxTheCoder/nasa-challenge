// T82: blink SPHEREx's survey passes anywhere on the map. SPHEREx maps the whole sky once every ~6
// months (pass 1: May-Oct 2025, pass 2: Nov 2025-Apr 2026, pass 3: May 2026-); the Live API renders
// live tiles from one pass's images only (`/api/sky/spherex-live-p<n>`, HiPS orders 6-7). Zoomed out,
// the IRSA cube combines all passes, so the buttons ask to zoom in first.

import { $, el } from "./util.js";
import * as explore from "./explore.js";

const PASSES = [1, 2, 3];
const MAX_FOV_DEG = 2.0;     // live orders 6-7: views of ~2 deg or less
const st = { shown: null, timer: null, buttons: [], blink: null, note: null };

function zoomedIn() {
  const v = explore.getSky()?.view();
  return Boolean(v && v.fov <= MAX_FOV_DEG);
}

async function pick(n) {
  if (!zoomedIn()) return;
  st.shown = n;
  st.buttons.forEach((b, i) => b.setAttribute("aria-pressed", String(PASSES[i] === n)));
  document.dispatchEvent(new CustomEvent("explore:epoch-picked"));   // mapframes.js steps aside
  if (n === null) explore.hideOverlay();
  else await explore.showLayer(`p${n}`);
}

function stop() {
  clearInterval(st.timer);
  st.timer = null;
  if (st.blink) { st.blink.setAttribute("aria-pressed", "false"); st.blink.textContent = "▶ Blink passes"; }
}

function update() {
  const ok = zoomedIn();
  st.buttons.forEach((b) => { b.disabled = !ok; });
  if (st.blink) st.blink.disabled = !ok;
  if (st.note) st.note.textContent = ok ? "" : "zoom in to 2° to blink passes";
  if (!ok && st.timer) stop();
}

function init() {
  const box = $("#explore-passes");
  if (!box || st.blink) return;
  st.buttons = PASSES.map((n) => el("button", { type: "button", class: "link", "aria-pressed": "false",
    title: `Only images from survey pass ${n}` }, `P${n}`));
  st.buttons.forEach((b, i) => b.addEventListener("click", () => { stop(); pick(st.shown === PASSES[i] ? null : PASSES[i]); }));
  st.blink = el("button", { type: "button", class: "link", "aria-pressed": "false",
    title: "Flip through the survey passes here (loads each pass's tiles the first time)" }, "▶ Blink passes");
  st.blink.addEventListener("click", () => {
    if (st.timer) { stop(); return; }
    st.blink.setAttribute("aria-pressed", "true");
    st.blink.textContent = "❚❚ Stop";
    let i = Math.max(0, PASSES.indexOf(st.shown));
    pick(PASSES[i]);
    st.timer = setInterval(() => { i = (i + 1) % PASSES.length; pick(PASSES[i]); }, 900);
  });
  st.note = el("span", { class: "muted small" });
  box.replaceChildren(el("span", { class: "muted small" }, "Survey passes:"), ...st.buttons, st.blink, st.note);
  explore.on("change", update);
  update();
}

document.addEventListener("explore:ready", init);
// A new field resets the map's overlays: forget which pass was shown.
document.addEventListener("viewer:target", () => { stop(); st.shown = null; st.buttons.forEach((b) => b.setAttribute("aria-pressed", "false")); });

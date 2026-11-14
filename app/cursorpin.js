// T55: a 📍 follows the mouse over the map: the mouse holds it by its head (the needle points below),
// with the sky position in two lines to its right. It hides over the floating panels (so it never
// covers a control) and when the mouse leaves the window. After "Go" it stands on the map centre
// (the Go target) until the mouse moves: a web page can't move the mouse itself.

import { el } from "./util.js";
import * as explore from "./explore.js";

const st = { node: null, ra: null, dec: null, pos: null, overPanel: false, parked: false };

const sign = (x) => (x >= 0 ? "+" : "−");

/** Map-relative px of a client position (the map fills the window, but measure anyway). */
function local(clientX, clientY) {
  const r = document.querySelector("#sky")?.getBoundingClientRect();
  return r ? [clientX - r.left, clientY - r.top] : [clientX, clientY];
}

function update() {
  if (!st.node) return;
  const visible = st.pos && (!st.overPanel || st.parked);
  const sky = visible ? explore.skyAt(...local(...st.pos)) : null;
  st.node.hidden = !sky;
  if (!sky) return;
  st.node.style.transform = `translate(${st.pos[0]}px, ${st.pos[1]}px)`;
  st.ra.textContent = `RA ${sky[0].toFixed(4)}°`;
  st.dec.textContent = `Dec ${sign(sky[1])}${Math.abs(sky[1]).toFixed(4)}°`;
}

/** Stand the 📍 at client point (x, y) (e.g. the map centre after Go) until the mouse moves. */
export function showPinAt(x, y) {
  st.pos = [x, y];
  st.parked = true;
  update();
}

export function initCursorPin() {
  st.ra = el("span");
  st.dec = el("span");
  st.node = el("div", { class: "cursor-pin", hidden: true, "aria-hidden": "true" },
    el("span", { class: "cursor-pin-icon" }, "📍"),
    el("span", { class: "cursor-pin-pill" }, st.ra, st.dec));
  document.body.append(st.node);

  addEventListener("pointermove", (e) => {
    st.pos = [e.clientX, e.clientY];
    st.parked = false;                                   // the mouse moved: follow it again
    st.overPanel = Boolean(e.target.closest?.(".hud-panel, .hud-hint"));
    update();
  }, { passive: true });
  document.documentElement.addEventListener("pointerleave", () => {
    if (!st.parked) { st.pos = null; update(); }
  });
  // panning, zooming, keys: the sky under the resting mouse changes
  const hook = () => explore.on("change", () => update());
  if (explore.getSky()) hook();
  else document.addEventListener("explore:ready", hook, { once: true });
}

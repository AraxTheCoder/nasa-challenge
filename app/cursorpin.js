// T55: a 📍 follows the mouse over the map, with the sky position under it in a pill below.
// It hides over the floating panels (so it never covers a control) and when the mouse leaves the
// window, except right after "Go": then it stays where the mouse is (the Go target now lies there)
// until the mouse moves on.

import { el } from "./util.js";
import * as explore from "./explore.js";

const STICKY_PX = 6;     // after Go: mouse movement that releases the pin over a panel

const st = { node: null, pill: null, pos: null, overPanel: false, sticky: null };

const fmt = (ra, dec) => `RA ${ra.toFixed(4)}°  Dec ${dec >= 0 ? "+" : ""}${dec.toFixed(4)}°`;

/** Map-relative px of a client position (the map fills the window, but measure anyway). */
function local(clientX, clientY) {
  const r = document.querySelector("#sky")?.getBoundingClientRect();
  return r ? [clientX - r.left, clientY - r.top] : [clientX, clientY];
}

function update() {
  if (!st.node) return;
  const visible = st.pos && (!st.overPanel || st.sticky);
  const sky = visible ? explore.skyAt(...local(...st.pos)) : null;
  st.node.hidden = !sky;
  if (!sky) return;
  st.node.style.transform = `translate(${st.pos[0]}px, ${st.pos[1]}px)`;
  st.pill.textContent = fmt(sky[0], sky[1]);
}

/** Last mouse position over the window (client px), or null before the first move. */
export function pointer() { return st.pos; }

/** After Go: show the pin at the mouse even over a panel, until the mouse moves on. */
export function stickHere() {
  if (!st.pos) return;
  st.sticky = [...st.pos];
  update();
}

export function initCursorPin() {
  st.pill = el("span", { class: "cursor-pin-pill" });
  st.node = el("div", { class: "cursor-pin", hidden: true, "aria-hidden": "true" },
    el("span", { class: "cursor-pin-icon" }, "📍"), st.pill);
  document.body.append(st.node);

  addEventListener("pointermove", (e) => {
    st.pos = [e.clientX, e.clientY];
    st.overPanel = Boolean(e.target.closest?.(".hud-panel, .hud-hint"));
    if (st.sticky && Math.hypot(st.pos[0] - st.sticky[0], st.pos[1] - st.sticky[1]) > STICKY_PX) st.sticky = null;
    update();
  }, { passive: true });
  document.documentElement.addEventListener("pointerleave", () => { st.pos = null; st.sticky = null; update(); });
  // panning, zooming, keys, Go: the sky under the resting mouse changes
  const hook = () => explore.on("change", () => update());
  if (explore.getSky()) hook();
  else document.addEventListener("explore:ready", hook, { once: true });
}

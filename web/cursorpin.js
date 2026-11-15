// T55: the 📍 marker: the needle tip on the spot (on the mouse in pick mode), the spot's RA/Dec in
// two lines centred under it.
//  - After "Go", or after picking a spot: the marker stands on that sky position (moves with the
//    map, not with the mouse) and fades out after 5 s.
//  - Pick mode (📍 button): the marker follows the mouse over the map; a left click (not a drag)
//    picks that spot, Esc cancels. It hides over the floating panels so it never covers a control.

import { el } from "./util.js";
import * as explore from "./explore.js";

const FADE_AFTER_MS = 5000;
const CLICK_PX = 4;            // more movement between press and release is a drag, not a pick

const st = {
  node: null, ra: null, dec: null,
  mode: "off",                 // "off" | "pick" (follows the mouse) | "pinned" (stands on a sky position)
  pos: null,                   // pick: last mouse position (client px)
  overPanel: false,
  pinned: null,                // pinned: {ra, dec}
  fadeTimer: null, down: null, onPick: null, onModeChange: null,
};

const sign = (x) => (x >= 0 ? "+" : "−");

const skyRect = () => document.querySelector("#sky")?.getBoundingClientRect() ?? { left: 0, top: 0 };

function setMode(mode) {
  st.mode = mode;
  document.body.classList.toggle("pin-picking", mode === "pick");
  st.onModeChange?.(mode);
}

function show(clientX, clientY, ra, dec) {
  st.node.hidden = false;
  st.node.style.transform = `translate(${clientX}px, ${clientY}px)`;
  st.ra.textContent = `RA ${ra.toFixed(4)}°`;
  st.dec.textContent = `Dec ${sign(dec)}${Math.abs(dec).toFixed(4)}°`;
}

function update() {
  if (!st.node) return;
  const r = skyRect();
  if (st.mode === "pick" && st.pos && !st.overPanel) {
    const sky = explore.skyAt(st.pos[0] - r.left, st.pos[1] - r.top);
    if (sky) return show(st.pos[0], st.pos[1], sky[0], sky[1]);
  } else if (st.mode === "pinned" && st.pinned) {
    const s = explore.screenAt(st.pinned.ra, st.pinned.dec);
    if (s) return show(s[0] + r.left, s[1] + r.top, st.pinned.ra, st.pinned.dec);
  }
  st.node.hidden = true;
}

/** Stand the marker on (ra, dec) and fade it out after 5 s (after Go, or after a pick). */
export function pinAt(ra, dec) {
  clearTimeout(st.fadeTimer);
  st.pinned = { ra, dec };
  setMode("pinned");
  st.node.classList.remove("cursor-pin-fading");
  update();
  st.fadeTimer = setTimeout(() => {
    st.node.classList.add("cursor-pin-fading");          // CSS fades it; then it is gone
    st.fadeTimer = setTimeout(() => { if (st.mode === "pinned") setMode("off"); update(); }, 800);
  }, FADE_AFTER_MS);
}

/** Pick mode on/off: the marker follows the mouse until a left click picks a spot (or Esc). */
export function setPicking(on) {
  clearTimeout(st.fadeTimer);
  st.node.classList.remove("cursor-pin-fading");
  setMode(on ? "pick" : "off");
  update();
}

export const isPicking = () => st.mode === "pick";

/** opts.onPick(ra, dec): a spot was picked; opts.onModeChange(mode): "off" | "pick" | "pinned". */
export function initCursorPin(opts = {}) {
  st.onPick = opts.onPick ?? null;
  st.onModeChange = opts.onModeChange ?? null;
  st.ra = el("span");
  st.dec = el("span");
  st.node = el("div", { class: "cursor-pin", hidden: true, "aria-hidden": "true" },
    el("span", { class: "cursor-pin-icon" }, "📍"),
    el("span", { class: "cursor-pin-pill" }, st.ra, st.dec));
  document.body.append(st.node);

  addEventListener("pointermove", (e) => {
    st.pos = [e.clientX, e.clientY];
    st.overPanel = Boolean(e.target.closest?.(".hud-panel, .deck, .wheel"));
    if (st.mode === "pick") update();
  }, { passive: true });
  document.documentElement.addEventListener("pointerleave", () => {
    st.pos = null;
    if (st.mode === "pick") update();
  });

  // pick: a left click on the map (press + release without dragging) takes that spot
  const map = document.querySelector("#sky");
  map.addEventListener("pointerdown", (e) => {
    st.down = st.mode === "pick" && e.button === 0 ? [e.clientX, e.clientY] : null;
  }, true);
  map.addEventListener("pointerup", (e) => {
    const d = st.down;
    st.down = null;
    if (!d || st.mode !== "pick" || Math.hypot(e.clientX - d[0], e.clientY - d[1]) > CLICK_PX) return;
    const r = skyRect();
    const sky = explore.skyAt(e.clientX - r.left, e.clientY - r.top);
    if (!sky) return;
    e.preventDefault();  // handled pick; the point-spectrum click handler must not select it twice
    pinAt(sky[0], sky[1]);
    st.onPick?.(sky[0], sky[1]);
  }, true);
  addEventListener("keydown", (e) => { if (e.key === "Escape" && st.mode === "pick") setPicking(false); });

  // panning, zooming, keys: the sky under the mouse, or the pinned spot's place on screen, changes
  const hook = () => explore.on("change", () => update());
  if (explore.getSky()) hook();
  else document.addEventListener("explore:ready", hook, { once: true });
}

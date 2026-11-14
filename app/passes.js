// T55 (/app/): blink SPHEREx's six-month survey passes on their own, anywhere on the map, as soon as the
// map is sharp (HiPS order 7, 3.2″ texels): below that nothing that moves between passes is visible.
// Pass layers are the Live API's spherex-live-p<n> (T82): live tiles from one pass's images only, on the
// same HEALPix grid as the map, so the screen's tiles are rendered once and cached for everyone.
// Loading starts one zoom level earlier (order 6: the tiles a zoom in at the centre would show), and only
// passes whose visible tiles are all loaded take part, so the blink never shows half-loaded passes.
//
// Source switch (next to Debug): "passes" (this, default) or "epochs" (the Blink button builds a field
// and its epochs are blinked, T32). A built field always switches to "epochs".

import { $, el } from "./util.js";
import * as explore from "./explore.js";

export const SHARP_ORDER = 7;    // deepest live order: blink only here
const STEP_MS = 800;
const MODE_KEY = "spherex-app-blink-source";

const st = { mode: "passes", passes: [], layers: false, shown: -1, paused: false, timer: null,
  buttons: [], play: null, note: null, listeners: [] };

export const mode = () => st.mode;
export const sharp = () => (explore.baseOrder() ?? 0) >= SHARP_ORDER;
export function onModeChange(fn) { st.listeners.push(fn); }

/** "passes" or "epochs"; remembered in this browser. */
export async function setMode(m, { remember = true } = {}) {
  if (m !== "passes" && m !== "epochs") return;
  const changed = m !== st.mode;
  st.mode = m;
  if (remember) { try { localStorage.setItem(MODE_KEY, m); } catch { /* private mode */ } }
  const sel = $("#blink-source");
  if (sel) sel.value = m;
  $("#explore-passes").hidden = m !== "passes";
  if (m === "passes") await loadLayers();
  else { st.layers = false; st.shown = -1; }        // the field's epochs replace the pass layers
  update();
  if (changed) st.listeners.forEach((fn) => fn(m));
}

async function loadLayers() {
  if (st.layers || !st.passes.length) return;
  st.layers = true;
  st.shown = -1;
  const made = await explore.setPassLayers(st.passes, SHARP_ORDER);
  if (st.mode !== "passes") return;
  if (!made.length) { st.layers = false; st.note.textContent = "survey passes unavailable (Live API?)"; }
}

function show(i) {
  if (i === st.shown) return;                        // showOverlay redraws: only on a change
  st.shown = i;
  explore.showOverlay(i);
  st.buttons.forEach((b, j) => b.setAttribute("aria-pressed", String(j === i)));
}

/** Per pass: "ready" (all visible tiles loaded, some with data), "empty" (none has data) or "loading". */
function states() {
  return st.passes.map((_, i) => {
    const p = explore.overlayProgress(i);
    if (!p || !p.total || p.done < p.total) return { state: "loading", p };
    return { state: p.ok ? "ready" : "empty", p };
  });
}

function update() {
  if (st.mode !== "passes" || !st.layers) return;
  const s = states(), on = sharp();
  st.buttons.forEach((b, i) => {
    const { state, p } = s[i];
    b.disabled = state === "empty";
    b.classList.toggle("loading", state === "loading");
    b.title = state === "empty" ? `Pass ${st.passes[i]}: no SPHEREx images here`
      : state === "loading" ? `Pass ${st.passes[i]}: loading ${p?.done ?? 0}/${p?.total ?? "?"} tiles`
        : `Show only survey pass ${st.passes[i]} (${passDates(st.passes[i])})`;
  });
  const ready = s.map((x, i) => (x.state === "ready" ? i : -1)).filter((i) => i >= 0);
  const loading = s.filter((x) => x.state === "loading");
  const tiles = loading.reduce((a, x) => [a[0] + (x.p?.done ?? 0), a[1] + (x.p?.total ?? 0)], [0, 0]);
  if (!on) {
    show(-1);
    const order = explore.baseOrder() ?? 0;
    st.note.textContent = order >= SHARP_ORDER - 1
      ? `zoom in once more to blink${loading.length && tiles[1] ? ` · loading ${tiles[0]}/${tiles[1]}` : ""}`
      : "zoom in to level 7 to blink the passes";
    return;
  }
  st.note.textContent = loading.length ? `loading ${tiles[0]}/${tiles[1]} tiles` : "";
  if (st.paused) {
    if (st.shown >= 0 && s[st.shown]?.state === "empty") show(-1);
    return;
  }
  if (ready.length < 2) { show(ready.length === 1 && !loading.length ? ready[0] : -1); return; }
  if (!ready.includes(st.shown)) show(ready[0]);
}

function step() {
  if (st.mode !== "passes" || st.paused || !sharp()) return;
  const ready = states().map((x, i) => (x.state === "ready" ? i : -1)).filter((i) => i >= 0);
  if (ready.length < 2) return;
  const k = ready.indexOf(st.shown);
  show(ready[(k + 1) % ready.length]);
}

function setPaused(p) {
  st.paused = p;
  st.play.setAttribute("aria-pressed", String(!p));
  st.play.textContent = p ? "▶" : "❚❚";
  st.play.title = p ? "Blink the survey passes again" : "Pause the blink (stay on the shown pass)";
  update();
}

/** Calendar span of pass n (from tilegen.render: 182.625 d from 2025-05-01). */
function passDates(n) {
  const start = Date.UTC(2025, 4, 1) + (n - 1) * 182.625 * 864e5;
  const f = (t) => new Date(t).toISOString().slice(0, 7);
  return `${f(start)} – ${f(start + 182.625 * 864e5 - 864e5)}`;
}

/** Call once the map exists. */
export async function initPasses() {
  st.passes = explore.surveyPasses();
  const box = $("#explore-passes");
  st.buttons = st.passes.map((n, i) => {
    const b = el("button", { type: "button", class: "link", "aria-pressed": "false" }, `P${n}`);
    b.addEventListener("click", () => { setPaused(true); show(st.shown === i ? -1 : i); });
    return b;
  });
  st.play = el("button", { type: "button", class: "link", "aria-pressed": "true" }, "❚❚");
  st.play.addEventListener("click", () => setPaused(!st.paused));
  st.note = el("span", { class: "muted small" });
  box.replaceChildren(el("span", { class: "muted small", title: "SPHEREx maps the whole sky once every ~6 months" },
    "Passes:"), ...st.buttons, st.play, st.note);
  setPaused(false);
  const sel = $("#blink-source");
  sel.addEventListener("change", () => setMode(sel.value));
  let saved = "passes";
  try { saved = localStorage.getItem(MODE_KEY) ?? "passes"; } catch { /* private mode */ }
  if (!st.passes.length) {                           // map without pass layers (offline / old API)
    sel.querySelector('option[value="passes"]').disabled = true;
    saved = "epochs";
  }
  st.mode = null;                                    // force a full setMode
  await setMode(saved, { remember: false });
  explore.onTiles(update);                           // every redraw: loading state, zoom level
  st.timer = setInterval(step, STEP_MS);
}

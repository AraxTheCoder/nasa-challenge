// T55 (T90: web/autoblink.js, was app/passes.js): blink SPHEREx's six-month survey passes by themselves, anywhere on the map, from level 6 on
// (the pass layers' live orders 6-7; coarser, the IRSA cube combines all passes). Field epochs (app.js) come
// at level 7, where the map is fully sharp.
// Pass layers are the Live API's spherex-live-p<n> (T82): live tiles from one pass's images only, on the
// same HEALPix grid as the map, so the screen's tiles are rendered once and cached for everyone.
// Loading starts one zoom level earlier (order 5: the tiles a zoom in at the centre would show), and only
// passes whose visible tiles are all loaded take part, so the blink never shows half-loaded passes.
// Always running: no play / pause, no buttons. Each pass is labelled with when SPHEREx imaged the view
// centre in it (GET /api/pass-dates), e.g. "Aug–Sep 2025".
//
// The source is chosen by app.js on its own: "passes" (this, default) or "epochs" (the field of the order-6
// tile the view rests on, once it is built, T32); app.js shows which one in a text indicator.

import { $, el } from "./util.js";
import * as explore from "./explore.js";

export const SHARP_ORDER = 7;    // deepest live order: the field epochs blink only here
export const PASS_ORDER = 6;     // the pass layers' first live order: they blink from here on
const STEP_MS = 800;
const DATES_MOVE_DEG = 0.3;      // ask for the dates again once the centre moved this far

const st = { mode: "passes", passes: [], layers: false, layerCall: 0, colour: false, paused: false, still: false, shown: -1, labels: [], note: null, listeners: [],
  dates: null, datesAt: null, datesTimer: null };

export const mode = () => st.mode;
export const sharp = () => (explore.wantedOrder() ?? 0) >= SHARP_ORDER;
export const passesOn = () => (explore.wantedOrder() ?? 0) >= PASS_ORDER;
export function onModeChange(fn) { st.listeners.push(fn); }
export const colour = () => st.colour;
export const paused = () => st.paused;

/** T100: the Blink switch is off: the shown pass stays until a date label is clicked. */
export function setStill(on) { st.still = !!on; }

/** T90: the frame tools (or another base map) drive the map: leave the overlays alone until resumed. */
export async function setPaused(on) {
  if (st.paused === !!on) return;
  st.paused = !!on;
  if (!st.paused && st.mode === "passes") { st.layers = false; await loadLayers(); }   // others may have changed them
  update();
}

/** T89: false colour (all detectors combined) or the band's detector; reloads the pass layers. */
export async function setColour(on) {
  if (st.colour === !!on) return;
  st.colour = !!on;
  if (st.mode === "passes") { st.layers = false; await loadLayers(); update(); }
}

/** "passes" or "epochs" (app.js decides; the options object is accepted for older callers). */
export async function setMode(m, _opts = {}) {
  if (m !== "passes" && m !== "epochs") return;
  const changed = m !== st.mode;
  st.mode = m;
  // Stop the old source immediately, before any replacement metadata can stall.
  if (changed) st.listeners.forEach((fn) => fn(m));
  $("#blink-passes").hidden = m !== "passes";
  // under blinking passes the base map only shows through their holes: the IRSA cube (order 5) is enough
  // there, and its tiles are no live renders competing with the passes'
  explore.setBaseCap(m === "passes" ? PASS_ORDER - 1 : null);
  if (m === "passes") await loadLayers();
  else { ++st.layerCall; st.layers = false; st.shown = -1; }        // the field's epochs replace the pass layers
  update();
}

async function loadLayers() {
  if (st.layers || !st.passes.length) return;
  const call = ++st.layerCall;
  st.layers = true;
  st.shown = -1;
  const made = await explore.setPassLayers(st.passes, st.colour);
  if (call !== st.layerCall || st.mode !== "passes") return;
  if (!made.length) { st.layers = false; st.note.textContent = "survey passes unavailable (Live API?)"; }
}

function show(i) {
  st.labels.forEach((b, j) => b.classList.toggle("current", j === i));   // also after a reset of st.shown
  if (i === st.shown) return;                        // showOverlay redraws: only on a change
  st.shown = i;
  explore.showOverlay(i);
}

/** Per pass: "ready" (all visible tiles loaded, some with data), "empty" (none has data) or "loading". */
function states() {
  return st.passes.map((n, i) => {
    if (st.dates && !st.dates.has(n)) return { state: "empty", p: null };   // no images of this spot
    const p = explore.overlayProgress(i);
    if (!p || !p.total || p.done < p.total) return { state: "loading", p };
    return { state: p.ok ? "ready" : "empty", p };
  });
}

const readyOf = (s) => s.map((x, i) => (x.state === "ready" ? i : -1)).filter((i) => i >= 0);

function update() {
  if (st.mode !== "passes" || !st.layers || st.paused) return;
  const s = states(), on = passesOn();
  st.labels.forEach((b, i) => {
    const { state, p } = s[i];
    b.hidden = state === "empty";
    b.classList.toggle("loading", state === "loading");
    const d = st.dates?.get(st.passes[i]);
    b.title = `Survey pass ${st.passes[i]}` + (d ? `: imaged here ${d.start} – ${d.end}` : "")
      + (state === "loading" ? ` · loading ${p?.done ?? 0}/${p?.total ?? "?"} tiles` : "");
  });
  const loading = s.filter((x) => x.state === "loading");
  const tiles = loading.reduce((a, x) => [a[0] + (x.p?.done ?? 0), a[1] + (x.p?.total ?? 0)], [0, 0]);
  const progress = loading.length && tiles[1] ? `loading ${tiles[0]}/${tiles[1]} tiles` : "";
  if (!on) {
    show(-1);
    const order = explore.wantedOrder() ?? 0;
    st.note.textContent = order >= PASS_ORDER - 1 ? ["zoom in once more to blink", progress].filter(Boolean).join(" · ")
      : "zoom in to level 6 to blink";
    return;
  }
  st.note.textContent = progress;
  const ready = readyOf(s);
  if (ready.length < 2) { show(ready.length === 1 && !loading.length ? ready[0] : -1); return; }
  if (!ready.includes(st.shown)) show(ready[0]);
}

function step() {
  if (st.mode !== "passes" || st.paused || st.still || !passesOn()) return;
  const ready = readyOf(states());
  if (ready.length < 2) return;
  show(ready[(ready.indexOf(st.shown) + 1) % ready.length]);
}

// ---------- when each pass imaged the view centre ----------

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2025-08-18", "2025-09-30" -> "Aug–Sep 2025"; same month -> "Mar 2026"; over New Year -> "Dec 2025–Jan 2026". */
export function monthSpan(start, end) {
  const [y0, m0] = start.split("-").map(Number), [y1, m1] = (end ?? start).split("-").map(Number);
  if (y0 === y1 && m0 === m1) return `${MONTHS[m0 - 1]} ${y0}`;
  if (y0 === y1) return `${MONTHS[m0 - 1]}–${MONTHS[m1 - 1]} ${y0}`;
  return `${MONTHS[m0 - 1]} ${y0}–${MONTHS[m1 - 1]} ${y1}`;
}

/** A pass's label: its visits here, e.g. "Mar 2026", "Apr & Oct 2025", "Oct 2025 & Apr 2026". */
export function visitLabel(d) {
  const v = d.visits?.length ? d.visits : [d];
  if (v.length === 1) return monthSpan(v[0].start, v[0].end);
  const parts = v.map((x) => monthSpan(x.start, x.end));
  const year = (t) => t.slice(-4);
  if (v.every((x) => /^[A-Z][a-z]{2}(–[A-Z][a-z]{2})? \d{4}$/.test(monthSpan(x.start, x.end)))
      && new Set(parts.map(year)).size === 1) {
    return parts.map((p) => p.slice(0, -5)).join(" & ") + ` ${year(parts[0])}`;    // same year: "Apr & Oct 2025"
  }
  return parts.join(" & ");
}

const sep = (a, b) => {
  const d = Math.PI / 180;
  const c = Math.sin(a.dec * d) * Math.sin(b.dec * d) + Math.cos(a.dec * d) * Math.cos(b.dec * d) * Math.cos((a.ra - b.ra) * d);
  return Math.acos(Math.min(1, c)) / d;
};

function labelPass(i, text) { st.labels[i].textContent = text; }

async function askDates() {
  const v = explore.view(), api = explore.getApiBase();
  if (!v || !api || (explore.wantedOrder() ?? 0) < PASS_ORDER - 1) return;
  if (st.datesAt && sep(st.datesAt, v) < DATES_MOVE_DEG) return;
  const at = { ra: v.ra, dec: v.dec };
  st.datesAt = at;
  try {
    const res = await fetch(`${api.replace(/\/$/, "")}/api/pass-dates?ra=${v.ra.toFixed(4)}&dec=${v.dec.toFixed(4)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const body = await res.json();
    if (st.datesAt !== at) return;
    st.dates = new Map(body.passes.map((p) => [p.pass, p]));
    st.passes.forEach((n, i) => {
      const d = st.dates.get(n);
      labelPass(i, d ? visitLabel(d) : `pass ${n}`);
    });
  } catch {
    if (st.datesAt !== at) return;
    st.datesAt = null;                               // ask again on the next move
    st.dates = null;
    st.passes.forEach((n, i) => labelPass(i, `pass ${n}`));
  }
  update();
}

function onMove() {
  const v = explore.view();
  if (!v || (st.datesAt && sep(st.datesAt, v) < DATES_MOVE_DEG)) return;   // mouse moves too: cheap test first
  clearTimeout(st.datesTimer);
  st.datesTimer = setTimeout(askDates, 300);
}

/** Call once the map exists. */
export async function initPasses() {
  st.passes = explore.surveyPasses();
  const box = $("#blink-passes");
  st.labels = st.passes.map((n) => el("span", { class: "pass-label" }, `pass ${n}`));
  // T100: a click shows that pass (if it is loaded here); with the Blink switch off it then stays
  st.labels.forEach((b, i) => b.addEventListener("click", () => {
    if (st.mode === "passes" && !st.paused && passesOn() && states()[i].state === "ready") show(i);
  }));
  st.note = el("span", { class: "muted small" });
  box.replaceChildren(...st.labels, st.note);
  st.mode = null;                                    // force a full setMode
  await setMode(st.passes.length ? "passes" : "epochs");   // no pass layers (offline / old API): epochs only
  explore.onTiles(update);                           // every redraw: loading state, zoom level
  explore.on("change", onMove);
  onMove();
  setInterval(step, STEP_MS);
}

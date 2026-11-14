// T55 (/app/): blink SPHEREx's six-month survey passes by themselves, anywhere on the map, as soon as the
// map is sharp (HiPS order 7, 3.2″ texels): below that nothing that moves between passes is visible.
// Pass layers are the Live API's spherex-live-p<n> (T82): live tiles from one pass's images only, on the
// same HEALPix grid as the map, so the screen's tiles are rendered once and cached for everyone.
// Loading starts one zoom level earlier (order 6: the tiles a zoom in at the centre would show), and only
// passes whose visible tiles are all loaded take part, so the blink never shows half-loaded passes.
// Always running: no play / pause, no buttons. Each pass is labelled with when SPHEREx imaged the view
// centre in it (GET /api/pass-dates), e.g. "Aug–Sep 2025".
//
// Source switch (next to Debug): "passes" (this, default) or "epochs" (app.js builds the view's field at
// level 7 and blinks its epochs, T32). A field opened from a link switches to "epochs".

import { $, el } from "./util.js";
import * as explore from "./explore.js";

export const SHARP_ORDER = 7;    // deepest live order: blink only here
const STEP_MS = 800;
const MODE_KEY = "spherex-app-blink-source";
const DATES_MOVE_DEG = 0.3;      // ask for the dates again once the centre moved this far

const st = { mode: "passes", passes: [], layers: false, shown: -1, labels: [], note: null, listeners: [],
  dates: null, datesAt: null, datesTimer: null };

export const mode = () => st.mode;
export const sharp = () => (explore.wantedOrder() ?? 0) >= SHARP_ORDER;
export function onModeChange(fn) { st.listeners.push(fn); }

/** "passes" or "epochs"; remembered in this browser unless remember is false. */
export async function setMode(m, { remember = true } = {}) {
  if (m !== "passes" && m !== "epochs") return;
  const changed = m !== st.mode;
  st.mode = m;
  if (remember) { try { localStorage.setItem(MODE_KEY, m); } catch { /* private mode */ } }
  const sel = $("#blink-source");
  if (sel) sel.value = m;
  $("#explore-passes").hidden = m !== "passes";
  explore.setBaseCap(m === "passes" ? SHARP_ORDER - 1 : null);
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
  st.labels.forEach((b, j) => b.classList.toggle("current", j === i));
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
  if (st.mode !== "passes" || !st.layers) return;
  const s = states(), on = sharp();
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
    st.note.textContent = order >= SHARP_ORDER - 1 ? ["zoom in once more to blink", progress].filter(Boolean).join(" · ")
      : "zoom in to level 7 to blink";
    return;
  }
  st.note.textContent = progress;
  const ready = readyOf(s);
  if (ready.length < 2) { show(ready.length === 1 && !loading.length ? ready[0] : -1); return; }
  if (!ready.includes(st.shown)) show(ready[0]);
}

function step() {
  if (st.mode !== "passes" || !sharp()) return;
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

const sep = (a, b) => {
  const d = Math.PI / 180;
  const c = Math.sin(a.dec * d) * Math.sin(b.dec * d) + Math.cos(a.dec * d) * Math.cos(b.dec * d) * Math.cos((a.ra - b.ra) * d);
  return Math.acos(Math.min(1, c)) / d;
};

function labelPass(i, text) { st.labels[i].textContent = text; }

async function askDates() {
  const v = explore.view(), api = explore.getApiBase();
  if (!v || !api || (explore.wantedOrder() ?? 0) < SHARP_ORDER - 1) return;
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
      labelPass(i, d ? monthSpan(d.start, d.end) : `pass ${n}`);
    });
  } catch {
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
  const box = $("#explore-passes");
  st.labels = st.passes.map((n) => el("span", { class: "pass-label" }, `pass ${n}`));
  st.note = el("span", { class: "muted small" });
  box.replaceChildren(...st.labels, st.note);
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
  explore.on("change", onMove);
  onMove();
  setInterval(step, STEP_MS);
}

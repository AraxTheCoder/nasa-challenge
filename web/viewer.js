// Frame viewer: stacks all frames of one target and blinks between two (T11), with an epoch
// timeline, a wavelength filter and wavelength-matched pairs (T12).
// Knows nothing about where target.json came from; app.js hands it the parsed JSON and its URL.
//
// State lives in `state` only. Anything that changes A, B, the shown frame or the filter ends in
// refreshMarks(), which updates every place that shows them (stage label, buttons, table, timeline,
// pair picker), so those views cannot disagree.

import { $, el, fmtDuration, fmtNum, fmtTime, isTyping, safeUrl } from "./util.js";
import { markTimeline, renderTimeline } from "./timeline.js";
import "./paths.js"; // T22: movement paths, listens to the viewer:* events below

const SCHEMA_VERSIONS = ["0.1", "0.2"]; // target.json versions this viewer understands
const MATCH_FALLBACK_UM = 0.05;          // "same wavelength" when frames carry no bandwidth_um

const state = {
  target: null,
  base: null,        // absolute URL of the target folder (frame paths are relative to it)
  frames: [],        // sorted by mjd
  pairs: [],         // v0.2 wavelength-matched pairs whose frames exist
  imgs: new Map(),   // frame id -> <img>
  broken: new Set(), // frame ids whose image failed to load
  filter: { min: null, max: null, detector: null }, // wavelength (µm) and detector filter
  aId: null,
  bId: null,
  shownId: null,
  playing: false,
  intervalMs: 500,
  timer: null,
};

export const currentTarget = () => state.target;

/** A and B with their image URLs, for other modules (diff.js). null when no target is shown. */
export function currentPair() {
  const a = frameById(state.aId);
  const b = frameById(state.bId);
  if (!state.target || !a || !b) return null;
  const { width = 1, height = 1 } = state.target.image ?? {};
  return { a, b, urlA: frameUrl(a), urlB: frameUrl(b), width, height, matched: a.id !== b.id && wavelengthMatched(a, b) };
}

/** Show one frame (stops blinking). For other modules, e.g. objects.js jumping to an object. */
export function showFrame(id) {
  if (!frameById(id)) return;
  stopBlink();
  show(id);
}
export const isSynthetic = (t) => t.synthetic !== false; // missing flag counts as synthetic

/** Light checks only; the full schema is docs/target.schema.json and is enforced upstream. */
export function checkTarget(t, expectedId) {
  if (!t || !Array.isArray(t.frames) || t.frames.length === 0) {
    throw new Error(`target "${expectedId ?? t?.id}" has no frames`);
  }
  const warnings = [];
  if (!SCHEMA_VERSIONS.includes(t.schema_version)) {
    warnings.push(`schema_version is ${JSON.stringify(t.schema_version)}, this viewer knows ${SCHEMA_VERSIONS.join(", ")}.`);
  }
  if (expectedId && t.id !== expectedId) warnings.push(`target.json id "${t.id}" differs from "${expectedId}".`);
  if (typeof t.synthetic !== "boolean") warnings.push("target.json has no synthetic flag; treating it as synthetic.");
  if (!t.image?.width || !t.image?.height) warnings.push("target.json has no image size; assuming square frames.");
  return warnings;
}

/** Show a parsed target.json. targetUrl is where it was loaded from (frame paths resolve against it). */
export function showTarget(target, targetUrl) {
  stopBlink();
  state.target = target;
  state.base = new URL(".", targetUrl).href;
  state.frames = [...target.frames].sort((a, b) => a.mjd - b.mjd);
  const ids = new Set(state.frames.map((f) => f.id));
  state.pairs = (Array.isArray(target.pairs) ? target.pairs : []).filter((p) => ids.has(p.a) && ids.has(p.b));
  state.broken = new Set();
  state.filter = { min: null, max: null, detector: null };
  [state.aId, state.bId] = defaultPair();

  renderTargetHead();
  renderStage();
  renderFrameTable();
  renderCompareControls();
  renderProvenance();
  $("#empty").hidden = true;
  $("#viewer-body").hidden = false;
  $("#side").hidden = false;
  drawTimeline(); // after un-hiding, so it can measure its width
  document.dispatchEvent(new CustomEvent("viewer:target", { detail: { target } })); // T22 paths
  show(state.aId);
}

/** Back to the empty state (no target shown). */
export function clearTarget() {
  stopBlink();
  state.target = null;
  state.frames = [];
  state.pairs = [];
  state.imgs = new Map();
  $("#frame-stack").replaceChildren();
  $("#overlay").replaceChildren();
  $("#timeline").replaceChildren();
  $("#synthetic-badge").hidden = true;
  $("#empty").hidden = false;
  $("#viewer-body").hidden = true;
  $("#side").hidden = true;
  document.title = "SPHEREx Blink";
  document.dispatchEvent(new CustomEvent("viewer:target", { detail: { target: null } }));
}

const frameById = (id) => state.frames.find((f) => f.id === id);
const rowFor = (id) => document.querySelector(`#frame-table tr[data-frame="${CSS.escape(id)}"]`);

// ---------- which frames count (filter, pairs, matching) ----------

function inFilter(f) {
  const { min, max, detector } = state.filter;
  if (min != null && !(f.wavelength_um >= min)) return false;
  if (max != null && !(f.wavelength_um <= max)) return false;
  if (detector != null && f.detector !== detector) return false;
  return true;
}

const visibleFrames = () => state.frames.filter(inFilter);
const isVisibleId = (id) => { const f = frameById(id); return !!f && inFilter(f); };

/** The v0.2 pair containing frames a and b (either order), if any. */
const pairOf = (a, b) => state.pairs.find((p) => (p.a === a && p.b === b) || (p.a === b && p.b === a));

/** Are A and B at (nearly) the same wavelength? Uses bandwidth_um (v0.2) when present. */
function wavelengthMatched(a, b) {
  if (pairOf(a.id, b.id)) return true;
  const dl = Math.abs(a.wavelength_um - b.wavelength_um);
  const bw = Math.min(a.bandwidth_um ?? Infinity, b.bandwidth_um ?? Infinity);
  return dl <= (Number.isFinite(bw) ? 0.5 * bw : MATCH_FALLBACK_UM);
}

/**
 * Best B for a given A among `candidates`: its pair partner if there is one, else the frame from
 * another epoch closest in wavelength (same detector preferred). null if A's epoch is all there is.
 */
function bestPartner(a, candidates) {
  for (const p of state.pairs) {
    const other = p.a === a.id ? p.b : p.b === a.id ? p.a : null;
    if (other && candidates.some((f) => f.id === other)) return frameById(other);
  }
  const others = candidates.filter((f) => f.epoch !== a.epoch);
  if (others.length === 0) return null;
  const cost = (f) => Math.abs(f.wavelength_um - a.wavelength_um) + (f.detector === a.detector ? 0 : 10);
  return others.reduce((best, f) => (cost(f) < cost(best) ? f : best));
}

/** Default A/B: the matched pair with the longest time between (most motion), else first frame + best partner. */
function defaultPair(candidates = state.frames) {
  const ids = new Set(candidates.map((f) => f.id));
  const pairs = state.pairs.filter((p) => ids.has(p.a) && ids.has(p.b));
  if (pairs.length) {
    const p = pairs.reduce((best, q) =>
      (q.dt_days ?? 0) > (best.dt_days ?? 0) || ((q.dt_days ?? 0) === (best.dt_days ?? 0) && q.dwave_um < best.dwave_um) ? q : best);
    return [p.a, p.b];
  }
  const a = candidates[0];
  const b = bestPartner(a, candidates) ?? candidates[candidates.length - 1];
  return [a.id, b.id];
}

// ---------- rendering ----------

function renderTargetHead() {
  const t = state.target;
  const synthetic = isSynthetic(t);
  document.title = `${t.name ?? t.id} · SPHEREx Blink`;
  $("#target-name").textContent = t.name ?? t.id;
  const epochs = new Set(state.frames.map((f) => f.epoch)).size;
  $("#target-meta").textContent = [
    `RA ${fmtNum(t.center?.ra_deg, 4)}°, Dec ${fmtNum(t.center?.dec_deg, 4)}°`,
    `${fmtNum(t.size_arcmin, 1)}′ field`,
    `${state.frames.length} frames, ${epochs} epoch${epochs === 1 ? "" : "s"}`,
  ].join(" · ");
  $("#synthetic-badge").hidden = !synthetic;
  $("#stage-watermark").hidden = !synthetic;
  $("#frame-count").textContent = `(${state.frames.length})`;
}

function renderStage() {
  const { width = 1, height = 1 } = state.target.image ?? {};
  $("#stage").style.setProperty("--ar", `${width} / ${height}`);
  // Pixel (0,0) is the centre of the top-left pixel (CONTRACTS), so the overlay viewBox starts at -0.5.
  const overlay = $("#overlay");
  overlay.setAttribute("viewBox", `-0.5 -0.5 ${width} ${height}`);
  overlay.setAttribute("preserveAspectRatio", "none");
  overlay.replaceChildren();

  // All frames stacked and preloaded; blinking only toggles visibility, so there is no flicker.
  state.imgs = new Map();
  const imgs = state.frames.map((f) => {
    const img = el("img", { src: frameUrl(f), alt: `Frame ${f.id}`, draggable: "false" });
    img.addEventListener("error", () => {
      if (state.imgs.get(f.id) !== img) return; // a newer target replaced this one
      state.broken.add(f.id);
      rowFor(f.id)?.classList.add("broken");
      if (state.shownId === f.id) updateStageError();
    });
    state.imgs.set(f.id, img);
    return img;
  });
  $("#frame-stack").replaceChildren(...imgs);
}

/**
 * Frame image URL with a build stamp. A rebuild (Rebuild button / refresh=1, or fixture → live) writes
 * new images under the same names, and the API lets browsers cache frames for a day; without the
 * stamp the browser shows the old images for frames whose names already existed.
 */
function frameUrl(f) {
  const url = new URL(f.image, state.base);
  const stamp = (state.target.provenance ?? []).map((p) => p.retrieved_utc ?? "").sort().pop();
  if (stamp) url.searchParams.set("v", stamp);
  return url.href;
}

function renderFrameTable() {
  const rows = state.frames.map((f) => {
    const radio = (slot) =>
      el("input", {
        type: "radio",
        name: `slot-${slot}`,
        value: f.id,
        "aria-label": `Use ${f.id} as ${slot.toUpperCase()}`,
        onchange: () => setSlot(slot, f.id),
      });
    const onclick = (e) => {
      if (e.target.tagName === "INPUT") return;
      stopBlink();
      show(f.id);
    };
    return el(
      "tr",
      { "data-frame": f.id, onclick },
      el("td", {}, radio("a")),
      el("td", {}, radio("b")),
      el("td", {}, f.id),
      el("td", { title: fmtTime(f.time_utc) }, fmtTime(f.time_utc).slice(0, 16)),
      el("td", {}, String(f.epoch ?? "–")),
      el("td", {}, fmtNum(f.wavelength_um, 2)),
      el("td", {}, f.detector == null ? "–" : `D${f.detector}`),
    );
  });
  $("#frame-table tbody").replaceChildren(...rows);
}

/** Wavelength inputs, detector picker and pair picker for the current target. */
function renderCompareControls() {
  $("#lam-min").value = "";
  $("#lam-max").value = "";

  const detectors = [...new Set(state.frames.map((f) => f.detector).filter((d) => d != null))].sort((a, b) => a - b);
  $("#det-filter").replaceChildren(
    el("option", { value: "" }, "all"),
    ...detectors.map((d) => {
      const ls = state.frames.filter((f) => f.detector === d).map((f) => f.wavelength_um);
      return el("option", { value: String(d) }, `D${d} (${fmtNum(Math.min(...ls), 2)}–${fmtNum(Math.max(...ls), 2)} µm)`);
    }),
  );
  $("#det-wrap").hidden = detectors.length < 2;

  $("#pair-select").replaceChildren(
    el("option", { value: "" }, state.pairs.length ? `${state.pairs.length} pairs…` : "none"),
    ...state.pairs.map((p, i) => {
      const a = frameById(p.a);
      const b = frameById(p.b);
      const label = `${p.a} ↔ ${p.b} · ${fmtNum(a.wavelength_um, 3)} µm · Δλ ${fmtNum(p.dwave_um ?? Math.abs(a.wavelength_um - b.wavelength_um), 3)}` +
        ` · ${fmtDuration(p.dt_days ?? b.mjd - a.mjd)}${p.detector == null ? "" : ` · D${p.detector}`}`;
      return el("option", { value: String(i) }, label);
    }),
  );
  $("#pair-wrap").hidden = state.pairs.length === 0;
}

function drawTimeline() {
  renderTimeline($("#timeline"), state.frames, {
    onPick: (id) => {
      if (!isVisibleId(id)) return; // outside the wavelength filter
      stopBlink();
      show(id);
    },
  });
}

function renderProvenance() {
  const items = (state.target.provenance ?? []).map((p) =>
    el("li", {}, el("strong", {}, p.service ?? "?"), ` · ${fmtTime(p.retrieved_utc)}`, el("br"), el("code", {}, p.query ?? "")),
  );
  $("#provenance-list").replaceChildren(...(items.length ? items : [el("li", { class: "muted" }, "none recorded")]));
}

function renderFrameInfo(f) {
  const a = frameById(state.aId);
  const b = frameById(state.bId);
  const src = safeUrl(f.source_url);
  let ab = "–";
  if (a && b) {
    ab = `${fmtDuration(b.mjd - a.mjd)} apart, Δλ ${fmtNum(Math.abs(b.wavelength_um - a.wavelength_um), 3)} µm`;
    if (a.id !== b.id) ab += wavelengthMatched(a, b) ? " · wavelength-matched" : " · different wavelengths: stars may change brightness";
  }
  const rows = [
    ["Frame", f.id],
    ["Time", fmtTime(f.time_utc)],
    ["MJD", fmtNum(f.mjd, 5)],
    ["Epoch", String(f.epoch ?? "–")],
    ["Wavelength", `${fmtNum(f.wavelength_um, 3)} µm (at centre)`],
    ["Detector", f.detector == null ? "–" : `D${f.detector}`],
    ["Obs ID", f.obs_id ?? "–"],
    ["Source", src ? el("a", { href: src, target: "_blank", rel: "noopener" }, "FITS") : "–"],
    ["A ↔ B", ab],
  ];
  $("#frame-info").replaceChildren(...rows.flatMap(([k, v]) => [el("dt", {}, k), el("dd", {}, v)]));
}

function updateStageError() {
  const box = $("#stage-error");
  const broken = state.broken.has(state.shownId);
  box.hidden = !broken;
  if (broken) box.textContent = `Image for frame ${state.shownId} failed to load: ${frameById(state.shownId)?.image}`;
}

/** The single place that paints A, B, the shown frame and the filter into every view. */
function refreshMarks() {
  const f = frameById(state.shownId);
  if (!f) return;
  const slot = f.id === state.aId ? "A" : f.id === state.bId ? "B" : null;
  const label = $("#stage-label");
  label.className = `stage-label${slot ? ` is-${slot.toLowerCase()}` : ""}`;
  label.textContent = [slot, f.id, `epoch ${f.epoch}`, `${fmtNum(f.wavelength_um, 2)} µm`, fmtTime(f.time_utc)]
    .filter(Boolean)
    .join(" · ");
  $("#btn-a").classList.toggle("active", slot === "A");
  $("#btn-b").classList.toggle("active", slot === "B");

  for (const tr of document.querySelectorAll("#frame-table tbody tr")) {
    const id = tr.dataset.frame;
    tr.classList.toggle("shown", id === f.id);
    tr.hidden = !isVisibleId(id);
    tr.querySelector('input[name="slot-a"]').checked = id === state.aId;
    tr.querySelector('input[name="slot-b"]').checked = id === state.bId;
  }

  markTimeline($("#timeline"), {
    shownId: f.id, aId: state.aId, bId: state.bId, isVisible: isVisibleId, filter: state.filter,
  });

  const pairIndex = state.pairs.indexOf(pairOf(state.aId, state.bId));
  $("#pair-select").value = pairIndex >= 0 ? String(pairIndex) : "";

  const filtered = state.filter.min != null || state.filter.max != null || state.filter.detector != null;
  const n = visibleFrames().length;
  $("#filter-count").textContent = filtered ? `${n} of ${state.frames.length} frames` : "";
  $("#lam-reset").hidden = !filtered;
}

// ---------- state changes ----------

function show(id) {
  const f = frameById(id);
  if (!f) return;
  state.shownId = id;
  for (const [fid, img] of state.imgs) img.classList.toggle("shown", fid === id);
  refreshMarks();
  keepRowVisible(rowFor(id));
  renderFrameInfo(f);
  updateStageError();
  document.dispatchEvent(new CustomEvent("viewer:frame", { detail: { frameId: id } }));
}

// Scroll only the frame table's own box so the row is visible. Not scrollIntoView(): that also
// scrolls the page, and in the narrow layout (table under the image) it pulls the image out of view
// on every blink.
function keepRowVisible(row) {
  const box = row?.closest(".table-wrap");
  if (!box) return;
  const r = row.getBoundingClientRect();
  const b = box.getBoundingClientRect();
  const head = box.querySelector("thead")?.getBoundingClientRect().height ?? 0;
  if (r.top < b.top + head) box.scrollTop -= b.top + head - r.top;
  else if (r.bottom > b.bottom) box.scrollTop += r.bottom - b.bottom;
}

function setSlot(slot, id) {
  if (slot === "a") state.aId = id;
  else state.bId = id;
  if (!state.playing) show(id);
  else {
    refreshMarks();
    renderFrameInfo(frameById(state.shownId));
  }
}

function setPair(a, b) {
  state.aId = a;
  state.bId = b;
  if (!state.playing) show(a);
  else {
    refreshMarks();
    renderFrameInfo(frameById(state.shownId));
  }
}

/** B := the best frame from another epoch for the current A (pair partner or closest wavelength). */
function matchB() {
  const a = frameById(state.aId);
  const b = a && bestPartner(a, visibleFrames());
  if (b) setPair(a.id, b.id);
}

/** Apply new filter values; keep A, B and the shown frame inside the filter. */
function setFilter(patch) {
  const next = { ...state.filter, ...patch };
  // Typing one bound past the other clears the other one (no surprise swapping of both boxes).
  if (next.min != null && next.max != null && next.min > next.max) {
    if ("min" in patch) next.max = null;
    else next.min = null;
  }
  state.filter = next;
  $("#lam-min").value = next.min ?? "";
  $("#lam-max").value = next.max ?? "";
  $("#det-filter").value = next.detector == null ? "" : String(next.detector);

  const visible = visibleFrames();
  if (visible.length && (!isVisibleId(state.aId) || !isVisibleId(state.bId))) {
    const a = isVisibleId(state.aId) ? frameById(state.aId) : visible[0];
    const b = isVisibleId(state.bId) && state.bId !== a.id ? frameById(state.bId)
      : bestPartner(a, visible) ?? visible[visible.length - 1];
    state.aId = a.id;
    state.bId = b.id;
  }
  const target = isVisibleId(state.shownId) ? state.shownId : visible.length ? state.aId : state.shownId;
  show(target);
}

function flip() {
  show(state.shownId === state.aId ? state.bId : state.aId);
}

function startBlink() {
  if (state.playing || !state.target) return;
  state.playing = true;
  if (state.shownId !== state.aId && state.shownId !== state.bId) show(state.aId);
  state.timer = setInterval(flip, state.intervalMs);
  updatePlayButton();
  document.dispatchEvent(new CustomEvent("viewer:blink", { detail: { playing: true } }));
}

export function stopBlink() {
  const was = state.playing;
  state.playing = false;
  clearInterval(state.timer);
  state.timer = null;
  updatePlayButton();
  if (was) document.dispatchEvent(new CustomEvent("viewer:blink", { detail: { playing: false } }));
}

function updatePlayButton() {
  const btn = $("#btn-play");
  btn.setAttribute("aria-pressed", String(state.playing));
  btn.textContent = state.playing ? "❚❚ Pause" : "▶ Blink";
}

/** Step through the frames inside the filter. */
function step(delta) {
  stopBlink();
  const frames = visibleFrames();
  if (frames.length === 0) return;
  const i = frames.findIndex((f) => f.id === state.shownId);
  const next = i < 0 ? 0 : Math.min(frames.length - 1, Math.max(0, i + delta));
  show(frames[next].id);
}

// ---------- wiring ----------

const numberOrNull = (v) => (v === "" || !Number.isFinite(Number(v)) ? null : Number(v));

export function initViewer() {
  $("#btn-a").addEventListener("click", () => { stopBlink(); show(state.aId); });
  $("#btn-b").addEventListener("click", () => { stopBlink(); show(state.bId); });
  $("#btn-play").addEventListener("click", () => (state.playing ? stopBlink() : startBlink()));

  const speed = $("#speed");
  const onSpeed = () => {
    state.intervalMs = Number(speed.value);
    $("#speed-out").textContent = `${state.intervalMs} ms`;
    if (state.playing) {
      clearInterval(state.timer);
      state.timer = setInterval(flip, state.intervalMs);
    }
  };
  speed.addEventListener("input", onSpeed);
  onSpeed();

  $("#lam-min").addEventListener("change", (e) => setFilter({ min: numberOrNull(e.target.value) }));
  $("#lam-max").addEventListener("change", (e) => setFilter({ max: numberOrNull(e.target.value) }));
  $("#det-filter").addEventListener("change", (e) => setFilter({ detector: numberOrNull(e.target.value) }));
  $("#lam-reset").addEventListener("click", () => setFilter({ min: null, max: null, detector: null }));
  $("#btn-match").addEventListener("click", () => matchB());
  $("#pair-select").addEventListener("change", (e) => {
    const p = state.pairs[Number(e.target.value)];
    if (!p) return;
    if (!isVisibleId(p.a) || !isVisibleId(p.b)) setFilter({ min: null, max: null, detector: null });
    setPair(p.a, p.b);
  });

  // Redraw the timeline when its width changes (window resize, layout switch).
  let lastWidth = 0;
  new ResizeObserver(([entry]) => {
    const w = Math.round(entry.contentRect.width);
    if (!state.target || w === lastWidth) return;
    lastWidth = w;
    drawTimeline();
    refreshMarks();
  }).observe($("#timeline"));

  document.addEventListener("keydown", (e) => {
    if (!state.target || e.altKey || e.ctrlKey || e.metaKey || isTyping(e.target)) return;
    // Buttons keep Space (it clicks them); radios and the slider also keep the arrow keys.
    const control = e.target.closest?.("input, button");
    if (control && (e.key === " " || (e.key.startsWith("Arrow") && control.tagName === "INPUT"))) return;
    if (e.key === " ") { e.preventDefault(); state.playing ? stopBlink() : startBlink(); }
    else if (e.key === "x" || e.key === "X") { stopBlink(); flip(); }
    else if (e.key === "m" || e.key === "M") { matchB(); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); step(-1); }
    else if (e.key === "ArrowRight") { e.preventDefault(); step(1); }
  });
}

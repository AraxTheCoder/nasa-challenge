// Frame viewer: stacks all frames of one target and blinks between two (T11).
// Knows nothing about where target.json came from; app.js hands it the parsed JSON and its URL.

import { $, el, fmtDuration, fmtNum, fmtTime, isTyping, safeUrl } from "./util.js";

const SCHEMA_VERSIONS = ["0.1", "0.2"]; // target.json versions this viewer understands

const state = {
  target: null,
  base: null,        // absolute URL of the target folder (frame paths are relative to it)
  frames: [],        // sorted by mjd
  imgs: new Map(),   // frame id -> <img>
  broken: new Set(), // frame ids whose image failed to load
  aId: null,
  bId: null,
  shownId: null,
  playing: false,
  intervalMs: 500,
  timer: null,
};

export const currentTarget = () => state.target;
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
  state.broken = new Set();
  [state.aId, state.bId] = defaultPair(state.frames);

  renderTargetHead();
  renderStage();
  renderFrameTable();
  renderProvenance();
  show(state.aId);
  $("#empty").hidden = true;
  $("#viewer-body").hidden = false;
  $("#side").hidden = false;
}

/** Back to the empty state (no target shown). */
export function clearTarget() {
  stopBlink();
  state.target = null;
  state.frames = [];
  state.imgs = new Map();
  $("#frame-stack").replaceChildren();
  $("#overlay").replaceChildren();
  $("#synthetic-badge").hidden = true;
  $("#empty").hidden = false;
  $("#viewer-body").hidden = true;
  $("#side").hidden = true;
  document.title = "SPHEREx Blink";
}

// A = first frame; B = first frame of a later epoch, else the last frame.
function defaultPair(frames) {
  const a = frames[0];
  const b = frames.find((f) => f.epoch !== a.epoch) ?? frames[frames.length - 1];
  return [a.id, b.id];
}

const frameById = (id) => state.frames.find((f) => f.id === id);
const rowFor = (id) => document.querySelector(`#frame-table tr[data-frame="${CSS.escape(id)}"]`);

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
    const img = el("img", { src: new URL(f.image, state.base).href, alt: `Frame ${f.id}`, draggable: "false" });
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

function renderFrameTable() {
  const rows = state.frames.map((f) => {
    const radio = (slot) =>
      el("input", {
        type: "radio",
        name: `slot-${slot}`,
        value: f.id,
        "aria-label": `Use ${f.id} as ${slot.toUpperCase()}`,
        checked: (slot === "a" ? state.aId : state.bId) === f.id,
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
  const rows = [
    ["Frame", f.id],
    ["Time", fmtTime(f.time_utc)],
    ["MJD", fmtNum(f.mjd, 5)],
    ["Epoch", String(f.epoch ?? "–")],
    ["Wavelength", `${fmtNum(f.wavelength_um, 3)} µm (at centre)`],
    ["Detector", f.detector == null ? "–" : `D${f.detector}`],
    ["Obs ID", f.obs_id ?? "–"],
    ["Source", src ? el("a", { href: src, target: "_blank", rel: "noopener" }, "FITS") : "–"],
    ["A ↔ B", a && b ? `${fmtDuration(b.mjd - a.mjd)} apart, Δλ ${fmtNum(Math.abs(b.wavelength_um - a.wavelength_um), 3)} µm` : "–"],
  ];
  $("#frame-info").replaceChildren(...rows.flatMap(([k, v]) => [el("dt", {}, k), el("dd", {}, v)]));
}

function updateStageError() {
  const box = $("#stage-error");
  const broken = state.broken.has(state.shownId);
  box.hidden = !broken;
  if (broken) box.textContent = `Image for frame ${state.shownId} failed to load: ${frameById(state.shownId)?.image}`;
}

// ---------- state changes ----------

function show(id) {
  const f = frameById(id);
  if (!f) return;
  state.shownId = id;
  for (const [fid, img] of state.imgs) img.classList.toggle("shown", fid === id);

  const slot = id === state.aId ? "A" : id === state.bId ? "B" : null;
  const label = $("#stage-label");
  label.className = `stage-label${slot ? ` is-${slot.toLowerCase()}` : ""}`;
  label.textContent = [slot, f.id, `epoch ${f.epoch}`, `${fmtNum(f.wavelength_um, 2)} µm`, fmtTime(f.time_utc)]
    .filter(Boolean)
    .join(" · ");

  $("#btn-a").classList.toggle("active", slot === "A");
  $("#btn-b").classList.toggle("active", slot === "B");
  for (const tr of document.querySelectorAll("#frame-table tbody tr")) {
    tr.classList.toggle("shown", tr.dataset.frame === id);
  }
  keepRowVisible(rowFor(id));
  renderFrameInfo(f);
  updateStageError();
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
  else renderFrameInfo(frameById(state.shownId));
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
}

export function stopBlink() {
  state.playing = false;
  clearInterval(state.timer);
  state.timer = null;
  updatePlayButton();
}

function updatePlayButton() {
  const btn = $("#btn-play");
  btn.setAttribute("aria-pressed", String(state.playing));
  btn.textContent = state.playing ? "❚❚ Pause" : "▶ Blink";
}

function step(delta) {
  stopBlink();
  const i = state.frames.findIndex((f) => f.id === state.shownId);
  const next = Math.min(state.frames.length - 1, Math.max(0, i + delta));
  show(state.frames[next].id);
}

// ---------- wiring ----------

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

  document.addEventListener("keydown", (e) => {
    if (!state.target || e.altKey || e.ctrlKey || e.metaKey || isTyping(e.target)) return;
    // Buttons keep Space (it clicks them); radios and the slider also keep the arrow keys.
    const control = e.target.closest?.("input, button");
    if (control && (e.key === " " || (e.key.startsWith("Arrow") && control.tagName === "INPUT"))) return;
    if (e.key === " ") { e.preventDefault(); state.playing ? stopBlink() : startBlink(); }
    else if (e.key === "x" || e.key === "X") { stopBlink(); flip(); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); step(-1); }
    else if (e.key === "ArrowRight") { e.preventDefault(); step(1); }
  });
}

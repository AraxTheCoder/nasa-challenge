// SPHEREx Blink (T55 redesign, /app/): the sky map is the whole page. The Live API
// (docs/CONTRACTS.md v0.3) builds fields on request; their SPHEREx epochs then show as map layers
// (blinkable), with traces and names of the fields' objects drawn on the map.
// "Go" only moves the map to the typed RA/Dec and pins it. "Blink" covers what is on screen with
// fields from a fixed sky grid (fieldgrid.js), built in parallel and cached by the Live API, so
// coming back is instant; a view of at most one cell builds one field of the view's size instead.
// ?ra=&dec=&size= in the page URL goes there on load (+ &blink=1 blinks that view); ?api=<base> sets the API.
//
// Unlike web/ there is no frame viewer, analysis or side panel below the map, and no offline
// (?data=) mode, which only fed the frame viewer.

import { DEFAULT_API, ApiError, health, requestField } from "./api.js";
import { $, el, fmtElapsed } from "./util.js";
import * as explore from "./explore.js";
import "./traces.js";      // T35: paths + per-epoch positions of the fields' objects on the map
import "./skylabels.js";   // T72: catalogue names anywhere on the map
import { initHud } from "./hud.js";   // T55: drag the floating panels anywhere
import { parseDec, parseRa } from "./coords.js";
import { initCursorPin, isPicking, pinAt, setPicking } from "./cursorpin.js";   // T55: 📍 marker + pick mode
import { CELL_ARCMIN, cellsCovering } from "./fieldgrid.js";

const SIZE_MIN = 5;
const SIZE_MAX = 210;   // API limit = one SPHEREx detector (3.49 deg), server/coords.py
const SIZE_DEFAULT = 15;
const MAX_CELLS = 30;   // more grid fields than this: ask to zoom in (each is a full build)
const PARALLEL = 8;     // grid fields built at the same time (8 x 30' measured 2026-11-14: 103 s for all)

// Catalogue labels: default OFF in /app/ (web/ defaults on); the choice is remembered per browser
// under its own key, so switching it in /web/ (same origin) doesn't change /app/.
const LABELS_KEY = "spherex.app.labels";
function labelsPref() {
  try { return localStorage.getItem(LABELS_KEY) === "1"; } catch { return false; }
}

const app = {
  labelsOn: labelsPref(),
  api: DEFAULT_API,
  presets: [],
  loadToken: 0,      // bumps on every new blink; stale async results check it and bail out
  abort: null,
  jobStart: 0,
  jobTimer: null,
  cells: [],         // the blinked fields: [{key, ra, dec, size, state, id, url, target}]
  shownTarget: null, // all ready fields merged into one target (for traces.js / skylabels.js)
  epochs: [],        // epoch numbers with layers in any field
  epochShown: null,
  epochSynthetic: false,
};

const params = () => new URLSearchParams(location.search);
const clampSize = (n) => Math.min(SIZE_MAX, Math.max(SIZE_MIN, Math.round(n)));

// ---------- messages ----------

function showMessage(text, kind = "error") {
  $("#messages").append(el("div", { class: `msg msg-${kind}` }, text));
}

function clearMessages() {
  $("#messages").replaceChildren();
}

function showLoadError(err) {
  if (!(err instanceof ApiError)) return showMessage(err.message);
  if (err.kind === "unreachable") {
    showMessage(`${err.message} Start it with "python web/dev.py" (see web/README.md), or open this page with ?api=<url>.`);
  } else if (err.kind === "bad_request") {
    showMessage(`Can't use these coordinates: ${err.message}`);
  } else if (err.kind === "no_data") {
    showMessage(`No SPHEREx images here: ${err.message}`, "warn");
  } else {
    showMessage(`Building the fields failed: ${err.message}`);
  }
}

// ---------- the shown fields ----------

/** Hand the fields to the map overlays (traces.js, skylabels.js); labels only while switched on. */
function publishTarget(target) {
  const shown = target && !app.labelsOn ? { ...target, labels: [] } : target;
  $("#synthetic-badge").hidden = !target || target.synthetic === false;   // missing flag counts as synthetic
  document.title = target ? `${target.name ?? target.id} · SPHEREx Blink` : "SPHEREx Blink";
  document.dispatchEvent(new CustomEvent("viewer:target", { detail: { target: shown } }));
}

/**
 * Several fields as one target for the overlays: frames, labels, known objects and detections of
 * all of them, frame ids prefixed per field (each field numbers its frames from f000).
 */
function mergeTargets(ts) {
  if (ts.length <= 1) return ts[0] ?? null;
  const pre = (k) => (id) => `${k}:${id}`;
  const posMap = (p, k) => (p ?? []).map((x) => ({ ...x, frame_id: pre(k)(x.frame_id) }));
  const out = {
    id: ts.map((t) => t.id).join("+"), name: `${ts.length} fields`, schema_version: ts[0].schema_version,
    synthetic: ts.some((t) => t.synthetic !== false), center: ts[0].center, size_arcmin: ts[0].size_arcmin,
    labels_requested: ts.every((t) => t.labels_requested), objects_requested: ts.every((t) => t.objects_requested),
    frames: [], labels: [], known_objects: [], detections: [],
  };
  ts.forEach((t, k) => {
    out.frames.push(...(t.frames ?? []).map((f) => ({ ...f, id: pre(k)(f.id) })));
    out.labels.push(...(t.labels ?? []).map((l) => ({ ...l, positions: posMap(l.positions, k) })));
    out.known_objects.push(...(t.known_objects ?? []).map((o) => ({ ...o, positions: posMap(o.positions, k) })));
    out.detections.push(...(t.detections ?? []).map((d) => ({ ...d, id: pre(k)(d.id), track: posMap(d.track, k) })));
  });
  return out;
}

function publishCells() {
  const ready = app.cells.filter((c) => c.state === "ready" && c.target);
  app.shownTarget = mergeTargets(ready.map((c) => c.target));
  publishTarget(app.shownTarget);
}

/** Light checks only; the full schema is docs/target.schema.json and is enforced upstream. */
function checkTarget(t, expectedId) {
  if (!t || !Array.isArray(t.frames) || t.frames.length === 0) {
    throw new Error(`target "${expectedId ?? t?.id}" has no frames`);
  }
}

// ---------- loading ----------

/** Start a new blink: cancels the previous one. Returns its token + abort signal. */
function beginLoad() {
  app.abort?.abort();
  app.abort = new AbortController();
  clearMessages();
  return { token: ++app.loadToken, signal: app.abort.signal };
}

async function fetchJson(url, signal) {
  const res = await fetch(url, { signal, cache: "no-cache" });
  if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
  return res.json();
}

function readForm() {
  const f = $("#field-form");
  return { ra: f.ra.value.trim(), dec: f.dec.value.trim() };
}

function fillForm(req) {
  const f = $("#field-form");
  f.ra.value = req.ra;
  f.dec.value = req.dec;
  syncPresetSelect();
}

/** Show the matching test field in the dropdown, or none once the user typed other coordinates. */
function syncPresetSelect() {
  const { ra, dec } = readForm();
  const i = app.presets.findIndex((p) => String(p.ra_deg) === ra && String(p.dec_deg) === dec);
  $("#preset").value = i >= 0 ? String(i) : "";
}

const presetRequest = (f) => ({ ra: String(f.ra_deg), dec: String(f.dec_deg), size: clampSize(f.size_arcmin ?? SIZE_DEFAULT) });
const defaultPreset = () => app.presets.find((p) => p.default) ?? app.presets[0] ?? null;

/** Pre-fill the form with the default test field (no request; the user presses Go). */
function fillDefaults() {
  const f = defaultPreset();
  if (f) fillForm(presetRequest(f));
}

/** ?ra=&dec= after Go; after Blink also &size= (the view's longer side) and &blink=1, so a reload or link blinks it again. */
function setPageUrl(req, push, blink = false) {
  const url = new URL(location.href);
  url.searchParams.set("ra", req.ra);
  url.searchParams.set("dec", req.dec);
  if (blink) {
    url.searchParams.set("size", String(req.size));
    url.searchParams.set("blink", "1");
  } else {
    url.searchParams.delete("size");
    url.searchParams.delete("blink");
  }
  if (url.href === location.href) return;
  if (push) history.pushState(null, "", url);
  else history.replaceState(null, "", url);
}

/** Do what the page URL asks for: go to ?ra=&dec= (and blink a view &size= wide if &blink=1). False if nothing. */
function loadFromUrl() {
  const p = params();
  const ra = p.get("ra")?.trim();
  const dec = p.get("dec")?.trim();
  if (!ra || !dec) return false;
  const req = { ra, dec, size: clampSize(Number(p.get("size")) || SIZE_DEFAULT) };
  fillForm(req);
  const blink = p.get("blink") === "1";
  app.blinkAfterGo = blink;                       // showGoal starts the blink once the view is there
  goTo(req, blink ? { fovDeg: req.size / 60 } : {});
  return true;
}

// ---------- T55 "Go": centre the position, zoomed all the way in, 📍 on it (no build) ----------

const GO_ORDER = 7;            // deepest live HiPS order (3.2″ texels): Go zooms to where it is sharp

/**
 * Go to req (as typed): centred and zoomed in to order 7 (opts.fovDeg overrides the zoom). The
 * 📍 with its RA/Dec stands on the position (it moves with the map) and fades out after 5 s.
 */
function goTo(req, opts = {}) {
  let ra, dec;
  try {
    ra = parseRa(req.ra);
    dec = parseDec(req.dec);
  } catch (err) {
    clearMessages();
    showMessage(`Can't use these coordinates: ${err.message}`);
    return false;
  }
  clearMessages();
  app.goal = { ra, dec, fovDeg: opts.fovDeg ?? null };
  app.goalPending = !explore.getSky();                   // then startExplore shows it once the map is up
  if (!app.goalPending) showGoal();
  return true;
}

function showGoal() {
  const g = app.goal;
  if (!g) return;
  explore.goTo(g.ra, g.dec, g.fovDeg ?? explore.fovForOrder(GO_ORDER) ?? undefined);
  pinAt(g.ra, g.dec);                                     // 📍 + RA/Dec on the position, fades after 5 s
  if (app.blinkAfterGo) { app.blinkAfterGo = false; startBlink({ push: false }); }
}

/** 📍 button: pick a position on the map. The picked spot goes into the form and the URL (like Go). */
function onPicked(ra, dec) {
  const req = { ra: ra.toFixed(4), dec: dec.toFixed(4) };
  fillForm(req);
  setPageUrl(req, true);
}

// ---------- T55 "Blink": cover the screen with grid fields, build them in parallel ----------

/** The fields Blink would build for the current view: grid cells, or one field for a small view. */
function blinkPlan() {
  const v = explore.view();
  if (!v) return null;
  const long = Math.max(v.fovArcmin, v.heightArcmin);
  const cells = long <= CELL_ARCMIN
    ? [{ key: "view", ra: v.ra, dec: v.dec, size: clampSize(Math.ceil(long)) }]
    : cellsCovering(explore.viewSamples(), [v.ra, v.dec]);
  return { v, long, cells };
}

function startBlink({ push = true } = {}) {
  const plan = blinkPlan();
  if (!plan) return;
  const { v, long, cells } = plan;
  if (cells.length > MAX_CELLS) {
    clearMessages();
    showMessage(`The view needs ${cells.length} fields; zoom in to at most ${MAX_CELLS} and Blink again.`, "warn");
    return;
  }
  const req = { ra: v.ra.toFixed(4), dec: v.dec.toFixed(4), size: clampSize(Math.ceil(long)) };
  fillForm(req);
  setPageUrl(req, push, true);
  runBlink(cells, req);
}

async function runBlink(cells, req) {
  const { token, signal } = beginLoad();
  resetFields();
  app.cells = cells.map((c) => ({ ...c, state: "building" }));
  explore.setOutlines(app.cells);                       // dashed right away: you can move off and find them again
  let done = 0, empty = 0, firstError = null;
  const progress = () => showJob(req, { done, total: app.cells.length,
    message: `${done - empty} ready${empty ? `, ${empty} without SPHEREx data` : ""}` });
  progress();
  const queue = [...app.cells];
  const worker = async () => {
    for (let c = queue.shift(); c; c = queue.shift()) {
      try {
        const { id, targetUrl } = await requestField(app.api,
          { ra: c.ra.toFixed(4), dec: c.dec.toFixed(4), size: c.size }, { signal });
        const target = await fetchJson(targetUrl, signal);
        if (token !== app.loadToken) return;
        checkTarget(target, id);
        Object.assign(c, { state: "ready", id, url: targetUrl, target });
        cellReady(c, token);
      } catch (err) {
        if (err.name === "AbortError" || token !== app.loadToken) return;
        c.state = "empty";
        empty++;
        if (!(err instanceof ApiError && err.kind === "no_data")) firstError ??= err;
      }
      done++;
      explore.setOutlines(app.cells);
      progress();
    }
  };
  await Promise.all(Array.from({ length: Math.min(PARALLEL, app.cells.length) }, worker));
  if (token !== app.loadToken) return;
  hideJob();
  if (firstError) showLoadError(firstError);
  else if (empty === app.cells.length) showMessage("No SPHEREx images here.", "warn");
}

/** Forget the blinked fields (outlines, epoch layers, overlays). */
function resetFields() {
  app.cells = [];
  app.epochs = [];
  app.epochShown = null;
  app.epochSynthetic = false;
  clearInterval(epochTimer);
  epochTimer = null;
  explore.setOutlines([]);
  explore.clearEpochs();
  renderEpochs();
  publishCells();
  $("#objects-note").textContent = "";
  $("#labels-note").textContent = "";
}

/** A field is built: its epochs join the map layers, its objects the traces. */
function cellReady(c, token) {
  explore.setOutlines(app.cells);
  publishCells();
  addEpochLayers(c, token);
  if (app.labelsOn && !c.target.labels_requested) requestExtra(c, "labels", token);
  if (!c.target.synthetic && !c.target.objects_requested) requestExtra(c, "objects", token);
}

// ---------- epochs: one button per epoch number, shown in every field at once ----------

let epochTimer = null;

async function addEpochLayers(c, token) {
  let info;
  try {
    const res = await fetch(`${app.api}/api/hips/${encodeURIComponent(c.id)}`);
    if (!res.ok) return;
    info = await res.json();
  } catch { return; }
  if (token !== app.loadToken || !info.layers?.length) return;
  const added = await explore.addEpochLayers(info.layers.map((l) => ({ ...l, cell: c.key, url: new URL(l.url, app.api).href })));
  if (token !== app.loadToken || !added.length) return;
  app.epochSynthetic ||= Boolean(info.synthetic);
  app.epochs = [...new Set([...app.epochs, ...added.map((l) => l.epoch)])].sort((a, b) => a - b);
  if (app.epochShown == null) app.epochShown = app.epochs[0];
  renderEpochs();
  explore.showEpoch(app.epochShown);
}

function pickEpoch(e) {
  app.epochShown = e;
  explore.showEpoch(e);
  for (const b of $("#explore-epochs").querySelectorAll("button[data-epoch]")) {
    b.setAttribute("aria-pressed", String(Number(b.dataset.epoch) === e));
  }
}

function renderEpochs() {
  const box = $("#explore-epochs");
  const blinking = Boolean(epochTimer);
  box.replaceChildren();
  box.hidden = !app.epochs.length;
  if (!app.epochs.length) return;
  const buttons = app.epochs.map((e) => el("button", { type: "button", class: "link", "data-epoch": String(e),
    "aria-pressed": String(e === app.epochShown), onclick: () => pickEpoch(e) }, `Ep. ${e}`));
  const blink = el("button", { type: "button", class: "link", "aria-pressed": String(blinking),
    title: "Flip through the epochs in the map" }, blinking ? "❚❚ Stop" : "▶ Blink epochs");
  blink.addEventListener("click", () => {
    const on = !epochTimer;
    clearInterval(epochTimer);
    epochTimer = null;
    if (on) {
      epochTimer = setInterval(() => {
        const i = app.epochs.indexOf(app.epochShown);
        pickEpoch(app.epochs[(i + 1) % app.epochs.length]);
      }, 700);
    }
    renderEpochs();
  });
  // no caption for real data; synthetic layers stay visibly labelled (CLAUDE.md)
  box.append(...(app.epochSynthetic ? [el("span", { class: "muted small" }, "synthetic:")] : []), ...buttons, blink);
}

// ---------- labels and known objects: asked per field, merged when they arrive ----------

/** kind "labels" (T37, SIMBAD + Gaia) or "objects" (T51, known asteroids/comets): poll, then reload the field. */
async function requestExtra(c, kind, token) {
  const flag = `${kind}Pending`;
  if (c[flag]) return;
  c[flag] = true;
  updateNotes();
  try {
    for (let i = 0; i < (kind === "labels" ? 120 : 360); i++) {
      const res = await fetch(`${app.api}/api/targets/${encodeURIComponent(c.id)}/${kind}`);
      const body = await res.json();
      if (token !== app.loadToken) return;
      if (body.status === "ready") break;
      if (body.status !== "building") throw new Error(body.message ?? `HTTP ${res.status}`);
      await new Promise((r) => setTimeout(r, kind === "labels" ? 1500 : 5000));
    }
    const fresh = await fetchJson(c.url);
    if (token !== app.loadToken) return;
    c.target = fresh;
    publishCells();
  } catch (err) {
    if (token === app.loadToken && kind === "labels") showMessage(`Labels unavailable: ${err.message}`, "warn");
  } finally {
    c[flag] = false;
    if (token === app.loadToken) updateNotes();
  }
}

function updateNotes() {
  const ready = app.cells.filter((c) => c.state === "ready");
  const labelsBusy = ready.some((c) => c.labelsPending);
  $("#labels-note").textContent = !app.labelsOn || !ready.length ? ""
    : labelsBusy ? "asking SIMBAD + Gaia…" : `${app.shownTarget?.labels?.length ?? 0}`;
  $("#objects-note").textContent = ready.some((c) => c.objectsPending) ? "looking up known asteroids and comets…" : "";
}

async function setLabels(on) {
  app.labelsOn = on;
  try { localStorage.setItem(LABELS_KEY, on ? "1" : "0"); } catch { /* private mode: not remembered */ }
  $("#labels-toggle").checked = on;
  document.dispatchEvent(new CustomEvent("labels:changed", { detail: { on } }));  // skylabels.js follows
  publishCells();
  if (on) for (const c of app.cells) if (c.state === "ready" && !c.target.labels_requested) requestExtra(c, "labels", app.loadToken);
  updateNotes();
}

// ---------- progress ----------

function showJob(req, progress = {}) {
  const job = $("#job");
  if (job.hidden) {
    job.hidden = false;
    app.jobStart = Date.now();
    clearInterval(app.jobTimer);
    app.jobTimer = setInterval(tickJob, 1000);
    tickJob();
  }
  const n = progress.total;
  $("#job-title").textContent = n > 1 ? `Building the ${n} fields on screen…` : "Building the field…";
  const bar = $("#job-progress");
  bar.max = Math.max(1, n);
  bar.value = progress.done;
  $("#job-message").textContent = [`RA ${req.ra}, Dec ${req.dec}, ${req.size}′ view`, `${progress.done} / ${n}`,
    progress.message].filter(Boolean).join(" · ");
}

function tickJob() {
  $("#job-elapsed").textContent = fmtElapsed(Date.now() - app.jobStart);
}

function hideJob() {
  $("#job").hidden = true;
  clearInterval(app.jobTimer);
  app.jobTimer = null;
}

async function loadPresets() {
  let fields = [];
  try {
    fields = (await fetchJson("presets.json")).fields ?? [];
  } catch {
    return; // quick picks are optional
  }
  app.presets = fields;
  const select = $("#preset");
  select.append(...fields.map((f, i) => el("option", { value: String(i), title: f.kind ?? "" }, f.name)));
  select.hidden = fields.length === 0;
}

function onPresetPicked() {
  const f = app.presets[Number($("#preset").value)];
  if (!f) return;
  const req = presetRequest(f);
  fillForm(req);
  if (goTo(req)) setPageUrl(req, true);   // like Go: jump + pin; Blink builds it
}

async function warnIfApiDown(fieldRequested) {
  if (fieldRequested || await health(app.api)) return;   // a requested field reports its own error
  showMessage(`The Live API at ${app.api} is not reachable. Start it with "python web/dev.py" (see web/README.md), or open this page with ?api=<url>.`, "warn");
}

// ---------- wiring ----------

function bindPage() {
  $("#field-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const req = readForm();
    if (!req.ra || !req.dec) return;
    fillForm(req);
    if (goTo(req)) setPageUrl(req, true);   // Go: jump + pin only; Blink builds the fields
  });
  $("#preset").addEventListener("change", onPresetPicked);
  $("#field-form").addEventListener("input", (e) => {
    if (e.target.name === "ra" || e.target.name === "dec") syncPresetSelect();
  });

  $("#job-cancel").addEventListener("click", () => {
    app.abort?.abort();
    hideJob();
    showMessage("Stopped waiting. The server keeps building these fields; Blink here again later and they come from the cache.", "warn");
  });

  window.addEventListener("popstate", () => {
    if (loadFromUrl()) return;
    app.abort?.abort();
    hideJob();
    clearMessages();
    resetFields();
    fillDefaults();
  });
}

// ---------- sky map (T30/T36) ----------

/** How much the map shows, and what Blink would build for it (the mouse position is in the 📍 pill). */
function updateExplorePos() {
  const plan = blinkPlan();
  if (!plan) return;
  const { v, cells } = plan;
  const arc = (a) => (a >= 120 ? `${(a / 60).toFixed(1)}°` : `${Math.round(a)}′`);
  const what = cells.length === 1 && cells[0].key === "view" ? `1 field of ${cells[0].size}′`
    : cells.length > MAX_CELLS ? `${cells.length} fields: zoom in` : `${cells.length} fields`;
  $("#explore-pos").textContent = `view ${arc(v.fovArcmin)} × ${arc(v.heightArcmin)} · Blink: ${what}`;
}

function setupBand(layer) {
  const box = $("#explore-band-box");
  const waves = explore.bandWavelengths();
  box.hidden = !(layer?.depth > 1);
  if (box.hidden) return;
  const input = $("#explore-band");
  input.max = String(layer.depth - 1);
  input.value = String(layer.slice);
  const show = () => {
    const w = waves[Number(input.value)];
    $("#explore-band-out").textContent = Number.isFinite(w) ? `${w.toFixed(3)} µm` : `#${input.value}`;
  };
  input.oninput = () => { explore.setBand(Number(input.value)); show(); };
  show();
}

async function startExplore() {
  $("#explore-blink").addEventListener("click", () => startBlink());
  const f = readForm();
  let start = {};
  try { start = { ra: parseRa(f.ra), dec: parseDec(f.dec) }; } catch { /* empty or odd form: default view */ }
  try {
    const sky = await explore.initExplore($("#sky"), {
      ra: start.ra, dec: start.dec, fovDeg: 2, api: app.api,
    });
    sky.on("change", updateExplorePos);
    // Debug overlay (tile outlines, max-zoom / sharp indicator): on by default in /app/; ?debug=0 starts it off
    const dbg = $("#sky-debug");
    dbg.checked = params().get("debug") !== "0";
    explore.setDebug(dbg.checked);
    dbg.addEventListener("change", () => explore.setDebug(dbg.checked));
    setupTilesSwitch();
    setupBand(sky.base);
    if (app.goalPending) { app.goalPending = false; showGoal(); }   // Go asked before the map existed
    updateExplorePos();
  } catch (err) {
    showMessage(`Sky map unavailable: ${err.message}`, "warn");
  }
}

// ---------- T47: live tiles from here or from the US VM next to the S3 bucket ----------

async function setupTilesSwitch() {
  let info;
  try { info = await (await fetch(`${app.api}/api/settings`)).json(); } catch { return; }
  if (!info.remote_available) return;
  const box = $("#tiles-box"), mode = $("#tiles-mode");
  box.hidden = false;
  mode.value = info.tiles;
  mode.title = `remote: ${info.remote_url}`;
  mode.addEventListener("change", async () => {
    try {
      const res = await fetch(`${app.api}/api/settings`, { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tiles: mode.value }) });
      const now = await res.json();
      if (!res.ok) throw new Error(now.error ?? `HTTP ${res.status}`);
      mode.value = now.tiles;
      setupBand(await explore.setSurvey(explore.DEFAULT_SURVEY));   // fresh layer: re-asks failed tiles
    } catch (err) {
      showMessage(`Could not switch tiles: ${err.message}`, "warn");
    }
  });
}

async function main() {
  // T40: the Labels switch; other modules can flip it with "labels:set" and follow "labels:changed".
  $("#labels-toggle").checked = app.labelsOn;
  $("#labels-toggle").addEventListener("change", (e) => setLabels(e.target.checked));
  document.addEventListener("labels:set", (e) => setLabels(Boolean(e.detail?.on)));
  queueMicrotask(() => document.dispatchEvent(new CustomEvent("labels:changed", { detail: { on: app.labelsOn } })));
  bindPage();
  initHud();
  const pinBtn = $("#pin-btn");
  initCursorPin({
    onPick: onPicked,
    onModeChange: (mode) => pinBtn.setAttribute("aria-pressed", String(mode === "pick")),
  });
  pinBtn.addEventListener("click", () => setPicking(!isPicking()));
  const p = params();
  if (p.get("api")) app.api = p.get("api");
  await loadPresets();
  startExplore();   // not awaited: the map loads in the background
  if (!loadFromUrl()) fillDefaults();
  await warnIfApiDown(p.get("blink") === "1");   // a Go needs no API; a build reports its own error
}

main();

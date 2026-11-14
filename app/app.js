// SPHEREx Blink (T55 redesign, /app/): the sky map is the whole page. The Live API
// (docs/CONTRACTS.md v0.3) builds any RA/Dec field on request; its SPHEREx epochs then show as map
// layers (blinkable), with traces and names of the field's objects drawn on the map.
// ?ra=&dec=&size= in the page URL requests that field on load; ?api=<base> sets the API address.
//
// Unlike web/ there is no frame viewer, analysis or side panel below the map, and no offline
// (?data=) mode, which only fed the frame viewer.

import { DEFAULT_API, ApiError, health, requestField } from "./api.js";
import { $, el, fmtElapsed } from "./util.js";
import * as explore from "./explore.js";
import "./traces.js";      // T35: paths + per-epoch positions of the field's objects on the map
import "./skylabels.js";   // T72: catalogue names anywhere on the map
import { initHud } from "./hud.js";   // T55: drag the floating panels anywhere

const SIZE_MIN = 5;
const SIZE_MAX = 60;
const SIZE_DEFAULT = 15;
const STEP_LABELS = {
  query: "Searching IRSA for SPHEREx images",
  download: "Downloading cutouts",
  align: "Aligning frames",
  render: "Rendering frames",
  detect: "Looking for moving sources",
};

// Catalogue labels: default OFF in /app/ (web/ defaults on); the choice is remembered per browser
// under its own key, so switching it in /web/ (same origin) doesn't change /app/.
const LABELS_KEY = "spherex.app.labels";
function labelsPref() {
  try { return localStorage.getItem(LABELS_KEY) === "1"; } catch { return false; }
}

const app = {
  labelsOn: labelsPref(),
  api: DEFAULT_API,
  request: null,     // last {ra, dec, size} asked for
  presets: [],
  loadToken: 0,      // bumps on every new load; stale async results check it and bail out
  abort: null,
  jobStart: 0,
  jobTimer: null,
  shownTarget: null,
  shownTargetUrl: null,
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
    showMessage(`Building the field failed: ${err.message}`);
  }
}

// ---------- the shown field ----------

/** Hand the field to the map overlays (traces.js, skylabels.js); labels only while switched on. */
function publishTarget(target) {
  const shown = target && !app.labelsOn ? { ...target, labels: [] } : target;
  $("#synthetic-badge").hidden = !target || target.synthetic === false;   // missing flag counts as synthetic
  document.title = target ? `${target.name ?? target.id} · SPHEREx Blink` : "SPHEREx Blink";
  document.dispatchEvent(new CustomEvent("viewer:target", { detail: { target: shown } }));
}

/** Light checks only; the full schema is docs/target.schema.json and is enforced upstream. */
function checkTarget(t, expectedId) {
  if (!t || !Array.isArray(t.frames) || t.frames.length === 0) {
    throw new Error(`target "${expectedId ?? t?.id}" has no frames`);
  }
  const warnings = [];
  if (expectedId && t.id !== expectedId) warnings.push(`target.json id "${t.id}" differs from "${expectedId}".`);
  if (typeof t.synthetic !== "boolean") warnings.push("target.json has no synthetic flag; treating it as synthetic.");
  return warnings;
}

// ---------- loading ----------

/** Start a new load: cancels the previous one. Returns its token + abort signal. */
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

async function openTarget(targetUrl, expectedId, token, signal) {
  const target = await fetchJson(targetUrl, signal);
  if (token !== app.loadToken) return;
  const warnings = checkTarget(target, expectedId);
  app.shownTargetUrl = targetUrl;
  syncExplore(target);
  publishTarget(target);
  if (app.labelsOn && !target.labels_requested) setLabels(true);
  loadObjects(target);
  warnings.forEach((w) => showMessage(w, "warn"));
}

function readForm() {
  const f = $("#field-form");
  return { ra: f.ra.value.trim(), dec: f.dec.value.trim(), size: clampSize(Number(f.size.value) || SIZE_DEFAULT) };
}

function fillForm(req) {
  const f = $("#field-form");
  f.ra.value = req.ra;
  f.dec.value = req.dec;
  f.size.value = String(req.size);
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

/** Pre-fill the form with the default test field (no request; the user presses Show). */
function fillDefaults() {
  const f = defaultPreset();
  if (f) fillForm(presetRequest(f));
}

function setPageUrl(req, push) {
  const url = new URL(location.href);
  url.searchParams.set("ra", req.ra);
  url.searchParams.set("dec", req.dec);
  url.searchParams.set("size", String(req.size));
  if (url.href === location.href) return;
  if (push) history.pushState(null, "", url);
  else history.replaceState(null, "", url);
}

/** Request what the page URL asks for (?ra=&dec=&size=). Returns false if it asks for nothing. */
function loadFromUrl() {
  const p = params();
  const ra = p.get("ra")?.trim();
  const dec = p.get("dec")?.trim();
  if (!ra || !dec) return false;
  const req = { ra, dec, size: clampSize(Number(p.get("size")) || SIZE_DEFAULT) };
  fillForm(req);
  loadField(req);
  return true;
}

async function loadField(req) {
  const { token, signal } = beginLoad();
  app.request = req;
  try {
    const onProgress = (progress, id) => { if (token === app.loadToken) showJob(req, progress, id); };
    const { id, targetUrl } = await requestField(app.api, req, { onProgress, signal });
    if (token !== app.loadToken) return;
    await openTarget(targetUrl, id, token, signal);
  } catch (err) {
    if (err.name === "AbortError" || token !== app.loadToken) return;
    showLoadError(err);
  } finally {
    if (token === app.loadToken) hideJob();
  }
}

function showJob(req, progress = {}, id = null) {
  const job = $("#job");
  if (job.hidden) {
    job.hidden = false;
    app.jobStart = Date.now();
    clearInterval(app.jobTimer);
    app.jobTimer = setInterval(tickJob, 1000);
    tickJob();
  }
  $("#job-title").textContent = `${STEP_LABELS[progress.step] ?? "Building field"}…`;
  const bar = $("#job-progress");
  const counted = Number.isFinite(progress.done) && Number.isFinite(progress.total) && progress.total > 0;
  if (counted) {
    bar.max = progress.total;
    bar.value = progress.done;
  } else {
    bar.removeAttribute("value"); // indeterminate
  }
  $("#job-message").textContent = [
    `RA ${req.ra}, Dec ${req.dec}, ${req.size}′`,
    counted ? `${progress.done} / ${progress.total}` : null,
    progress.message,
    id,
  ].filter(Boolean).join(" · ");
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
  setPageUrl(req, true);
  loadField(req);
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
    setPageUrl(req, true);
    loadField(req);
  });
  $("#preset").addEventListener("change", onPresetPicked);
  $("#field-form").addEventListener("input", (e) => {
    if (e.target.name === "ra" || e.target.name === "dec") syncPresetSelect();
  });

  $("#job-cancel").addEventListener("click", () => {
    app.abort?.abort();
    hideJob();
    showMessage("Stopped waiting. The server keeps building this field; ask again later and it comes from the cache.", "warn");
  });

  window.addEventListener("popstate", () => {
    if (loadFromUrl()) return;
    app.abort?.abort();
    hideJob();
    clearMessages();
    app.shownTarget = null;
    app.shownTargetUrl = null;
    publishTarget(null);
    fillDefaults();
  });
}

// ---------- sky map (T30/T36) ----------

function syncExplore(target) {
  app.shownTarget = target;
  const c = target?.center;
  if (!c) return;
  explore.goTo(c.ra_deg, c.dec_deg, Math.max(0.25, (target.size_arcmin * 3) / 60));
  explore.markField(c.ra_deg, c.dec_deg, target.size_arcmin);
  showEpochLayers(target);
}

// T32: the field's epochs as map layers, with buttons + blink, so epochs can be compared in the map.
let epochTimer = null;
let epochShown = 0;

async function showEpochLayers(target) {
  const box = $("#explore-epochs");
  clearInterval(epochTimer);
  box.replaceChildren();
  box.hidden = true;
  let info;
  try {
    const res = await fetch(`${app.api}/api/hips/${encodeURIComponent(target.id)}`);
    if (!res.ok) return;
    info = await res.json();
  } catch { return; }
  if (app.shownTarget !== target || !info.layers?.length) return;
  const layers = await explore.setEpochLayers(info.layers.map((l) => ({ ...l, url: new URL(l.url, app.api).href })));
  if (!layers.length || app.shownTarget !== target) return;
  const buttons = layers.map((l, i) => el("button", { type: "button", class: "link", title: l.label,
    "aria-pressed": String(i === 0) }, `Ep. ${l.epoch}`));
  const pick = (i) => {
    epochShown = i;
    explore.showEpoch(i);
    buttons.forEach((b, j) => b.setAttribute("aria-pressed", String(j === i)));
  };
  buttons.forEach((b, i) => b.addEventListener("click", () => pick(i)));
  const blink = el("button", { type: "button", class: "link", "aria-pressed": "false",
    title: "Flip through the epochs in the map" }, "▶ Blink epochs");
  blink.addEventListener("click", () => {
    const on = blink.getAttribute("aria-pressed") !== "true";
    blink.setAttribute("aria-pressed", String(on));
    blink.textContent = on ? "❚❚ Stop" : "▶ Blink epochs";
    clearInterval(epochTimer);
    if (on) epochTimer = setInterval(() => pick((epochShown + 1) % layers.length), 700);
  });
  // no caption for real data; synthetic layers stay visibly labelled (CLAUDE.md)
  box.append(...(info.synthetic ? [el("span", { class: "muted small" }, "synthetic:")] : []), ...buttons, blink);
  box.hidden = false;
  pick(0);
}

function updateExplorePos(_view, cursor) {
  const v = explore.view();
  if (!v) return;
  const f = (x) => `${x >= 0 ? "+" : ""}${x.toFixed(4)}°`;
  const where = cursor ? `RA ${cursor[0].toFixed(4)}° Dec ${f(cursor[1])}` : `RA ${v.ra.toFixed(4)}° Dec ${f(v.dec)}`;
  $("#explore-pos").textContent = `${where} · view ${v.fovArcmin >= 120 ? (v.fovArcmin / 60).toFixed(1) + "°" : Math.round(v.fovArcmin) + "′"}`;
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
  $("#explore-blink").addEventListener("click", () => {
    const v = explore.view();
    if (!v) return;
    const req = { ra: v.ra.toFixed(4), dec: v.dec.toFixed(4), size: clampSize(v.fovArcmin / 3) };
    fillForm(req);
    setPageUrl(req, true);
    loadField(req);
  });
  const f = readForm();
  try {
    const sky = await explore.initExplore($("#sky"), {
      ra: Number(f.ra) || undefined, dec: Number(f.dec) || undefined, fovDeg: 2, api: app.api,
    });
    sky.on("change", updateExplorePos);
    // Debug overlay (tile outlines, max-zoom / sharp indicator): on by default in /app/; ?debug=0 starts it off
    const dbg = $("#sky-debug");
    dbg.checked = params().get("debug") !== "0";
    explore.setDebug(dbg.checked);
    dbg.addEventListener("change", () => explore.setDebug(dbg.checked));
    setupTilesSwitch();
    setupBand(sky.base);
    if (app.shownTarget) syncExplore(app.shownTarget);   // a field loaded before the map was ready
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

// ---------- T37: catalogue labels only on request ----------

async function setLabels(on) {
  app.labelsOn = on;
  try { localStorage.setItem(LABELS_KEY, on ? "1" : "0"); } catch { /* private mode: not remembered */ }
  $("#labels-toggle").checked = on;
  document.dispatchEvent(new CustomEvent("labels:changed", { detail: { on } }));  // skylabels.js follows
  const t = app.shownTarget;
  const note = $("#labels-note");
  note.textContent = "";
  if (!t || !app.shownTargetUrl) return;
  if (!on || t.labels_requested) {
    publishTarget(t);
    if (on) note.textContent = `${t.labels?.length ?? 0}`;
    return;
  }
  const id = t.id;
  note.textContent = "asking SIMBAD + Gaia…";
  try {
    for (let i = 0; i < 120; i++) {
      const res = await fetch(`${app.api}/api/targets/${encodeURIComponent(id)}/labels`);
      const body = await res.json();
      if (app.shownTarget?.id !== id || !app.labelsOn) return;
      if (body.status === "ready") break;
      if (body.status !== "building") throw new Error(body.message ?? `HTTP ${res.status}`);
      await new Promise((r) => setTimeout(r, 1500));
    }
    const fresh = await fetchJson(app.shownTargetUrl);
    if (app.shownTarget?.id !== id || !app.labelsOn) return;
    app.shownTarget = fresh;
    publishTarget(fresh);
    note.textContent = `${fresh.labels?.length ?? 0}`;
  } catch (err) {
    note.textContent = "";
    showMessage(`Labels unavailable: ${err.message}`, "warn");
  }
}

/**
 * T51: known asteroids and comets arrive after the field (the Live API computes them in the
 * background). Poll /objects, then reload target.json so the traces include them.
 */
async function loadObjects(target) {
  const note = $("#objects-note");
  note.textContent = "";
  if (target.synthetic || target.objects_requested || !app.shownTargetUrl) return;
  const id = target.id;
  note.textContent = "looking up known asteroids and comets…";
  try {
    for (let i = 0; i < 360; i++) {
      const res = await fetch(`${app.api}/api/targets/${encodeURIComponent(id)}/objects`);
      const body = await res.json();
      if (app.shownTarget?.id !== id) return;
      if (body.status === "ready") break;
      if (body.status !== "building") throw new Error(body.message ?? `HTTP ${res.status}`);
      await new Promise((r) => setTimeout(r, 5000));
    }
    const fresh = await fetchJson(app.shownTargetUrl);
    if (app.shownTarget?.id !== id) return;
    note.textContent = "";
    app.shownTarget = fresh;
    publishTarget(fresh);
  } catch (err) {
    if (app.shownTarget?.id === id) note.textContent = `Known objects unavailable: ${err.message}`;
  }
}

async function main() {
  // T40: the Labels switch; other modules can flip it with "labels:set" and follow "labels:changed".
  $("#labels-toggle").checked = app.labelsOn;
  $("#labels-toggle").addEventListener("change", (e) => setLabels(e.target.checked));
  document.addEventListener("labels:set", (e) => setLabels(Boolean(e.detail?.on)));
  queueMicrotask(() => document.dispatchEvent(new CustomEvent("labels:changed", { detail: { on: app.labelsOn } })));
  bindPage();
  initHud();
  const p = params();
  if (p.get("api")) app.api = p.get("api");
  await loadPresets();
  startExplore();   // not awaited: the map loads in the background
  const requested = loadFromUrl();
  if (!requested) fillDefaults();
  await warnIfApiDown(requested);
}

main();

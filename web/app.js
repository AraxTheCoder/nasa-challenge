// SPHEREx Blink: page controller. Two ways to get data:
//  - live (default): the Live API (docs/CONTRACTS.md v0.3) builds any RA/Dec field on request.
//    ?ra=&dec=&size= in the page URL requests that field on load; ?api=<base> sets the API address.
//  - offline (?data=<folder>): read a static targets folder with an index.json, no server needed
//    (e.g. ?data=../fixtures/targets/). ?target=<id> picks a target there.
//
// Modules: api.js (Live API client), viewer.js (frames + blink), util.js (helpers).

import { DEFAULT_API, ApiError, health, requestField } from "./api.js";
import { $, el, fmtElapsed } from "./util.js";
import { checkTarget, clearTarget, initViewer, showTarget, stopBlink } from "./viewer.js";
import { initObjects } from "./objects.js";
import { initDiff } from "./diff.js";
import * as explore from "./explore.js";

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

// RA/Dec help bubble under the form (T29). Off while we test the site; switch on for the demo.
// The page URL can override it: ?tip=1 shows it, ?tip=0 hides it.
const FORM_TIP_ENABLED = false;
const TIP_DISMISSED_KEY = "spherex-blink.formTipDismissed";

// T40: catalogue labels default ON (fast since T38: 1-7 s, fetched in the background without
// blocking the field). The choice is remembered per browser.
function labelsPref() {
  try { return localStorage.getItem("spherex.labels") !== "0"; } catch { return true; }
}

const app = {
  labelsOn: labelsPref(),
  api: DEFAULT_API,
  dataRoot: null,    // offline mode: folder with index.json
  index: null,       // offline mode: parsed index.json
  request: null,     // live mode: last {ra, dec, size} asked for
  presets: [],
  loadToken: 0,      // bumps on every new load; stale async results check it and bail out
  abort: null,
  jobStart: 0,
  jobTimer: null,
};

const params = () => new URLSearchParams(location.search);
const withSlash = (s) => (s.endsWith("/") ? s : `${s}/`);
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
    showMessage(`${err.message} Start it with "python -m server --fixture" (see web/README.md), or open this page with ?api=<url>.`);
  } else if (err.kind === "bad_request") {
    showMessage(`Can't use these coordinates: ${err.message}`);
  } else if (err.kind === "no_data") {
    showMessage(`No SPHEREx images here: ${err.message}`, "warn");
  } else {
    showMessage(`Building the field failed: ${err.message}`);
  }
}

// ---------- loading (shared) ----------

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
  // T37: labels are shown only when switched on (and then asked for on demand)
  showTarget(app.labelsOn ? target : { ...target, labels: [] }, targetUrl);
  syncExplore(target);
  if (app.labelsOn && !target.labels_requested) setLabels(true);
  warnings.forEach((w) => showMessage(w, "warn"));
}

// ---------- live mode ----------

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
  $("#empty-default").hidden = !f;
  if (!f) return;
  fillForm(presetRequest(f));
  $("#empty-default-name").textContent = f.name;
  $("#empty-default-kind").textContent = f.kind ? ` (${f.kind.charAt(0).toLowerCase()}${f.kind.slice(1)})` : "";
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
  stopBlink();
  $("#empty-default").hidden = true;
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

// ---------- RA/Dec help bubble ----------

function tipEnabled() {
  const q = params().get("tip");
  return q === "1" ? true : q === "0" ? false : FORM_TIP_ENABLED;
}

function tipDismissed() {
  try {
    return localStorage.getItem(TIP_DISMISSED_KEY) === "1";
  } catch {
    return false; // storage blocked: just show it again next time
  }
}

/** force: the "?" button opens it even when automatic showing is off or "Got it" was clicked. */
function showTip({ force = false } = {}) {
  if (app.dataRoot || (!force && (!tipEnabled() || tipDismissed()))) return;
  $("#form-tip").hidden = false;
  $("#form-help").setAttribute("aria-expanded", "true");
  placeTip();
}

/**
 * One-row form (desktop): bubble right under the RA input, arrow pointing at it.
 * Stacked form (phone): bubble under the whole form, so it never covers an input you type into.
 */
function placeTip() {
  const tip = $("#form-tip");
  if (tip.hidden) return;
  const form = $("#field-form");
  const ra = form.ra;
  const stacked = form.dec.offsetTop > ra.offsetTop;
  const controls = [...form.querySelectorAll("input, select, button[type=submit]")].filter((c) => c.offsetParent);
  const bottom = stacked
    ? Math.max(...controls.map((c) => c.offsetTop + c.offsetHeight))
    : ra.offsetTop + ra.offsetHeight;
  const left = Math.max(0, Math.min(ra.offsetLeft, form.clientWidth - tip.offsetWidth));
  tip.style.left = `${left}px`;
  tip.style.top = `${bottom + 10}px`;
  tip.style.setProperty("--arrow-x", `${Math.max(12, ra.offsetLeft - left + 16)}px`);
}

function hideTip({ remember = false } = {}) {
  $("#form-tip").hidden = true;
  $("#form-help").setAttribute("aria-expanded", "false");
  if (!remember) return;
  try {
    localStorage.setItem(TIP_DISMISSED_KEY, "1");
  } catch {
    // storage blocked: it comes back on the next visit, which is fine
  }
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

async function showApiStatus(fieldRequested) {
  const h = await health(app.api);
  const info = $("#source-info");
  if (h) {
    const mode = h.mode === "fixture" ? "fixture mode: every field is the synthetic demo" : "live SPHEREx data";
    info.textContent = `Live API ${app.api} · ${mode}`;
  } else {
    info.textContent = `Live API ${app.api} · not reachable`;
    if (!fieldRequested) {
      showMessage(`The Live API at ${app.api} is not reachable. Start it with "python -m server --fixture" (see web/README.md), or open this page with ?api=<url>.`, "warn");
    }
  }
}

// ---------- offline mode ----------

async function startOffline(root) {
  app.dataRoot = new URL(withSlash(root), location.href).href;
  $("#field-form").hidden = true;
  $("#btn-rebuild").hidden = true;
  $("#picker").hidden = false;
  $("#source-info").textContent = `Offline mode · reading ${new URL(app.dataRoot).pathname}`;
  try {
    app.index = await fetchJson(`${app.dataRoot}index.json`);
    if (!Array.isArray(app.index.targets) || app.index.targets.length === 0) {
      throw new Error(`${app.dataRoot}index.json lists no targets.`);
    }
  } catch (err) {
    showMessage(`${err.message} Check the ?data= folder.`);
    return;
  }
  const select = $("#target-select");
  select.replaceChildren(
    ...app.index.targets.map((t) => {
      const name = t.name ?? t.id;
      const tag = t.synthetic !== false && !/synthetic/i.test(name) ? " (synthetic)" : "";
      return el("option", { value: t.id }, name + tag);
    }),
  );
  select.disabled = app.index.targets.length < 2;
  await openOfflineFromUrl();
}

async function openOfflineFromUrl() {
  const wanted = params().get("target");
  const t = app.index.targets.find((x) => x.id === wanted) ?? app.index.targets[0];
  await openOffline(t.id);
  if (wanted && t.id !== wanted) showMessage(`Target "${wanted}" not found, showing "${t.id}".`, "warn");
}

async function openOffline(id) {
  const { token, signal } = beginLoad();
  $("#target-select").value = id;
  try {
    await openTarget(new URL(`${encodeURIComponent(id)}/target.json`, app.dataRoot).href, id, token, signal);
    const url = new URL(location.href);
    url.searchParams.set("target", id);
    history.replaceState(null, "", url);
  } catch (err) {
    if (err.name !== "AbortError" && token === app.loadToken) showMessage(err.message);
  }
}

// ---------- wiring ----------

function bindPage() {
  $("#field-form").addEventListener("submit", (e) => {
    e.preventDefault();
    hideTip();
    const req = readForm();
    if (!req.ra || !req.dec) return;
    fillForm(req);
    setPageUrl(req, true);
    loadField(req);
  });
  $("#preset").addEventListener("change", () => { hideTip(); onPresetPicked(); });
  $("#field-form").addEventListener("focusin", (e) => {
    if (e.target.name === "ra" || e.target.name === "dec") showTip();
  });
  $("#form-tip-close").addEventListener("click", () => hideTip({ remember: true }));
  $("#form-help").addEventListener("click", () => ($("#form-tip").hidden ? showTip({ force: true }) : hideTip()));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") hideTip(); });
  window.addEventListener("resize", placeTip);
  $("#field-form").addEventListener("input", (e) => {
    if (e.target.name !== "ra" && e.target.name !== "dec") return;
    syncPresetSelect();
    $("#empty-default").hidden = true; // the form no longer holds the default field
  });
  $("#target-select").addEventListener("change", (e) => openOffline(e.target.value));

  $("#job-cancel").addEventListener("click", () => {
    app.abort?.abort();
    hideJob();
    showMessage("Stopped waiting. The server keeps building this field; ask again later and it comes from the cache.", "warn");
  });

  $("#btn-rebuild").addEventListener("click", () => {
    if (!app.request) return;
    if (!confirm("Rebuild this field from IRSA to pick up new SPHEREx data? This can take a few minutes.")) return;
    loadField({ ...app.request, refresh: true });
  });

  $("#btn-copy").addEventListener("click", async () => {
    const btn = $("#btn-copy");
    try {
      await navigator.clipboard.writeText(location.href);
      btn.textContent = "Copied ✓";
      setTimeout(() => { btn.textContent = "Copy link"; }, 1500);
    } catch {
      prompt("Copy this link:", location.href);
    }
  });

  window.addEventListener("popstate", () => {
    if (app.dataRoot) {
      if (app.index) openOfflineFromUrl();
    } else if (!loadFromUrl()) {
      app.abort?.abort();
      hideJob();
      clearMessages();
      clearTarget();
      fillDefaults();
    }
  });
}

// ---------- explore mode (T30) ----------

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
  if (app.dataRoot) return;                       // offline mode: no tile server
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
  box.append(el("span", { class: "muted small" }, info.synthetic ? "Epochs (synthetic):" : "SPHEREx epochs here:"),
    ...buttons, blink);
  box.hidden = false;
  pick(0);
}

function updateExplorePos(_view, cursor) {
  const v = explore.view();
  if (!v) return;
  const f = (x) => `${x >= 0 ? "+" : ""}${x.toFixed(4)}°`;
  const where = cursor ? `cursor RA ${cursor[0].toFixed(4)}° Dec ${f(cursor[1])}` : `RA ${v.ra.toFixed(4)}° Dec ${f(v.dec)}`;
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
  const sel = $("#explore-survey");
  explore.SURVEYS.forEach((s) => sel.append(el("option", { value: s.id }, s.label)));
  sel.value = explore.DEFAULT_SURVEY;
  sel.addEventListener("change", async () => {
    try { setupBand(await explore.setSurvey(sel.value)); }
    catch (err) { showMessage(err.message, "warn"); }
  });
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
      ra: Number(f.ra) || undefined, dec: Number(f.dec) || undefined, fovDeg: 2,
      api: app.dataRoot ? null : app.api,
    });
    sky.on("change", updateExplorePos);
    // Debug overlay (tile outlines, max-zoom / sharp indicator); ?debug=1 switches it on at load
    const dbg = $("#sky-debug");
    dbg.checked = params().get("debug") === "1";
    explore.setDebug(dbg.checked);
    dbg.addEventListener("change", () => explore.setDebug(dbg.checked));
    setupTilesSwitch(sel);
    setupBand(sky.base);
    if (app.shownTarget) syncExplore(app.shownTarget);   // a field loaded before the map was ready
    updateExplorePos();
  } catch (err) {
    showMessage(`Sky map unavailable: ${err.message}`, "warn");
  }
}

// ---------- T47: live tiles from here or from the US VM next to the S3 bucket ----------

async function setupTilesSwitch(surveySelect) {
  if (app.dataRoot) return;
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
      setupBand(await explore.setSurvey(surveySelect.value));   // fresh layer: re-asks failed tiles
    } catch (err) {
      showMessage(`Could not switch tiles: ${err.message}`, "warn");
    }
  });
}

// ---------- T37: catalogue labels only on request ----------

async function setLabels(on) {
  app.labelsOn = on;
  try { localStorage.setItem("spherex.labels", on ? "1" : "0"); } catch { /* private mode: not remembered */ }
  $("#labels-toggle").checked = on;
  document.dispatchEvent(new CustomEvent("labels:changed", { detail: { on } }));  // other switches follow
  const t = app.shownTarget;
  const note = $("#labels-note");
  note.textContent = "";
  if (!t || !app.shownTargetUrl) return;
  if (!on) {
    showTarget({ ...t, labels: [] }, app.shownTargetUrl);
    return;
  }
  if (t.labels_requested || app.dataRoot) {
    showTarget(t, app.shownTargetUrl);
    note.textContent = `${t.labels?.length ?? 0}`;
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
    showTarget(fresh, app.shownTargetUrl);
    note.textContent = `${fresh.labels?.length ?? 0}`;
  } catch (err) {
    note.textContent = "";
    showMessage(`Labels unavailable: ${err.message}`, "warn");
  }
}

async function main() {
  // T40: the Labels switch works in every mode (live, offline ?data=, ?explore=0); other modules can
  // flip it with a "labels:set" event and follow it via "labels:changed".
  $("#labels-toggle").checked = app.labelsOn;
  $("#labels-toggle").addEventListener("change", (e) => setLabels(e.target.checked));
  document.addEventListener("labels:set", (e) => setLabels(Boolean(e.detail?.on)));
  queueMicrotask(() => document.dispatchEvent(new CustomEvent("labels:changed", { detail: { on: app.labelsOn } })));
  initViewer();
  initObjects();
  initDiff();
  bindPage();
  const p = params();
  if (p.get("api")) app.api = p.get("api");
  if (p.get("data")) {
    $("#explore").hidden = true; // offline mode has no tile server; an empty map box only confuses
    await startOffline(p.get("data"));
    return;
  }
  await loadPresets();
  // ?explore=0 skips the sky map (embeds, slow connections, and the browser test, which must not
  // depend on external tile servers being up).
  if (p.get("explore") === "0") $("#explore").hidden = true;
  else startExplore();   // not awaited: the map loads in the background
  const requested = loadFromUrl();
  if (!requested) {
    fillDefaults();
    showTip();
  }
  await showApiStatus(requested);
}

main();

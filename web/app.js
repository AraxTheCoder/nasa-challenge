// SPHEREx Blink: page controller. T90: one page with two parts.
//  - First screen (T55 redesign): the sky map fills the window, the controls float over it (hud.js).
//    "Go" moves the map to the typed RA/Dec and pins it (cursorpin.js). Blinking starts by itself: from
//    level 6 the survey passes (autoblink.js), at level 7 resting on one HiPS order-6 tile builds that
//    tile's field quietly and blinks its epochs; the band slider and "false colour" apply to all of it.
//  - Below (scroll the page): everything of web/: map tools (base map, north up, Joerg's pass buttons,
//    "Blink this spot"), the field form ("Show" builds a field of a chosen size), the
//    frame viewer (map only by default, T80/T81), analysis, spectra, objects, frames, provenance.
//    Using the map tools or the frame viewer takes the map over until the view moves to another tile.
// Two ways to get data:
//  - live (default): the Live API (docs/CONTRACTS.md) builds any RA/Dec field on request.
//    ?ra=&dec=&size= (or &blink=1) in the page URL builds that field on load; ?ra=&dec= alone goes there
//    like Go; ?api=<base> sets the API address.
//  - offline (?data=<folder>): read a static targets folder with an index.json, no server needed
//    (e.g. ?data=../fixtures/targets/). ?target=<id> picks a target there.
//
// Modules: api.js (Live API client), viewer.js (frames + blink), util.js (helpers), explore.js + sky.js
// (the map), autoblink.js (survey passes), hud.js (panels), cursorpin.js (📍), coords.js (RA/Dec input).

import { DEFAULT_API, ApiError, health, requestField } from "./api.js";
import { $, el, fmtElapsed } from "./util.js";
import { checkTarget, clearTarget, initViewer, showTarget, stopBlink } from "./viewer.js";
import { initObjects } from "./objects.js";
import { initDiff } from "./diff.js";
import { initPhotometry } from "./photometry.js";
import "./mapframes.js"; // T81: the frame viewer's A/B, blink, play and A − B drive the map
import "./passes.js";    // T82: blink SPHEREx's six-month survey passes anywhere on the map (buttons, map tools)
import "./outliers.js";  // T86: sources in the field with unusual spectra
import "./tour.js";      // T92: guided tour of the official targets ("▶ Tour", ?tour=1)
import { initLamPick, lamFromUrl, setLamUrl } from "./lampick.js";
import { initStack } from "./stackview.js";
import { nearestBand, parseLam } from "./lambda.js";
import * as explore from "./explore.js";
import { initChemistry } from "./chemistry.js";
import { initHud } from "./hud.js";   // T55: drag the floating panels anywhere
import { parseDec, parseRa } from "./coords.js";
import { initCursorPin, isPicking, pinAt, setPicking } from "./cursorpin.js";   // T55: 📍 marker + pick mode
import * as passes from "./autoblink.js";   // T55: survey passes blink by themselves from level 6
import { ang2pix, tileGrid } from "./healpix.js";

const SIZE_MIN = 5;
const SIZE_MAX = 210;   // API limit = one SPHEREx detector (3.49 deg), server/coords.py
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

// Catalogue labels: default OFF since T55 (fetched on demand when switched on); remembered per browser.
const LABELS_KEY = "spherex.labels";
function labelsPref() {
  try { return localStorage.getItem(LABELS_KEY) === "1"; } catch { return false; }
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
  shownTarget: null,
  shownTargetUrl: null,
  goal: null,        // T55 Go: {ra, dec, fovDeg}
  goalPending: false,
  manualMap: false,  // T90: map tools / frame viewer below drive the map; automatic blinking waits
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
    showMessage(`${err.message} Start it with "python web/dev.py" or "python -m server --fixture" (see web/README.md), or open this page with ?api=<url>.`);
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

/** The field to the frame viewer below and the map overlays (traces.js, skylabels.js; viewer:target);
 *  labels only while switched on (T37). */
function publishTarget(target) {
  if (!target) { clearTarget(); document.title = "SPHEREx Blink"; return; }
  showTarget(app.labelsOn ? target : { ...target, labels: [] }, app.shownTargetUrl);
  document.title = `${target.name ?? target.id} · SPHEREx Blink`;
}

async function openTarget(targetUrl, expectedId, token, signal) {
  const target = await fetchJson(targetUrl, signal);
  if (token !== app.loadToken) return;
  const warnings = checkTarget(target, expectedId);
  app.shownTargetUrl = targetUrl;
  app.shownTarget = target;
  publishTarget(target);
  syncExplore(target);
  if (app.labelsOn && !target.labels_requested) setLabels(true);
  loadObjects(target);
  checkUpdates(target);
  warnings.forEach((w) => showMessage(w, "warn"));
}

// ---------- live mode: the field form below ("Show" builds a field) ----------

function readForm() {
  const f = $("#field-form");
  return { ra: f.ra.value.trim(), dec: f.dec.value.trim(), size: clampSize(Number(f.size.value) || SIZE_DEFAULT) };
}

/** Both forms show the position: the field form below (with size) and the Go form on the map. */
function fillForm(req) {
  const f = $("#field-form");
  f.ra.value = req.ra;
  f.dec.value = req.dec;
  if (req.size) f.size.value = String(req.size);
  const g = $("#go-form");
  g.ra.value = req.ra;
  g.dec.value = req.dec;
  syncPresetSelect();
}

/** Show the matching quick pick in both dropdowns (and why it is interesting), or none once the user typed
 *  other coordinates. */
function syncPresetSelect() {
  const { ra, dec } = readForm();
  const i = app.presets.findIndex((p) => String(p.ra_deg) === ra && String(p.dec_deg) === dec);
  $("#preset").value = i >= 0 ? String(i) : "";
  $("#go-preset").value = i >= 0 ? String(i) : "";
  showWhy(i >= 0 ? app.presets[i].name : "", i >= 0 ? app.presets[i].why : null);
}

function showWhy(title, text) {
  $("#pick-why").hidden = !text;
  $("#pick-why").replaceChildren(...(text ? [el("strong", {}, `${title}: `), text] : []));
}

const presetRequest = (f) => ({ ra: String(f.ra_deg), dec: String(f.dec_deg), size: clampSize(f.size_arcmin ?? SIZE_DEFAULT) });
const defaultPreset = () => app.presets.find((p) => p.default) ?? app.presets[0] ?? null;

/** Pre-fill the forms with the default test field (no request; Go or Show). */
function fillDefaults() {
  const f = defaultPreset();
  $("#empty-default").hidden = !f;
  if (!f) return;
  fillForm(presetRequest(f));
  $("#empty-default-name").textContent = f.name;
  $("#empty-default-kind").textContent = f.kind ? ` (${f.kind.charAt(0).toLowerCase()}${f.kind.slice(1)})` : "";
}

/** ?ra=&dec= (Go), plus &size= for a built field (Show), so a reload or shared link does the same again. */
function setPageUrl(req, push, build = true) {
  const url = new URL(location.href);
  url.searchParams.set("ra", req.ra);
  url.searchParams.set("dec", req.dec);
  if (build && req.size) url.searchParams.set("size", String(req.size));
  else url.searchParams.delete("size");
  url.searchParams.delete("blink");
  if (url.href === location.href) return;
  if (push) history.pushState(null, "", url);
  else history.replaceState(null, "", url);
}

/** Do what the page URL asks for: ?ra=&dec=&size= (or &blink=1) builds that field, ?ra=&dec= alone goes
 *  there like Go. Returns false if it asks for nothing. */
function loadFromUrl() {
  const p = params();
  const ra = p.get("ra")?.trim();
  const dec = p.get("dec")?.trim();
  if (!ra || !dec) return false;
  const req = { ra, dec, size: clampSize(Number(p.get("size")) || SIZE_DEFAULT) };
  fillForm(req);
  if (p.get("size") || p.get("blink") === "1") loadField(req);
  else goTo(req);
  return true;
}

/** Build (or fetch the cached) field req. quiet (T55 automatic builds): no progress panel, no error popup:
 *  progress and errors go to the blink indicator instead. */
async function loadField(req, { quiet = false } = {}) {
  const { token, signal } = beginLoad();
  if (!quiet) stopBlink();
  $("#empty-default").hidden = true;
  app.request = req;
  if (!quiet) { app.manualMap = false; passes.setPaused(false); }   // an explicit field takes the map again
  try {
    const onProgress = (progress, id) => {
      if (token !== app.loadToken) return;
      if (quiet) { autoField.progress = progress; showBlinkStatus(); } else showJob(req, progress, id);
    };
    const { id, targetUrl } = await requestField(app.api, req, { onProgress, signal });
    if (token !== app.loadToken) return;
    await openTarget(targetUrl, id, token, signal);
  } catch (err) {
    if (err.name === "AbortError" || token !== app.loadToken) return;
    if (quiet) {
      autoField.building = null;
      autoField.error = err.message ?? String(err);
      showBlinkStatus();
    } else showLoadError(err);
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
  // The five official fields (presets.json) and, since T65, fields where something moves (discover.json).
  // Both are optional: without them the forms still work. Same list in both dropdowns: below it builds
  // the field (Show), on the map it goes there (Go).
  const [official, more] = await Promise.all(["presets.json", "discover.json"].map((u) =>
    fetchJson(u).then((d) => d.fields ?? []).catch(() => [])));
  app.presets = [...official.map((f) => ({ ...f, group: "Official test fields" })), ...more];
  for (const select of [$("#preset"), $("#go-preset")]) {
    const groups = new Map();
    app.presets.forEach((f, i) => {
      if (!groups.has(f.group)) groups.set(f.group, el("optgroup", { label: f.group }));
      groups.get(f.group).append(el("option", { value: String(i), title: f.why ?? f.kind ?? "" }, f.name));
    });
    select.append(...groups.values());
    select.hidden = app.presets.length === 0;
  }
  $("#surprise").hidden = more.length === 0;
}

/** "Surprise me" (T65): a random field from discover.json, not the one already shown. */
function surprise() {
  const shown = $("#preset").value;
  const pool = app.presets.map((f, i) => ({ f, i })).filter(({ f, i }) => f.group !== "Official test fields" && String(i) !== shown);
  if (!pool.length) return;
  $("#preset").value = String(pool[Math.floor(Math.random() * pool.length)].i);
  onPresetPicked();
}

/** Quick pick below: build that field (Show). */
function onPresetPicked() {
  const f = app.presets[Number($("#preset").value)];
  if (!f) return;
  const req = presetRequest(f);
  fillForm(req);
  setPageUrl(req, true, true);
  loadField(req);
}

/** Quick pick on the map: go there (Go: jump + pin; the blink comes by itself). */
function onGoPresetPicked() {
  const f = app.presets[Number($("#go-preset").value)];
  if (!f) return;
  const req = presetRequest(f);
  fillForm(req);
  if (goTo(req)) setPageUrl(req, true, false);
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
      showMessage(`The Live API at ${app.api} is not reachable. Start it with "python web/dev.py" or "python -m server --fixture" (see web/README.md), or open this page with ?api=<url>.`, "warn");
    }
  }
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
  window.scrollTo({ top: 0, behavior: "smooth" });       // T90: the map is the first screen
  return true;
}

function showGoal() {
  const g = app.goal;
  if (!g) return;
  explore.goTo(g.ra, g.dec, g.fovDeg ?? explore.fovForOrder(GO_ORDER) ?? undefined);
  pinAt(g.ra, g.dec);                                     // 📍 + RA/Dec on the position, fades after 5 s
}

/** 📍 button: pick a position on the map. The picked spot goes into the forms and the URL (like Go). */
function onPicked(ra, dec) {
  const req = { ra: ra.toFixed(4), dec: dec.toFixed(4) };
  fillForm(req);
  setPageUrl(req, true, false);
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
    setPageUrl(req, true, true);
    loadField(req);
  });
  // T55 Go form on the map: jump + pin only; the blink comes by itself
  $("#go-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const g = $("#go-form");
    const req = { ra: g.ra.value.trim(), dec: g.dec.value.trim() };
    if (!req.ra || !req.dec) return;
    fillForm({ ...req, size: readForm().size });
    if (goTo(req)) setPageUrl(req, true, false);
  });
  $("#go-form").addEventListener("input", (e) => {
    if (e.target.name !== "ra" && e.target.name !== "dec") return;
    const f = $("#field-form");
    f.ra.value = $("#go-form").ra.value;
    f.dec.value = $("#go-form").dec.value;
    syncPresetSelect();
  });
  $("#go-preset").addEventListener("change", onGoPresetPicked);
  $("#preset").addEventListener("change", () => { hideTip(); onPresetPicked(); });
  $("#surprise").addEventListener("click", () => { hideTip(); surprise(); });
  $("#to-below").addEventListener("click", () => $("#map-tools").scrollIntoView({ behavior: "smooth" }));
  $("#field-form").addEventListener("focusin", (e) => {
    if (e.target.name === "ra" || e.target.name === "dec") showTip();
  });
  $("#form-tip-close").addEventListener("click", () => hideTip({ remember: true }));
  $("#form-help").addEventListener("click", () => ($("#form-tip").hidden ? showTip({ force: true }) : hideTip()));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") hideTip(); });
  window.addEventListener("resize", placeTip);
  $("#field-form").addEventListener("input", (e) => {
    if (e.target.name !== "ra" && e.target.name !== "dec") return;
    const g = $("#go-form");
    g.ra.value = $("#field-form").ra.value;
    g.dec.value = $("#field-form").dec.value;
    syncPresetSelect();
    $("#empty-default").hidden = true; // the form no longer holds the default field
  });
  $("#target-select").addEventListener("change", (e) => openOffline(e.target.value));

  $("#job-cancel").addEventListener("click", () => {
    app.abort?.abort();
    hideJob();
    showMessage("Stopped waiting. The server keeps building this field; ask again later and it comes from the cache.", "warn");
  });

  $("#target-updates-rebuild").addEventListener("click", () => $("#btn-rebuild").click());
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

  // T90: the map tools and the frame viewer below drive the map (T81 mapframes.js, T82 pass buttons):
  // while they do, the automatic blink leaves the map alone, until the view moves to another tile.
  const takeOver = (e) => {
    if (!e.target.closest?.(".layout, #map-tools, #chem-box") || e.target.closest?.("#field-form, #photometry")) return;
    setManual(true);
  };
  document.addEventListener("pointerdown", takeOver, true);
  document.addEventListener("map:take", () => setManual(true));   // T93: a tool on the map itself (Chemistry)
  document.addEventListener("keydown", (e) => {
    if (e.target.closest?.("input, select, textarea, .sky-stage")) return;
    if ([" ", "p", "P", "x", "X", "m", "M", "d", "D", "ArrowLeft", "ArrowRight"].includes(e.key) && app.shownTarget) setManual(true);
  }, true);

  window.addEventListener("popstate", () => {
    if (app.dataRoot) {
      if (app.index) openOfflineFromUrl();
    } else if (!loadFromUrl()) {
      app.abort?.abort();
      hideJob();
      clearMessages();
      app.shownTarget = null;
      app.shownTargetUrl = null;
      clearTarget();
      fillDefaults();
    }
  });
}

/** T90: the user drives the map from below (true) or the automatic blink may again (false). */
function setManual(on) {
  if (app.manualMap === on) return;
  app.manualMap = on;
  passes.setPaused(on);
  showBlinkStatus();
  document.dispatchEvent(new CustomEvent("map:manual", { detail: { on } }));   // T93: chemistry.js steps back
}

// ---------- sky map (T30/T36) ----------

/** A field arrived: an automatic one (tile build) is remembered for its tile + band; one asked for
 *  explicitly (Show, a link, Blink this spot) moves the map there and is outlined (web/). */
function syncExplore(target) {
  app.shownTarget = target;
  const c = target?.center;
  if (!c) return;
  if (autoField.building) {
    autoField.ready.set(autoField.building, target);   // tile|variant it was built for
    autoField.building = null;
  } else if (!app.dataRoot) {
    autoField.explicit = target;
    explore.goTo(c.ra_deg, c.dec_deg, Math.max(0.25, (target.size_arcmin * 3) / 60));
    explore.markField(c.ra_deg, c.dec_deg, target.size_arcmin);
  }
  if (app.dataRoot) return;
  decideSource();                                     // shows its epochs (or keeps the passes)
}

/** T55: blink source changed: epochs = the shown field's layers (if any); passes = autoblink.js's. */
function onBlinkSource(m) {
  clearInterval(epochTimer);
  if (m === "epochs") {
    explore.hideEpochs();
    if (app.shownTarget) showEpochLayers(app.shownTarget);
  } else {
    $("#explore-epochs").hidden = true;
  }
  showBlinkStatus();
}

// T32: the field's epochs as map layers, blinking by themselves (T55), so epochs can be compared in the map;
// T81: the frames as layers too (A/B, blink, play and A − B in the map: mapframes.js).
let epochTimer = null;
let epochShown = 0;
let epochVariant = null;

/** T89: which epoch image fits the band setting: false colour (e<n>c), the band's detector (e<n>d<det>, when
 *  the field holds several), else the epoch's frames as they are (a one-detector field). */
function epochSuffix(l) {
  if (passes.colour()) return "c";
  const det = explore.detector();
  return (l.detectors?.length ?? 0) > 1 && l.detectors.includes(det) ? `d${det}` : "";
}

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
  if (app.shownTarget !== target || !info.layers?.length || passes.mode() !== "epochs") return;
  const abs = (l) => ({ ...l, url: new URL(l.url, app.api).href });
  epochVariant = `${target.id}|${passes.colour() ? "rgb" : explore.detector()}`;
  const layers = await explore.setFieldLayers(info.layers.map((l) => ({ ...abs(l), url: abs(l).url + epochSuffix(l) })),
    (info.frame_layers ?? []).map(abs), new URL(`/api/hips/${encodeURIComponent(target.id)}`, app.api).href);
  if (!layers.length || app.shownTarget !== target || passes.mode() !== "epochs") return;
  // T55: when, not "Ep. n": the epoch's month(s) from its label "Epoch 1 · 2025-06-03 – 2025-06-10 · …"
  const labels = layers.map((l) => {
    const d = (l.label ?? "").match(/\d{4}-\d{2}-\d{2}/g);
    return el("span", { class: "pass-label", title: l.label }, d ? passes.monthSpan(d[0], d[d.length - 1]) : `epoch ${l.epoch}`);
  });
  const pick = (i) => {
    epochShown = i;
    explore.showEpoch(i);
    document.dispatchEvent(new CustomEvent("explore:epoch-picked"));   // mapframes.js steps aside
    labels.forEach((b, j) => b.classList.toggle("current", j === i));
  };
  // no caption for real data; synthetic layers stay visibly labelled (CLAUDE.md)
  box.append(...(info.synthetic ? [el("span", { class: "muted small" }, "synthetic:")] : []), ...labels);
  box.hidden = false;
  pick(0);
  // always blinking (like the passes), while nobody drives the map from below
  epochTimer = setInterval(() => {
    if (!app.manualMap) pick((epochShown + 1) % layers.length);
  }, 800);
}

/** How much the map shows (on the map), and the cursor / centre position + north-up state (map tools below). */
function updateExplorePos(_view, cursor) {
  const v = explore.view();
  if (!v) return;
  const arc = (a) => (a >= 120 ? `${(a / 60).toFixed(1)}°` : `${Math.round(a)}′`);
  $("#explore-pos").textContent = `view ${arc(v.fovArcmin)} × ${arc(v.heightArcmin)}`;
  const f = (x) => `${x >= 0 ? "+" : ""}${x.toFixed(4)}°`;
  const where = cursor ? `cursor RA ${cursor[0].toFixed(4)}° Dec ${f(cursor[1])}` : `RA ${v.ra.toFixed(4)}° Dec ${f(v.dec)}`;
  $("#map-pos").textContent = `${where} · view ${v.fovArcmin >= 120 ? (v.fovArcmin / 60).toFixed(1) + "°" : Math.round(v.fovArcmin) + "′"}`;
  const sv = explore.getSky()?.view();
  const tilted = sv && Math.abs(sv.roll) > 1;
  const nb = $("#sky-north");
  nb.textContent = tilted ? `N↑ (${Math.round(sv.roll)}°)` : "N↑";
  nb.classList.toggle("muted", !tilted);
  if (!cursor) decideSource();                    // mouse moves alone don't change what blinks
}

// ---------- T55: what blinks, decided by itself ----------
// Survey passes from level 6. Resting at level 7 on one HiPS order-6 tile (~55′, about one screen) builds
// that tile's field in the background for the band shown (same grid for everyone: built once, then cached);
// once it is ready and the view is still on that tile, its field epochs blink (aligned frames, traces,
// detections). A field asked for explicitly (Show, a link, Blink this spot) blinks while the view is on
// it. Moving out of the tile or zooming out goes back to the survey passes. No buttons, no popup.

const FIELD_ORDER = 6;
const AUTO_BUILD_MS = 2000;
// keys "<tile>|d<n>": only the band's detector (fast, ~1/6 of the cutouts); false colour uses the same field
// (T89 LRGB: its detail x the colour of the all-band cube, layer e<n>c); ready: key -> its target, kept so
// returning to a tile or band shows it at once
const autoField = { key: null, building: null, ready: new Map(), explicit: null, progress: null, error: null, timer: null };

/** T89: what a field must hold for the current band setting: the band's detector (also for false colour). */
const fieldVariant = () => `d${explore.detector()}`;

/** Order-6 tile under the view centre (null when not at level 7 or no map). */
function centreTile() {
  const v = explore.view();
  return v && passes.sharp() ? ang2pix(FIELD_ORDER, v.ra, v.dec) : null;
}

/** Square field around tile pix that covers all of it: centre + side (arcmin), within the API's limits. */
function tileField(pix) {
  const g = tileGrid(FIELD_ORDER, pix, 4);
  const c = tileGrid(FIELD_ORDER, pix, 2).slice(8, 10);        // middle point of the 3 x 3 grid
  const cos = Math.cos((c[1] * Math.PI) / 180) || 1e-6;
  let half = 0;
  for (let i = 0; i < g.length; i += 2) {
    const dra = ((g[i] - c[0] + 540) % 360) - 180;
    half = Math.max(half, Math.abs(dra * cos), Math.abs(g[i + 1] - c[1]));
  }
  return { ra: c[0].toFixed(4), dec: c[1].toFixed(4), size: clampSize(Math.ceil(2 * half * 60 * 1.02)) };
}

const fieldKey = () => { const t = centreTile(); return t === null ? null : `${t}|${fieldVariant()}`; };

/** The explicitly asked-for field (Show, a link, Blink this spot), while the view centre is on it: it
 *  blinks at any zoom, as in web/ before T90. */
function explicitHere() {
  const t = autoField.explicit, v = explore.view();
  if (!t?.center || !v) return null;
  const d = Math.PI / 180, { ra_deg: ra, dec_deg: dec } = t.center;
  const c = Math.sin(dec * d) * Math.sin(v.dec * d) + Math.cos(dec * d) * Math.cos(v.dec * d) * Math.cos((ra - v.ra) * d);
  return (Math.acos(Math.min(1, c)) / d) * 60 <= t.size_arcmin / 2 ? t : null;
}

/** Called on every view / band change and when a field is ready: pick the source, start a build after a rest. */
function decideSource() {
  if (app.dataRoot || !explore.getSky()) return;
  const key = fieldKey();
  const moved = key !== autoField.key;
  autoField.key = key;
  if (moved && app.manualMap) setManual(false);          // another tile / zoom level: automatic again
  const ready = (key && autoField.ready.get(key)) || explicitHere();
  if (ready && ready !== app.shownTarget) {               // a field built earlier for this tile + band: show it
    app.shownTarget = ready;
    app.shownTargetUrl = new URL(`/api/targets/${encodeURIComponent(ready.id)}/target.json`, app.api).href;
    publishTarget(ready);
    if (passes.mode() === "epochs") showEpochLayers(ready);
  }
  const want = ready ? "epochs" : "passes";
  if (passes.mode() !== want) passes.setMode(want, { remember: false });
  else if (want === "epochs" && ready && epochVariant !== `${ready.id}|${passes.colour() ? "rgb" : explore.detector()}`) {
    showEpochLayers(ready);                               // same field, other band / colour: its other images
  }
  if (moved) {
    clearTimeout(autoField.timer);
    autoField.error = null;
    if (key && !ready && autoField.building !== key) {
      autoField.timer = setTimeout(() => buildTile(key), AUTO_BUILD_MS);
    }
  }
  showBlinkStatus();
}

function buildTile(key) {
  if (fieldKey() !== key || app.manualMap) return;
  const [pix, variant] = key.split("|");
  const req = { ...tileField(Number(pix)), auto: true, detector: Number(variant.slice(1)) };
  autoField.building = key;
  autoField.progress = null;
  loadField(req, { quiet: true });
  showBlinkStatus();
}

/** The text indicator next to the switches: what is blinking right now, and what is on its way. */
function showBlinkStatus() {
  const out = $("#blink-status");
  if (!out) return;
  const key = autoField.key;
  let text;
  if (app.manualMap) text = "Blink: map tools / frame viewer below (move to another tile to resume)";
  else if (!passes.passesOn()) text = "Blink: zoom in to level 6";
  else if (key === null) text = "Blink: survey passes · field epochs at level 7";
  else if (passes.mode() === "epochs") text = "Blink: field epochs";
  else {
    text = "Blink: survey passes";
    if (autoField.building === key) {
      const p = autoField.progress;
      const step = p?.step ? STEP_LABELS[p.step] ?? p.step : "building";
      const n = Number.isFinite(p?.done) && Number.isFinite(p?.total) && p.total ? ` ${p.done}/${p.total}` : "";
      text += ` · field epochs: ${step.toLowerCase()}${n}…`;
    } else if (autoField.error) text += ` · field epochs failed: ${autoField.error}`;
  }
  out.textContent = text;
}

// T89: SPHEREx's 6 detectors; one image covers a detector's whole range (a λ gradient across its face)
const DETECTOR_UM = [[0.75, 1.09], [1.10, 1.62], [1.63, 2.41], [2.42, 3.82], [3.83, 4.41], [4.42, 5.00]];

/** The band slider (+ typed µm, T78), the detector it means (T89) and the false-colour switch. */
function setupBand(layer) {
  const box = $("#explore-band-box");
  const waves = explore.bandWavelengths();
  box.hidden = !(layer?.depth > 1);
  if (box.hidden) return;
  const input = $("#explore-band");
  const lamBox = $("#explore-band-lam");   // T78: type the wavelength, the map takes the closest channel
  const colour = $("#band-colour");
  input.max = String(layer.depth - 1);
  input.value = String(layer.slice);
  const show = () => {
    const w = waves[Number(input.value)];
    lamBox.value = Number.isFinite(w) ? w.toFixed(3) : "";
    const d = explore.detector(), [lo, hi] = DETECTOR_UM[d - 1];
    $("#explore-band-out").textContent = colour.checked
      ? `µm · detail D${d} ${lo.toFixed(2)}–${hi.toFixed(2)} µm · colour: all bands`
      : `µm · ch. ${Number(input.value) + 1}/${layer.depth} · D${d} ${lo.toFixed(2)}–${hi.toFixed(2)} µm`;
    $("#explore-band-out").title = colour.checked
      ? "False colour (LRGB): the detail (what moves, sharp, per pass / epoch) comes from this band; the colour from all bands of SPHEREx's all-sky cube (blue = detectors 1+2, green = 3+4, red = 5+6; coarser, all passes together)"
      : "Blinking images show this detector's whole range: SPHEREx's filter changes wavelength across each detector, so one image is not one channel. Zoomed out (IRSA cube) the map shows the exact channel.";
  };
  const toBand = (i) => { input.value = String(i); explore.setBand(i); show(); decideSource(); };
  input.oninput = () => { explore.setBand(Number(input.value)); show(); decideSource(); };
  lamBox.onchange = () => {
    const lam = parseLam(lamBox.value);
    const i = lam == null ? -1 : nearestBand(waves, lam);
    if (i < 0) { show(); return; }       // not a wavelength: back to the current channel
    toBand(i);
    setLamUrl(lam);
  };
  colour.onchange = async () => {
    show();
    // the base map too, so false colour shows at every zoom (zoomed out: IRSA cube, one channel per detector)
    await explore.setSurvey(currentSurvey());
    explore.setBand(Number(input.value));          // the new base map starts on its default band
    await passes.setColour(colour.checked);
    decideSource();
  };
  const urlLam = lamFromUrl();
  const i = urlLam == null ? -1 : nearestBand(waves, urlLam);
  if (i >= 0 && i !== layer.slice) toBand(i);
  else show();
}

/** The base map in use: T89 false colour, else the one picked under "Map" (default: SPHEREx live). */
const currentSurvey = () => ($("#band-colour")?.checked ? "spherex-live-rgb" : $("#explore-survey").value || explore.DEFAULT_SURVEY);

async function startExplore() {
  const sel = $("#explore-survey");
  explore.SURVEYS.filter((s) => s.id !== "spherex-live-rgb").forEach((s) => sel.append(el("option", { value: s.id }, s.label)));
  sel.value = explore.DEFAULT_SURVEY;
  sel.addEventListener("change", async () => {
    try {
      const layer = await explore.setSurvey(currentSurvey());
      if (!$("#band-colour").checked) setupBand(layer);
    } catch (err) { showMessage(err.message, "warn"); }
  });
  $("#explore-blink").addEventListener("click", () => {
    const v = explore.view();
    if (!v) return;
    const req = { ra: v.ra.toFixed(4), dec: v.dec.toFixed(4), size: clampSize(v.fovArcmin / 3) };
    fillForm(req);
    setPageUrl(req, true, true);
    loadField(req);
  });
  const f = readForm();
  let start = {};
  try { start = { ra: parseRa(f.ra), dec: parseDec(f.dec) }; } catch { /* empty or odd form: default view */ }
  try {
    const sky = await explore.initExplore($("#sky"), {
      ra: start.ra, dec: start.dec, fovDeg: 2,
      api: app.dataRoot ? null : app.api,
    });
    sky.on("change", updateExplorePos);
    // Debug overlay (tile outlines, max-zoom / sharp indicator): on by default since T55; ?debug=0 starts it off
    const dbg = $("#sky-debug");
    dbg.checked = params().get("debug") !== "0";
    explore.setDebug(dbg.checked);
    dbg.addEventListener("change", () => explore.setDebug(dbg.checked));
    setupTilesSwitch();
    setupBand(sky.base);
    passes.onModeChange(onBlinkSource);
    await passes.initPasses();
    // the source follows the zoom level: passes from level 6, field epochs at 7
    let lastSharp = null;
    explore.onTiles(() => {
      const s = `${passes.passesOn()}${passes.sharp()}`;
      if (s !== lastSharp) { lastSharp = s; decideSource(); }
    });
    if (app.goalPending) { app.goalPending = false; showGoal(); }   // Go asked before the map existed
    if (app.shownTarget) syncExplore(app.shownTarget);   // a field loaded before the map was ready
    updateExplorePos();
  } catch (err) {
    showMessage(`Sky map unavailable: ${err.message}`, "warn");
  }
}

// ---------- T47: live tiles from here, from the US VM next to the S3 bucket, or both (balanced) ----------

async function setupTilesSwitch() {
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
      const layer = await explore.setSurvey(currentSurvey());      // fresh layer: re-asks failed tiles
      if (!$("#band-colour").checked) setupBand(layer);
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
  document.dispatchEvent(new CustomEvent("labels:changed", { detail: { on } }));  // other switches follow
  const t = app.shownTarget;
  const note = $("#labels-note");
  note.textContent = "";
  if (!t || !app.shownTargetUrl) return;
  if (!on) {
    publishTarget(t);
    return;
  }
  if (t.labels_requested || app.dataRoot) {
    publishTarget(t);
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
    publishTarget(fresh);
    note.textContent = `${fresh.labels?.length ?? 0}`;
  } catch (err) {
    note.textContent = "";
    showMessage(`Labels unavailable: ${err.message}`, "warn");
  }
}

/**
 * T64: newer SPHEREx data? The Live API compares the images known when the field was built with the image
 * index now (and the bucket's release folders). Quiet when up to date, apart from a tooltip on the line.
 */
async function checkUpdates(target) {
  const box = $("#target-updates");
  box.hidden = true;
  $("#target-updates-rebuild").hidden = true;
  $("#target-meta").title = "";
  if (target.synthetic || app.dataRoot || !target.id) return;
  let body;
  try {
    const res = await fetch(`${app.api}/api/targets/${encodeURIComponent(target.id)}/updates`);
    body = await res.json();
    if (!res.ok || body.status !== "ready") return;
  } catch { return; }
  if (app.shownTarget?.id !== target.id) return;
  const newer = body.newer_images > 0;
  const text = [newer ? body.message : null, body.release_note].filter(Boolean).join(" ");
  $("#target-meta").title = `Newer data: ${body.message} Checked against ${body.checked_label}.`;
  if (!text) return;
  $("#target-updates-text").textContent = `${text} (checked against ${body.checked_label})`;
  $("#target-updates-rebuild").hidden = !newer;
  box.hidden = false;
}

/**
 * T51: known asteroids and comets (JPL) arrive after the field: the Live API asks JPL in the
 * background (rate-limited, minutes per field). Poll /objects, then reload target.json.
 * The note shows in the Objects panel below and, short, on the map.
 */
async function loadObjects(target) {
  const notes = [$("#objects-note"), $("#objects-hud-note")];
  const say = (long, short = long) => { notes[0].textContent = long; notes[1].textContent = short; };
  say("");
  if (target.synthetic || target.objects_requested || app.dataRoot || !app.shownTargetUrl) return;
  const id = target.id;
  say("Asking JPL for known asteroids and comets (can take a few minutes)…", "looking up known asteroids and comets…");
  try {
    for (let i = 0; i < 360; i++) {   // up to ~30 min; JPL allows 20 searches per 5 min
      const res = await fetch(`${app.api}/api/targets/${encodeURIComponent(id)}/objects`);
      const body = await res.json();
      if (app.shownTarget?.id !== id) return;
      if (body.status === "ready") break;
      if (body.status !== "building") throw new Error(body.message ?? `HTTP ${res.status}`);
      await new Promise((r) => setTimeout(r, 5000));
    }
    const fresh = await fetchJson(app.shownTargetUrl);
    if (app.shownTarget?.id !== id) return;
    say("");
    app.shownTarget = fresh;
    publishTarget(fresh);
  } catch (err) {
    if (app.shownTarget?.id === id) say(`Known objects unavailable: ${err.message}`);
  }
}

async function main() {
  // T40: the Labels switch works in every mode (live, offline ?data=, ?explore=0); other modules can
  // flip it with a "labels:set" event and follow it via "labels:changed".
  $("#labels-toggle").checked = app.labelsOn;
  $("#labels-toggle").addEventListener("change", (e) => setLabels(e.target.checked));
  $("#sky-north").addEventListener("click", () => { explore.northUp(); updateExplorePos(); });
  document.addEventListener("labels:set", (e) => setLabels(Boolean(e.detail?.on)));
  queueMicrotask(() => document.dispatchEvent(new CustomEvent("labels:changed", { detail: { on: app.labelsOn } })));
  initViewer();
  initObjects();
  initDiff();
  initPhotometry();
  initLamPick();
  initStack();
  bindPage();
  initHud();
  const pinBtn = $("#pin-btn");
  initCursorPin({
    onPick: onPicked,
    onModeChange: (mode) => pinBtn.setAttribute("aria-pressed", String(mode === "pick")),
  });
  pinBtn.addEventListener("click", () => setPicking(!isPicking()));
  const p = params();
  // Map only (Joerg, 2026-11-14): the explore map is the one view of the sky; the frame viewer (image,
  // blink controls, timeline, frame panels) stays in the code for ?frames=1, offline ?data= and
  // ?explore=0 (CI browser test). Spectra come from clicks on the map (T79).
  if (!(p.get("frames") === "1" || p.get("explore") === "0" || p.get("data"))) document.body.classList.add("map-only");
  if (p.get("api")) app.api = p.get("api");
  if (p.get("data")) {
    $("#explore").hidden = true; // offline mode has no tile server; an empty map box only confuses
    $("#map-tools").hidden = true;
    await startOffline(p.get("data"));
    return;
  }
  await loadPresets();
  // ?explore=0 skips the sky map (embeds, slow connections, and the browser test, which must not
  // depend on external tile servers being up).
  if (p.get("explore") === "0") { $("#explore").hidden = true; $("#map-tools").hidden = true; }
  else startExplore();   // not awaited: the map loads in the background
  initChemistry(app.api);   // T93: the Chemistry selector, for real fields on the map
  const requested = loadFromUrl();
  if (!requested) {
    fillDefaults();
    showTip();
  }
  await showApiStatus(requested);
}

main();

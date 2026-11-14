// SPHEREx Blink: static viewer (T11).
// Reads only <data-root>/index.json, <data-root>/<id>/target.json and the frame images
// (see docs/CONTRACTS.md). No build step, no live API calls.
//
// Data root: ?data=<url> if given, otherwise the first of DATA_ROOTS that has an index.json.
// `targets/` is what gets deployed; `../fixtures/targets/` is the dev fallback when the repo root
// is served (python3 -m http.server, then open /web/).

const DATA_ROOTS = ["targets/", "../fixtures/targets/"];
const SCHEMA_VERSIONS = ["0.1", "0.2"]; // target.json versions this viewer understands

const state = {
  root: null,
  index: null,
  target: null,
  base: null,        // URL of the open target folder, ends with "/"
  frames: [],        // sorted by mjd
  imgs: new Map(),   // frame id -> <img>
  broken: new Set(), // frame ids whose image failed to load
  aId: null,
  bId: null,
  shownId: null,
  playing: false,
  intervalMs: 500,
  timer: null,
  loadToken: 0,
};

const $ = (sel) => document.querySelector(sel);

function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (v == null || v === false) continue;
    if (k === "class") node.className = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v === true ? "" : v);
  }
  node.append(...children.flat().filter((c) => c != null && c !== false));
  return node;
}

// ---------- loading ----------

async function fetchJson(url) {
  const res = await fetch(url, { cache: "no-cache" });
  if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
  return res.json();
}

function withSlash(s) {
  return s.endsWith("/") ? s : `${s}/`;
}

async function loadIndex() {
  const param = new URLSearchParams(location.search).get("data");
  const roots = param ? [withSlash(param)] : DATA_ROOTS;
  const failures = [];
  for (const root of roots) {
    try {
      const index = await fetchJson(`${root}index.json`);
      if (!Array.isArray(index.targets)) throw new Error(`${root}index.json has no "targets" list`);
      return { root, index };
    } catch (err) {
      failures.push(err.message);
    }
  }
  throw new Error(
    `No index.json found (${failures.join("; ")}). ` +
      "Serve the repo root over HTTP (python3 -m http.server) and open /web/, " +
      "or pass ?data=<folder with index.json>.",
  );
}

// Light checks only; the full schema is docs/target.schema.json and is enforced upstream.
function checkTarget(t, id) {
  if (!t || !Array.isArray(t.frames) || t.frames.length === 0) {
    throw new Error(`target "${id}" has no frames`);
  }
  const warnings = [];
  if (!SCHEMA_VERSIONS.includes(t.schema_version)) {
    warnings.push(`schema_version is ${JSON.stringify(t.schema_version)}, this viewer knows ${SCHEMA_VERSIONS.join(", ")}.`);
  }
  if (t.id !== id) warnings.push(`target.json id "${t.id}" differs from its folder "${id}".`);
  if (typeof t.synthetic !== "boolean") warnings.push("target.json has no synthetic flag; treating it as synthetic.");
  if (!t.image?.width || !t.image?.height) warnings.push("target.json has no image size; assuming square frames.");
  return warnings;
}

const isSynthetic = (t) => t.synthetic !== false; // missing flag counts as synthetic

// ---------- messages ----------

function showMessage(text, kind = "error") {
  $("#messages").append(el("div", { class: `msg msg-${kind}` }, text));
}

function clearMessages() {
  $("#messages").replaceChildren();
}

// ---------- formatting ----------

function fmtTime(iso) {
  if (!iso) return "–";
  return iso.replace("T", " ").replace(/\.\d+/, "").replace(/Z$/, " UTC");
}

function fmtNum(v, digits) {
  return typeof v === "number" && Number.isFinite(v) ? v.toFixed(digits) : "–";
}

function fmtDuration(days) {
  const d = Math.abs(days);
  const h = d * 24;
  if (h < 1) return `${Math.round(h * 60)} min`;
  if (h < 48) return `${h.toFixed(1)} h`;
  return `${d.toFixed(1)} d`;
}

const frameById = (id) => state.frames.find((f) => f.id === id);
const safeUrl = (u) => (typeof u === "string" && /^https?:\/\//i.test(u) ? u : null);

// ---------- target picker ----------

function renderPicker() {
  const select = $("#target-select");
  select.replaceChildren(
    ...state.index.targets.map((t) => {
      const name = t.name ?? t.id;
      const tag = t.synthetic !== false && !/synthetic/i.test(name) ? " (synthetic)" : "";
      return el("option", { value: t.id }, name + tag);
    }),
  );
  select.disabled = state.index.targets.length < 2;
}

async function openTarget(id) {
  const token = ++state.loadToken;
  stopBlink();
  clearMessages();
  $("#target-select").value = id;
  $("#target-name").textContent = "Loading…";

  const base = `${state.root}${encodeURIComponent(id)}/`;
  const target = await fetchJson(`${base}target.json`);
  if (token !== state.loadToken) return; // a newer target was picked meanwhile
  const warnings = checkTarget(target, id);

  state.target = target;
  state.base = base;
  state.frames = [...target.frames].sort((a, b) => a.mjd - b.mjd);
  state.broken = new Set();
  [state.aId, state.bId] = defaultPair(state.frames);

  const url = new URL(location.href);
  url.searchParams.set("target", id);
  history.replaceState(null, "", url);

  warnings.forEach((w) => showMessage(w, "warn"));
  renderTargetHead();
  renderStage();
  renderFrameTable();
  renderProvenance();
  show(state.aId);
}

// A = first frame; B = first frame of a later epoch, else the last frame.
function defaultPair(frames) {
  const a = frames[0];
  const b = frames.find((f) => f.epoch !== a.epoch) ?? frames[frames.length - 1];
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
    const img = el("img", { src: `${state.base}${f.image}`, alt: `Frame ${f.id}`, draggable: "false" });
    img.addEventListener("error", () => {
      state.broken.add(f.id);
      document.querySelector(`tr[data-frame="${CSS.escape(f.id)}"]`)?.classList.add("broken");
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
    const row = el(
      "tr",
      { "data-frame": f.id, onclick: (e) => { if (e.target.tagName !== "INPUT") { stopBlink(); show(f.id); } } },
      el("td", {}, radio("a")),
      el("td", {}, radio("b")),
      el("td", {}, f.id),
      el("td", { title: fmtTime(f.time_utc) }, fmtTime(f.time_utc).slice(0, 16)),
      el("td", {}, String(f.epoch ?? "–")),
      el("td", {}, fmtNum(f.wavelength_um, 2)),
      el("td", {}, f.detector == null ? "–" : `D${f.detector}`),
    );
    return row;
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
  document.querySelector(`tr[data-frame="${CSS.escape(id)}"]`)?.scrollIntoView({ block: "nearest" });
  renderFrameInfo(f);
  updateStageError();
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

function stopBlink() {
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

function bindControls() {
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

  $("#target-select").addEventListener("change", (e) => {
    openTarget(e.target.value).catch((err) => showMessage(err.message));
  });

  document.addEventListener("keydown", (e) => {
    if (!state.target || e.altKey || e.ctrlKey || e.metaKey) return;
    if (e.target.closest?.("input, select, textarea, button")) {
      // let form controls keep their own keys (arrows in the slider, Space on buttons)
      if (e.key === " " || e.key.startsWith("Arrow")) return;
    }
    if (e.key === " ") { e.preventDefault(); state.playing ? stopBlink() : startBlink(); }
    else if (e.key === "x" || e.key === "X") { stopBlink(); flip(); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); step(-1); }
    else if (e.key === "ArrowRight") { e.preventDefault(); step(1); }
  });
}

async function main() {
  bindControls();
  try {
    const { root, index } = await loadIndex();
    state.root = root;
    state.index = index;
    $("#data-root").textContent = new URL(root, location.href).pathname;
    if (index.targets.length === 0) throw new Error(`${root}index.json lists no targets.`);
    renderPicker();
    const wanted = new URLSearchParams(location.search).get("target");
    const first = index.targets.find((t) => t.id === wanted) ?? index.targets[0];
    await openTarget(first.id);
    if (wanted && first.id !== wanted) showMessage(`Target "${wanted}" not found, showing "${first.id}".`, "warn");
  } catch (err) {
    $("#target-name").textContent = "Could not load data";
    showMessage(err.message);
  }
}

main();

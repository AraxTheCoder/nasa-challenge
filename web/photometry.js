// Light curves and spectra on the fly (T49). Asks the Live API for aperture photometry at a position
// (default: the field centre, i.e. the object the user asked for; "Measure a star" + click for any
// other) and draws two charts:
//  - Spectrum: brightness vs wavelength, one small panel per epoch (shared axes), the other epochs as
//    grey ghosts behind, so a change shows without needing a colour per epoch.
//  - Change at the same wavelength: for frames of consecutive epochs whose wavelengths at the star
//    match (|dλ| <= half the bandwidth), the brightness change in %. A constant star scatters around 0.
// Colours: epoch transitions use the first three categorical slots (validated, dark, all pairs);
// facets instead of a fourth colour (palette check fails for 4 on the dark surface).
// T63: on the spectrum, a baseline "what a plain star would give" (spectrum.js), rings on the points
// that leave it, optional feature markers, and plain-words hints below the chart.

import { $, el, fmtNum, fmtTime } from "./util.js";
import { currentTarget, targetBase } from "./viewer.js";
import { getApiBase, getSky } from "./explore.js";
import { nearestLabel } from "./skylabels.js";
import { analyse, FEATURES, FIT_MAX_UM, fmtT } from "./spectrum.js";

const NS = "http://www.w3.org/2000/svg";
const TRANSITION_COLOURS = ["#3987e5", "#d95926", "#199e70"]; // categorical slots 1-3, dark mode, validated
const st = { target: null, measuring: false, token: 0, pos: null, sky: null, data: null, context: true, features: false };
const home = { parent: null, next: null };   // where the panel sits in the field view (T79 moves it under the map)
let chartId = 0;

function svg(tag, attrs = {}, ...children) {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null) n.setAttribute(k, String(v));
  n.append(...children);
  return n;
}

function niceTicks(lo, hi, count = 4) {
  const span = hi - lo || 1;
  const raw = span / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => span / s <= count + 1) ?? raw;
  const out = [];
  for (let t = Math.ceil(lo / step) * step; t <= hi + step * 1e-9; t += step) out.push(+t.toFixed(10));
  return out;
}

const sig3 = (v) => String(parseFloat(v.toPrecision(3))); // 750 not 750.0, 1.25 not 1.250
const fmtFlux = (v) => (Math.abs(v) >= 1e6 ? `${sig3(v / 1e6)} Jy` : Math.abs(v) >= 1e3 ? `${sig3(v / 1e3)} mJy` : `${sig3(v)} µJy`);
const median = (xs) => {
  const s = [...xs].sort((a, b) => a - b);
  const m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
};

/**
 * Matches between an earlier and a later epoch at the same wavelength (at the star), with % change.
 * Any epoch pair counts (SPHEREx's wavelength steps rarely line up between neighbouring epochs);
 * at most 3 transitions are kept (the ones with most matches), so 3 validated colours suffice.
 */
export function matchedChanges(frames) {
  const ok = frames.filter((f) => !f.masked && f.flux_ujy > 0);
  const epochs = [...new Set(ok.map((f) => f.epoch))].sort((a, b) => a - b);
  const all = [];
  epochs.forEach((e1, i) => epochs.slice(i + 1).forEach((e2) => {
    const later = ok.filter((f) => f.epoch === e2);
    for (const a of ok.filter((f) => f.epoch === e1)) {
      const b = later.filter((x) => Math.abs(x.wavelength_um - a.wavelength_um) <=
          0.5 * Math.min(a.bandwidth_um ?? 0.05, x.bandwidth_um ?? 0.05))
        .sort((x, y) => Math.abs(x.wavelength_um - a.wavelength_um) - Math.abs(y.wavelength_um - a.wavelength_um))[0];
      if (!b) continue;
      const ratio = b.flux_ujy / a.flux_ujy;
      const err = 100 * ratio * Math.hypot((a.err_ujy ?? 0) / a.flux_ujy, (b.err_ujy ?? 0) / b.flux_ujy);
      all.push({ a, b, pct: (ratio - 1) * 100, err, wavelength: (a.wavelength_um + b.wavelength_um) / 2, key: `${e1}→${e2}` });
    }
  }));
  const counts = new Map();
  for (const c of all) counts.set(c.key, (counts.get(c.key) ?? 0) + 1);
  const kept = [...counts.entries()].sort((x, y) => y[1] - x[1]).slice(0, 3).map(([k]) => k).sort();
  const out = all.filter((c) => kept.includes(c.key)).map((c) => ({ ...c, transition: kept.indexOf(c.key) }));
  out.omitted = counts.size - kept.length;
  return out;
}

function spectrumChart(frames, width, ana) {
  // T84: exposures in a spike/dip event (server: pipeline/anomaly.py) get a red ring
  const anomalous = new Set((st.data?.anomalies?.items ?? []).flatMap((a) => a.frames ?? (a.frame_id ? [a.frame_id] : [])));
  const epochs = [...new Set(frames.map((f) => f.epoch))].sort((a, b) => a - b);
  const good = frames.filter((f) => !f.masked && Number.isFinite(f.flux_ujy));
  const H = 150, top = 22, bottom = 26, left = 52, gap = 10;
  const pw = (width - left - gap * (epochs.length - 1)) / Math.max(epochs.length, 1);
  const fl = good.map((f) => f.flux_ujy);
  const lo = Math.min(0, ...fl), hi = Math.max(1, ...fl) * 1.08;
  const yOf = (v) => top + (H - top - bottom) * (1 - (v - lo) / (hi - lo));
  const root = svg("svg", { class: "ph-svg", width, height: H, viewBox: `0 0 ${width} ${H}`, role: "img",
    "aria-label": "Spectrum: brightness against wavelength, one panel per epoch" });
  for (const t of niceTicks(lo, hi)) {
    root.append(svg("line", { class: "ph-grid", x1: left, x2: width, y1: yOf(t), y2: yOf(t) }),
      svg("text", { class: "ph-axis", x: left - 6, y: yOf(t) + 3.5, "text-anchor": "end" }, fmtFlux(t)));
  }
  const cid = `ph-clip-${++chartId}`;
  epochs.forEach((ep, i) => {
    const x0 = left + i * (pw + gap);
    const xOf = (w) => x0 + 6 + (pw - 12) * ((w - 0.7) / (5.1 - 0.7));
    root.append(
      svg("rect", { class: "ph-panel", x: x0, y: top - 4, width: pw, height: H - top - bottom + 8, rx: 4 }),
      svg("text", { class: "ph-title", x: x0 + 2, y: top - 9 }, `Epoch ${ep}`),
      svg("text", { class: "ph-axis", x: x0 + 2, y: H - 6 }, "0.7"),
      svg("text", { class: "ph-axis", x: x0 + pw - 2, y: H - 6, "text-anchor": "end" }, "5 µm"),
    );
    if (st.features) {
      for (const f of FEATURES) {
        const x = xOf(f.um);
        root.append(svg("g", { class: "ph-feature-g" }, svg("title", {}, `${f.name} · ${f.um} µm: ${f.what}`),
          svg("line", { class: "ph-feature", x1: x, x2: x, y1: top - 2, y2: H - bottom + 2 }),
          svg("line", { class: "ph-feature-hit", x1: x, x2: x, y1: top - 2, y2: H - bottom + 2 })));
      }
    }
    const e = ana?.perEpoch.get(ep);
    if (st.context && e?.fit) {
      // the baseline, clipped to the panel: solid where it was fitted, dashed where extrapolated
      const clip = `${cid}-${ep}`;
      root.append(svg("clipPath", { id: clip }, svg("rect", { x: x0, y: top - 4, width: pw, height: H - top - bottom + 8 })));
      const line = (a, b) => Array.from({ length: 40 }, (_, k) => a + (b - a) * k / 39)
        .map((w) => `${xOf(w).toFixed(1)},${yOf(Math.min(e.fit.model(w), hi * 3)).toFixed(1)}`).join(" ");
      const tip = `Baseline: ${fmtT(e.fit)} star fitted to ${e.fit.n} points below ${FIT_MAX_UM} µm` +
        (e.fit.poor ? " (poor fit: the points don't follow one star shape)" : "");
      root.append(svg("g", { "clip-path": `url(#${clip})`, class: e.fit.poor ? "ph-base-poor" : "" }, svg("title", {}, tip),
        svg("polyline", { class: "ph-base", points: line(0.7, e.fit.umMax) }),
        svg("polyline", { class: "ph-base ph-base-x", points: line(e.fit.umMax, 5.1) })));
    }
    for (const f of good.filter((g) => g.epoch !== ep)) { // ghosts: the other epochs
      root.append(svg("circle", { class: "ph-ghost", cx: xOf(f.wavelength_um), cy: yOf(f.flux_ujy), r: 2.5 }));
    }
    for (const f of frames.filter((g) => g.epoch === ep)) {
      const cx = xOf(f.wavelength_um);
      if (f.masked || !Number.isFinite(f.flux_ujy)) {
        root.append(svg("text", { class: "ph-masked", x: cx, y: H - bottom + 1, "text-anchor": "middle" }, "×",
          svg("title", {}, `${f.frame_id} · ${fmtNum(f.wavelength_um, 3)} µm · flagged (saturated or bad pixels)`)));
        continue;
      }
      const g = svg("g", { class: "ph-pt" }, svg("title", {}, `${f.frame_id} · ${fmtNum(f.wavelength_um, 3)} µm · ` +
        `${fmtFlux(f.flux_ujy)} ± ${fmtFlux(f.err_ujy ?? 0)} · ${fmtTime(f.time_utc)}`));
      if (f.err_ujy) g.append(svg("line", { class: "ph-err", x1: cx, x2: cx, y1: yOf(f.flux_ujy - f.err_ujy), y2: yOf(f.flux_ujy + f.err_ujy) }));
      g.append(svg("circle", { class: "ph-dot", cx, cy: yOf(f.flux_ujy), r: 4 }));
      const off = st.context && e?.regions.some((r) => r.points.some((p) => p.frame_id === f.frame_id));
      if (off) g.append(svg("circle", { class: "ph-flag", cx, cy: yOf(f.flux_ujy), r: 7 }));
      if (anomalous.has(f.frame_id)) g.append(svg("circle", { class: "ph-anom", cx, cy: yOf(f.flux_ujy), r: 9 }));
      root.append(g);
    }
  });
  return root;
}

function changeChart(changes, width) {
  const H = 140, top = 12, bottom = 26, left = 52;
  const vals = changes.flatMap((c) => [c.pct - c.err, c.pct + c.err]);
  const m = Math.max(10, ...vals.map(Math.abs)) * 1.1;
  const yOf = (v) => top + (H - top - bottom) * (1 - (v + m) / (2 * m));
  const xOf = (w) => left + 6 + (width - left - 12) * ((w - 0.7) / (5.1 - 0.7));
  const root = svg("svg", { class: "ph-svg", width, height: H, viewBox: `0 0 ${width} ${H}`, role: "img",
    "aria-label": "Brightness change between consecutive epochs at matched wavelengths" });
  root.append(svg("rect", { class: "ph-panel", x: left, y: top - 4, width: width - left, height: H - top - bottom + 8, rx: 4 }));
  for (const t of niceTicks(-m, m, 4)) {
    root.append(svg("line", { class: t === 0 ? "ph-zero" : "ph-grid", x1: left, x2: width, y1: yOf(t), y2: yOf(t) }),
      svg("text", { class: "ph-axis", x: left - 6, y: yOf(t) + 3.5, "text-anchor": "end" }, `${t > 0 ? "+" : ""}${fmtNum(t, 0)}%`));
  }
  for (const w of [1, 2, 3, 4, 5]) root.append(svg("text", { class: "ph-axis", x: xOf(w), y: H - 6, "text-anchor": "middle" }, `${w} µm`));
  for (const c of changes) {
    const colour = TRANSITION_COLOURS[c.transition % TRANSITION_COLOURS.length];
    const x = xOf(c.wavelength);
    root.append(svg("g", { class: "ph-pt" },
      svg("title", {}, `epoch ${c.a.epoch} → ${c.b.epoch} at ${fmtNum(c.wavelength, 3)} µm: ${c.pct > 0 ? "+" : ""}${fmtNum(c.pct, 1)}% ± ${fmtNum(c.err, 1)}% (${c.a.frame_id} → ${c.b.frame_id})`),
      svg("line", { class: "ph-err", x1: x, x2: x, y1: yOf(c.pct - c.err), y2: yOf(c.pct + c.err) }),
      svg("circle", { class: "ph-dot-c", cx: x, cy: yOf(c.pct), r: 4.5, fill: colour })));
  }
  return root;
}

function render() {
  const box = $("#photometry");
  const body = $("#ph-body");
  const d = st.data;
  if (!d) return;
  const w = Math.max(300, Math.round(body.clientWidth || 600));
  const frames = d.frames ?? [];
  const good = frames.filter((f) => !f.masked && Number.isFinite(f.flux_ujy));
  // T84: exposures of a spike/dip event (e.g. an asteroid passing) stay in the spectrum chart (ringed)
  // but not in the baseline hints or the light curve, which would otherwise read them as the source.
  const odd = new Set((d.anomalies?.items ?? []).flatMap((a) => a.frames ?? (a.frame_id ? [a.frame_id] : [])));
  const steady = odd.size ? frames.filter((f) => !odd.has(f.frame_id)) : frames;
  const changes = matchedChanges(steady);
  const at = `(RA ${fmtNum(d.ra_deg, 4)}°, Dec ${fmtNum(d.dec_deg, 4)}°)`;
  const where = st.sky ? `at the point clicked on the map ${at}` : st.pos ? `at the clicked star ${at}` : `at the field centre ${at}`;
  const what = d.all_exposures ? `exposures (all SPHEREx images of this spot)` : "frames";
  const parts = [el("p", { class: "ph-where small" }, `${good.length} of ${frames.length} ${what} measured ${where}.`)];
  if (frames.length && !good.length) {
    parts.push(el("p", { class: "msg msg-warn" }, "Every frame is flagged at this position: the star is saturated " +
      "(too bright for SPHEREx) or sits on bad pixels, so aperture photometry can't measure it."));
  }
  if (good.length) {
    const ana = analyse(steady);
    parts.push(el("h4", {}, "Spectrum (brightness vs. wavelength)"), spectrumToggles(), spectrumChart(frames, w, ana),
      el("p", { class: "muted small" }, "One panel per epoch; grey dots are the other epochs, × marks flagged frames." +
        (st.context ? " Line: what a plain star would give (dashed where extrapolated); ringed points leave it." : "")));
    if (st.features) {
      parts.push(el("p", { class: "muted small ph-features-key" }, "Feature markers (hover a dotted line): " +
        FEATURES.map((f) => `${f.name} ${f.um}`).join(" · ") + " µm"));
    }
    if (st.context) parts.push(contextBox(ana));
    if (d.anomalies) parts.push(anomalyBox(d.anomalies));
    const legend = [...new Set(changes.map((c) => c.transition))].map((k) => {
      const c = changes.find((x) => x.transition === k);
      const sub = changes.filter((x) => x.transition === k).map((x) => x.pct);
      const med = median(sub);
      const mixed = sub.some((v) => v > 0) && sub.some((v) => v < 0);
      return el("span", { class: "ph-key" }, el("span", { class: "ph-swatch", style: `background:${TRANSITION_COLOURS[k % 3]}` }),
        ` epoch ${c.a.epoch} → ${c.b.epoch}: median ${med > 0 ? "+" : ""}${fmtNum(med, 0)}% (${sub.length} match${sub.length === 1 ? "" : "es"}${mixed ? ", mixed signs" : ""})`);
    });
    parts.push(el("h4", {}, "Change at the same wavelength (light curve)"),
      changes.length ? changeChart(changes, w) : el("p", { class: "muted small" }, "No frames of different epochs at the same wavelength here."),
      changes.length ? el("p", { class: "ph-legend small" }, ...legend) : null,
      el("p", { class: "muted small" }, "Each dot compares two frames of different epochs whose wavelengths at the star match " +
        "(within half a channel). Near 0% = constant; clearly above or below at several wavelengths = the star changed." +
        (changes.omitted ? ` ${changes.omitted} more epoch pair(s) with fewer matches not shown.` : "")));
  }
  parts.push(el("p", { class: "muted small" }, d.note ?? ""));
  body.replaceChildren(...parts);
  box.hidden = false;
}

function spectrumToggles() {
  const box = (key, label) => {
    const input = el("input", { type: "checkbox" });
    input.checked = st[key];
    input.addEventListener("change", () => { st[key] = input.checked; render(); });
    return el("label", { class: "ph-toggle small" }, input, ` ${label}`);
  };
  return el("div", { class: "ph-toggles" }, box("context", "Expected + hints"), box("features", "Feature markers"));
}

/** "What this spectrum says": the baseline, the regions that leave it, and why they could be interesting. */
/** T84: what changed in a non-continuous way (server-side, all exposures only). */
function anomalyBox(an) {
  const items = an.items ?? [];
  const kindWord = { spike: "Spike", dip: "Dip", level: "Brightness change", shape: "Shape change" };
  return el("div", { class: "ph-context ph-anomalies" },
    el("h4", {}, "What changed in a non-continuous way"),
    el("p", { class: items.length ? "" : "muted" }, an.summary ?? ""),
    items.length ? el("ul", { class: "ph-anom-list" }, ...items.slice(0, 8).map((a) =>
      el("li", {}, el("strong", { class: a.known?.length ? "ph-anom-known" : "" }, `${kindWord[a.type] ?? a.type}: `), a.reason))) : null,
    items.length > 8 ? el("p", { class: "muted small" }, `${items.length - 8} more.`) : null,
    el("p", { class: "muted small" }, "Red rings in the spectrum: the exposures of a spike or dip. " + (an.method ?? "")));
}

function contextBox(ana) {
  const out = [el("h4", {}, "What this spectrum says")];
  const eps = (list) => (list.length === 1 ? `epoch ${list[0]}` : `epochs ${list.join(", ")}`);
  if (ana.saturated) {
    out.push(el("p", { class: "small" }, `No baseline: the points below ${FIT_MAX_UM} µm are flagged (saturated or bad pixels), ` +
      "so there is nothing to tell what a plain star of this colour would give."));
    return el("div", { class: "ph-context" }, ...out);
  }
  if (ana.noFit) {
    out.push(el("p", { class: "small" }, `No baseline: no epoch has 3 or more good points below ${FIT_MAX_UM} µm.`));
    return el("div", { class: "ph-context" }, ...out);
  }
  const fitted = [...ana.perEpoch.entries()].filter(([, e]) => e.fit);
  out.push(el("p", { class: "small" }, `Baseline: a blackbody fitted to each epoch's points below ${FIT_MAX_UM} µm, i.e. what a ` +
    "plain star of that colour would give (" + fitted.map(([ep, e]) => `epoch ${ep}: ${e.fit.poor ? "no good fit" : fmtT(e.fit).replace(/^a /, "")}`).join("; ") + ")."));
  if (ana.poorEpochs.length) {
    out.push(el("p", { class: "small ph-hint" }, el("strong", {}, `In ${eps(ana.poorEpochs)} the short-wavelength points don't follow one star shape. `),
      "Absorption bands (water, methane: a cool atmosphere such as a brown dwarf's), two sources blended in one aperture, " +
      "or the source changed while it was observed?"));
  }
  for (const r of ana.regions) {
    out.push(el("p", { class: "small ph-hint" }, el("span", { class: "ph-hint-mark", "aria-hidden": "true" }, r.sign > 0 ? "▲ " : "▼ "),
      el("strong", {}, `${r.hint.title}. `), r.hint.text, el("span", { class: "muted" }, ` (${eps(r.epochs)}, ${r.n} points)`)));
  }
  if (!ana.regions.length && !ana.poorEpochs.length) {
    out.push(el("p", { class: "small" }, "No group of points leaves the baseline by more than 3σ and 30 %: up to 5 µm this looks " +
      "like a plain star (within the ~10 % calibration)."));
  }
  out.push(el("p", { class: "muted small" }, "Hints, not results: they say what usually causes such a shape, not what this source is. " +
    "Each SPHEREx point is a different exposure, so a variable source can bend the spectrum too."));
  return el("div", { class: "ph-context" }, ...out);
}

function drawMarker() {
  let g = document.getElementById("ph-layer");
  if (!g) {
    g = document.createElementNS(NS, "g");
    g.id = "ph-layer";
    $("#overlay").append(g);
  }
  g.replaceChildren();
  if (!st.pos) return;
  const { x, y } = st.pos;
  g.append(svg("circle", { class: "ph-marker", cx: x, cy: y, r: 3, "vector-effect": "non-scaling-stroke" }),
    svg("line", { class: "ph-marker", x1: x - 6, x2: x - 3.5, y1: y, y2: y, "vector-effect": "non-scaling-stroke" }),
    svg("line", { class: "ph-marker", x1: x + 3.5, x2: x + 6, y1: y, y2: y, "vector-effect": "non-scaling-stroke" }));
}

async function load() {
  const base = targetBase();
  const t = currentTarget();
  if (!base || !t) return;
  const token = ++st.token;
  const url = new URL("photometry", base);
  if (st.pos) {
    url.searchParams.set("x", st.pos.x.toFixed(2));
    url.searchParams.set("y", st.pos.y.toFixed(2));
  }
  $("#photometry").hidden = false;
  $("#ph-status").textContent = "measuring…";
  try {
    const res = await fetch(url, { cache: "no-cache" });
    const body = await res.json().catch(() => null);
    if (token !== st.token) return;
    if (!res.ok || body?.status !== "ready") {
      // Offline folders (no API) and synthetic fields (server: no_data) have nothing to measure: no panel.
      // Real failures (e.g. 500) keep the panel and say why.
      const nothing = !body || res.status === 404 || body.status === "no_data";
      $("#photometry").hidden = nothing;
      $("#ph-body").replaceChildren(el("p", { class: "muted small" }, nothing ? "" : `Photometry failed: ${body.message ?? res.status}`));
      $("#ph-status").textContent = "";
      return;
    }
    st.data = body;
    $("#ph-status").textContent = "";
    render();
    loadAll(url, token);
  } catch {
    if (token === st.token) { $("#photometry").hidden = true; }
  }
}

/**
 * T66: the field keeps ~40 frames for blinking, but ~300 SPHEREx exposures cover each position. Once the
 * quick answer is shown, ask for all of them (the server measures tiny cutouts in the background, ~15-30 s
 * the first time, then cached) and redraw the spectrum and light curve with every point.
 */
async function loadAll(url, token) {
  const all = new URL(url);
  all.searchParams.set("all", "1");
  try {
    for (let i = 0; i < 300; i++) {
      const res = await fetch(all, { cache: "no-cache" });
      const body = await res.json().catch(() => null);
      if (token !== st.token) return;
      if (body?.status === "ready") {
        st.data = body;
        $("#ph-status").textContent = `all ${body.frames?.length ?? 0} exposures`;
        render();
        return;
      }
      if (body?.status !== "building") throw new Error(body?.message ?? `HTTP ${res.status}`);
      $("#ph-status").textContent = body.total ? `adding all exposures… ${body.done}/${body.total}` : "adding all exposures…";
      await new Promise((r) => setTimeout(r, 1000));
    }
  } catch (err) {
    if (token === st.token) $("#ph-status").textContent = `field frames only (all exposures failed: ${err.message})`;
  }
}

/** T79: the panel under the frame viewer (field) or right under the map (a map click). */
function placePanel(underMap) {
  const panel = $("#photometry");
  if (!home.parent) { home.parent = panel.parentNode; home.next = panel.nextSibling; }
  if (underMap) { if (panel.previousElementSibling !== $("#explore")) $("#explore").after(panel); }
  else if (panel.parentNode !== home.parent) home.parent.insertBefore(panel, home.next);
}

/** A click on the frame image (in or out of "Measure a star" mode): measure there. */
function measureAtStage(e) {
  const t = currentTarget();
  if (!t) return;
  const r = $("#stage").getBoundingClientRect();
  const { width = 1, height = 1 } = t.image ?? {};
  st.pos = { x: ((e.clientX - r.left) / r.width) * width - 0.5, y: ((e.clientY - r.top) / r.height) * height - 0.5 };
  st.sky = null;
  setMeasuring(false);
  placePanel(false);
  drawMarker();
  getSky()?.redraw();
  load();
}

/** T79: a click on the map: every exposure at that sky point, no field needed. */
async function loadSky(ra, dec) {
  const api = getApiBase();
  if (!api) return;
  const token = ++st.token;
  st.sky = { ra, dec };
  st.pos = null;
  st.data = null;
  drawMarker();
  getSky()?.redraw();
  placePanel(true);
  $("#photometry").hidden = false;
  $("#ph-body").replaceChildren(el("p", { class: "muted small" },
    `Measuring every SPHEREx exposure at RA ${fmtNum(ra, 4)}°, Dec ${fmtNum(dec, 4)}° (the first time takes ~15-30 s)…`));
  $("#ph-status").textContent = "measuring…";
  $("#photometry").scrollIntoView({ block: "nearest", behavior: "smooth" });
  await loadAll(`${api.replace(/\/$/, "")}/api/photometry?ra=${ra.toFixed(5)}&dec=${dec.toFixed(5)}`, token);
}

function mapMarker(ctx, proj) {
  if (!st.sky) return;
  const s = proj.toScreen(st.sky.ra, st.sky.dec);
  if (!s.front) return;
  ctx.save();
  ctx.strokeStyle = "#ffd27a"; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.arc(s.x, s.y, 7, 0, 2 * Math.PI); ctx.stroke();
  for (const [a, b] of [[-14, -9], [9, 14]]) {
    ctx.beginPath(); ctx.moveTo(s.x + a, s.y); ctx.lineTo(s.x + b, s.y); ctx.moveTo(s.x, s.y + a); ctx.lineTo(s.x, s.y + b); ctx.stroke();
  }
  ctx.restore();
}

/** Map: a press + release that barely moved is a click (a drag pans); wait a moment so a double click still zooms. */
function hookMap() {
  const sky = getSky();
  const box = $("#sky");
  if (!sky || !box || box.dataset.phClick) return;
  box.dataset.phClick = "1";
  let proj = null, down = null, timer = null;
  sky.addDrawHook((ctx, p) => { proj = p; mapMarker(ctx, p); });
  box.addEventListener("pointerdown", (e) => { down = e.isPrimary ? { x: e.clientX, y: e.clientY } : null; });
  box.addEventListener("pointerup", (e) => {
    const d = down;
    down = null;
    if (!d || !proj || Math.hypot(e.clientX - d.x, e.clientY - d.y) > 4) return;
    if (e.target.closest?.("button, a, input, select, label, .paths-tip")) return;
    clearTimeout(timer);
    const canvas = box.querySelector("canvas") ?? box;
    const r = canvas.getBoundingClientRect();
    const px = e.clientX - r.left, py = e.clientY - r.top;
    timer = setTimeout(() => {
      const snap = nearestLabel(px, py);   // a labelled dot within a few px wins
      const pos = snap ? [snap.ra_deg, snap.dec_deg] : proj.fromScreen(px, py);
      if (pos) loadSky(((pos[0] % 360) + 360) % 360, pos[1]);
    }, 280);
  });
  box.addEventListener("dblclick", () => clearTimeout(timer));
}

function setMeasuring(on) {
  st.measuring = on;
  if (on) $("#stage").scrollIntoView({ block: "nearest", behavior: "smooth" }); // the button sits below the image
  $("#ph-measure").setAttribute("aria-pressed", String(on));
  $("#stage").classList.toggle("is-measuring", on);
  $("#ph-catcher").hidden = !on;
}

export function initPhotometry() {
  $("#ph-measure").addEventListener("click", () => setMeasuring(!st.measuring));
  $("#ph-centre").addEventListener("click", () => { st.pos = null; drawMarker(); load(); });
  $("#ph-catcher").addEventListener("click", measureAtStage);
  // T79: a plain click on the image measures too; clicks on labels/paths keep opening the inspector.
  $("#stage").addEventListener("click", (e) => {
    if (st.measuring || e.target.closest?.(".path-hit, .paths-tip, #ph-catcher, button, a, input, select, label")) return;
    measureAtStage(e);
  });
  document.addEventListener("explore:ready", hookMap);
  hookMap();
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && st.measuring) setMeasuring(false); });
  document.addEventListener("viewer:target", (e) => {
    st.target = e.detail?.target ?? null;
    st.pos = null;
    st.sky = null;
    placePanel(false);
    getSky()?.redraw();
    st.data = null;
    document.getElementById("ph-layer")?.remove();
    setMeasuring(false);
    $("#photometry").hidden = true;
    if (st.target) load(); // the server decides: synthetic fields answer no_data
  });
  let lastW = 0;
  new ResizeObserver(([entry]) => {
    const w = Math.round(entry.contentRect.width);
    if (w !== lastW && st.data) { lastW = w; render(); }
  }).observe($("#ph-body"));
}

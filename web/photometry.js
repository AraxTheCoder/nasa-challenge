// Selected-position aperture brightness (T49/T140). Spectrum shows one survey visit at a time;
// Changes between visits compares matched wavelengths, with one earlier/later visit pair selected.
// Model hints, reference features and quality details remain optional. T138's selection/loading stays separate.

import { $, el, fmtNum, fmtTime } from "./util.js";
import { currentTarget, targetBase } from "./viewer.js";
import { getApiBase, getSky } from "./explore.js";
import { nearestLabel } from "./skylabels.js";
import { analyse, FEATURES, FIT_MAX_UM, fmtT } from "./spectrum.js";
import { motionBox } from "./motion.js";
import { analysisNote } from "./analysisnote.js";
import { anomalyCopy, LIMITS } from "./analysiscopy.js";

import { usable, measurementError, periodKey, observingPeriods, matchedChanges, comparisonGroups } from "./brightness.js";
export { matchedChanges } from "./brightness.js";
const NS = "http://www.w3.org/2000/svg";
const CHANGE_COLOUR = "#6da7ec";
const st = { target: null, measuring: false, token: 0, pos: null, sky: null, data: null, context: false, features: false, compare: false, view: "spectrum", epoch: null, pair: null, details: {} };
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
function spectrumChart(frames, width, ana) {
  // T84: exposures in a spike/dip event (server: pipeline/anomaly.py) get a red ring
  const anomalous = new Set((st.data?.anomalies?.items ?? []).flatMap((a) => a.frames ?? (a.frame_id ? [a.frame_id] : [])));
  const epochs = [st.epoch];
  const good = frames.filter(usable);
  const H = 248, top = 28, bottom = 46, left = 64, gap = 10;
  const pw = (width - left - gap * (epochs.length - 1)) / Math.max(epochs.length, 1);
  const fl = good.flatMap((f) => [f.flux_ujy - (measurementError(f) ?? 0), f.flux_ujy + (measurementError(f) ?? 0)]);
  const lo = Math.min(0, ...fl), hi = Math.max(1, ...fl) * 1.08;
  const yOf = (v) => top + (H - top - bottom) * (1 - (v - lo) / (hi - lo));
  const root = svg("svg", { class: "ph-svg", width, height: H, viewBox: `0 0 ${width} ${H}`, role: "img",
    "aria-label": "Spectrum: brightness against infrared wavelength for the selected observing visit" });
  root.append(svg("text", { class: "ph-axis", x: left, y: 12 }, "Brightness"),
    svg("text", { class: "ph-axis", x: left + (width - left) / 2, y: H - 6, "text-anchor": "middle" }, "Wavelength (µm)"));
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
      svg("title", {}, ep === "unknown" ? "Undated observations" : `Visit ${ep}`),
    );
    for (const w of [1, 2, 3, 4, 5]) root.append(svg("text", { class: "ph-axis", x: xOf(w), y: H - 26, "text-anchor": "middle" }, String(w)));
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
    for (const f of good.filter((g) => st.compare && periodKey(g) !== ep)) { // ghosts: the other epochs
      root.append(svg("circle", { class: "ph-ghost", cx: xOf(f.wavelength_um), cy: yOf(f.flux_ujy), r: 2.5 }));
    }
    for (const f of frames.filter((g) => periodKey(g) === ep)) {
      if (!Number.isFinite(f.wavelength_um)) continue;
      const cx = xOf(f.wavelength_um);
      if (f.masked || !Number.isFinite(f.flux_ujy)) {
        root.append(svg("text", { class: "ph-masked", x: cx, y: H - bottom + 1, "text-anchor": "middle" }, "×",
          svg("title", {}, `${f.frame_id} · ${fmtNum(f.wavelength_um, 3)} µm · flagged (saturated or bad pixels)`)));
        continue;
      }
      const error = measurementError(f);
      const g = svg("g", { class: "ph-pt" }, svg("title", {}, `${f.frame_id} · ${fmtNum(f.wavelength_um, 3)} µm · ` +
        `${fmtFlux(f.flux_ujy)}${error == null ? " · uncertainty unavailable" : ` ± ${fmtFlux(error)}`} · ${fmtTime(f.time_utc)}`));
      if (error != null) g.append(svg("line", { class: "ph-err", x1: cx, x2: cx, y1: yOf(f.flux_ujy - error), y2: yOf(f.flux_ujy + error) }));
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
  const H = 248, top = 28, bottom = 46, left = 64;
  const vals = changes.flatMap((c) => [c.pct - (c.err ?? 0), c.pct + (c.err ?? 0)]);
  const m = Math.max(10, ...vals.map(Math.abs)) * 1.1;
  const yOf = (v) => top + (H - top - bottom) * (1 - (v + m) / (2 * m));
  const xOf = (w) => left + 6 + (width - left - 12) * ((w - 0.7) / (5.1 - 0.7));
  const root = svg("svg", { class: "ph-svg", width, height: H, viewBox: `0 0 ${width} ${H}`, role: "img",
    "aria-label": "Brightness difference by wavelength between the selected earlier and later visits" });
  root.append(svg("text", { class: "ph-axis", x: left, y: 12 }, "Change (%)"),
    svg("text", { class: "ph-axis", x: left + (width - left) / 2, y: H - 6, "text-anchor": "middle" }, "Wavelength (µm)"));
  root.append(svg("rect", { class: "ph-panel", x: left, y: top - 4, width: width - left, height: H - top - bottom + 8, rx: 4 }));
  for (const t of niceTicks(-m, m, 4)) {
    root.append(svg("line", { class: t === 0 ? "ph-zero" : "ph-grid", x1: left, x2: width, y1: yOf(t), y2: yOf(t) }),
      svg("text", { class: "ph-axis", x: left - 6, y: yOf(t) + 3.5, "text-anchor": "end" }, `${t > 0 ? "+" : ""}${fmtNum(t, 0)}%`));
  }
  for (const w of [1, 2, 3, 4, 5]) root.append(svg("text", { class: "ph-axis", x: xOf(w), y: H - 26, "text-anchor": "middle" }, String(w)));
  for (const c of changes) {
    const colour = CHANGE_COLOUR;
    const x = xOf(c.wavelength);
    root.append(svg("g", { class: "ph-pt" },
      svg("title", {}, `epoch ${c.a.epoch} → ${c.b.epoch} at ${fmtNum(c.wavelength, 3)} µm: ${c.pct > 0 ? "+" : ""}${fmtNum(c.pct, 1)}%${c.err == null ? " · uncertainty unavailable" : ` ± ${fmtNum(c.err, 1)}%`} (${c.a.frame_id} → ${c.b.frame_id})`),
      ...(c.err == null ? [] : [svg("line", { class: "ph-err", x1: x, x2: x, y1: yOf(c.pct - c.err), y2: yOf(c.pct + c.err) })]),
      svg("circle", { class: "ph-dot-c", cx: x, cy: yOf(c.pct), r: 4.5, fill: colour })));
  }
  return root;
}

function disclosure(id, label, ...children) {
  const box = el("details", { id, class: "ph-details" }, el("summary", { id: `${id}-toggle` }, label), ...children);
  box.open = Boolean(st.details[id]);
  box.addEventListener("toggle", () => { if (box.isConnected) st.details[id] = box.open; });
  return box;
}
function selectControl(id, label, options, value, change) {
  const select = el("select", { id }, ...options.map(([key, text]) => el("option", { value: key }, text)));
  select.value = String(value);
  select.addEventListener("change", () => { change(select.value); render(); });
  return el("label", { class: "ph-select", for: id }, el("span", { class: "small muted" }, label), select);
}
function viewTabs() {
  const tabs = [["spectrum", "Spectrum"], ["changes", "Changes between visits"]].map(([key, label]) => {
    const button = el("button", { id: `ph-${key}-tab`, type: "button", role: "tab", "aria-selected": String(st.view === key),
      "aria-controls": `ph-${key}-view`, tabindex: st.view === key ? "0" : "-1" }, label);
    button.addEventListener("click", () => { st.view = key; render(); });
    button.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
      event.preventDefault(); event.stopPropagation();
      st.view = event.key === "Home" ? "spectrum" : event.key === "End" ? "changes" : st.view === "spectrum" ? "changes" : "spectrum";
      render(); $(`#ph-${st.view}-tab`)?.focus({ preventScroll: true });
    });
    return button;
  });
  return el("div", { class: "ph-view-tabs", role: "tablist", "aria-label": "Brightness view" }, ...tabs);
}
function render() {
  const box = $("#photometry"), body = $("#ph-body"), d = st.data;
  if (!d) return;
  const focusId = body.contains(document.activeElement) ? document.activeElement.id : null;
  for (const detail of body.querySelectorAll("details.ph-details")) st.details[detail.id] = detail.open;
  const w = Math.max(220, Math.round(body.clientWidth || 600));
  const frames = d.frames ?? [], good = frames.filter(usable), periods = observingPeriods(frames);
  const odd = new Set((d.anomalies?.items ?? []).flatMap((a) => a.frames ?? (a.frame_id ? [a.frame_id] : [])));
  const steady = odd.size ? frames.filter((f) => !odd.has(f.frame_id)) : frames;
  const changes = matchedChanges(steady), groups = comparisonGroups(changes);
  if (!periods.some((p) => p.id === st.epoch)) st.epoch = [...periods].sort((a, b) => b.usable - a.usable)[0]?.id;
  if (!groups.some((g) => g.key === st.pair)) st.pair = groups[0]?.key ?? null;
  const period = periods.find((p) => p.id === st.epoch), comparison = groups.find((g) => g.key === st.pair);
  const at = `(RA ${fmtNum(d.ra_deg, 4)}°, Dec ${fmtNum(d.dec_deg, 4)}°)`;
  const where = st.sky?.name ? `at ${st.sky.name} ${at}` : st.sky ? `at the point clicked on the map ${at}` : st.pos ? `at the clicked star ${at}` : `at the field centre ${at}`;
  const what = d.all_exposures ? "exposures" : "frames";
  const parts = [el("p", { class: "ph-where small muted" }, `${good.length} of ${frames.length} ${what} measured ${where}.`),
    el("p", { class: "ph-intro" }, "Explore the infrared light measured in a small circle around this position."), viewTabs()];
  if (!good.length) {
    for (const view of ["spectrum", "changes"]) parts.push(el("section", { id: `ph-${view}-view`, role: "tabpanel", "aria-labelledby": `ph-${view}-tab`, hidden: st.view !== view },
      el("div", { class: "ph-empty", role: "status" }, el("h4", {}, frames.length ? "No usable brightness measurements" : "No observations at this position"),
      el("p", { class: "muted" }, frames.length ? "Every measurement is flagged or unavailable. Try a nearby source or check Data quality below." : "Try another position or wait for more observations to finish loading."))));
  } else {
    const ana = analyse(steady.filter((f) => Number.isFinite(f.wavelength_um)));
    const spectrum = el("section", { id: "ph-spectrum-view", role: "tabpanel", "aria-labelledby": "ph-spectrum-tab", hidden: st.view !== "spectrum" },
      el("h4", {}, "Where is this source brightest?"),
      el("p", { class: "small muted" }, "Left to right: infrared wavelength. Higher dots: more light. Each dot is a separate exposure; the small bars show measurement uncertainty where available."),
      selectControl("ph-epoch", "Observing visit", periods.map((p) => [p.id, `${p.label} · ${p.dates}`]), st.epoch,
        (value) => { st.epoch = periods.find((p) => String(p.id) === value)?.id; }),
      el("p", { class: "ph-visit-count small muted" }, `${period?.usable ?? 0} usable of ${period?.total ?? 0} observations in this visit. The brightness scale stays the same when you switch visits.`),
      spectrumChart(frames, w, ana),
      el("p", { class: "ph-legend small muted" }, "● measured brightness · × flagged observation", st.compare ? " · grey dots: other visits" : ""),
      disclosure("ph-overlays", "Overlays and interpretation", spectrumToggles(),
        st.context ? contextBox(ana) : el("p", { class: "small muted" }, "The approximate stellar model is optional. It is a comparison shape, not an object identification."),
        st.features ? el("p", { class: "ph-features-key small muted" }, "Reference wavelengths: " + FEATURES.map((f) => `${f.name} ${f.um}`).join("; ") + " µm. A nearby marker does not confirm a molecule.") : null));
    const pairLabel = (g) => {
      const first = periods.find((p) => p.id === g.earlier), last = periods.find((p) => p.id === g.later);
      return `${first?.label ?? g.earlier} → ${last?.label ?? g.later} · ${g.changes.length} wavelength match${g.changes.length === 1 ? "" : "es"}`;
    };
    const comparisonView = el("section", { id: "ph-changes-view", role: "tabpanel", "aria-labelledby": "ph-changes-tab", hidden: st.view !== "changes" },
      el("h4", {}, "Did the brightness change between visits?"),
      el("p", { class: "small muted" }, "Compare nearly the same wavelength on two visits. +50% means brighter in the later visit; −50% means dimmer. The zero line means no measured change."),
      comparison ? selectControl("ph-pair", "Earlier → later visit", groups.map((g) => [g.key, pairLabel(g)]), st.pair, (value) => { st.pair = value; }) : null,
      comparison ? el("p", { class: "ph-comparison-dates small muted" }, `${periods.find((p) => p.id === comparison.earlier)?.dates} → ${periods.find((p) => p.id === comparison.later)?.dates}`) : null,
      comparison ? el("p", { class: "ph-change-summary" }, `Median measured difference: ${comparison.median >= 0 ? "+" : ""}${fmtNum(comparison.median, 0)}% · ${comparison.changes.length} wavelength match${comparison.changes.length === 1 ? "" : "es"}`) : null,
      comparison ? changeChart(comparison.changes, w) : el("p", { class: "ph-empty muted" }, periods.filter((p) => p.id !== "unknown").length < 2
        ? "At least two observing visits are needed. There is no between-visit comparison yet."
        : "These visits have no usable, positive-brightness measurements close enough in wavelength to compare. Missing matches do not mean the source stayed constant."),
      comparison ? el("p", { class: "ph-legend small muted" }, "Each dot is one wavelength match. Bars, where available, show measurement uncertainty; a bar crossing zero is consistent with no change.") : null,
      el("p", { class: "small muted" }, "Wavelength is on the horizontal axis here too. Calibration, source motion and nearby sources can also affect a measured difference."),
      odd.size ? el("p", { class: "small muted" }, `${odd.size} observations flagged as possible brief events are left out of this comparison; they remain marked in Spectrum.`) : null,
      d.anomalies?.items?.length ? disclosure("ph-events", "Possible brief events", anomalyBox(d.anomalies)) : null);
    parts.push(spectrum, comparisonView);
  }
  const excluded = frames.length - good.length;
  parts.push(disclosure("ph-quality", `Data quality · ${excluded} excluded observation${excluded === 1 ? "" : "s"}`,
    el("p", { class: "small muted" }, `${good.length} usable of ${frames.length} ${what}. Flagged or missing measurements are excluded from comparisons. A flag can come from the source, a neighbour or the background.`), flagsBox(d)),
    disclosure("ph-method", "How is brightness measured?",
      el("p", {}, "For each exposure, the app adds the light in a small circle around the selected position and subtracts the nearby sky background. Flux in µJy is a brightness measure: a larger number means more light."),
      el("p", {}, "Spectrum shows brightness against infrared wavelength, one observing visit at a time. A visit groups exposures from a survey epoch; its wavelengths may have been observed on different dates."),
      el("p", {}, "Changes between visits compares an earlier and later exposure only when their wavelengths differ by no more than half of the narrower spectral channel. Percent change is relative to the earlier exposure. These are comparisons by wavelength, not a time-axis light curve."),
      el("p", { class: "muted" }, "The measuring circle can include neighbours. The approximate aperture correction and calibration limit how precisely you can interpret the spectral shape or a brightness change."),
      d.note ? el("p", { class: "small muted" }, d.note) : null));
  parts.push(motionBox(d.ra_deg, d.dec_deg));
  body.replaceChildren(...parts.filter(Boolean));
  box.hidden = false;
  if (focusId) document.getElementById(focusId)?.focus({ preventScroll: true });
}
function spectrumToggles() {
  const box = (key, label) => {
    const input = el("input", { id: `ph-${key}`, type: "checkbox" });
    input.checked = st[key];
    input.addEventListener("change", () => { st[key] = input.checked; render(); });
    return el("label", { class: "ph-toggle small" }, input, ` ${label}`);
  };
  return el("div", { class: "ph-toggles" }, box("compare", "Show other visits in grey"), box("context", "Approximate stellar model"), box("features", "Feature markers"));
}

/** "What this spectrum says": the baseline, the regions that leave it, and why they could be interesting. */
/** T84: what changed in a non-continuous way (server-side, all exposures only). */
function anomalyBox(an) {
  const items = an.items ?? [];
  return el("div", { class: "ph-context ph-anomalies" },
    el("h4", {}, "Possible changes"),
    analysisNote(items.length ? `${items.length} change${items.length === 1 ? "" : "s"} flagged · cause uncertain` : "No changes passed this check",
      `These comparisons can flag intrinsic changes or measurement effects. Non-detection does not establish a constant source. ${an.method ?? ""}`, "muted small"),
    items.length ? el("ul", { class: "ph-anom-list" }, ...items.slice(0, 8).map((a) => {
      const copy = anomalyCopy(a);
      return el("li", {}, analysisNote(copy.brief, copy.detail));
    })) : null,
    items.length > 8 ? el("p", { class: "muted small" }, `${items.length - 8} more.`) : null);
}

/** T60: SPHEREx's own quality flags at this spot: which ones, in how many exposures, and what they mean. */
function flagsBox(d) {
  const frames = d.frames ?? [];
  if (!frames.some((f) => Array.isArray(f.flags))) return null;      // measured before T60: no flags stored
  const count = new Map();
  for (const f of frames) for (const n of f.flags ?? []) count.set(n, (count.get(n) ?? 0) + 1);
  const mean = d.flag_meanings ?? {};
  const order = { bad: 0, warn: 1, info: 2 };
  const rows = [...count.entries()].sort((a, b) => (order[mean[a[0]]?.kind] ?? 1) - (order[mean[b[0]]?.kind] ?? 1) || b[1] - a[1]);
  const word = { bad: "unreliable", warn: "look twice", info: "note" };
  return el("div", { class: "ph-context ph-flags" },
    el("h4", {}, "SPHEREx quality flags at this spot"),
    rows.length ? el("ul", { class: "ph-flag-list" }, ...rows.map(([n, c]) => {
      const m = mean[n] ?? { kind: "warn", meaning: "" };
      return el("li", {}, el("span", { class: `ph-flag ph-flag-${m.kind}`, title: word[m.kind] ?? "" }, n),
        analysisNote(`${c}/${frames.length} exposures`, `${m.meaning || "Quality flag reported by SPHEREx."} Set somewhere in the measuring aperture; this does not necessarily describe the source itself.`));
    })) : el("p", { class: "muted" }, `No flag set within the aperture in any of the ${frames.length} exposures.`),
    analysisNote("Flags indicate measurement quality", "Flags are supplied with the images. Red flags exclude measurements from these checks; amber asks for caution; grey is information. A flag can belong to background or another source in the aperture.", "muted small"));
}

function contextBox(ana) {
  const out = [el("h4", {}, "Spectrum hints")];
  const eps = (list) => `epoch${list.length === 1 ? "" : "s"} ${list.join(", ")}`;
  if (ana.saturated || ana.noFit) {
    out.push(analysisNote("Baseline unavailable · interpretation uncertain", ana.saturated
      ? `Short-wavelength measurements below ${FIT_MAX_UM} µm are flagged. A reliable baseline cannot be fitted.`
      : `At least 3 usable short-wavelength measurements spanning 0.3 µm are needed. Missing coverage limits interpretation.`));
    return el("div", { class: "ph-context" }, ...out);
  }
  const fitted = [...ana.perEpoch.entries()].filter(([, e]) => e.fit);
  out.push(analysisNote("Baseline: simplified stellar model", `A blackbody is fitted below ${FIT_MAX_UM} µm in each epoch: ` +
    fitted.map(([ep, e]) => `${eps([ep])}: ${e.fit.poor ? "poor fit" : fmtT(e.fit)}`).join("; ") +
    ". This fitted colour temperature is not a measured stellar temperature. The model can misrepresent galaxies, cool atmospheres, extinction and blends.", "muted small"));
  if (ana.poorEpochs.length) out.push(analysisNote("Poor baseline fit · hints less reliable", `${eps(ana.poorEpochs)} do not follow the simple stellar model. No particular cause is established. ${LIMITS}`));
  for (const r of ana.regions) out.push(analysisNote(r.hint.title + " · tentative",
    `${r.hint.text} ${eps(r.epochs)}; ${r.n} points. These exposures were not all taken at the same time.`));
  if (!ana.regions.length && !ana.poorEpochs.length) out.push(analysisNote("No deviations passed this check",
    "No consistent group exceeded the baseline thresholds. This does not confirm a normal star or rule out weak features. The fit uses an approximate 10% calibration floor."));
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

/** T79: the panel with the field's frame tools (field) or first among the analysis panels (a map click). */
function placePanel(underMap) {
  const panel = $("#photometry");
  if (!home.parent) { home.parent = panel.parentNode; home.next = panel.nextSibling; }
  const top = $("#analysis-top") ?? $("#explore");
  if (underMap) { if (panel.previousElementSibling !== top) top.after(panel); }
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

/** T86: open the spectrum of a named source (e.g. from the unusual-spectra list), same as a map click there. */
export function openSpectrum(ra, dec, name, options = {}) { return loadSky(ra, dec, name, options); }

/** T79: a click on the map: every exposure at that sky point, no field needed. */
async function loadSky(ra, dec, name = null, { focusRegion = false } = {}) {
  const api = getApiBase();
  if (!api) return;
  const token = ++st.token;
  st.sky = { ra, dec, name };
  st.pos = null;
  st.data = null;
  drawMarker();
  getSky()?.redraw();
  placePanel(true);
  $("#photometry").hidden = false;
  $("#ph-body").replaceChildren(el("p", { class: "muted small" },
    `Measuring every SPHEREx exposure at RA ${fmtNum(ra, 4)}°, Dec ${fmtNum(dec, 4)}° (the first time takes ~15-30 s)…`));
  $("#ph-status").textContent = "measuring…";
  if (focusRegion) document.dispatchEvent(new CustomEvent("analysis:position", { detail: { ra, dec } }));
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
  box.addEventListener("pointerdown", (e) => { clearTimeout(timer); down = e.isPrimary && e.button === 0 ? { x: e.clientX, y: e.clientY } : null; });
  box.addEventListener("pointerup", (e) => {
    const d = down;
    down = null;
    if (e.defaultPrevented || !d || !proj || Math.hypot(e.clientX - d.x, e.clientY - d.y) > 4) return;
    if (e.target.closest?.("button, a, input, select, label, .paths-tip")) return;
    clearTimeout(timer);
    const canvas = box.querySelector("canvas") ?? box;
    const r = canvas.getBoundingClientRect();
    const px = e.clientX - r.left, py = e.clientY - r.top;
    // Resolve the sky position now; a later pan must not change what this click selected.
    const snap = nearestLabel(px, py);
    const pos = snap ? [snap.ra_deg, snap.dec_deg] : proj.fromScreen(px, py);
    timer = setTimeout(() => {
      if (pos) loadSky(((pos[0] % 360) + 360) % 360, pos[1], snap?.name ?? null, { focusRegion: true });
    }, 280);
  });
  box.addEventListener("dblclick", () => clearTimeout(timer));
  box.addEventListener("pointercancel", () => { down = null; clearTimeout(timer); });
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
  $("#ph-centre").addEventListener("click", () => { st.pos = null; st.sky = null; placePanel(false); drawMarker(); getSky()?.redraw(); load(); });
  $("#ph-catcher").addEventListener("click", measureAtStage);
  // T79: a plain click on the image measures too; clicks on labels/paths keep opening the inspector.
  $("#stage").addEventListener("click", (e) => {
    if (st.measuring || e.target.closest?.(".path-hit, .paths-tip, #ph-catcher, button, a, input, select, label")) return;
    measureAtStage(e);
  });
  document.addEventListener("explore:ready", hookMap);
  hookMap();
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && st.measuring) setMeasuring(false); });
  document.addEventListener("analysis:clear", () => {
    ++st.token;
    st.sky = null;
    st.pos = null;
    st.data = null;
    $("#photometry").hidden = true;
    getSky()?.redraw();
  });
  document.addEventListener("viewer:target", (e) => {
    st.target = e.detail?.target ?? null;
    // A point spectrum is independent of field epochs and catalogue-label refreshes.
    if (st.sky) { getSky()?.redraw(); if (st.data) render(); return; }
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

// for web/tests and the console: open the spectrum panel at a sky position, as a map click there would
globalThis.spherexSpectrumAt = (ra, dec, name = null) => loadSky(ra, dec, name, { focusRegion: true });

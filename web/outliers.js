// T86: sources in the open field whose spectrum doesn't look like the field's ordinary sources.
// The Live API measures every catalogue source in every SPHEREx exposure of the field (T85, ~20 s the first
// time, then cached) and ranks them (pipeline/spectral_outliers.py). This panel shows the list: name, why
// it stands out in plain words, caveats, and a small chart of how far each band is off. A click on a name
// opens that source's spectrum in the spectrum panel (already measured, so at once).
//
// T135: the measured sources include ones found in SPHEREx's own images (not in any label); flagged ones carry a
// catalogue lookup ("not catalogued" first). Started only by the toggle or the panel's button.
//
// Events: listens to viewer:target {target}; fires outliers:list {targetId, items} when a list is shown,
// for anyone who wants to mark the sources (e.g. the map).
//
// T61: below the list, "Changes brightness": sources whose flux changes between exposures at the same wavelength
// (variable stars, new ones first), from the same measurement (`variability` in the answer). On the map they get
// dashed yellow rings marked "V"; a click there opens the spectrum and light curve (the map's own click, T79).
//
// T88: the same on the map. "Unusual spectra" in the map bar (next to Labels; remembered per browser) rings
// the field's outliers where they are (orange, rank number, the selected one blue), measuring the field first
// if needed (progress in the bar). Clicking a ring opens a card on the map with the reason, the band chart and
// buttons for the spectrum and the charts. Panel, colour diagram and map share one selection. Drawn through
// explore.js's public draw hook and pointer events on #sky only: no change to the map's own code.

import { $, el, fmtNum } from "./util.js";
import { analysisNote } from "./analysisnote.js";
import { outlierCopy, LIMITS } from "./analysiscopy.js";
import { targetBase } from "./viewer.js";
import { openSpectrum } from "./photometry.js";
import { getSky } from "./explore.js";

const NS = "http://www.w3.org/2000/svg";
const SHOW = 10;
// Validated pair on the dark panel (same as the spectrum panel's first two slots; validate_palette.js, dark):
// "stands out" and "selected / expected shape". Ordinary sources stay neutral grey: context, not a category.
const C_ODD = "#d95926", C_SEL = "#3987e5";
const C_VAR = "#f5c04a";      // T61: changes brightness (the theme's --warn; dashed, so not a colour-only cue)
const st = { target: null, token: 0, data: null, all: false, allVar: false, sel: null, lastW: 0,
  mapOn: readPref(), card: null, placed: [], hooked: false };
const PREF = "spherex.outliers";

function readPref() {
  try { return localStorage.getItem("spherex.outliers") === "1"; } catch { return false; }
}

function svg(tag, attrs = {}, ...children) {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  n.append(...children);
  return n;
}

function panel() {
  let box = $("#outliers");
  if (!box) {
    box = el("section", { id: "outliers", class: "outliers panel", "aria-labelledby": "ol-title" },
      el("div", { class: "ol-head" }, el("h3", { id: "ol-title" }, "Unusual spectra in this field"),
        el("span", { id: "ol-status", class: "muted small" })),
      el("div", { id: "ol-body" }));
    box.hidden = true;
    ($("#analysis-top") ?? $("#explore"))?.after(box);   // T124: at the top of the analysis panels
    const mirror = el("label", { class: "ol-maptoggle small", title: "Ring these sources on the map" },
      el("input", { type: "checkbox", id: "ol-map-mirror" }), " show on the map");
    mirror.querySelector("input").addEventListener("change", (e) => setMap(e.target.checked));
    box.querySelector(".ol-head").append(mirror);
  }
  return box;
}

/** How far each band is off, in %: bars up (brighter) / down (fainter), the flagged runs solid. */
function residualChart(it, w = 220, h = 46) {
  const bands = it.bands_um, res = it.residual_pct;
  const lx = (um) => (Math.log(um) - Math.log(0.74)) / (Math.log(5.05) - Math.log(0.74)) * (w - 8) + 4;
  const lim = Math.max(30, ...res.filter((v) => v != null).map((v) => Math.min(Math.abs(v), 150)));
  const y = (v) => h / 2 - (Math.max(-lim, Math.min(lim, v)) / lim) * (h / 2 - 3);
  const inRun = (um) => it.deviations.some((d) => um >= d.um_min && um <= d.um_max);
  const bw = Math.max(2, (w - 8) / bands.length - 2);
  const g = svg("svg", { class: "ol-chart", width: w, height: h, viewBox: `0 0 ${w} ${h}`, role: "img",
    "aria-label": `Off by band: ${it.deviations.map((d) => `${d.pct > 0 ? "+" : ""}${Math.round(d.pct)}% at ${d.um_min}-${d.um_max} µm`).join(", ")}` });
  g.append(svg("line", { x1: 2, x2: w - 2, y1: h / 2, y2: h / 2, class: "ol-zero" }));
  bands.forEach((um, k) => {
    const v = res[k];
    if (v == null) return;
    const top = Math.min(y(v), h / 2), ht = Math.max(1, Math.abs(y(v) - h / 2));
    g.append(svg("rect", { x: lx(um) - bw / 2, y: top, width: bw, height: ht,
      class: `ol-bar ${v > 0 ? "ol-up" : "ol-down"}${inRun(um) ? " ol-run" : ""}` },
    svg("title", {}, `${fmtNum(um, 2)} µm: ${v > 0 ? "+" : ""}${fmtNum(v, 0)} %`)));
  });
  for (const um of [1, 2, 3, 4, 5]) {
    g.append(svg("text", { x: lx(um), y: h - 1, class: "ol-tick", "text-anchor": "middle" }, `${um}`));
  }
  return g;
}


/** Round-number ticks between lo and hi. */
function ticks(lo, hi, n = 5) {
  const span = hi - lo || 1;
  const step0 = span / n, mag = 10 ** Math.floor(Math.log10(step0));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= step0) ?? 10 * mag;
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(6));
  return out;
}

function extent(vals, pad) {
  const v = vals.filter((x) => x != null && Number.isFinite(x));
  if (!v.length) return [0, 1];
  const lo = Math.min(...v), hi = Math.max(...v), p = (hi - lo || 0.2) * pad;
  return [lo - p, hi + p];
}

function selectSource(id, card = st.mapOn) {
  st.sel = id;
  if (card) st.card = id;
  render();
  getSky()?.redraw();
}

/** Every judged source by two SPHEREx colours: ordinary ones form a sequence, outliers are coloured. */
function colourChart(d, W) {
  const pts = (d.points ?? []).filter((p) => p.x != null && p.y != null);
  const H = Math.round(Math.min(320, Math.max(220, W * 0.72)));
  const m = { l: 46, r: 12, t: 12, b: 40 };
  const [x0, x1] = extent(pts.map((p) => p.x), 0.08), [y0, y1] = extent(pts.map((p) => p.y), 0.08);
  const X = (v) => m.l + (v - x0) / (x1 - x0) * (W - m.l - m.r);
  const Y = (v) => H - m.b - (v - y0) / (y1 - y0) * (H - m.t - m.b);
  const [sa, sb] = d.colours?.short ?? [1, 1.35], [ma, mb] = d.colours?.mid ?? [1.9, 2.5], [la, lb] = d.colours?.long ?? [3.4, 4.8];
  const g = svg("svg", { class: "ol-cc", width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: "img",
    "aria-label": `Colour–colour diagram of ${pts.length} sources; ${pts.filter((p) => p.outlier).length} stand out` });
  for (const v of ticks(x0, x1)) {
    g.append(svg("line", { x1: X(v), x2: X(v), y1: m.t, y2: H - m.b, class: "ol-grid" }),
      svg("text", { x: X(v), y: H - m.b + 13, class: "ol-tick", "text-anchor": "middle" }, fmtNum(v, 1)));
  }
  for (const v of ticks(y0, y1)) {
    g.append(svg("line", { x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v), class: "ol-grid" }),
      svg("text", { x: m.l - 5, y: Y(v) + 3, class: "ol-tick", "text-anchor": "end" }, fmtNum(v, 1)));
  }
  g.append(svg("text", { x: (m.l + W - m.r) / 2, y: H - 6, class: "ol-axis", "text-anchor": "middle" },
    `redder at short λ → (${sa}–${sb} minus ${ma}–${mb} µm, mag)`),
  svg("text", { x: 11, y: (m.t + H - m.b) / 2, class: "ol-axis", "text-anchor": "middle", transform: `rotate(-90 11 ${(m.t + H - m.b) / 2})` },
    `more light at ${la}–${lb} µm →`));
  const order = [...pts].sort((a, b) => (a.outlier - b.outlier) || (a.score - b.score));
  for (const p of order) {
    const cx = X(p.x), cy = Y(p.y);
    const r = p.outlier ? Math.min(8, 4.5 + Math.sqrt(p.score) / 3) : 3.5;
    const dot = svg("circle", { cx, cy, r, class: p.outlier ? "ol-dot ol-dot-odd" : p.reference ? "ol-dot" : "ol-dot ol-dot-other" });
    if (p.outlier) dot.style.fill = C_ODD;            // a style: the stylesheet's grey would beat an attribute
    g.append(dot);
    if (p.id === st.sel) g.append(svg("circle", { cx, cy, r: r + 4, class: "ol-ring", stroke: C_SEL }));
    const hit = svg("circle", { cx, cy, r: Math.max(8, r + 3), class: "ol-hit" },
      svg("title", {}, `${p.name}${p.otype && p.otype !== "*" ? ` (${p.otype})` : ""}: ${p.outlier ? `stands out, score ${fmtNum(p.score, 0)}` : "not flagged by this model"}. Click to show its bands.`));
    hit.addEventListener("click", () => selectSource(p.id));
    g.append(hit);
  }
  return g;
}

/** The selected source's band shape against what an ordinary source of its kind would show. */
function shapeChart(d, p, W) {
  const um = d.bands_um ?? [], env = d.groups?.[p.peer_group]?.envelope ?? d.envelope ?? {};
  const H = Math.round(Math.min(320, Math.max(220, W * 0.72)));
  const m = { l: 46, r: 12, t: 12, b: 40 };
  const it = (d.items ?? []).find((i) => i.id === p.id);
  const inRun = (u) => it?.deviations?.some((dv) => u >= dv.um_min && u <= dv.um_max);
  const [y0, y1] = extent([...(env.p16 ?? []), ...(env.p84 ?? []), ...p.shape, ...p.model], 0.08);
  const lx0 = Math.log(0.74), lx1 = Math.log(5.05);
  const X = (u) => m.l + (Math.log(u) - lx0) / (lx1 - lx0) * (W - m.l - m.r);
  const Y = (v) => H - m.b - (v - y0) / (y1 - y0) * (H - m.t - m.b);
  const g = svg("svg", { class: "ol-shape", width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: "img",
    "aria-label": `Bands of ${p.name} against an ordinary source of its kind` });
  for (const f of [0.25, 0.5, 1, 2, 4]) {
    const v = Math.log10(f);
    if (v < y0 || v > y1) continue;
    g.append(svg("line", { x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v), class: "ol-grid" }),
      svg("text", { x: m.l - 5, y: Y(v) + 3, class: "ol-tick", "text-anchor": "end" }, `×${f}`));
  }
  for (const u of [1, 2, 3, 4, 5]) {
    g.append(svg("line", { x1: X(u), x2: X(u), y1: m.t, y2: H - m.b, class: "ol-grid" }),
      svg("text", { x: X(u), y: H - m.b + 13, class: "ol-tick", "text-anchor": "middle" }, `${u}`));
  }
  g.append(svg("text", { x: (m.l + W - m.r) / 2, y: H - 6, class: "ol-axis", "text-anchor": "middle" }, p.wavelength_frame === "rest" ? "rest-frame wavelength (µm)" : "wavelength (µm)"),
    svg("text", { x: 11, y: (m.t + H - m.b) / 2, class: "ol-axis", "text-anchor": "middle", transform: `rotate(-90 11 ${(m.t + H - m.b) / 2})` },
      "brightness, own level taken out"));
  // field spread: 68 % of the ordinary sources (16th–84th percentile per band)
  const band = um.map((u, k) => [u, env.p16?.[k], env.p84?.[k]]).filter(([, a, b]) => a != null && b != null);
  if (band.length > 1) {
    const top = band.map(([u, , b]) => `${X(u)},${Y(b)}`), bot = band.map(([u, a]) => `${X(u)},${Y(a)}`).reverse();
    g.append(svg("polygon", { points: [...top, ...bot].join(" "), class: "ol-env" }));
  }
  const line = (vals, cls, stroke) => {
    const segs = [];
    let cur = [];
    um.forEach((u, k) => { if (vals[k] == null) { if (cur.length) segs.push(cur); cur = []; } else cur.push(`${X(u)},${Y(vals[k])}`); });
    if (cur.length) segs.push(cur);
    for (const s of segs) if (s.length > 1) g.append(svg("polyline", { points: s.join(" "), class: cls, ...(stroke ? { stroke } : {}) }));
  };
  line(p.model, "ol-model", C_SEL);
  line(p.shape, "ol-src", p.outlier ? C_ODD : "#8b93a7");
  um.forEach((u, k) => {
    const v = p.shape[k];
    if (v == null) return;
    const run = inRun(u), mod = p.model[k];
    const off = mod != null ? (10 ** (v - mod) - 1) * 100 : null;
    g.append(svg("circle", { cx: X(u), cy: Y(v), r: run ? 5 : 3.5, class: "ol-pt", style: `fill:${p.outlier ? C_ODD : "#8b93a7"}` },
      svg("title", {}, `${fmtNum(u, 2)} µm: ${off == null ? "" : `${off > 0 ? "+" : ""}${fmtNum(off, 0)} % vs. an ordinary source of its kind`}${run ? " (part of a consistent deviation)" : ""}`)));
  });
  return g;
}

function vizBlock(d) {
  const pts = d.points ?? [];
  if (!pts.length) return null;
  const top = d.items?.[0]?.id;
  const p = pts.find((q) => q.id === st.sel) ?? pts.find((q) => q.id === top) ?? pts[0];
  st.sel = p.id;
  const it = (d.items ?? []).find((i) => i.id === p.id);
  const full = Math.max(300, Math.round($("#ol-body").clientWidth || 600));
  const two = full >= 760;
  const W = two ? Math.floor((full - 16) / 2) - 4 : full;   // slack: rounding must not wrap the second chart
  const key = (cls, text, color) => el("span", { class: "ol-key" }, el("span", { class: `ol-sw ${cls}`, style: color ? `--c:${color}` : null }), text);
  return el("div", { class: "ol-viz" },
    el("figure", { class: "ol-fig", style: `width:${W}px` },
      el("figcaption", { class: "small" }, "Colours: galaxies at rest, other sources as observed"),
      colourChart(d, W),
      el("p", { class: "ol-legend small muted" }, key("ol-sw-ord", "reference sources"), key("ol-sw-odd", "stands out", C_ODD),
        key("ol-sw-sel", "selected", C_SEL), " · click a dot")),
    el("figure", { class: "ol-fig", style: `width:${W}px` },
      el("figcaption", { class: "small" }, el("strong", {}, p.name), p.outlier ? "" : " (not flagged)", `: its bands vs. ${p.peer_group ?? "peers"}`),
      shapeChart(d, p, W),
      el("p", { class: "ol-legend small muted" }, key("ol-sw-pt", p.outlier ? "this source" : "this source", p.outlier ? C_ODD : "#8b93a7"),
        key("ol-sw-line", "peer model", C_SEL), key("ol-sw-env", `68 % of ${p.peer_group ?? "peer"} references`)),
      it ? analysisNote(outlierCopy(it).brief, outlierCopy(it).detail) : analysisNote("No consistent model deviation", "This check found no consistent deviation from the peer model. Weak features or model limitations can still be present.", "muted small")));
}

/** T135: SPHEREx-only sources (found in SPHEREx's own images) carry a catalogue lookup: "not catalogued", the
 *  catalogue that has it ("in Gaia DR3"), or its SIMBAD type. */
function tagOf(it) {
  if (!it.tag) return null;
  const m = it.catalogues ?? {};
  const text = it.tag === "new" ? "no catalogue match"
    : it.tag === "other" ? `SIMBAD: ${m.simbad?.kind ?? m.simbad?.otype}`
    : `in ${(Object.values(m).find(Boolean)?.name ?? "").split(" ").slice(0, -1).join(" ") || "a catalogue"}`;
  return el("span", { class: `small ${it.tag === "new" ? "ol-new" : "muted"}`,
    title: `A missing catalogue match does not establish a new object. Found in SPHEREx's own images; looked up in ${Object.keys(m).join(", ")}${it.catalogues_failed?.length ? ` (no answer: ${it.catalogues_failed.join(", ")})` : ""}` }, text);
}

function item(it) {
  const name = el("button", { type: "button", class: "link ol-name", title: "Open its spectrum" }, it.name);
  name.addEventListener("click", () => openSpectrum(it.ra_deg, it.dec_deg, it.name));
  const li = el("li", { class: `ol-item${it.id === st.sel ? " is-selected" : ""}`, title: "Click to show it in the charts" },
    el("div", { class: "ol-row" }, name, tagOf(it),
      el("span", { class: "muted small" }, [it.otype && it.otype !== "*" ? it.otype : "", it.mag != null ? `mag ${fmtNum(it.mag, 1)}` : ""]
        .filter(Boolean).join(" · ")),
      el("span", { class: "ol-score small", title: "Ranking score: summed significance of the consistent deviations (halved for blends)" },
        `score ${fmtNum(it.score, 0)}`)),
    el("div", { class: "ol-row ol-detail" }, residualChart(it), analysisNote(outlierCopy(it).brief, outlierCopy(it).detail)),
    it.caveats?.length ? analysisNote("Measurement caveats", it.caveats.join("; ") + ". " + LIMITS, "muted small ol-caveat") : null);
  li.addEventListener("click", (e) => { if (!e.target.closest("button")) selectSource(it.id); });
  return li;
}

/** T61: sources that change brightness between exposures at the same wavelength (detect/variability.py). */
function varBlock(d) {
  const v = d.variability;
  if (!v || v.status === "error") return null;
  const vars = v.variables ?? [];
  const head = el("h4", { class: "ol-subhead" }, "Possible variability");
  const note = analysisNote(vars.length ? `${vars.length} source${vars.length === 1 ? "" : "s"} flagged · cause uncertain` : "No variability passed this check",
    "Repeated differences at similar wavelengths can indicate variability. Blends, extended sources, calibration and sampling can affect the result. Not being catalogued as variable does not establish a new discovery.", "muted small");
  if (!vars.length) return el("div", { class: "ol-var" }, head, note);
  const shown = st.allVar ? vars : vars.slice(0, SHOW);
  const list = el("ol", { class: "ol-list" }, ...shown.map((r) => {
    const name = el("button", { type: "button", class: "link ol-name", title: "Open its spectrum and light curve" }, r.name);
    name.addEventListener("click", () => openSpectrum(r.ra_deg, r.dec_deg, r.name));
    return el("li", { class: "ol-item" },
      el("div", { class: "ol-row" }, name,
        el("span", { class: `small ${r.catalogued_variable ? "muted" : "ol-new"}` }, r.catalogued_variable ? `catalogued variable (${r.otype})` : "not listed as variable"),
        analysisNote(`±${fmtNum(r.amplitude_mag, 2)} mag`, `${r.reason}. 90% of same-wavelength pairs change less than this amplitude; this is not a physical variability model. Instrumental effects and blends may contribute.`, "ol-score small")));
  }));
  const parts = [head, note, list];
  if (vars.length > SHOW) {
    const more = el("button", { type: "button", class: "link small" }, st.allVar ? "Show fewer" : `Show all ${vars.length}`);
    more.addEventListener("click", () => { st.allVar = !st.allVar; render(); });
    parts.push(more);
  }
  parts.push(analysisNote(`${v.n_judged ?? 0} sources compared`, `${v.blended?.length ?? 0} blended or extended sources left out. ${v.method ?? ""} Significance depends on the adopted error model.`, "muted small"));
  return el("div", { class: "ol-var" }, ...parts);
}

function redshiftBlock(d) {
  const rank = { estimated: 0, catalogue: 1, ambiguous: 2, insufficient_evidence: 3, insufficient_data: 4 };
  const shifts = [...(d.redshifts?.sources ?? [])].sort((a, b) => (rank[a.status] ?? 5) - (rank[b.status] ?? 5));
  if (!shifts.length) return null;
  const row = (r) => {
    const name = el("button", { type: "button", class: "link" }, r.name);
    name.addEventListener("click", () => openSpectrum(r.ra_deg, r.dec_deg, r.name));
    const brief = r.status === "catalogue" ? `z = ${r.z} · catalogue` :
      r.status === "estimated" ? `z ≈ ${Number(r.z.toFixed(3))} · tentative` : "Redshift uncertain";
    const alternatives = (r.alternatives ?? []).map((a) => `z ≈ ${a.z}, ${a.profile_name}: ${a.features.filter((f) => f.status === "detected").map((f) => f.name).join(", ")}`).join("; ");
    const detail = r.status === "catalogue" ? `From ${r.origin}${r.quality ? `, quality ${r.quality}` : ""}. A published catalogue value, not remeasured here; source association and catalogue quality still matter.` :
      `Experimental feature-template search over z=0–1. ${r.reason ?? "Insufficient usable spectral evidence"}. ` +
      (r.z_interval ? `Local fit interval ${r.z_interval[0]}–${r.z_interval[1]}; systematic and template uncertainty are not included. ` : "An uncertain shift is not applied. ") +
      (alternatives ? `Possible fits: ${alternatives}. ` : "") + "This is not a confirmed redshift or object classification.";
    return el("li", { class: "ol-item" }, name, " · ", analysisNote(brief, detail));
  };
  const accepted = shifts.filter((r) => r.status === "catalogue" || r.status === "estimated");
  const uncertain = shifts.filter((r) => r.status !== "catalogue" && r.status !== "estimated");
  return el("section", {}, el("h4", {}, "Redshifts"),
    analysisNote("Catalogue or tentative spectral estimate", "Catalogue values take priority. Missing values are fitted experimentally over z=0–1. Ambiguous shifts and poor fits are excluded from automatic matching. Objects outside this range and absorption-only spectra can remain unresolved.", "muted small"),
    accepted.length ? el("ul", { class: "ol-list" }, ...accepted.slice(0, SHOW).map(row)) : null,
    accepted.length > SHOW ? el("details", {}, el("summary", {}, `Show ${accepted.length - SHOW} more`), el("ul", { class: "ol-list" }, ...accepted.slice(SHOW).map(row))) : null,
    uncertain.length ? el("details", {}, el("summary", {}, `${uncertain.length} unresolved shift${uncertain.length === 1 ? "" : "s"}`), el("ul", { class: "ol-list" }, ...uncertain.map(row))) : null);
}

function profileBlock(d) {
  const profiles = d.chemistry_profiles;
  if (!profiles) return null;
  const matches = profiles.matches ?? [];
  const labels = { brown_dwarfs: "brown dwarf", young_stars: "young star", cool_giants: "cool giant",
    protostars: "protostar", starburst: "star-forming galaxy", quasars: "quasar", ionised_gas: "ionised gas",
    cloud_ices: "ice absorption", cloud_edge: "illuminated cloud edge" };
  return el("section", { class: "ol-profiles" },
    el("h4", {}, "Chemistry candidates"),
    analysisNote("Feature patterns · identities unconfirmed", `${profiles.method} Significance is model-dependent and has not been calibrated as a classification probability.`, "muted small"),
    matches.length ? el("ul", { class: "ol-list" }, ...matches.map((m) => {
      const name = el("button", { type: "button", class: "link" }, m.name);
      name.addEventListener("click", () => openSpectrum(m.ra_deg, m.dec_deg, m.name));
      const evidence = m.features.map((f) => f.status === "insufficient_coverage"
        ? `${f.name ?? f.feature}: insufficient coverage` : `${f.name ?? f.feature}: ${f.pct > 0 ? "+" : ""}${f.pct}%, ${f.significance}σ, ${f.epochs_agree}/${f.epochs_seen} epochs agree (${f.status === "detected" ? "threshold passed" : "below threshold"})`).join("; ");
      return el("li", { class: "ol-item" }, name, " · ", analysisNote(`Possible ${labels[m.profile] ?? m.profile_name.toLowerCase()}`,
        `${evidence}. ${m.redshift_origin && m.redshift_origin !== "rest" ? `z=${m.z} (${m.redshift_origin}). ` : ""}${(m.caveats ?? []).join(" ")} ${LIMITS}`));
    })) : analysisNote("No candidates passed this check", "Missing wavelength coverage, low signal or a mismatched template can prevent a match. This does not rule out the object types being sought.", "muted small"),
    profiles.skipped?.length ? analysisNote("Some redshift profiles unchecked", "A reliable redshift was unavailable; galaxy/quasar profiles were not evaluated for those sources.", "muted small") : null);
}

function render() {
  const d = st.data;
  const body = $("#ol-body");
  if (!d) return;
  const parts = [];
  const c = st.target?.center;
  if (c) parts.push(el("p", { id: "ol-scope", class: "small muted" },
    `Region: RA ${fmtNum(c.ra_deg, 4)}°, Dec ${fmtNum(c.dec_deg, 4)}° · ${st.target.size_arcmin ?? "?"}′`));
  if (d.status === "not_started") {
    const go = el("button", { type: "button" }, "Analyse sources: spectra + chemistry profiles");
    go.addEventListener("click", () => load(true));
    parts.push(analysisNote("Compare spectra and feature patterns", "Measures catalogue and image-detected sources using the available exposures, then checks model deviations, possible variability and chemistry patterns. Results are candidates; noisy or incomplete measurements can remain unjudged."), go);
  } else if (d.status === "building") {
    parts.push(el("p", { class: "small" }, d.total ? `Reading exposures… ${d.done}/${d.total}` : "Reading exposures…"));
  } else if (d.status === "ready") {
    const items = d.items ?? [];
    const nj = d.not_judged ?? [];
    parts.push(analysisNote(items.length ? `${items.length} ${items.length === 1 ? "spectrum" : "spectra"} flagged · interpretation uncertain` : d.n_judged ? "No deviations passed this check" : "Insufficient data for comparison", `${d.summary ?? ""} ${LIMITS}`, items.length ? "" : "muted small"));
    parts.push(redshiftBlock(d));
    parts.push(profileBlock(d));
    parts.push(vizBlock(d));
    if (items.length) {
      const shown = st.all ? items : items.slice(0, SHOW);
      parts.push(el("ol", { class: "ol-list" }, ...shown.map(item)));
      if (items.length > SHOW) {
        const more = el("button", { type: "button", class: "link small" }, st.all ? "Show fewer" : `Show all ${items.length}`);
        more.addEventListener("click", () => { st.all = !st.all; render(); });
        parts.push(more);
      }
    }
    parts.push(analysisNote(`${d.n_judged ?? 0}/${d.field?.n_sources ?? "?"} sources compared · ${d.field?.n_exposures ?? "?"} exposures`,
      `${nj.length} sources unjudged: insufficient clean bands, peers or a reliable redshift. Bars show residuals relative to a peer model. ${d.method ?? ""} Model significance is not an identification probability.`, "muted small"));
    const vb = varBlock(d);
    if (vb) parts.push(vb);
  } else {
    parts.push(el("p", { class: "msg msg-warn" }, `Couldn't measure the field: ${d.message ?? d.status}`));
  }
  body.replaceChildren(...parts.filter(Boolean));
  $("#ol-status").textContent = d.status === "ready" && d.items?.length ? `${d.items.length} flagged` : "";
  mapNote();
}

async function load(start = false) {
  const base = targetBase();
  if (!base || !st.target) return;
  const token = ++st.token;
  const url = new URL("spectral-outliers", base);
  if (start) url.searchParams.set("start", "1");
  try {
    for (let i = 0; i < 600; i++) {
      const res = await fetch(url, { cache: "no-cache" });
      const body = await res.json().catch(() => null);
      if (token !== st.token) return;
      if (!body || res.status === 404 || body.status === "no_data") { panel().hidden = true; return; }   // offline folder / synthetic
      st.data = body;
      panel().hidden = false;
      render();
      if (body.status === "ready") {
        document.dispatchEvent(new CustomEvent("outliers:list", { detail: { targetId: st.target?.id, items: body.items ?? [] } }));
      }
      if (body.status !== "building") return;
      url.searchParams.delete("start");
      await new Promise((r) => setTimeout(r, 1000));
    }
  } catch {
    if (token === st.token) panel().hidden = true;
  }
}

document.addEventListener("viewer:target", (e) => {
  st.target = e.detail?.target ?? null;
  st.data = null;
  st.all = false;
  st.allVar = false;
  st.sel = null;
  st.card = null;
  st.token++;
  panel().hidden = true;
  cardEl().hidden = true;
  mapNote();
  getSky()?.redraw();
  // Measured only on a click (Decision 2026-11-15, Mati): the toggle or the panel's button; here just the stored
  // result, if any (T130 had started it for every explicit / selected field).
  if (st.target && st.target.synthetic === false) load(st.mapOn);
});

// ---------- T88: on the map ----------

function mapNote() {
  const note = $("#outliers-note");
  const mirror = $("#ol-map-mirror");
  if (mirror) mirror.checked = st.mapOn;
  if (!note) return;
  const d = st.data;
  note.textContent = !st.mapOn ? "" :
    !st.target ? "open a field first" :
    !d ? "" :
    d.status === "building" ? (d.total ? `measuring ${d.done}/${d.total}…` : "measuring…") :
    d.status === "ready" ? [d.items?.length ? `${d.items.length} ringed` : "none flagged",
      d.variability?.variables?.length ? `${d.variability.variables.length} changing (dashed, V)` : ""].filter(Boolean).join(", ") :
    d.status === "not_started" ? "" : "failed";
}

function setMap(on) {
  st.mapOn = on;
  try { localStorage.setItem(PREF, on ? "1" : "0"); } catch { /* private mode: not remembered */ }
  const t = $("#outliers-toggle");
  if (t) t.checked = on;
  if (!on) { st.card = null; cardEl().hidden = true; }
  if (on && st.target?.synthetic === false && (!st.data || st.data.status === "not_started")) load(true);
  mapNote();
  hookMap();
  getSky()?.redraw();
}

/** T61: sources that change brightness, dashed rings marked "V" (the map's own click opens the light curve). */
function paintVariables(ctx, proj) {
  const vars = st.data?.variability?.variables ?? [];
  if (!vars.length) return;
  const v = proj.view();
  ctx.save();
  ctx.font = "bold 10px sans-serif";
  for (const r of vars) {
    const s = proj.toScreen(r.ra_deg, r.dec_deg);
    if (!s.front || s.x < -30 || s.y < -30 || s.x > v.width + 30 || s.y > v.height + 30) continue;
    const rad = 9;
    ctx.setLineDash([]);
    ctx.lineWidth = 4.5; ctx.strokeStyle = "rgba(0,0,0,0.7)";
    ctx.beginPath(); ctx.arc(s.x, s.y, rad, 0, 2 * Math.PI); ctx.stroke();
    ctx.setLineDash([4, 3]);
    ctx.lineWidth = 2; ctx.strokeStyle = C_VAR;
    ctx.beginPath(); ctx.arc(s.x, s.y, rad, 0, 2 * Math.PI); ctx.stroke();
    ctx.setLineDash([]);
    ctx.lineWidth = 3; ctx.strokeStyle = "rgba(0,0,0,0.8)"; ctx.fillStyle = C_VAR;
    ctx.strokeText("V", s.x - rad - 9, s.y - rad * 0.6);
    ctx.fillText("V", s.x - rad - 9, s.y - rad * 0.6);
  }
  ctx.restore();
}

function paintMap(ctx, proj) {
  st.placed = [];
  const d = st.data;
  if (st.mapOn && d?.status === "ready") paintVariables(ctx, proj);
  if (!st.mapOn || d?.status !== "ready" || !d.items?.length) { placeCard(null); return; }
  const v = proj.view();
  ctx.save();
  ctx.font = "bold 11px sans-serif";
  d.items.forEach((it, k) => {
    const s = proj.toScreen(it.ra_deg, it.dec_deg);
    if (!s.front || s.x < -30 || s.y < -30 || s.x > v.width + 30 || s.y > v.height + 30) return;
    const r = 7 + Math.min(5, Math.sqrt(it.score) / 2);
    ctx.lineWidth = 4.5; ctx.strokeStyle = "rgba(0,0,0,0.7)";
    ctx.beginPath(); ctx.arc(s.x, s.y, r, 0, 2 * Math.PI); ctx.stroke();
    ctx.lineWidth = 2.5; ctx.strokeStyle = C_ODD;
    ctx.beginPath(); ctx.arc(s.x, s.y, r, 0, 2 * Math.PI); ctx.stroke();
    if (it.id === st.sel) {
      ctx.lineWidth = 2.5; ctx.strokeStyle = C_SEL;
      ctx.beginPath(); ctx.arc(s.x, s.y, r + 5, 0, 2 * Math.PI); ctx.stroke();
    }
    const label = String(k + 1);
    ctx.lineWidth = 3; ctx.strokeStyle = "rgba(0,0,0,0.8)"; ctx.fillStyle = "#ffffff";
    ctx.strokeText(label, s.x + r * 0.75 + 2, s.y - r * 0.75 - 1);
    ctx.fillText(label, s.x + r * 0.75 + 2, s.y - r * 0.75 - 1);
    st.placed.push({ x: s.x, y: s.y, r, it });
  });
  ctx.restore();
  placeCard(st.placed.find((p) => p.it.id === st.card) ?? null);
}

function cardEl() {
  let c = $("#ol-card");
  if (!c) {
    c = el("div", { id: "ol-card", class: "ol-card", role: "dialog", "aria-label": "Unusual spectrum" });
    c.hidden = true;
    // the map's own click (spectrum at the point) and drag must not see clicks on the card
    for (const ev of ["pointerdown", "pointerup", "click", "dblclick", "wheel"]) c.addEventListener(ev, (e) => e.stopPropagation());
    $("#sky")?.append(c);
  }
  return c;
}

function placeCard(p) {
  const c = cardEl();
  if (!p) { c.hidden = true; return; }
  if (c.dataset.id !== p.it.id) fillCard(c, p.it);
  const box = $("#sky");
  const W = box?.clientWidth ?? 600, H = box?.clientHeight ?? 400;
  c.hidden = false;
  const w = c.offsetWidth || 300, h = c.offsetHeight || 160;
  let x = p.x + p.r + 12, y = p.y - h / 2;
  if (x + w > W - 8) x = p.x - p.r - 12 - w;
  c.style.left = `${Math.max(8, Math.min(W - w - 8, x))}px`;
  c.style.top = `${Math.max(8, Math.min(H - h - 8, y))}px`;
}

function fillCard(c, it) {
  c.dataset.id = it.id;
  const rank = (st.data?.items ?? []).findIndex((i) => i.id === it.id) + 1;
  const close = el("button", { type: "button", class: "link ol-card-x", "aria-label": "Close" }, "×");
  close.addEventListener("click", () => { st.card = null; c.hidden = true; getSky()?.redraw(); });
  const spec = el("button", { type: "button" }, "Spectrum");
  spec.addEventListener("click", () => openSpectrum(it.ra_deg, it.dec_deg, it.name));
  const charts = el("button", { type: "button", class: "link" }, "Charts ↓");
  charts.addEventListener("click", () => { st.sel = it.id; render(); panel().scrollIntoView({ behavior: "smooth", block: "start" }); });
  c.replaceChildren(...[
    el("div", { class: "ol-card-head" }, el("strong", {}, `${rank}. ${it.name}`), close),
    el("p", { class: "small muted" }, [it.otype && it.otype !== "*" ? it.otype : "", it.mag != null ? `mag ${fmtNum(it.mag, 1)}` : "",
      `score ${fmtNum(it.score, 0)}`].filter(Boolean).join(" · ")),
    residualChart(it, 260, 44),
    analysisNote(outlierCopy(it).brief, outlierCopy(it).detail),
    it.caveats?.length ? analysisNote("Measurement caveats", it.caveats.join("; ") + ". " + LIMITS, "muted small") : null,
    el("div", { class: "ol-card-actions" }, spec, charts)].filter(Boolean));   // replaceChildren would print "null"
}

function hookMap() {
  const sky = getSky();
  const box = $("#sky");
  if (!sky || !box || st.hooked) return;
  st.hooked = true;
  sky.addDrawHook(paintMap);
  let down = null;
  box.addEventListener("pointerdown", (e) => { down = e.isPrimary ? { x: e.clientX, y: e.clientY } : null; });
  box.addEventListener("pointerup", (e) => {
    const d0 = down;
    down = null;
    if (e.defaultPrevented || !st.mapOn || !d0 || Math.hypot(e.clientX - d0.x, e.clientY - d0.y) > 4 || !st.placed.length) return;
    const r = box.getBoundingClientRect();
    const x = e.clientX - r.left, y = e.clientY - r.top;
    let best = null, bd = Infinity;
    for (const p of st.placed) {
      const dd = Math.hypot(p.x - x, p.y - y);
      if (dd <= p.r + 6 && dd < bd) { bd = dd; best = p; }
    }
    if (!best) return;
    // T141: the ring takes the click (the map's own click would make its spot a new analysis region since T138 and
    // clear this list) and opens the spectrum itself, as the map's click did (T79)
    e.preventDefault();
    selectSource(best.it.id, true);
    openSpectrum(best.it.ra_deg, best.it.dec_deg, best.it.name);
  });
}

function addToggle() {
  if ($("#outliers-toggle")) return;
  const labels = $("#labels-toggle")?.closest("label");
  if (!labels) return;
  const box = el("label", { title: "Ring the sources of the open field whose spectrum doesn't look like the field's ordinary " +
    "sources (T86), and dashed V rings on the ones that change brightness (T61). Measures the field the first time (~20 s)." },
  el("input", { id: "outliers-toggle", type: "checkbox" }), " Unusual spectra ", el("span", { id: "outliers-note", class: "muted small" }));
  labels.after(box);
  const input = box.querySelector("input");
  input.checked = st.mapOn;
  input.addEventListener("change", () => setMap(input.checked));
}

addToggle();
document.addEventListener("explore:ready", hookMap);
hookMap();
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && st.card) { st.card = null; cardEl().hidden = true; getSky()?.redraw(); }
});

new ResizeObserver(() => {
  const w = Math.round($("#ol-body")?.clientWidth || 0);
  if (w && Math.abs(w - st.lastW) > 8 && st.data?.status === "ready") { st.lastW = w; render(); }
}).observe(panel());
// for web/tests and the console: where the rings are drawn right now (screen px inside #sky)
globalThis.spherexOutliers = { placed: () => st.placed.map((p) => ({ x: p.x, y: p.y, id: p.it.id, name: p.it.name })) };

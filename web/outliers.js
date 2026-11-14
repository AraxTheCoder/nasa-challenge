// T86: sources in the open field whose spectrum doesn't look like the field's ordinary sources.
// The Live API measures every catalogue source in every SPHEREx exposure of the field (T85, ~20 s the first
// time, then cached) and ranks them (pipeline/spectral_outliers.py). This panel shows the list: name, why
// it stands out in plain words, caveats, and a small chart of how far each band is off. A click on a name
// opens that source's spectrum in the spectrum panel (already measured, so at once).
//
// Events: listens to viewer:target {target}; fires outliers:list {targetId, items} when a list is shown,
// for anyone who wants to mark the sources (e.g. the map).

import { $, el, fmtNum } from "./util.js";
import { targetBase } from "./viewer.js";
import { openSpectrum } from "./photometry.js";

const NS = "http://www.w3.org/2000/svg";
const SHOW = 10;
// Validated pair on the dark panel (same as the spectrum panel's first two slots; validate_palette.js, dark):
// "stands out" and "selected / expected shape". Ordinary sources stay neutral grey: context, not a category.
const C_ODD = "#d95926", C_SEL = "#3987e5";
const st = { target: null, token: 0, data: null, all: false, sel: null, lastW: 0 };

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
    ($("#discoveries") ?? $("#explore"))?.after(box);
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

function selectSource(id) { st.sel = id; render(); }

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
      svg("title", {}, `${p.name}${p.otype && p.otype !== "*" ? ` (${p.otype})` : ""}: ${p.outlier ? `stands out, score ${fmtNum(p.score, 0)}` : "ordinary"}. Click to show its bands.`));
    hit.addEventListener("click", () => selectSource(p.id));
    g.append(hit);
  }
  return g;
}

/** The selected source's band shape against what an ordinary source of its kind would show. */
function shapeChart(d, p, W) {
  const um = d.bands_um ?? [], env = d.envelope ?? {};
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
  g.append(svg("text", { x: (m.l + W - m.r) / 2, y: H - 6, class: "ol-axis", "text-anchor": "middle" }, "wavelength (µm)"),
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
      el("figcaption", { class: "small" }, "The field by colour: each dot is a source"),
      colourChart(d, W),
      el("p", { class: "ol-legend small muted" }, key("ol-sw-ord", "ordinary (defines normal)"), key("ol-sw-odd", "stands out", C_ODD),
        key("ol-sw-sel", "selected", C_SEL), " · click a dot")),
    el("figure", { class: "ol-fig", style: `width:${W}px` },
      el("figcaption", { class: "small" }, el("strong", {}, p.name), p.outlier ? "" : " (ordinary)", ": its bands vs. the field"),
      shapeChart(d, p, W),
      el("p", { class: "ol-legend small muted" }, key("ol-sw-pt", p.outlier ? "this source" : "this source", p.outlier ? C_ODD : "#8b93a7"),
        key("ol-sw-line", "an ordinary source of its kind", C_SEL), key("ol-sw-env", "68 % of ordinary sources")),
      it ? el("p", { class: "small" }, it.reason) : el("p", { class: "small muted" }, "Fits the field's ordinary shape: no consistent deviation.")));
}

function item(it) {
  const name = el("button", { type: "button", class: "link ol-name", title: "Open its spectrum" }, it.name);
  name.addEventListener("click", () => openSpectrum(it.ra_deg, it.dec_deg, it.name));
  const li = el("li", { class: `ol-item${it.id === st.sel ? " is-selected" : ""}`, title: "Click to show it in the charts" },
    el("div", { class: "ol-row" }, name,
      el("span", { class: "muted small" }, [it.otype && it.otype !== "*" ? it.otype : "", it.mag != null ? `mag ${fmtNum(it.mag, 1)}` : ""]
        .filter(Boolean).join(" · ")),
      el("span", { class: "ol-score small", title: "Ranking score: summed significance of the consistent deviations (halved for blends)" },
        `score ${fmtNum(it.score, 0)}`)),
    el("div", { class: "ol-row ol-detail" }, residualChart(it), el("p", { class: "small" }, it.reason)),
    it.caveats?.length ? el("p", { class: "muted small ol-caveat" }, `Caveat: ${it.caveats.join("; ")}.`) : null);
  li.addEventListener("click", (e) => { if (!e.target.closest("button")) selectSource(it.id); });
  return li;
}

function render() {
  const d = st.data;
  const body = $("#ol-body");
  if (!d) return;
  const parts = [];
  if (d.status === "not_started") {
    const go = el("button", { type: "button" }, "Find sources with unusual spectra");
    go.addEventListener("click", () => load(true));
    parts.push(el("p", { class: "small" }, "Measures every catalogue source of this field in every SPHEREx exposure " +
      "(~20 s the first time) and lists the ones whose spectral shape doesn't fit what ordinary sources here look like."), go);
  } else if (d.status === "building") {
    parts.push(el("p", { class: "small" }, d.total ? `Reading exposures… ${d.done}/${d.total}` : "Reading exposures…"));
  } else if (d.status === "ready") {
    const items = d.items ?? [];
    const nj = d.not_judged ?? [];
    const sat = nj.filter((n) => n.why.startsWith("saturated")).length;
    parts.push(el("p", { class: items.length ? "" : "muted" }, d.summary ?? ""));
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
    parts.push(el("p", { class: "muted small" },
      `${d.field?.n_sources ?? "?"} sources in ${d.field?.n_exposures ?? "?"} exposures; ${d.n_judged ?? 0} had enough clean bands` +
      (nj.length ? ` (not judged: ${sat} saturated, ${nj.length - sat} too faint)` : "") + ". " +
      "Bars: how far each band is from the field's ordinary shape (solid = the consistent deviations). " + (d.method ?? "")));
  } else {
    parts.push(el("p", { class: "msg msg-warn" }, `Couldn't measure the field: ${d.message ?? d.status}`));
  }
  body.replaceChildren(...parts);
  $("#ol-status").textContent = d.status === "ready" && d.items?.length ? `${d.items.length} found` : "";
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
  st.sel = null;
  st.token++;
  panel().hidden = true;
  if (st.target && st.target.synthetic === false) load(false);
});

new ResizeObserver(() => {
  const w = Math.round($("#ol-body")?.clientWidth || 0);
  if (w && Math.abs(w - st.lastW) > 8 && st.data?.status === "ready") { st.lastW = w; render(); }
}).observe(panel());

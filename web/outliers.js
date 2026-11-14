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
const st = { target: null, token: 0, data: null, all: false };

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

function item(it) {
  const name = el("button", { type: "button", class: "link ol-name", title: "Open its spectrum" }, it.name);
  name.addEventListener("click", () => openSpectrum(it.ra_deg, it.dec_deg, it.name));
  return el("li", { class: "ol-item" },
    el("div", { class: "ol-row" }, name,
      el("span", { class: "muted small" }, [it.otype && it.otype !== "*" ? it.otype : "", it.mag != null ? `mag ${fmtNum(it.mag, 1)}` : ""]
        .filter(Boolean).join(" · ")),
      el("span", { class: "ol-score small", title: "Ranking score: summed significance of the consistent deviations (halved for blends)" },
        `score ${fmtNum(it.score, 0)}`)),
    el("div", { class: "ol-row ol-detail" }, residualChart(it), el("p", { class: "small" }, it.reason)),
    it.caveats?.length ? el("p", { class: "muted small ol-caveat" }, `Caveat: ${it.caveats.join("; ")}.`) : null);
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
    document.dispatchEvent(new CustomEvent("outliers:list", { detail: { targetId: st.target?.id, items } }));
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
  st.token++;
  panel().hidden = true;
  if (st.target && st.target.synthetic === false) load(false);
});

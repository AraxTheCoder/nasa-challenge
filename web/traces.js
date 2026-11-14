// T35 Tracing over the stitched sky: draw the shown field's important objects onto the explore map
// (Aladin Lite, T30/T32): a line through their per-frame positions, one dot per epoch (mean
// position), the shown epoch's dot highlighted while the map blinks, and the name with a popup.
// Slow movers get a dashed arrow along their motion, labelled as exaggerated: at map scale
// Barnard's Star's 10"/yr is invisible otherwise.
//
// Data: target.json `labels`, `known_objects`, `detections` (RA/Dec per frame). Events:
//   viewer:target {target}  (viewer.js)     explore:epoch {epoch}  (explore.js, T32 epoch buttons)

import { $, el } from "./util.js";
import { getAladin } from "./explore.js";

const st = { target: null, epoch: null, on: true, layers: null, objs: [] };
const EPOCH_COLOURS = ["#6cb4ff", "#9be38a", "#ffd27a", "#ff9a6c", "#e88bff", "#7fe3e0"];
const ARROW_ARCMIN = 1.5;   // drawn length of the exaggerated arrow
const SLOW_ARCSEC = 30;     // traces shorter than this get the arrow

function sepArcsec(a, b) {
  const d = Math.PI / 180;
  const x = Math.sin(((b.dec_deg - a.dec_deg) * d) / 2) ** 2 +
    Math.cos(a.dec_deg * d) * Math.cos(b.dec_deg * d) * Math.sin(((b.ra_deg - a.ra_deg) * d) / 2) ** 2;
  return (2 * Math.asin(Math.min(1, Math.sqrt(x))) * 180 * 3600) / Math.PI;
}

function pickObjects(t) {
  const order = new Map([...t.frames].sort((a, b) => a.mjd - b.mjd).map((f, i) => [f.id, i]));
  const epochOf = new Map(t.frames.map((f) => [f.id, f.epoch]));
  const out = [];
  const add = (name, kind, positions, extra = {}) => {
    const pts = (positions ?? []).filter((p) => order.has(p.frame_id) && Number.isFinite(p.ra_deg))
      .sort((a, b) => order.get(a.frame_id) - order.get(b.frame_id));
    if (!pts.length) return;
    const byEpoch = new Map();
    for (const p of pts) {
      const e = epochOf.get(p.frame_id);
      if (!byEpoch.has(e)) byEpoch.set(e, []);
      byEpoch.get(e).push(p);
    }
    const means = [...byEpoch].sort((a, b) => a[0] - b[0]).map(([epoch, ps]) => ({
      epoch, ra_deg: ps.reduce((s, p) => s + p.ra_deg, 0) / ps.length, dec_deg: ps.reduce((s, p) => s + p.dec_deg, 0) / ps.length,
    }));
    out.push({ name, kind, pts, means, reach: Math.max(...pts.map((p) => sepArcsec(pts[0], p))), ...extra });
  };
  for (const d of t.detections ?? []) {
    if (d.status === "artifact") continue;
    add(d.matched_object ?? `${d.id} (${d.status})`, `detection, ${d.status}`, d.track, { mover: true, synthetic: d.synthetic !== false });
  }
  const detected = new Set((t.detections ?? []).map((d) => d.matched_object).filter(Boolean));
  for (const k of t.known_objects ?? []) {
    if (!detected.has(k.name)) add(k.name, "known small body", k.positions, { mover: true, synthetic: k.synthetic !== false });
  }
  for (const l of t.labels ?? []) {
    const imp = Number.isFinite(l.importance) ? l.importance : l.named ? 2 : 3;
    const moving = l.motion?.class && l.motion.class !== "still";
    if (imp <= 1 || (imp === 2 && moving)) {
      add(l.name, l.kind + (l.motion?.class ? ` · ${l.motion.class}` : ""), l.positions,
        { motion: l.motion, field: imp === 0, synthetic: false });
    }
  }
  return out;
}

function clear() {
  const m = getAladin();
  if (st.layers && m) {
    try { m.aladin.removeLayer?.(st.layers.lines); } catch {}
    try { m.aladin.removeLayer?.(st.layers.cat); } catch {}
    try { st.layers.lines.removeAll?.(); st.layers.cat.removeAll?.(); } catch {}
  }
  st.layers = null;
}

function colourFor(epoch) {
  const epochs = [...new Set(st.target.frames.map((f) => f.epoch))].sort((a, b) => a - b);
  return EPOCH_COLOURS[Math.max(0, epochs.indexOf(epoch)) % EPOCH_COLOURS.length];
}

function draw() {
  const m = getAladin();
  clear();
  updateNote();
  if (!m || !st.target || !st.on) return;
  const { A, aladin } = m;
  const lines = A.graphicOverlay({ name: "Traces (T35)", color: "#ffd27a", lineWidth: 2 });
  const cat = A.catalog({ name: "Traced objects (T35)", color: "#ffd27a", sourceSize: 14, shape: "circle",
    displayLabel: true, labelColumn: "name", labelColor: "#ffe2a8", labelFont: "12px sans-serif", onClick: "showPopup" });
  aladin.addOverlay(lines);
  aladin.addCatalog(cat);
  st.layers = { lines, cat };
  const sources = [];
  for (const o of st.objs) {
    // the trace itself, segment by segment in epoch colours
    for (let i = 1; i < o.pts.length; i++) {
      const a = o.pts[i - 1], b = o.pts[i];
      lines.add(A.polyline([[a.ra_deg, a.dec_deg], [b.ra_deg, b.dec_deg]], { color: colourFor(st.target.frames.find((f) => f.id === b.frame_id)?.epoch), lineWidth: 2 }));
    }
    // one dot per epoch (mean position); the shown epoch is bigger
    for (const e of o.means) {
      const r = (e.epoch === st.epoch ? 9 : 4) / 3600;
      lines.add(A.circle(e.ra_deg, e.dec_deg, r, { color: colourFor(e.epoch), lineWidth: e.epoch === st.epoch ? 3 : 1.5 }));
    }
    // slow movers: exaggerated, labelled direction arrow from the shown epoch's position
    const first = o.means[0], last = o.means[o.means.length - 1];
    if (o.means.length > 1 && o.reach > 0.3 && o.reach < SLOW_ARCSEC) {
      const here = o.means.find((e) => e.epoch === st.epoch) ?? last;
      const cd = Math.cos((here.dec_deg * Math.PI) / 180) || 1e-6;
      const dx = (last.ra_deg - first.ra_deg) * cd, dy = last.dec_deg - first.dec_deg, n = Math.hypot(dx, dy) || 1;
      const L = ARROW_ARCMIN / 60, tip = [here.ra_deg + ((dx / n) * L) / cd, here.dec_deg + (dy / n) * L];
      lines.add(A.polyline([[here.ra_deg, here.dec_deg], tip], { color: "#ffd27a", lineWidth: 1.5, lineDash: [6, 4] }));
      const k = Math.round((ARROW_ARCMIN * 60) / o.reach);
      sources.push(A.source(tip[0], tip[1], { name: `motion ×${k}, not to scale` }));
    }
    const here = o.means.find((e) => e.epoch === st.epoch) ?? o.means[o.means.length - 1];
    const rate = o.motion?.rate_arcsec_per_yr != null && o.motion.class !== "still" ? `${o.motion.rate_arcsec_per_yr.toFixed(2)}″/yr ${o.motion.direction ?? ""}` : "";
    sources.push(A.source(here.ra_deg, here.dec_deg, {
      name: o.name + (o.synthetic ? " · synthetic" : ""),
      popupTitle: o.name, popupDesc: [o.kind, rate, `${o.means.length} epoch(s), moves ${o.reach.toFixed(1)}″ in this series`].filter(Boolean).join(" · "),
    }));
  }
  cat.addSources(sources);
}

function updateNote() {
  const n = $("#traces-note");
  if (n) n.textContent = st.on && st.target ? `${st.objs.length} traced` : "";
}

function controls() {
  if ($("#traces-toggle")) return;
  const anchor = $("#explore-epochs");
  if (!anchor) return;
  anchor.after(el("label", { id: "traces-toggle", title: "Paths, per-epoch positions and names of the shown field's important objects (T35)" },
    el("input", { type: "checkbox", checked: st.on, onchange: (e) => { st.on = e.target.checked; draw(); } }),
    " Traces ", el("span", { id: "traces-note", class: "muted small" })));
}

document.addEventListener("viewer:target", (e) => {
  st.target = e.detail?.target ?? null;
  st.objs = st.target ? pickObjects(st.target) : [];
  st.epoch = null;
  controls();
  draw(); // works if the map is already up; otherwise the first explore:epoch draws
});

document.addEventListener("explore:epoch", (e) => {
  st.epoch = e.detail?.epoch ?? null;
  controls();
  draw();
});

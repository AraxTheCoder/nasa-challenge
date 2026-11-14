// T35 Tracing over the stitched sky: draw the shown field's important objects onto the explore map
// (own sky map since T36, was Aladin Lite in T30/T32): a line through their per-frame positions, one dot per epoch (mean
// position), the shown epoch's dot highlighted while the map blinks, and the name with a popup.
// Slow movers get a dashed arrow along their motion, labelled as exaggerated: at map scale
// Barnard's Star's 10"/yr is invisible otherwise.
//
// Data: target.json `labels`, `known_objects`, `detections` (RA/Dec per frame). Events:
//   viewer:target {target}  (viewer.js)     explore:epoch {epoch}  (explore.js, T32 epoch buttons)

import { $, el } from "./util.js";
import { getSky } from "./explore.js";

const st = { target: null, epoch: null, on: false, layers: null, objs: [] };   // T55 /app/: traces off by default
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

// T36 (Jonathan): drawn with a canvas hook of our own sky map (sky.js) instead of Aladin overlays.
// pickObjects() above is unchanged.
let hooked = false;

function ensureHook() {
  const sky = getSky();
  if (!sky || hooked) return;
  sky.addDrawHook(paint);
  hooked = true;
}

function colourFor(epoch) {
  const epochs = [...new Set(st.target.frames.map((f) => f.epoch))].sort((a, b) => a - b);
  return EPOCH_COLOURS[Math.max(0, epochs.indexOf(epoch)) % EPOCH_COLOURS.length];
}

function draw() {
  updateNote();
  ensureHook();
  getSky()?.redraw();
}

function paint(ctx, proj) {
  if (!st.target || !st.on) return;
  const P = (ra, dec) => { const s = proj.toScreen(ra, dec); return s.front ? s : null; };
  const epochOfFrame = new Map(st.target.frames.map((f) => [f.id, f.epoch]));
  ctx.save();
  ctx.font = "12px sans-serif";
  ctx.lineCap = "round";
  for (const o of st.objs) {
    // the trace itself, segment by segment in epoch colours
    ctx.lineWidth = 2;
    for (let i = 1; i < o.pts.length; i++) {
      const a = P(o.pts[i - 1].ra_deg, o.pts[i - 1].dec_deg), b = P(o.pts[i].ra_deg, o.pts[i].dec_deg);
      if (!a || !b) continue;
      ctx.strokeStyle = colourFor(epochOfFrame.get(o.pts[i].frame_id));
      ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
    }
    // one dot per epoch (mean position); the shown epoch is bigger
    for (const e of o.means) {
      const s = P(e.ra_deg, e.dec_deg);
      if (!s) continue;
      const big = e.epoch === st.epoch;
      ctx.strokeStyle = colourFor(e.epoch);
      ctx.lineWidth = big ? 3 : 1.5;
      ctx.beginPath(); ctx.arc(s.x, s.y, big ? 9 : 4, 0, 2 * Math.PI); ctx.stroke();
    }
    const here = o.means.find((e) => e.epoch === st.epoch) ?? o.means[o.means.length - 1];
    const hs = P(here.ra_deg, here.dec_deg);
    if (!hs) continue;
    // slow movers: exaggerated, labelled direction arrow from the shown epoch's position
    const first = o.means[0], last = o.means[o.means.length - 1];
    if (o.means.length > 1 && o.reach > 0.3 && o.reach < SLOW_ARCSEC) {
      const cd = Math.cos((here.dec_deg * Math.PI) / 180) || 1e-6;
      const dx = (last.ra_deg - first.ra_deg) * cd, dy = last.dec_deg - first.dec_deg, n = Math.hypot(dx, dy) || 1;
      const L = ARROW_ARCMIN / 60;
      const tip = P(here.ra_deg + ((dx / n) * L) / cd, here.dec_deg + (dy / n) * L);
      if (tip) {
        ctx.strokeStyle = "#ffd27a"; ctx.lineWidth = 1.5; ctx.setLineDash([6, 4]);
        ctx.beginPath(); ctx.moveTo(hs.x, hs.y); ctx.lineTo(tip.x, tip.y); ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = "#ffd27a";
        ctx.fillText(`motion ×${Math.round((ARROW_ARCMIN * 60) / o.reach)}, not to scale`, tip.x + 6, tip.y - 4);
      }
    }
    ctx.fillStyle = "#ffe2a8";
    ctx.strokeStyle = "rgba(0,0,0,0.7)"; ctx.lineWidth = 3;
    const name = o.name + (o.synthetic ? " · synthetic" : "");
    ctx.strokeText(name, hs.x + 12, hs.y + 4);
    ctx.fillText(name, hs.x + 12, hs.y + 4);
  }
  ctx.restore();
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

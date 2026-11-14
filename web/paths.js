// Movement paths (T22): for every object with a position per frame (labels, known objects,
// detections) draw its path through all frames into the #overlay SVG: one line, a tick per frame,
// colour from early (blue) to late (orange), the current position ringed and named.
// Slow movers whose whole path is shorter than SLOW_PX get an exaggerated arrow that says so.
//
// Listens to the viewer's events; knows nothing else about the viewer:
//   viewer:target {target}   a target was shown (null = cleared)
//   viewer:frame  {frameId}  a frame was shown

import { $, el } from "./util.js";
import "./trail.js"; // T23 trail view, same viewer events

const SVG = "http://www.w3.org/2000/svg";
document.head.append(el("link", { rel: "stylesheet", href: new URL("./paths.css", import.meta.url).href }));
const SLOW_PX = 3;          // paths shorter than this get an exaggerated direction arrow
const STILL_PX = 0.3;       // below this an object counts as not moving: no path, marker only
const ARROW_PX = 12;        // length of the exaggerated arrow in image pixels

const opts = { names: true, catalogue: false, movers: true, paths: true };
const st = { target: null, frames: [], order: new Map(), objects: [], frameId: null, unit: 1 };

const svg = (tag, attrs = {}, ...kids) => {
  const n = document.createElementNS(SVG, tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null) n.setAttribute(k, v);
  n.append(...kids.filter(Boolean));
  return n;
};

// ---------- data ----------

function collect(t) {
  const out = [];
  for (const l of t.labels ?? []) {
    out.push({
      group: l.named ? "names" : "catalogue", name: l.name, info: l.kind, source: l.source, mag: l.mag,
      otype: l.otype, pm: l.pm_mas_yr, motion: l.motion, positions: l.positions ?? [], synthetic: false,
    });
  }
  for (const k of t.known_objects ?? []) {
    out.push({ group: "movers", name: k.name, info: "known small body", source: k.source, positions: k.positions ?? [], synthetic: k.synthetic !== false });
  }
  for (const d of t.detections ?? []) {
    if (d.status === "artifact") continue;
    out.push({
      group: "movers", name: d.matched_object ?? `${d.id} (${d.status})`, info: `detection, ${d.status}`,
      rate: d.motion?.rate_arcsec_per_hr, score: d.score, source: "our detection", positions: d.track ?? [], synthetic: d.synthetic !== false,
    });
  }
  // a detection matched to a known object replaces it, so the same body isn't drawn twice
  const matched = new Set((t.detections ?? []).filter((d) => d.status !== "artifact").map((d) => d.matched_object).filter(Boolean));
  for (let i = out.length - 1; i >= 0; i--) {
    if (out[i].info === "known small body" && matched.has(out[i].name)) out.splice(i, 1);
  }
  for (const o of out) {
    o.pts = o.positions
      .filter((p) => st.order.has(p.frame_id) && Number.isFinite(p.x) && Number.isFinite(p.y))
      .sort((a, b) => st.order.get(a.frame_id) - st.order.get(b.frame_id));
    o.byFrame = new Map(o.pts.map((p) => [p.frame_id, p]));
    const xs = o.pts.map((p) => p.x), ys = o.pts.map((p) => p.y);
    o.extent = o.pts.length ? Math.hypot(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys)) : 0;
  }
  return out.filter((o) => o.pts.length);
}

/** 0 = first frame time, 1 = last frame time. */
function timeFrac(frameId) {
  const f = st.frames[st.order.get(frameId)];
  const t0 = st.frames[0].mjd, t1 = st.frames[st.frames.length - 1].mjd;
  return t1 > t0 ? (f.mjd - t0) / (t1 - t0) : 0;
}
// early = blue, late = orange, through a light middle so both ends read on dark sky
const timeColour = (u) => `hsl(${Math.round(205 - 180 * u)} 90% ${Math.round(62 + 10 * Math.sin(Math.PI * u))}%)`;

// ---------- drawing ----------

function layer() {
  let g = $("#paths-layer");
  if (!g) {
    const { width = 1, height = 1 } = st.target.image ?? {};
    const clip = svg("clipPath", { id: "paths-clip" }, svg("rect", { x: -0.5, y: -0.5, width, height }));
    g = svg("g", { id: "paths-layer", "clip-path": "url(#paths-clip)" });
    $("#overlay").append(svg("defs", {}, clip), g);
  }
  return g;
}

function draw() {
  if (!st.target) return;
  const g = layer();
  g.replaceChildren();
  const u = st.unit;               // screen px per image px
  const px = (n) => n / u;         // n screen px in image px
  const visible = st.objects.filter((o) => opts[o.group]);
  // paths first, markers and names on top
  const paths = [], marks = [], names = [], hits = [];
  for (const o of visible) {
    const moving = o.extent >= STILL_PX;
    if (opts.paths && moving && o.pts.length > 1) {
      for (let i = 1; i < o.pts.length; i++) {
        const a = o.pts[i - 1], b = o.pts[i];
        paths.push(svg("line", {
          x1: a.x, y1: a.y, x2: b.x, y2: b.y, class: "path-seg",
          stroke: timeColour((timeFrac(a.frame_id) + timeFrac(b.frame_id)) / 2),
        }));
      }
      for (const p of o.pts) {
        paths.push(svg("circle", { cx: p.x, cy: p.y, r: px(2.2), class: "path-tick", fill: timeColour(timeFrac(p.frame_id)) }));
      }
    }
    const cur = o.byFrame.get(st.frameId);
    if (!cur) continue;
    if (opts.paths && moving && o.extent < SLOW_PX && o.pts.length > 1) {
      // exaggerated arrow along the overall motion, clearly marked as not to scale
      const a = o.pts[0], b = o.pts[o.pts.length - 1];
      const dx = (b.x - a.x) / o.extent, dy = (b.y - a.y) / o.extent;
      const x2 = cur.x + dx * ARROW_PX, y2 = cur.y + dy * ARROW_PX;
      const head = px(6), nx = -dy, ny = dx;
      paths.push(svg("line", { x1: cur.x, y1: cur.y, x2, y2, class: "path-arrow" }));
      paths.push(svg("polygon", {
        class: "path-arrowhead",
        points: `${x2 + dx * head},${y2 + dy * head} ${x2 + nx * head * 0.6},${y2 + ny * head * 0.6} ${x2 - nx * head * 0.6},${y2 - ny * head * 0.6}`,
      }));
      const k = Math.round(ARROW_PX / o.extent);
      names.push(svg("text", { x: x2 + dx * px(10), y: y2 + dy * px(10) + px(4), class: "path-note", "font-size": px(11) },
        `motion ×${k}, not to scale`));
    }
    const ring = o.group === "catalogue" ? 4 : 9;
    marks.push(svg("circle", { cx: cur.x, cy: cur.y, r: px(ring), class: `path-mark is-${o.group}` }));
    hits.push(svg("circle", { cx: cur.x, cy: cur.y, r: px(Math.max(ring + 3, 8)), class: "path-hit", "data-obj": st.objects.indexOf(o) }));
    if (o.group !== "catalogue") {
      const right = cur.x < (st.target.image?.width ?? 1) * 0.7;
      const cls = o.motion?.class && o.motion.class !== "still" ? ` · ${o.motion.class}` : "";
      const text = o.name + cls + (o.synthetic ? " · synthetic" : "");
      names.push(svg("text", {
        x: cur.x + (right ? 1 : -1) * px(ring + 5), y: cur.y + px(4), "text-anchor": right ? "start" : "end",
        class: `path-name is-${o.group}`, "font-size": px(12),
      }, text));
    }
  }
  g.append(...paths, ...marks, ...names, ...hits);
  if (tip.obj && !visible.includes(tip.obj)) hideTip(true);
  else if (tip.obj) fillTip(tip.obj);
  updateLegend(visible);
}

// ---------- hover / click info ----------

const tip = { obj: null, pinned: false };

function tipEl() {
  let t = $("#paths-tip");
  if (!t) {
    t = el("div", { id: "paths-tip", class: "paths-tip", role: "tooltip", hidden: true });
    $("#stage").append(t);
  }
  return t;
}

const sexa = (deg, hours) => {
  let v = hours ? deg / 15 : Math.abs(deg);
  const h = Math.floor(v), m = Math.floor((v - h) * 60), s = ((v - h) * 60 - m) * 60;
  const sign = hours ? "" : deg < 0 ? "−" : "+";
  return hours ? `${h}h${String(m).padStart(2, "0")}m${s.toFixed(1).padStart(4, "0")}s`
               : `${sign}${h}°${String(m).padStart(2, "0")}′${s.toFixed(0).padStart(2, "0")}″`;
};
// direction of motion in the image, as position angle east of north (x right = west, y down = south)
const paDeg = (dx, dy) => ((Math.atan2(-dx, -dy) * 180) / Math.PI + 360) % 360;
const compass = (pa) => ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][Math.round(pa / 45) % 8];

function fillTip(o) {
  const t = tipEl();
  const cur = o.byFrame.get(st.frameId) ?? o.pts[0];
  const first = o.pts[0], last = o.pts[o.pts.length - 1];
  const scale = st.target.image?.pixel_scale_arcsec ?? 6.15;
  const rows = [["Type", o.info + (o.otype && o.otype !== "*" ? ` (${o.otype})` : "")]];
  rows.push(["Source", o.source === "simbad" ? "SIMBAD" : o.source === "gaia_dr3" ? "Gaia DR3" : (o.source ?? "–")]);
  if (o.mag != null) rows.push(["Brightness", `G = ${o.mag.toFixed(1)} mag`]);
  if (o.pm != null) {
    const pa = o.extent > 0 ? paDeg(last.x - first.x, last.y - first.y) : null;
    rows.push(["Proper motion", `${(o.pm / 1000).toFixed(o.pm >= 1000 ? 2 : 3)}″/yr` + (pa != null && o.pm > 20 ? ` toward ${compass(pa)} (${pa.toFixed(0)}°)` : "")]);
  }
  if (o.motion?.class) {
    const m = o.motion, rate = m.class === "fast mover" ? `${m.max_rate_within_epoch_arcsec_per_hr.toFixed(1)}″/h`
      : m.rate_arcsec_per_yr != null && m.class !== "still" ? `${m.rate_arcsec_per_yr.toFixed(2)}″/yr` : "";
    rows.push(["Motion", `${m.class}${rate ? ` · ${rate}` : ""}${m.direction && m.class !== "still" ? ` toward ${m.direction}` : ""}`]);
    rows.push(["", m.note]);
  }
  if (o.rate != null) rows.push(["Rate", `${o.rate.toFixed(1)}″/h`]);
  if (o.score != null) rows.push(["Score", o.score.toFixed(2)]);
  if (o.pts.length > 1) {
    const d0 = st.frames[st.order.get(first.frame_id)]?.time_utc?.slice(0, 10), d1 = st.frames[st.order.get(last.frame_id)]?.time_utc?.slice(0, 10);
    rows.push(["Over this series", o.extent < STILL_PX ? `doesn't move visibly (${(o.extent * scale).toFixed(1)}″)`
      : `moves ${o.extent.toFixed(1)} px = ${(o.extent * scale).toFixed(1)}″, ${d0} → ${d1}`]);
  }
  rows.push(["Here", `RA ${sexa(cur.ra_deg, true)}  Dec ${sexa(cur.dec_deg, false)}`]);
  rows.push(["", `${cur.ra_deg.toFixed(5)}°, ${cur.dec_deg.toFixed(5)}° · pixel ${cur.x.toFixed(1)}, ${cur.y.toFixed(1)}`]);
  if (o.synthetic) rows.push(["Note", "synthetic, not a real object"]);
  const link = !o.synthetic && Number.isFinite(cur.ra_deg)
    ? el("a", { href: `https://simbad.cfa.harvard.edu/simbad/sim-coo?Coord=${cur.ra_deg.toFixed(5)}%20${cur.dec_deg >= 0 ? "%2B" : ""}${cur.dec_deg.toFixed(5)}&Radius=10&Radius.unit=arcsec`, target: "_blank", rel: "noopener" }, "Look up in SIMBAD ↗")
    : null;
  t.replaceChildren(
    el("strong", {}, o.name),
    el("dl", {}, ...rows.flatMap(([k, v]) => [el("dt", {}, k), el("dd", {}, v)])),
    tip.pinned ? el("div", { class: "paths-tip-foot" }, link, el("button", { type: "button", class: "link", onclick: () => hideTip(true) }, "Close")) : el("div", { class: "paths-tip-foot muted" }, "click to pin"),
  );
  // place next to the object, flipped to stay inside the stage
  const stage = $("#stage").getBoundingClientRect();
  const x = (cur.x + 0.5) * st.unit, y = (cur.y + 0.5) * st.unit;
  t.hidden = false;
  const w = t.offsetWidth, h = t.offsetHeight;
  t.style.left = `${Math.max(4, Math.min(stage.width - w - 4, x + 14 + w > stage.width ? x - w - 14 : x + 14))}px`;
  t.style.top = `${Math.max(4, Math.min(stage.height - h - 4, y - h / 2))}px`;
}

function hideTip(force = false) {
  if (tip.pinned && !force) return;
  tip.obj = null; tip.pinned = false;
  tipEl().hidden = true;
}

function hitObject(e) {
  const i = e.target?.dataset?.obj;
  return i == null ? null : st.objects[Number(i)];
}

document.addEventListener("pointerover", (e) => {
  if (!e.target.classList?.contains("path-hit") || tip.pinned) return;
  tip.obj = hitObject(e); if (tip.obj) fillTip(tip.obj);
});
document.addEventListener("pointerout", (e) => {
  if (e.target.classList?.contains("path-hit")) hideTip();
});
document.addEventListener("click", (e) => {
  if (e.target.classList?.contains("path-hit")) {
    const o = hitObject(e);
    tip.pinned = !(tip.pinned && tip.obj === o); tip.obj = o;
    if (tip.pinned) fillTip(o); else hideTip(true);
  } else if (tip.pinned && !e.target.closest?.("#paths-tip")) hideTip(true);
});
document.addEventListener("keydown", (e) => { if (e.key === "Escape") hideTip(true); });

// ---------- controls + legend ----------

function controls() {
  let box = $("#paths-controls");
  if (box) return box;
  const cb = (key, label) => el("label", { class: "paths-check" },
    el("input", { type: "checkbox", id: `paths-${key}`, checked: opts[key], onchange: (e) => { opts[key] = e.target.checked; draw(); } }),
    ` ${label}`);
  box = el("div", { id: "paths-controls", class: "paths-controls" },
    el("div", { class: "paths-row" },
      cb("paths", "Paths"), cb("names", "Names"), cb("movers", "Known objects & detections"), cb("catalogue", "Catalogue stars")),
    el("div", { class: "paths-legend" },
      el("span", { id: "paths-t0", class: "muted small" }), el("span", { class: "paths-ramp", "aria-hidden": "true" }),
      el("span", { id: "paths-t1", class: "muted small" }), el("span", { id: "paths-count", class: "muted small" })));
  $("#viewer-body .controls").after(box);
  return box;
}

function updateLegend(visible) {
  const box = controls();
  box.hidden = st.objects.length === 0;
  $("#paths-t0").textContent = st.frames[0]?.time_utc?.slice(0, 10) ?? "";
  $("#paths-t1").textContent = st.frames[st.frames.length - 1]?.time_utc?.slice(0, 10) ?? "";
  const moving = visible.filter((o) => o.extent >= STILL_PX).length;
  $("#paths-count").textContent = `· ${visible.length} shown, ${moving} moving`;
  for (const g of ["names", "catalogue", "movers"]) {
    const n = st.objects.filter((o) => o.group === g).length;
    const input = $(`#paths-${g}`);
    input.disabled = n === 0;
    input.parentElement.title = n ? `${n} in this field` : "none in this field";
  }
}

// ---------- wiring ----------

function measure() {
  const stage = $("#stage");
  const w = st.target?.image?.width ?? 1;
  st.unit = stage && stage.clientWidth ? stage.clientWidth / w : 1;
}

document.addEventListener("viewer:target", (e) => {
  const t = e.detail?.target ?? null;
  st.target = t;
  st.frameId = null;
  hideTip(true);
  if (!t) { $("#paths-controls")?.setAttribute("hidden", ""); return; }
  st.frames = [...t.frames].sort((a, b) => a.mjd - b.mjd);
  st.order = new Map(st.frames.map((f, i) => [f.id, i]));
  st.objects = collect(t);
  measure();
  controls();
});

document.addEventListener("viewer:frame", (e) => {
  st.frameId = e.detail?.frameId ?? null;
  draw();
});

new ResizeObserver(() => { if (st.target) { measure(); draw(); } }).observe(document.documentElement);

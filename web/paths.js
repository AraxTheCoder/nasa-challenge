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
import "./inspector.js"; // T23 object inspector, opened by clicking an object

const SVG = "http://www.w3.org/2000/svg";
document.head.append(el("link", { rel: "stylesheet", href: new URL("./paths.css", import.meta.url).href }));
const SLOW_PX = 3;          // paths shorter than this get an exaggerated direction arrow
const STILL_PX = 0.3;       // below this an object counts as not moving: no path, marker only
const ARROW_PX = 12;        // length of the exaggerated arrow in image pixels

const opts = { names: true, catalogue: false, movers: true, paths: true, allNames: false };
const NAME_CAP = 8; // T34: at most this many names on the image unless "all names" is on
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
    // importance (CONTRACTS v0.7): 0 field object, 1 notable motion, 2 named/notable, 3 catalogue no., 4 Gaia.
    // Older targets have none: derive it the same way, roughly.
    const notable = l.motion?.class && l.motion.class !== "still";
    const imp = Number.isFinite(l.importance) ? l.importance
      : l.source === "gaia_dr3" ? 4 : notable ? 1 : l.named ? 2 : 3;
    out.push({
      group: imp === 4 ? "catalogue" : "names", importance: imp, name: l.name, info: l.kind, source: l.source,
      mag: l.mag, otype: l.otype, pm: l.pm_mas_yr, motion: l.motion, aliases: l.aliases ?? [],
      positions: l.positions ?? [], synthetic: false,
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
  const paths = [], marks = [], names = [], hits = [], wanted = [];
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
    const field = o.importance === 0, minor = o.importance === 3;
    const ring = o.group === "catalogue" ? 4 : field ? 13 : minor ? 5 : 9;
    marks.push(svg("circle", { cx: cur.x, cy: cur.y, r: px(ring), class: `path-mark is-${o.group}${field ? " is-field" : ""}${minor ? " is-minor" : ""}` }));
    hits.push(svg("circle", { cx: cur.x, cy: cur.y, r: px(Math.max(ring + 3, 8)), class: "path-hit", tabindex: 0,
      role: "button", "aria-label": `${o.name}, ${o.info ?? ""}`, "data-obj": st.objects.indexOf(o) }));
    // T34: names for movers always; for labels only importance <= 2 (or all with "all names")
    if (o.group === "movers" || o.importance <= 2 || (opts.allNames && o.group !== "catalogue")) {
      const cls = o.motion?.class && o.motion.class !== "still" ? ` · ${o.motion.class}` : "";
      const prio = o.group === "movers" ? -1 : o.importance;
      wanted.push({ o, cur, ring, text: o.name + cls + (o.synthetic ? " · synthetic" : ""), prio });
    }
  }
  names.push(...placeNames(wanted, px));
  g.append(...paths, ...marks, ...names, ...hits);
  if (tip.obj && !visible.includes(tip.obj)) hideTip(true);
  else if (tip.obj) fillTip(tip.obj);
  updateLegend(visible);
}

// Cleaner labels: each name tries right, left, above, below its object and takes the first spot
// that overlaps no name placed before it (moving objects go first). No free spot: name hidden,
// ring stays, hover still shows everything.
function placeNames(wanted, px) {
  const W = st.target.image?.width ?? 1, H = st.target.image?.height ?? 1;
  const fs = px(12), charW = fs * 0.62, placed = [], out = [];
  let hidden = 0;
  wanted.sort((a, b) => a.prio - b.prio || (a.o.mag ?? 99) - (b.o.mag ?? 99));
  for (const w of wanted) {
    const tw = w.text.length * charW, th = fs * 1.1, gap = px(w.ring + 5);
    const { x, y } = w.cur;
    const tries = [
      { x: x + gap, y: y + fs * 0.35, anchor: "start", box: [x + gap, y - th / 2, tw, th] },
      { x: x - gap, y: y + fs * 0.35, anchor: "end", box: [x - gap - tw, y - th / 2, tw, th] },
      { x, y: y - gap - fs * 0.2, anchor: "middle", box: [x - tw / 2, y - gap - th, tw, th] },
      { x, y: y + gap + fs * 0.9, anchor: "middle", box: [x - tw / 2, y + gap, tw, th] },
    ];
    const fits = (b) => b[0] >= -0.5 && b[1] >= -0.5 && b[0] + b[2] <= W && b[1] + b[3] <= H &&
      !placed.some((p) => b[0] < p[0] + p[2] && p[0] < b[0] + b[2] && b[1] < p[1] + p[3] && p[1] < b[1] + b[3]);
    const spot = !opts.allNames && out.length >= NAME_CAP ? null : tries.find((t) => fits(t.box));
    if (!spot) { hidden++; continue; }
    placed.push(spot.box);
    out.push(svg("text", { x: spot.x, y: spot.y, "text-anchor": spot.anchor, class: `path-name is-${w.o.group}`, "font-size": fs }, w.text));
  }
  st.hiddenNames = hidden;
  return out;
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
  if (o.importance === 0) rows.push(["", "the object at the position you asked for"]);
  if (o.aliases?.length) rows.push(["Also", o.aliases.slice(0, 4).join(", ") + (o.aliases.length > 4 ? ` +${o.aliases.length - 4}` : "")]);
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
    tip.pinned ? el("div", { class: "paths-tip-foot" }, link, el("button", { type: "button", class: "link", onclick: () => hideTip(true) }, "Close")) : el("div", { class: "paths-tip-foot muted" }, "click for the inspector"),
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
    hideTip(true);
    document.dispatchEvent(new CustomEvent("paths:select", { detail: { obj: o } }));
  } else if (tip.pinned && !e.target.closest?.("#paths-tip")) hideTip(true);
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") hideTip(true);
  if ((e.key === "Enter" || e.key === " ") && e.target.classList?.contains("path-hit")) {
    e.preventDefault(); e.stopPropagation();
    hideTip(true);
    document.dispatchEvent(new CustomEvent("paths:select", { detail: { obj: hitObject(e) } }));
  }
}, true);
document.addEventListener("focusin", (e) => {
  if (e.target.classList?.contains("path-hit") && !tip.pinned) { tip.obj = hitObject(e); if (tip.obj) fillTip(tip.obj); }
});
document.addEventListener("focusout", (e) => { if (e.target.classList?.contains("path-hit")) hideTip(); });

// ---------- controls + legend ----------

function controls() {
  let box = $("#paths-controls");
  if (box) return box;
  const cb = (key, label) => el("label", { class: "paths-check" },
    el("input", { type: "checkbox", id: `paths-${key}`, checked: opts[key], onchange: (e) => { opts[key] = e.target.checked; draw(); } }),
    ` ${label}`);
  box = el("div", { id: "paths-controls", class: "paths-controls" },
    el("div", { class: "paths-row" },
      cb("paths", "Paths"), cb("names", "Names"), cb("allNames", "All names"), cb("movers", "Known objects & detections"), cb("catalogue", "Catalogue stars")),
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
  $("#paths-count").textContent = `· ${visible.length} shown, ${moving} moving` +
    (st.hiddenNames ? ` · ${st.hiddenNames} more name${st.hiddenNames === 1 ? "" : "s"} on hover` : "");
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

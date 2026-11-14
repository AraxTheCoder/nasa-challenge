// T72 Labels anywhere on the explore map: when zoomed in to MAX_FOV_DEG or closer, ask the Live API
// for the catalogue labels around the view (GET /api/sky-labels: SIMBAD, VSX, CatWISE; cached on the
// server) and draw them. The API sorts them by importance; names are placed in that order where they
// fit, the rest get a dot (name on hover). Names that the field traces (traces.js) already draw are
// skipped. Follows the app's Labels switch ("labels:changed").

import { $, el, sourceName } from "./util.js";
import { getApiBase, getSky } from "./explore.js";

const MAX_FOV_DEG = 2.0;     // wider views: too many objects, too little room
const DEBOUNCE_MS = 350;
const COLOURS = { simbad: "#9cc3ff", vsx: "#ffb36b", catwise2020: "#e88bff" };
const st = { on: true, region: null, labels: [], pending: null, timer: null, hooked: false, placed: [],
  traced: new Set(), tip: null };

function namesBudget(fov) { return fov > 1 ? 30 : fov > 0.4 ? 70 : 200; }

function regionKey(v) {
  const r = Math.min(1, Math.max(0.25, v.fov * 0.6));
  return { ra: v.ra, dec: v.dec, radius: r };
}

function covers(region, v) {
  if (!region) return false;
  const d = Math.PI / 180;
  const c = Math.sin(region.dec * d) * Math.sin(v.dec * d) + Math.cos(region.dec * d) * Math.cos(v.dec * d) * Math.cos((region.ra - v.ra) * d);
  const sep = Math.acos(Math.min(1, Math.max(-1, c))) / d;
  return sep + v.fov * 0.5 <= region.radius * 1.1;
}

async function fetchFor(v) {
  const api = getApiBase();
  if (!api) return;
  const q = regionKey(v);
  const url = `${api.replace(/\/$/, "")}/api/sky-labels?ra=${q.ra.toFixed(4)}&dec=${q.dec.toFixed(4)}&radius=${q.radius}`;
  st.pending = url;
  try {
    const res = await fetch(url);
    if (!res.ok) return;
    const body = await res.json();
    if (st.pending !== url) return;            // a newer view asked meanwhile
    st.region = { ra: body.center.ra_deg, dec: body.center.dec_deg, radius: body.radius_deg };
    st.labels = body.labels ?? [];
    getSky()?.redraw();
  } catch { /* the map works without names */ }
}

function onChange(v) {
  if (!st.on || !v || v.fov > MAX_FOV_DEG) return;
  if (covers(st.region, v)) return;
  clearTimeout(st.timer);
  st.timer = setTimeout(() => fetchFor(v), DEBOUNCE_MS);
}

function paint(ctx, proj) {
  st.placed = [];
  const v = proj.view();
  if (!st.on || !v || v.fov > MAX_FOV_DEG || !st.labels.length) return;
  const boxes = [];
  let named = 0;
  const budget = namesBudget(v.fov);
  ctx.save();
  ctx.font = "11px sans-serif";
  for (const l of st.labels) {
    if (st.traced.has(l.name)) continue;
    const s = proj.toScreen(l.ra_deg, l.dec_deg);
    if (!s.front || s.x < -20 || s.y < -20 || s.x > v.width + 20 || s.y > v.height + 20) continue;
    const colour = COLOURS[l.source] ?? "#9cc3ff";
    ctx.strokeStyle = colour; ctx.lineWidth = 1.2;
    ctx.beginPath(); ctx.arc(s.x, s.y, 3.5, 0, 2 * Math.PI); ctx.stroke();
    st.placed.push({ x: s.x, y: s.y, l });
    if (named >= budget) continue;
    const w = ctx.measureText(l.name).width + 4, h = 13;
    const box = { x: s.x + 6, y: s.y - 10, w, h };
    if (boxes.some((b) => box.x < b.x + b.w && b.x < box.x + box.w && box.y < b.y + b.h && b.y < box.y + box.h)) continue;
    boxes.push(box);
    named++;
    ctx.fillStyle = colour; ctx.strokeStyle = "rgba(0,0,0,0.75)"; ctx.lineWidth = 3;
    ctx.strokeText(l.name, s.x + 7, s.y + 1);
    ctx.fillText(l.name, s.x + 7, s.y + 1);
  }
  ctx.restore();
}

// ---------- hover: what is this dot? ----------

function tipEl() {
  if (!st.tip) {
    st.tip = el("div", { class: "paths-tip", hidden: true, style: "position:absolute;pointer-events:none;z-index:5" });
    $("#sky")?.append(st.tip);
  }
  return st.tip;
}

function onMove(e) {
  const box = $("#sky")?.getBoundingClientRect();
  if (!box) return;
  const x = e.clientX - box.left, y = e.clientY - box.top;
  let best = null, bd = 64;
  for (const p of st.placed) {
    const d = (p.x - x) ** 2 + (p.y - y) ** 2;
    if (d < bd) { bd = d; best = p; }
  }
  const tip = tipEl();
  if (!best) { tip.hidden = true; return; }
  const l = best.l;
  const rows = [l.kind, sourceName(l.source), l.note, l.mag != null ? `${l.mag_band ?? "G"} = ${l.mag.toFixed(1)} mag` : null,
    l.pm_mas_yr ? `moves ${(l.pm_mas_yr / 1000).toFixed(l.pm_mas_yr >= 1000 ? 2 : 3)}″/yr` : null,
    l.aliases?.length ? `also ${l.aliases.slice(0, 3).join(", ")}` : null].filter(Boolean);
  tip.replaceChildren(el("strong", {}, l.name), ...rows.map((r) => el("div", { class: "small" }, r)));
  tip.style.left = `${best.x + 12}px`;
  tip.style.top = `${best.y + 12}px`;
  tip.hidden = false;
}

// ---------- wiring ----------

function hook() {
  const sky = getSky();
  if (!sky || st.hooked) return;
  st.hooked = true;
  sky.addDrawHook(paint);
  sky.on("change", onChange);
  const c = $("#sky");
  c?.addEventListener("mousemove", onMove);
  c?.addEventListener("mouseleave", () => { if (st.tip) st.tip.hidden = true; });
  onChange(sky.view());
}

document.addEventListener("explore:ready", hook);
document.addEventListener("labels:changed", (e) => {
  st.on = Boolean(e.detail?.on);
  hook();
  if (st.on) onChange(getSky()?.view());
  getSky()?.redraw();
});
// Names that traces.js draws for the shown field (same rule as its pickObjects): not twice.
document.addEventListener("viewer:target", (e) => {
  const t = e.detail?.target;
  st.traced = new Set();
  for (const l of t?.labels ?? []) {
    const imp = Number.isFinite(l.importance) ? l.importance : l.named ? 2 : 3;
    const moving = l.motion?.class && l.motion.class !== "still";
    if (imp <= 1 || (imp === 2 && moving)) {
      st.traced.add(l.name);
      (l.aliases ?? []).forEach((a) => st.traced.add(a));
    }
  }
  getSky()?.redraw();
});

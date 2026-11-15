// T133: optional order-6 community attention overlay. The API supplies distinct-browser tiers.
import { $, el } from "./util.js";
import { DEFAULT_API } from "./api.js";
import * as explore from "./explore.js";
import { ang2pix, tileGrid } from "./healpix.js";

const ORDER = 6, COLOURS = { unvisited: "#a4acba", light: "#68b9ff", moderate: "#e2b859", high: "#78d2a5" };
const state = { on: false, hooked: false, tiles: [], request: 0, timer: null };
const note = (text) => { const n = $("#community-coverage-note"); if (n) { n.textContent = text; n.hidden = !state.on; } };
function bounds() {
  const sky = $("#sky");
  return sky ? { width: sky.clientWidth, height: sky.clientHeight } : null;
}
function samples() {
  const box = bounds(), sky = explore.getSky(), v = explore.view();
  if (!box?.width || !box.height || !sky?.proj || !v || v.fovArcmin > 480) return null;
  const ids = new Set();
  for (let x = 0; x <= 24; x++) for (let y = 0; y <= 16; y++) {
    const p = sky.proj.fromScreen(box.width * x / 24, box.height * y / 16);
    if (p) ids.add(ang2pix(ORDER, p[0], p[1]));
    if (ids.size > 200) return null;
  }
  return [...ids];
}
async function refresh() {
  const request = ++state.request;
  state.tiles = []; explore.redraw();
  if (!state.on) { note(""); return; }
  const ids = samples();
  if (!ids?.length) { note("Zoom in to see tile coverage (view up to 8°). Coverage overview is in Community."); return; }
  note("Loading community coverage…");
  try {
    const base = (explore.getApiBase() ?? new URLSearchParams(location.search).get("api") ?? DEFAULT_API).replace(/\/$/, "");
    const response = await fetch(`${base}/api/community/counts?pix=${ids.join(",")}`, { cache: "no-cache", signal: AbortSignal.timeout(15000) });
    if (!response.ok) throw Error();
    const data = await response.json();
    if (request !== state.request || !state.on) return;
    if (!data.coverage) { note("Community coverage needs the updated Live API."); return; }
    state.tiles = ids.filter((pix) => data.coverage[String(pix)]).map((pix) => ({ pix, ...data.coverage[String(pix)] }));
    note("Attention: gray = unvisited · blue = 1–2 browsers · amber = 3–9 · green = 10+. Visits do not establish a complete review.");
    explore.redraw();
  } catch { if (request === state.request) note("Community coverage unavailable. Try switching it on again."); }
}
function paint(ctx, proj) {
  if (!state.on || !state.tiles.length || document.body.classList.contains("community-workspace")) return;
  ctx.save();
  for (const tile of state.tiles) {
    const n = 4, grid = tileGrid(ORDER, tile.pix, n), indices = [];
    for (let b = 0; b < n; b++) indices.push(b);
    for (let a = 0; a < n; a++) indices.push(a * (n + 1) + n);
    for (let b = n; b > 0; b--) indices.push(n * (n + 1) + b);
    for (let a = n; a > 0; a--) indices.push(a * (n + 1));
    const points = indices.map((i) => proj.toScreen(grid[2 * i], grid[2 * i + 1]));
    if (points.some((p) => !p.front)) continue;
    const colour = COLOURS[tile.level];
    if (!colour) continue;
    ctx.beginPath();
    points.forEach((p, i) => i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y));
    ctx.closePath();
    ctx.fillStyle = colour; ctx.globalAlpha = .09; ctx.fill();
    ctx.strokeStyle = colour; ctx.globalAlpha = .8; ctx.lineWidth = 1.5;
    ctx.setLineDash(tile.level === "unvisited" ? [4, 4] : []); ctx.stroke();
  }
  ctx.restore();
}
function hook() {
  const sky = explore.getSky();
  if (!sky?.addDrawHook || state.hooked) return;
  const row = $("#labels-toggle")?.closest(".hud-row");
  if (!row) return;
  state.hooked = true;
  const input = el("input", { id: "community-coverage-toggle", type: "checkbox", "aria-label": "Community coverage", "aria-describedby": "community-coverage-note" });
  const label = el("label", { class: "community-coverage-label" }, input, " Community coverage",
    el("span", { id: "community-coverage-note", class: "small muted", hidden: true, role: "status" }));
  row.append(label);
  sky.addDrawHook(paint);
  input.addEventListener("change", () => { state.on = input.checked; refresh(); });
  const schedule = () => {
    if (!state.on) return;
    ++state.request; state.tiles = []; explore.redraw();
    clearTimeout(state.timer); state.timer = setTimeout(refresh, 350);
  };
  sky.on("change", schedule);
  document.addEventListener("community:coverage-changed", schedule);
}
document.addEventListener("explore:ready", hook);
setTimeout(hook, 0);

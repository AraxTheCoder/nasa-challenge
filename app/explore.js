// T30/T36 Sky map: Google-Earth-style pan/zoom over the whole sky with our own HiPS renderer
// (sky.js, no dependencies). T55: one base map only, SPHEREx 102 bands with live deep zoom.
// Overlays: the shown field's SPHEREx epochs (T32), blinkable.
// Draw hooks let other modules (field outline, traces.js) paint on top.

import { createSky } from "./sky.js";

export const SURVEYS = [
  // T42: IRSA cube up to order 5, deeper zoom = live tiles from the AWS level-2 images (our server)
  { id: "spherex-live", label: "SPHEREx · 102 bands · live deep zoom",
    urls: [], fallback: ["https://irsa.ipac.caltech.edu/data/hips/SPHEREx/spherex_allsky_cube"] },
];
export const DEFAULT_SURVEY = "spherex-live";

let sky = null;
let apiBase = null;        // T41: our server caches + prefetches the map tiles (/api/sky/<id>)
let outlines = [];         // T55: [{state, pts}] red outlines of the blinked field cells
let epochLayers = [];

export const getSky = () => sky;
export const getApiBase = () => apiBase;   // T72: skylabels.js asks the Live API too

/** Create the map. opts: {ra, dec, fovDeg} */
export async function initExplore(container, opts = {}) {
  apiBase = opts.api ?? null;
  sky = createSky(container, { ra: opts.ra ?? 269.4463, dec: opts.dec ?? 4.7682, fov: opts.fovDeg ?? 2 });
  sky.addDrawHook(drawField);
  await setSurvey(DEFAULT_SURVEY);
  document.dispatchEvent(new CustomEvent("explore:ready"));   // T72: skylabels.js hooks in
  return sky;
}

/** Switch the base map; tries each mirror in turn. Returns the layer (.depth > 1 for cubes). */
export async function setSurvey(id) {
  const s = SURVEYS.find((x) => x.id === id);
  if (!s || !sky) return null;
  let last;
  const urls = [...(apiBase ? [`${apiBase.replace(/\/$/, "")}/api/sky/${s.id}`] : []), ...s.urls, ...(s.fallback ?? [])];
  for (const url of urls) {
    try {
      const layer = await sky.setBase(url, { label: s.label });
      document.dispatchEvent(new CustomEvent("explore:survey", { detail: { id, layer } }));
      return layer;
    } catch (e) { last = e; }
  }
  throw new Error(`${s.label}: map server not reachable (${last?.message ?? "?"})`);
}

/** Wavelengths (µm) of a cube map's slices, or []. */
export function bandWavelengths() {
  return (sky?.base?.props.data_cube_crval3_arr ?? "").split(/\s+/).filter(Boolean).map(Number);
}

/** Cube maps: choose the band (0-based slice). */
export function setBand(i) { sky?.setSlice(i); }

export function goTo(ra, dec, fovDeg) { sky?.goTo(ra, dec, fovDeg); }

/** T55 "Go": put sky point (ra, dec) under screen point (x, y) of the map (px from its top left). */
export function placeAt(ra, dec, x, y, fovDeg) { sky?.placeAt(ra, dec, x, y, fovDeg); }

/** Field of view (deg) that shows HiPS order k sharp (one texel per screen pixel), or null before the map. */
export function fovForOrder(k) { return sky ? sky.fovForOrder(k) : null; }

/** [ra, dec] in degrees under screen point (x, y) of the map, or null (off the sky / no map yet). */
export function skyAt(x, y) { return sky?.proj.fromScreen(x, y) ?? null; }

/** Screen point [x, y] of the map (px from its top left) where (ra, dec) is drawn, or null (behind / no map). */
export function screenAt(ra, dec) {
  const s = sky?.proj.toScreen(ra, dec);
  return s && s.front ? [s.x, s.y] : null;
}

/** Current view centre (deg) and field of view (arcmin: fovArcmin horizontal, heightArcmin vertical). */
export function view() {
  if (!sky) return null;
  const v = sky.view();
  return { ra: v.ra, dec: v.dec, fovArcmin: v.fov * 60, heightArcmin: (v.fov * 60 * v.height) / v.width };
}

export function on(ev, fn) { sky?.on(ev, fn); }
export function setDebug(on) { sky?.setDebug(on); }
export function addDrawHook(fn) { sky?.addDrawHook(fn); }
export function redraw() { sky?.redraw(); }

/**
 * T55: red outlines of the blinked field cells, [{ra, dec, size (arcmin), state}]: dashed while a cell
 * builds, solid once it is ready, grey where SPHEREx has no data. Squares on the sky, like the fields.
 */
export function setOutlines(cells) {
  outlines = (cells ?? []).map((c) => ({ state: c.state, pts: squarePoints(c.ra, c.dec, c.size) }));
  sky?.redraw();
}

/** Points along the edge of a square field of sizeArcmin around (ra, dec) (densified: follows the projection). */
function squarePoints(ra, dec, sizeArcmin) {
  const h = sizeArcmin / 120, c = Math.cos((dec * Math.PI) / 180) || 1e-6;
  const corners = [[-h, -h], [h, -h], [h, h], [-h, h], [-h, -h]];
  const pts = [];
  for (let i = 0; i < 4; i++) {
    const [ax, ay] = corners[i], [bx, by] = corners[i + 1];
    for (let t = 0; t < 8; t++) pts.push([ra + (ax + ((bx - ax) * t) / 8) / c, dec + ay + ((by - ay) * t) / 8]);
  }
  return pts;
}

/** [ra, dec] points over the whole view (a grid of samples at most ~step px apart), to find the cells it touches. */
export function viewSamples(maxStepArcmin = 10) {
  if (!sky) return [];
  const v = sky.view();
  const pxPerArcmin = v.width / (v.fov * 60);
  const nx = Math.max(4, Math.ceil(v.width / (maxStepArcmin * pxPerArcmin))), ny = Math.max(4, Math.ceil(v.height / (maxStepArcmin * pxPerArcmin)));
  const out = [];
  for (let j = 0; j <= ny; j++) for (let i = 0; i <= nx; i++) {
    const p = sky.proj.fromScreen((v.width * i) / nx, (v.height * j) / ny);
    if (p) out.push(p);
  }
  return out;
}

const OUTLINE_STYLE = {
  building: { color: "#ff5252", dash: [6, 5] },
  ready: { color: "#ff5252", dash: [] },
  empty: { color: "rgb(160 170 190 / 0.6)", dash: [3, 5] },
};

function drawField(ctx, proj) {
  for (const o of outlines) {
    const style = OUTLINE_STYLE[o.state] ?? OUTLINE_STYLE.building;
    ctx.save();
    ctx.strokeStyle = style.color;
    ctx.setLineDash(style.dash);
    ctx.lineWidth = 2;
    ctx.beginPath();
    let started = false;
    for (const [ra, dec] of [...o.pts, o.pts[0]]) {
      const s = proj.toScreen(ra, dec);
      if (!s.front) { started = false; continue; }
      if (!started) { ctx.moveTo(s.x, s.y); started = true; } else ctx.lineTo(s.x, s.y);
    }
    ctx.stroke();
    ctx.restore();
  }
}

/** T32/T55: per-epoch HiPS of the blinked fields (Live API), [{epoch, label, url (absolute)}] per
 * field; added as they arrive. All are prefetched, one epoch (all fields) is drawn at a time. */
export async function addEpochLayers(layers) {
  if (!sky) return [];
  const added = await sky.addOverlays(layers);
  epochLayers.push(...added);
  return added;
}

/** Show epoch number `epoch` in every field at once (null: none). */
export function showEpoch(epoch) {
  sky?.showEpochGroup(epoch);
  // T35: traces.js highlights each object's position in the shown epoch
  document.dispatchEvent(new CustomEvent("explore:epoch", { detail: { epoch } }));
}

export function clearEpochs() {
  epochLayers = [];
  sky?.setOverlays([]);
}

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
let field = null;          // {ra, dec, size} of the blink field, drawn as an outline
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

/** Red outline = a square field of sizeArcmin around (ra, dec) (a link to a built field). */
export function markField(ra, dec, sizeArcmin) {
  const h = sizeArcmin / 120, c = Math.cos((dec * Math.PI) / 180) || 1e-6;
  const corners = [[-h, -h], [h, -h], [h, h], [-h, h], [-h, -h]];
  const pts = [];
  for (let i = 0; i < 4; i++) {
    const [ax, ay] = corners[i], [bx, by] = corners[i + 1];
    for (let t = 0; t < 8; t++) {            // densified, so the outline follows the projection
      pts.push([ra + (ax + ((bx - ax) * t) / 8) / c, dec + ay + ((by - ay) * t) / 8]);
    }
  }
  markRegion(pts);
}

/** Red outline = this closed polygon of [ra, dec] points (deg). */
export function markRegion(points) {
  field = points?.length > 2 ? points : null;
  sky?.redraw();
}

/**
 * T55 Blink: the part of the current view a centred square field of sizeArcmin covers (the whole
 * view when it fits), as [ra, dec] points along its edges, so the red outline shows what is built.
 */
export function viewRegion(sizeArcmin) {
  if (!sky) return null;
  const v = sky.view();
  const pxPerArcmin = v.width / (v.fov * 60), half = (sizeArcmin / 2) * pxPerArcmin;
  const x0 = Math.max(0, v.width / 2 - half), x1 = Math.min(v.width, v.width / 2 + half);
  const y0 = Math.max(0, v.height / 2 - half), y1 = Math.min(v.height, v.height / 2 + half);
  const corners = [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]];
  const pts = [];
  for (let i = 0; i < 4; i++) {
    const [ax, ay] = corners[i], [bx, by] = corners[i + 1];
    for (let t = 0; t < 16; t++) {
      const p = sky.proj.fromScreen(ax + ((bx - ax) * t) / 16, ay + ((by - ay) * t) / 16);
      if (p) pts.push(p);
    }
  }
  return pts;
}

function drawField(ctx, proj) {
  if (!field) return;
  ctx.save();
  ctx.strokeStyle = "#ff5252";
  ctx.lineWidth = 2;
  ctx.beginPath();
  let started = false;
  for (const [ra, dec] of [...field, field[0]]) {
    const s = proj.toScreen(ra, dec);
    if (!s.front) { started = false; continue; }
    if (!started) { ctx.moveTo(s.x, s.y); started = true; } else ctx.lineTo(s.x, s.y);
  }
  ctx.stroke();
  ctx.restore();
}

/** T32: per-epoch HiPS from our Live API. layers: [{epoch, label, url (absolute)}]. All are
 * prefetched; one is drawn at a time, so blinking is instant once loaded (requirement R2). */
export async function setEpochLayers(layers) {
  if (!sky) return [];
  epochLayers = await sky.setOverlays(layers);
  return epochLayers;
}

export function showEpoch(i) {
  sky?.showOverlay(i);
  // T35: traces.js highlights each object's position in the shown epoch
  document.dispatchEvent(new CustomEvent("explore:epoch", { detail: { epoch: epochLayers[i]?.epoch ?? null } }));
}

export function hideEpochs() {
  epochLayers = [];
  sky?.setOverlays([]);
}

// ---------- T55: survey passes as map layers (T82 spherex-live-p<n>), blinked at the sharp order ----------

/** Survey passes the map's live layer has images from (its x_survey_passes), e.g. [1, 2, 3]. */
export function surveyPasses() {
  return (sky?.base?.props.x_survey_passes ?? "").split(/\s+/).filter(Boolean).map(Number);
}

/** Put one overlay per pass on the map (replaces the field's epochs). Returns the layers made. */
export async function setPassLayers(passes, order) {
  if (!sky || !apiBase) return [];
  const base = apiBase.replace(/\/$/, "");
  epochLayers = await sky.setOverlays(passes.map((n) => ({
    url: `${base}/api/sky/spherex-live-p${n}`, label: `Survey pass ${n}`, epoch: null, pass: n, sharpOrder: order })));
  return epochLayers;
}

/** {total, done, ok} tiles of overlay i for this view, or null. */
export function overlayProgress(i) { return sky?.overlayProgress(i) ?? null; }

/** Draw overlay i, or none (-1), without the epoch event (passes are not field epochs). */
export function showOverlay(i) { sky?.showOverlay(i); }

/** Order the screen needs for one texel per pixel (may exceed what the map has), or null. */
export function wantedOrder() { return sky?.stats()?.wanted ?? null; }
/** Highest order the base map draws (null = its own maximum, 7). */
export function setBaseCap(k) { sky?.setBaseCap(k); }
export function onTiles(fn) { sky?.on("tiles", fn); }

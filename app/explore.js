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
let pin = null;            // T55 "Go": {ra, dec} marked with a pin
let epochLayers = [];

export const getSky = () => sky;
export const getApiBase = () => apiBase;   // T72: skylabels.js asks the Live API too

/** Create the map. opts: {ra, dec, fovDeg} */
export async function initExplore(container, opts = {}) {
  apiBase = opts.api ?? null;
  sky = createSky(container, { ra: opts.ra ?? 269.4463, dec: opts.dec ?? 4.7682, fov: opts.fovDeg ?? 2 });
  sky.addDrawHook(drawField);
  sky.addDrawHook(drawPin);
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

/** Current view centre (deg) and field of view (arcmin, horizontal). */
export function view() {
  if (!sky) return null;
  const v = sky.view();
  return { ra: v.ra, dec: v.dec, fovArcmin: v.fov * 60 };
}

export function on(ev, fn) { sky?.on(ev, fn); }
export function setDebug(on) { sky?.setDebug(on); }
export function addDrawHook(fn) { sky?.addDrawHook(fn); }
export function redraw() { sky?.redraw(); }

export function markField(ra, dec, sizeArcmin) {
  field = { ra, dec, size: sizeArcmin };
  sky?.redraw();
}

/** T55: mark a position with a pin (the "Go" target); null removes it. */
export function setPin(ra, dec) {
  pin = Number.isFinite(ra) && Number.isFinite(dec) ? { ra, dec } : null;
  sky?.redraw();
}

/** A map pin whose tip sits on the position: round head, pointed foot, white rim, shadow. */
function drawPin(ctx, proj) {
  if (!pin) return;
  const s = proj.toScreen(pin.ra, pin.dec);
  if (!s.front) return;
  const r = 9, h = 26;                       // head radius, tip-to-head-centre height (px)
  const cx = s.x, cy = s.y - h;
  ctx.save();
  ctx.shadowColor = "rgb(0 0 0 / 0.6)";
  ctx.shadowBlur = 6;
  ctx.shadowOffsetY = 2;
  ctx.beginPath();
  const a = Math.acos(r / h);                // tangent points of the straight sides on the head
  ctx.moveTo(s.x, s.y);
  ctx.arc(cx, cy, r, Math.PI / 2 + a, Math.PI / 2 - a + 2 * Math.PI, false);
  ctx.closePath();
  ctx.fillStyle = "#ff5252";
  ctx.fill();
  ctx.shadowColor = "transparent";
  ctx.lineWidth = 2;
  ctx.strokeStyle = "#fff";
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(cx, cy, 3.5, 0, 2 * Math.PI);
  ctx.fillStyle = "#fff";
  ctx.fill();
  ctx.restore();
}

function drawField(ctx, proj) {
  if (!field) return;
  const h = field.size / 120, c = Math.cos((field.dec * Math.PI) / 180) || 1e-6;
  const corners = [[-h, -h], [h, -h], [h, h], [-h, h], [-h, -h]];
  ctx.save();
  ctx.strokeStyle = "#ff5252";
  ctx.lineWidth = 2;
  ctx.beginPath();
  let started = false;
  for (let i = 0; i < 4; i++) {
    const [ax, ay] = corners[i], [bx, by] = corners[i + 1];
    for (let t = 0; t <= 8; t++) {           // densified, so the outline follows the projection
      const x = ax + ((bx - ax) * t) / 8, y = ay + ((by - ay) * t) / 8;
      const s = proj.toScreen(field.ra + x / c, field.dec + y);
      if (!s.front) { started = false; continue; }
      if (!started) { ctx.moveTo(s.x, s.y); started = true; } else ctx.lineTo(s.x, s.y);
    }
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

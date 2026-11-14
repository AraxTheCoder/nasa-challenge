// T30/T36 Sky map: Google-Earth-style pan/zoom over the whole sky with our own HiPS renderer
// (sky.js, no dependencies). Base maps: SPHEREx all-sky (IRSA DR1 cube, 102 bands; CDS per-detector
// maps) and comparison surveys. Overlays: the shown field's SPHEREx epochs (T32), blinkable.
// Draw hooks let other modules (field outline, traces.js) paint on top.

import { createSky } from "./sky.js";

export const SURVEYS = [
  // T42: IRSA cube up to order 5, deeper zoom = live tiles from the AWS level-2 images (our server)
  { id: "spherex-live", label: "SPHEREx · 102 bands · live deep zoom",
    urls: [], fallback: ["https://irsa.ipac.caltech.edu/data/hips/SPHEREx/spherex_allsky_cube"] },
  { id: "spherex-cube", label: "SPHEREx all-sky · 102 bands (IRSA DR1)",
    urls: ["https://irsa.ipac.caltech.edu/data/hips/SPHEREx/spherex_allsky_cube"] },
  ...[1, 2, 3, 4, 5, 6].map((d) => ({
    id: `spherex-d${d}`,
    label: `SPHEREx D${d} · ${["0.75–1.1", "1.1–1.6", "1.6–2.4", "2.4–3.8", "3.8–4.4", "4.4–5.0"][d - 1]} µm (CDS QR2)`,
    urls: [`https://alasky.cds.unistra.fr/SPHEREx/D${d}`, `https://alaskybis.cds.unistra.fr/SPHEREx/D${d}`],
  })),
  { id: "2mass", label: "Compare: 2MASS colour (IRSA)", urls: ["https://irsa.ipac.caltech.edu/data/hips/CDS/2MASS/Color"] },
  { id: "allwise", label: "Compare: AllWISE colour (IRSA)", urls: ["https://irsa.ipac.caltech.edu/data/hips/CDS/AllWISE/RGB-W4-W2-W1"] },
];
export const DEFAULT_SURVEY = "spherex-live";

let sky = null;
let apiBase = null;        // T41: our server caches + prefetches the map tiles (/api/sky/<id>)
let field = null;          // {ra, dec, size} of the blink field, drawn as an outline
let epochLayers = [];

export const getSky = () => sky;

/** Create the map. opts: {ra, dec, fovDeg} */
export async function initExplore(container, opts = {}) {
  apiBase = opts.api ?? null;
  sky = createSky(container, { ra: opts.ra ?? 269.4463, dec: opts.dec ?? 4.7682, fov: opts.fovDeg ?? 2 });
  sky.addDrawHook(drawField);
  await setSurvey(DEFAULT_SURVEY);
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
export function northUp() { sky?.northUp(); }
export function addDrawHook(fn) { sky?.addDrawHook(fn); }
export function redraw() { sky?.redraw(); }

export function markField(ra, dec, sizeArcmin) {
  field = { ra, dec, size: sizeArcmin };
  sky?.redraw();
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

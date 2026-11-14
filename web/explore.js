// T30 Explore mode: Google-Earth-style pan/zoom over the whole sky with Aladin Lite v3 and the
// SPHEREx HiPS maps that CDS publishes (one per detector, all epochs combined), plus Gaia/WISE/
// SIMBAD for context. "Blink this spot" hands the view centre to the per-epoch blink viewer.
//
// HiPS layers per epoch (T32) are added by addEpochLayers() when the Live API offers them.

// CDS hosts it too, but aladin.cds.unistra.fr answered 404 on 2026-11-14; jsDelivr mirrors npm.
const ALADIN_JS = "https://cdn.jsdelivr.net/npm/aladin-lite@3.8.2/dist/aladin.js";

export const SURVEYS = [
  { id: "CDS/P/SPHEREx/QR2/D1", label: "SPHEREx D1 · 0.75–1.1 µm" },
  { id: "CDS/P/SPHEREx/QR2/D2", label: "SPHEREx D2 · 1.1–1.6 µm" },
  { id: "CDS/P/SPHEREx/QR2/D3", label: "SPHEREx D3 · 1.6–2.4 µm" },
  { id: "CDS/P/SPHEREx/QR2/D4", label: "SPHEREx D4 · 2.4–3.8 µm" },
  { id: "CDS/P/SPHEREx/QR2/D5", label: "SPHEREx D5 · 3.8–4.4 µm" },
  { id: "CDS/P/SPHEREx/QR2/D6", label: "SPHEREx D6 · 4.4–5.0 µm" },
  // IRSA's own SPHEREx DR1 cube (13"/px, one slice per band); hosted at IRSA, so it still works
  // when the CDS tile servers are down.
  { id: "https://irsa.ipac.caltech.edu/data/hips/SPHEREx/spherex_allsky_cube", label: "SPHEREx DR1 cube (IRSA, 13″/px)" },
  { id: "https://irsa.ipac.caltech.edu/data/hips/CDS/AllWISE/RGB-W4-W2-W1", label: "Compare: AllWISE colour (IRSA)" },
  { id: "https://irsa.ipac.caltech.edu/data/hips/CDS/2MASS/Color", label: "Compare: 2MASS colour (IRSA)" },
  { id: "CDS/P/unWISE/color-W2-W1W2-W1", label: "Compare: unWISE (W1+W2)" },
  { id: "CDS/P/DSS2/color", label: "Compare: DSS2 optical" },
];

const CATALOGS = {
  gaia: { url: "https://axel.u-strasbg.fr/HiPSCatService/I/355/gaiadr3", name: "Gaia DR3", color: "#4fc3f7" },
  simbad: { url: "https://axel.u-strasbg.fr/HiPSCatService/Simbad", name: "SIMBAD", color: "#ffb74d" },
};

let A = null;          // Aladin Lite namespace
let aladin = null;     // the instance
const catalogs = {};   // name -> catalog layer
let epochLayers = [];  // T32: [{epoch, layer}]

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = src;
    s.charset = "utf-8";
    s.onload = resolve;
    s.onerror = () => reject(new Error(`could not load ${src}`));
    document.head.append(s);
  });
}

/** Create the sky view. opts: {ra, dec, fovDeg, onBlink(ra, dec, fovArcmin)} */
export async function initExplore(container, opts) {
  await loadScript(ALADIN_JS);
  A = window.A;
  await A.init;
  aladin = A.aladin(container, {
    survey: SURVEYS[0].id,
    target: `${opts.ra ?? 269.4463} ${opts.dec ?? 4.7682}`,
    fov: opts.fovDeg ?? 2,
    cooFrame: "ICRSd",
    showReticle: true,
    showCooGrid: false,
    showLayersControl: false,
    showGotoControl: true,
    showFullscreenControl: true,
    showFrame: true,
  });
  return aladin;
}

export function setSurvey(id) {
  aladin?.setBaseImageLayer(id);
}

export function toggleCatalog(key, on) {
  if (!aladin) return;
  const c = CATALOGS[key];
  if (on && !catalogs[key]) {
    catalogs[key] = A.catalogHiPS(c.url, { name: c.name, color: c.color, sourceSize: 8, onClick: "showPopup" });
    aladin.addCatalog(catalogs[key]);
  } else if (catalogs[key]) {
    on ? catalogs[key].show() : catalogs[key].hide();
  }
}

export function goTo(ra, dec, fovDeg) {
  if (!aladin) return;
  aladin.gotoRaDec(Number(ra), Number(dec));
  if (fovDeg) aladin.setFoV(fovDeg);
}

/** Current view centre (deg) and field of view (arcmin, horizontal). */
export function view() {
  if (!aladin) return null;
  const [ra, dec] = aladin.getRaDec();
  const [fovX] = aladin.getFov();
  return { ra, dec, fovArcmin: fovX * 60 };
}

/** Draw the outline of the field the blink viewer shows. */
let fieldOverlay = null;
export function markField(ra, dec, sizeArcmin) {
  if (!aladin) return;
  if (!fieldOverlay) {
    fieldOverlay = A.graphicOverlay({ color: "#ff5252", lineWidth: 2, name: "Blink field" });
    aladin.addOverlay(fieldOverlay);
  }
  fieldOverlay.removeAll();
  const h = sizeArcmin / 120;               // half side in deg
  const c = Math.cos((dec * Math.PI) / 180) || 1e-6;
  const pts = [[-h, -h], [h, -h], [h, h], [-h, h], [-h, -h]].map(([dx, dy]) => [ra + dx / c, dec + dy]);
  fieldOverlay.add(A.polyline(pts));
}

/** T32: per-epoch HiPS from our Live API. layers: [{epoch, label, url (absolute)}].
 * All epochs are added as overlay layers at once and switched by opacity, so blinking is instant
 * once their tiles are loaded (requirement R2). */
export function setEpochLayers(layers) {
  hideEpochs();
  const make = A.HiPS || A.imageHiPS;
  epochLayers = layers.map((l, i) => {
    const layer = make(l.url, { name: l.label, imgFormat: "png" });
    aladin.setOverlayImageLayer(layer, `epoch${i}`);
    aladin.getOverlayImageLayer(`epoch${i}`)?.setOpacity(i === 0 ? 1 : 0);
    return { ...l, name: `epoch${i}` };
  });
  return epochLayers;
}

export function showEpoch(i) {
  epochLayers.forEach((l, j) => aladin?.getOverlayImageLayer(l.name)?.setOpacity(j === i ? 1 : 0));
}

export function hideEpochs() {
  epochLayers.forEach((l) => aladin?.removeImageLayer?.(l.name));
  epochLayers = [];
}

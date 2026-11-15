// T91: a star's motion measured from SPHEREx alone, shown in the spectrum panel when the point clicked is a
// catalogued star that moves (≥ 0.3″/yr): "SPHEREx: 10.46 ± 0.19″/yr toward north; Gaia 10.39″/yr: agrees".
// Asks GET /api/targets/<id>/motion?name=<label id>&start=0 for a cached result first; a button starts the
// measurement (~15 s, a fit to the star and its reference stars in every exposure) and polls until it's done.

import { el, fmtNum } from "./util.js";
import { analysisNote } from "./analysisnote.js";
import { currentTarget, targetBase } from "./viewer.js";

// The server decides whether the clicked spot is a moving catalogued star (≥ 0.3″/yr, within 8″): the viewer's
// copy of the field doesn't always carry its labels (they come on request). 404 "none" = no box.
const cache = new Map();          // `${target id}|${ra}|${dec}` -> answer
// The next boxes measure right away instead of offering a button (the tour). T118: a deadline, not a one-shot
// flag: the spectrum panel re-renders while its spectrum loads and every render makes a new box; with a one-shot
// flag a later box asked with start=0 before the job existed, showed the button and stopped polling.
let autoUntil = 0;
const AUTO_MS = 60000;

/** The next motion boxes (for a minute, until one sees the job) start measuring by themselves (T92: the tour). */
export function measureNext() { autoUntil = Date.now() + AUTO_MS; }

const COMPASS = ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"];
const dir = (pa) => COMPASS[Math.round(((pa % 360) + 360) % 360 / 45) % 8];

function body(r, label) {
  if (r.status === "ready") {
    const cat = r.catalogue ?? {};
    const plx = r.parallax;
    return [
      el("p", { class: "ph-motion-big" }, `${fmtNum(r.pm_total_arcsec_yr, 2)} ± ${fmtNum(r.pm_total_err, 2)}″ per year, toward the ${dir(r.pa_deg)}`),
      analysisNote("Catalogue comparison", `Catalogue (${cat.source === "simbad" ? "SIMBAD / Gaia" : cat.source ?? "catalogue"}): ${fmtNum(cat.pm_total_arcsec_yr, 2)}″ per year toward ${dir(cat.pa_deg)}. SPHEREx ${r.verdict}. Agreement depends on fit errors and source association.`, "muted small"),
      plx?.reliable ? analysisNote(`${fmtNum(plx.distance_pc, 2)} pc · distance estimate`,
        `Inferred from fitted parallax ${fmtNum(plx.parallax_arcsec, 3)} ± ${fmtNum(plx.parallax_err, 3)}″. This estimate depends on the astrometric model and can have additional systematic uncertainty.`) : null,
      analysisNote(r.n_measured != null && r.n_exposures != null ? `${r.n_measured}/${r.n_exposures} exposures · fitted motion` : "Motion fit details",
        (r.measured_in === "deep stacks" ? "Measured in combined deep images, not individual exposures. " : "Measured against reference stars in individual exposures. ") +
        `${fmtNum(r.span_years, 1)} years, ${r.epochs?.length ?? 0} epochs, ${r.n_references} references. ${plx && !plx.reliable ? `Distance unresolved: ${plx.note}. ` : ""}${r.method ?? ""} Position errors, blends and calibration can affect the fit.`, "muted small"),
    ];
  }
  if (r.status === "building") return [el("p", { class: "small" }, r.total ? `Measuring… ${r.done}/${r.total} exposures` : "Measuring…")];
  return [el("p", { class: "small muted" }, r.message ?? `Can't measure ${label.name}'s motion here.`)];
}

async function fetchMotion(where, start, box, token) {
  const key = `${currentTarget()?.id}|${where.ra.toFixed(5)}|${where.dec.toFixed(5)}`;
  const url = new URL("motion", targetBase());
  url.searchParams.set("ra", where.ra.toFixed(6));
  url.searchParams.set("dec", where.dec.toFixed(6));
  url.searchParams.set("start", start ? "1" : "0");
  for (let i = 0; i < 300; i++) {
    let r = null, http = 0;
    try { const res = await fetch(url, { cache: "no-cache" }); http = res.status; r = await res.json(); } catch { r = null; }
    if (!box.isConnected || box.dataset.token !== token) return;
    if (http === 404 || r?.status === "none" || r?.status === "no_data") { box.remove(); cache.set(key, null); return; }
    if (!r) { box.remove(); return; }
    const label = { name: (r.name ?? "this star").replace(/^\* /, ""), pm_mas_yr: r.catalogue_pm_mas_yr };
    if (r.status !== "building" && r.status !== "not_started") cache.set(key, r);
    if (start && (r.status === "building" || r.status === "ready")) autoUntil = 0;   // T118: the job is on its way
    box.hidden = false;
    fill(box, label, r, where);
    if (r.status !== "building") return;
    url.searchParams.set("start", "0");
    await new Promise((res) => setTimeout(res, 1000));
  }
}

function fill(box, label, r, where) {
  const parts = [el("h4", {}, `Motion estimate · ${label.name}`)];
  if (r.status === "not_started") {
    const go = el("button", { type: "button" }, "Measure it from SPHEREx (~15 s)");
    go.addEventListener("click", () => fetchMotion(where, true, box, box.dataset.token));
    parts.push(analysisNote("Catalogue suggests motion", "This position matches a catalogue source with proper motion. A fit to SPHEREx positions against reference stars can provide an independent comparison; blending and astrometric calibration affect its uncertainty."), go);
  } else {
    parts.push(...body(r, label));
  }
  box.replaceChildren(...parts.filter(Boolean));
}

/** The box for the spectrum panel (filled, or removed again, by the server's answer for this spot). */
export function motionBox(ra, dec) {
  const t = currentTarget();
  if (!t || t.synthetic !== false || !targetBase()) return null;
  const where = { ra, dec };
  const key = `${t.id}|${ra.toFixed(5)}|${dec.toFixed(5)}`;
  if (cache.has(key) && cache.get(key) === null) return null;
  const box = el("div", { class: "ph-context ph-motion" });
  box.dataset.token = String(Math.random());
  const hit = cache.get(key);
  if (hit) fill(box, { name: (hit.name ?? "this star").replace(/^\* /, "") }, hit, where);
  else {
    box.hidden = true;                                   // shown once the server says it's a moving star
    fetchMotion(where, Date.now() < autoUntil, box, box.dataset.token);
  }
  return box;
}

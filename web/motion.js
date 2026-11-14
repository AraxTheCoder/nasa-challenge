// T91: a star's motion measured from SPHEREx alone, shown in the spectrum panel when the point clicked is a
// catalogued star that moves (≥ 0.3″/yr): "SPHEREx: 10.46 ± 0.19″/yr toward north; Gaia 10.39″/yr: agrees".
// Asks GET /api/targets/<id>/motion?name=<label id>&start=0 for a cached result first; a button starts the
// measurement (~15 s, a fit to the star and its reference stars in every exposure) and polls until it's done.

import { el, fmtNum } from "./util.js";
import { currentTarget, targetBase } from "./viewer.js";

// The server decides whether the clicked spot is a moving catalogued star (≥ 0.3″/yr, within 8″): the viewer's
// copy of the field doesn't always carry its labels (they come on request). 404 "none" = no box.
const cache = new Map();          // `${target id}|${ra}|${dec}` -> answer
let autoStart = false;            // the next box measures right away instead of offering a button (the tour)

/** The next motion box starts measuring by itself (T92: the tour's "Measure its speed"). */
export function measureNext() { autoStart = true; }

const COMPASS = ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"];
const dir = (pa) => COMPASS[Math.round(((pa % 360) + 360) % 360 / 45) % 8];

function body(r, label) {
  if (r.status === "ready") {
    const cat = r.catalogue ?? {};
    const plx = r.parallax;
    return [
      el("p", { class: "ph-motion-big" }, `${fmtNum(r.pm_total_arcsec_yr, 2)} ± ${fmtNum(r.pm_total_err, 2)}″ per year, toward the ${dir(r.pa_deg)}`),
      el("p", {}, `Catalogue (${cat.source === "simbad" ? "SIMBAD / Gaia" : cat.source ?? "catalogue"}): ${fmtNum(cat.pm_total_arcsec_yr, 2)}″ per year toward the ${dir(cat.pa_deg)}. SPHEREx ${r.verdict}.`),
      plx?.reliable ? el("p", {}, `Its yearly wobble from Earth's orbit (parallax ${fmtNum(plx.parallax_arcsec, 3)} ± ${fmtNum(plx.parallax_err, 3)}″) puts it at `,
        el("strong", {}, `${fmtNum(plx.distance_pc, 2)} parsec`), ` (${fmtNum(plx.distance_pc * 3.2616, 1)} light years).`) : null,
      el("p", { class: "muted small" }, `Measured in ${r.n_measured} of ${r.n_exposures} exposures over ${fmtNum(r.span_years, 1)} years, ` +
        `${r.epochs?.length ?? 0} epochs, ${r.n_references} reference stars. ${plx && !plx.reliable ? `Distance: ${plx.note}. ` : ""}${r.method ?? ""}`),
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
    box.hidden = false;
    fill(box, label, r, where);
    if (r.status !== "building") return;
    url.searchParams.set("start", "0");
    await new Promise((res) => setTimeout(res, 1000));
  }
}

function fill(box, label, r, where) {
  const parts = [el("h4", {}, `How fast ${label.name} moves, measured by SPHEREx`)];
  if (r.status === "not_started") {
    const go = el("button", { type: "button" }, "Measure it from SPHEREx (~15 s)");
    go.addEventListener("click", () => fetchMotion(where, true, box, box.dataset.token));
    parts.push(el("p", { class: "small" }, "It is a catalogued star that moves. SPHEREx can measure how fast on its own: " +
      "the star's position in every exposure, against fixed background stars."), go);
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
    fetchMotion(where, autoStart, box, box.dataset.token);
    autoStart = false;
  }
  return box;
}

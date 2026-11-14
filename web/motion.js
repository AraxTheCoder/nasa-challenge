// T91: a star's motion measured from SPHEREx alone, shown in the spectrum panel when the point clicked is a
// catalogued star that moves (≥ 0.3″/yr): "SPHEREx: 10.46 ± 0.19″/yr toward north; Gaia 10.39″/yr: agrees".
// Asks GET /api/targets/<id>/motion?name=<label id>&start=0 for a cached result first; a button starts the
// measurement (~15 s, a fit to the star and its reference stars in every exposure) and polls until it's done.

import { el, fmtNum } from "./util.js";
import { currentTarget, targetBase } from "./viewer.js";

const MIN_PM_MAS_YR = 300;
const NEAR_ARCSEC = 8;
const cache = new Map();          // `${target id}|${label id}` -> answer

const COMPASS = ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"];
const dir = (pa) => COMPASS[Math.round(((pa % 360) + 360) % 360 / 45) % 8];

/** The moving catalogued star at (ra, dec) in the open field, if any. */
function movingLabelAt(ra, dec) {
  const t = currentTarget();
  if (!t || t.synthetic !== false) return null;
  let best = null, bd = NEAR_ARCSEC;
  for (const l of t.labels ?? []) {
    if (!(l.pm_mas_yr >= MIN_PM_MAS_YR) || ["asteroid", "comet", "planet", "moon"].includes((l.kind ?? "").toLowerCase())) continue;
    for (const p of l.positions ?? []) {
      const d = Math.hypot((p.ra_deg - ra) * Math.cos(dec * Math.PI / 180), p.dec_deg - dec) * 3600;
      if (d < bd) { bd = d; best = l; }
    }
  }
  return best;
}

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

async function fetchMotion(label, start, box, token) {
  const key = `${currentTarget()?.id}|${label.id}`;
  const url = new URL("motion", targetBase());
  url.searchParams.set("name", label.id);
  url.searchParams.set("start", start ? "1" : "0");
  for (let i = 0; i < 300; i++) {
    let r;
    try { r = await (await fetch(url, { cache: "no-cache" })).json(); } catch { r = null; }
    if (!box.isConnected || box.dataset.token !== token) return;
    if (!r) { fill(box, label, { status: "error", message: "the Live API didn't answer" }); return; }
    if (r.status !== "building" && r.status !== "not_started") cache.set(key, r);
    fill(box, label, r);
    if (r.status !== "building") return;
    url.searchParams.set("start", "0");
    await new Promise((res) => setTimeout(res, 1000));
  }
}

function fill(box, label, r) {
  const parts = [el("h4", {}, `How fast ${label.name} moves, measured by SPHEREx`)];
  if (r.status === "not_started") {
    const go = el("button", { type: "button" }, "Measure it from SPHEREx (~15 s)");
    go.addEventListener("click", () => fetchMotion(label, true, box, box.dataset.token));
    parts.push(el("p", { class: "small" }, `The catalogue says ${fmtNum(label.pm_mas_yr / 1000, 2)}″ per year. ` +
      "SPHEREx can measure it on its own: the star's position in every exposure, against fixed background stars."), go);
  } else {
    parts.push(...body(r, label));
  }
  box.replaceChildren(...parts.filter(Boolean));
}

/** The box for the spectrum panel, or null if (ra, dec) is not a moving catalogued star of the open field. */
export function motionBox(ra, dec) {
  const label = movingLabelAt(ra, dec);
  if (!label || !targetBase()) return null;
  const box = el("div", { class: "ph-context ph-motion" });
  box.dataset.token = String(Math.random());
  const hit = cache.get(`${currentTarget()?.id}|${label.id}`);
  if (hit) fill(box, label, hit);
  else { fill(box, label, { status: "building" }); fetchMotion(label, false, box, box.dataset.token); }
  return box;
}

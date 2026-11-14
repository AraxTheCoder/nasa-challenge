// Spectrum context (T63): what a normal source would look like, and why a deviation is interesting.
// Pure functions, no DOM (checked by web/tests/spectrum_check.mjs); photometry.js draws the result.
//
// 1. Baseline: a blackbody fitted to the short-wavelength points (<= FIT_MAX_UM) of one epoch, i.e.
//    "what a plain star of this colour would give", extrapolated to 5 µm.
// 2. Deviations: points that leave the baseline by more than Z_MIN sigma AND by a clear factor, where
//    sigma includes a calibration floor (bright stars have 0.3 % statistical errors, but SPHEREx channels
//    agree only to ~10 %). Two or more neighbouring points of the same sign make a "region"; single
//    points are ignored.
// 3. Hints: plain words for each region, from what is known to sit at that wavelength (ices, PAH,
//    hydrogen lines, warm dust, cool atmospheres). Always a hint, never a result.

export const FIT_MAX_UM = 2.5;     // K band: up to here a star is close to a blackbody
export const FLOOR = 0.1;          // calibration floor, fraction of the flux
export const Z_MIN = 3;
export const RATIO_UP = 1.3, RATIO_DOWN = 0.75;
export const POOR_FIT = 5;      // reduced chi² above this: the short points don't follow one star shape
const HC_K_UM = 14387.77;          // h c / k in µm·K
const T_GRID = Array.from({ length: 161 }, (_, i) => 1000 * 40 ** (i / 160)); // 1,000-40,000 K, log steps

// Wavelengths that mean something in SPHEREx's 0.75-5 µm range (standard values, checked 2026-11-14).
export const FEATURES = [
  { um: 1.282, name: "Pa-β", kind: "line", what: "hydrogen emission: hot gas, e.g. a young star still pulling in material" },
  { um: 2.166, name: "Br-γ", kind: "line", what: "hydrogen emission: hot gas, e.g. a young star still pulling in material" },
  { um: 3.05, name: "H₂O ice", kind: "ice", what: "water ice on cold dust grains, in a cloud in front of the source or around it" },
  { um: 3.3, name: "PAH", kind: "band", what: "carbon-rich molecules (PAHs) glowing in UV light; in cool brown dwarfs, methane absorbs here instead" },
  { um: 3.53, name: "CH₃OH ice", kind: "ice", what: "methanol ice on cold dust grains" },
  { um: 4.052, name: "Br-α", kind: "line", what: "hydrogen emission: hot gas, e.g. a young star still pulling in material" },
  { um: 4.27, name: "CO₂ ice", kind: "ice", what: "carbon-dioxide ice on cold dust grains (one of SPHEREx's main science goals)" },
  { um: 4.67, name: "CO ice", kind: "ice", what: "carbon-monoxide ice on very cold dust grains; in cool atmospheres, CO gas absorbs here too" },
];

/** Blackbody shape in F_nu (arbitrary scale) at wavelength um for temperature t. */
export function planckNu(um, t) {
  const x = HC_K_UM / (um * t);
  return x > 700 ? 0 : 1 / (um ** 3 * Math.expm1(x));
}

const sigma = (p, model) => Math.hypot(p.err ?? 0, FLOOR * Math.max(model, p.flux));

/**
 * Fit a blackbody to the points with um <= FIT_MAX_UM. points: [{um, flux, err}] (good points only).
 * Returns null if there are too few (< 3) or they span < 0.3 µm, else
 * {t, scale, n, umMin, umMax, redChi2, edge: "hot"|"cool"|null, model(um)}.
 */
export function fitBaseline(points) {
  const pts = points.filter((p) => p.um <= FIT_MAX_UM && p.flux > 0);
  if (pts.length < 3) return null;
  const umMin = Math.min(...pts.map((p) => p.um)), umMax = Math.max(...pts.map((p) => p.um));
  if (umMax - umMin < 0.3) return null;
  let best = null;
  for (const t of T_GRID) {
    const m = pts.map((p) => planckNu(p.um, t));
    if (m.every((v) => v === 0)) continue;
    // weights with the floor taken on the data (the model scale isn't known yet)
    const w = pts.map((p) => 1 / Math.hypot(p.err ?? 0, FLOOR * p.flux) ** 2);
    let num = 0, den = 0;
    pts.forEach((p, i) => { num += w[i] * p.flux * m[i]; den += w[i] * m[i] * m[i]; });
    if (!(den > 0)) continue;
    const scale = num / den;
    let chi2 = 0;
    pts.forEach((p, i) => { chi2 += ((p.flux - scale * m[i]) / sigma(p, scale * m[i])) ** 2; });
    if (!best || chi2 < best.chi2) best = { t, scale, chi2 };
  }
  if (!best) return null;
  const { t, scale } = best;
  return {
    t, scale, n: pts.length, umMin, umMax,
    redChi2: best.chi2 / Math.max(1, pts.length - 2),
    edge: t >= T_GRID[T_GRID.length - 3] ? "hot" : t <= T_GRID[2] ? "cool" : null,
    poor: best.chi2 / Math.max(1, pts.length - 2) > POOR_FIT,
    model: (um) => scale * planckNu(um, t),
  };
}

/** Each point with its baseline value, z and ratio; flag = +1 above, -1 below, 0 normal. */
export function compare(points, fit) {
  return points.filter((p) => p.flux != null && Number.isFinite(p.flux)).map((p) => {
    const model = fit.model(p.um);
    const z = (p.flux - model) / sigma(p, model);
    const ratio = model > 0 ? p.flux / model : Infinity;
    const flag = z > Z_MIN && ratio > RATIO_UP ? 1 : z < -Z_MIN && ratio < RATIO_DOWN ? -1 : 0;
    return { ...p, model, z, ratio, flag };
  }).sort((a, b) => a.um - b.um);
}

/** Runs of >= 2 neighbouring flagged points of the same sign: [{sign, umMin, umMax, n, ratio, points}]. */
export function regions(compared) {
  const out = [];
  let cur = null;
  for (const p of compared) {
    if (p.flag && cur && cur.sign === p.flag) { cur.points.push(p); continue; }
    if (cur && cur.points.length >= 2) out.push(cur);
    cur = p.flag ? { sign: p.flag, points: [p] } : null;
  }
  if (cur && cur.points.length >= 2) out.push(cur);
  return out.map((r) => {
    const rs = r.points.map((p) => p.ratio).sort((a, b) => a - b);
    const m = rs.length >> 1;
    return { sign: r.sign, points: r.points, n: r.points.length, umMin: r.points[0].um, umMax: r.points[r.points.length - 1].um,
      ratio: rs.length % 2 ? rs[m] : (rs[m - 1] + rs[m]) / 2 };
  });
}

const fmtUm = (v) => v.toFixed(2);
const range = (r) => (r.umMax - r.umMin < 0.05 ? `${fmtUm(r.umMin)} µm` : `${fmtUm(r.umMin)}–${fmtUm(r.umMax)} µm`);
export const fmtT = (fit) => !fit || fit.poor ? "a star-like" : fit.edge === "hot" ? "a hot (> 30,000 K)" : fit.edge === "cool" ? "a very cool (< 1,100 K)"
  : `a ~${(Math.round(fit.t / 100) * 100).toLocaleString("en-US")} K`;
const amount = (r) => (r.sign > 0 ? (r.ratio >= 1.95 ? `about ${r.ratio.toFixed(r.ratio >= 10 ? 0 : 1)}× the baseline` : `about ${Math.round((r.ratio - 1) * 100)}% above the baseline`)
  : `about ${Math.round((1 - r.ratio) * 100)}% below the baseline`);

/** Plain-words hint for a region: {title, text}. */
export function hint(r, fit) {
  const near = (kinds, pad) => FEATURES.filter((f) => kinds.includes(f.kind) && f.um >= r.umMin - pad && f.um <= r.umMax + pad);
  const star = fit && !fit.poor ? `${fmtT(fit)} star` : "a plain star";
  if (r.sign > 0) {
    const narrow = r.umMax - r.umMin <= 0.12;
    const lines = narrow ? near(["line", "band"], 0.06) : [];
    if (lines.length) {
      const f = lines[0];
      return { title: `Bright at ${range(r)} (${amount(r)})`, text: `${f.name} sits here: ${f.what}?` };
    }
    const beyond = r.points ? r.points.filter((p) => p.um > FIT_MAX_UM).length : r.nBeyond;
    if (r.umMax >= 3 && beyond * 2 >= r.n) {
      return { title: `More light at ${range(r)} than ${star} gives (${amount(r)})`,
        text: "Warm dust around it (a disk or shell, as around young stars)? Or the source is cooler than it looks: " +
          "brown dwarfs and giant planets are much brighter at 3–5 µm than a star-like baseline." };
    }
    return { title: `Redder than ${star} at ${range(r)} (${amount(r)})`,
      text: "A cool companion, hot dust close to the star, or dust in front of it that dims the blue end?" };
  }
  const ices = near(["ice", "band"], 0.1);
  if (ices.length) {
    const f = ices[0];
    return { title: `Less light at ${range(r)} (${amount(r)})`, text: `${f.name} absorbs here: ${f.what}?` };
  }
  return { title: `Less light at ${range(r)} than ${star} gives (${amount(r)})`,
    text: "Absorption by molecules (water, methane, CO) in a cool star's or brown dwarf's atmosphere, " +
      "or by ice and dust in a cold cloud in front of it?" };
}

/**
 * Whole analysis for one photometry answer: per epoch a fit + compared points, and the regions merged
 * across epochs (same sign, overlapping wavelengths) with the epochs they appear in.
 * frames: the API's photometry frames ({epoch, wavelength_um, flux_ujy, err_ujy, masked, bandwidth_um}).
 */
export function analyse(frames) {
  const epochs = [...new Set(frames.map((f) => f.epoch))].sort((a, b) => a - b);
  const perEpoch = new Map();
  for (const ep of epochs) {
    const pts = frames.filter((f) => f.epoch === ep && !f.masked && Number.isFinite(f.flux_ujy))
      .map((f) => ({ um: f.wavelength_um, flux: f.flux_ujy, err: f.err_ujy, frame_id: f.frame_id }));
    const fit = fitBaseline(pts);
    const shortFlagged = frames.some((f) => f.epoch === ep && f.masked && f.wavelength_um <= FIT_MAX_UM);
    perEpoch.set(ep, { fit, points: fit ? compare(pts, fit) : [], regions: [], shortFlagged });
    // A poor fit says nothing reliable inside its own range: keep only what lies beyond it.
    if (fit) perEpoch.get(ep).regions = regions(perEpoch.get(ep).points).filter((r) => !fit.poor || r.umMin > FIT_MAX_UM);
  }
  const merged = [];
  for (const [ep, e] of perEpoch) {
    for (const r of e.regions) {
      const m = merged.find((x) => x.sign === r.sign && r.umMin <= x.umMax + 0.1 && r.umMax >= x.umMin - 0.1);
      if (m) {
        m.epochs.push(ep);
        m.umMin = Math.min(m.umMin, r.umMin); m.umMax = Math.max(m.umMax, r.umMax);
        m.n += r.n; m.nBeyond += r.points.filter((p) => p.um > FIT_MAX_UM).length; m.ratios.push(r.ratio); m.fits.push(e.fit);
      } else {
        merged.push({ sign: r.sign, umMin: r.umMin, umMax: r.umMax, n: r.n, nBeyond: r.points.filter((p) => p.um > FIT_MAX_UM).length,
          epochs: [ep], ratios: [r.ratio], fits: [e.fit] });
      }
    }
  }
  for (const m of merged) {
    const rs = [...m.ratios].sort((a, b) => a - b);
    m.ratio = rs[rs.length >> 1];
    // name a temperature only if the epochs agree (variables give different fits per epoch)
    const good = m.fits.filter((f) => !f.poor).map((f) => f.t);
    const agree = good.length === m.fits.length && Math.max(...good) <= 1.3 * Math.min(...good);
    m.fit = agree ? m.fits.reduce((a, b) => (a.redChi2 <= b.redChi2 ? a : b)) : null;
    m.hint = hint(m, m.fit);
  }
  const fits = [...perEpoch.values()].map((e) => e.fit).filter(Boolean);
  const poorEpochs = [...perEpoch.entries()].filter(([, e]) => e.fit?.poor).map(([ep]) => ep);
  return { epochs, perEpoch, regions: merged.sort((a, b) => a.umMin - b.umMin), poorEpochs,
    noFit: fits.length === 0, saturated: fits.length === 0 && [...perEpoch.values()].some((e) => e.shortFlagged) };
}

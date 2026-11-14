// Type an exact wavelength (T78). Pure functions, no DOM (checked by web/tests/lambda_check.mjs);
// lampick.js wires them to the blink viewer, app.js to the sky map's band slider.

export const LAM_MIN = 0.7, LAM_MAX = 5.1;          // SPHEREx: 0.75-5.0 µm
const NEAR_UM = 0.25;                               // epochs whose closest frame is farther off are skipped

/** Parse "2.17", "2,17", "2.17 µm", "2170 nm" into µm; null if not a number in SPHEREx's range. */
export function parseLam(text) {
  const m = String(text ?? "").trim().replace(",", ".").match(/^([0-9]*\.?[0-9]+)\s*(µm|um|nm)?$/i);
  if (!m) return null;
  const v = Number(m[1]) / (m[2] && m[2].toLowerCase() === "nm" ? 1000 : 1);
  return v >= LAM_MIN && v <= LAM_MAX ? v : null;
}

/** Index of the band (cube slice) whose centre is closest to lam, or -1. */
export function nearestBand(waves, lam) {
  let best = -1;
  waves.forEach((w, i) => { if (Number.isFinite(w) && (best < 0 || Math.abs(w - lam) < Math.abs(waves[best] - lam))) best = i; });
  return best;
}

/**
 * A and B for "frames at lam": in each epoch the frame closest to lam (preferring the detector of the
 * overall closest frame, so A and B come from the same spectral band), then the earliest and the latest
 * of those epochs. Epochs whose closest frame is more than NEAR_UM off are skipped unless none is closer.
 * Returns null without frames, else {a, b (null if only one epoch), offA, offB, matched}.
 */
export function framesAt(frames, lam) {
  const ok = frames.filter((f) => Number.isFinite(f.wavelength_um));
  if (!ok.length) return null;
  const off = (f) => Math.abs(f.wavelength_um - lam);
  const det = ok.reduce((a, b) => (off(b) < off(a) ? b : a)).detector;
  const byEpoch = new Map();
  for (const f of ok) {
    const cur = byEpoch.get(f.epoch);
    const better = !cur || (f.detector === det) > (cur.detector === det) ||
      ((f.detector === det) === (cur.detector === det) && off(f) < off(cur));
    if (better) byEpoch.set(f.epoch, f);
  }
  let picks = [...byEpoch.values()].filter((f) => off(f) <= NEAR_UM);
  if (!picks.length) picks = [...byEpoch.values()];
  picks.sort((x, y) => x.mjd - y.mjd);
  const a = picks[0], b = picks.length > 1 ? picks[picks.length - 1] : null;
  const half = (f) => 0.5 * (f.bandwidth_um ?? 0.05);
  return {
    a, b, offA: a.wavelength_um - lam, offB: b ? b.wavelength_um - lam : null,
    matched: Boolean(b) && Math.abs(a.wavelength_um - b.wavelength_um) <= Math.min(half(a), half(b)),
  };
}

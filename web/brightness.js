// Display helpers for aperture brightness measurements. Wavelength matching follows T49's half-channel rule.
export const usable = (f) => !f.masked && Number.isFinite(f.flux_ujy) && Number.isFinite(f.wavelength_um);
export const measurementError = (f) => Number.isFinite(f.err_ujy) && f.err_ujy >= 0 ? f.err_ujy : null;
export const periodKey = (f) => f.epoch ?? "unknown";
export const median = (values) => {
  const sorted = [...values].sort((a, b) => a - b), mid = sorted.length >> 1;
  return sorted.length ? sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2 : null;
};
const timeOf = (f) => {
  const iso = Date.parse(f.time_utc);
  return Number.isFinite(iso) ? iso : Number.isFinite(f.mjd) ? (f.mjd - 40587) * 86400000 : null;
};
const date = (t) => new Date(t).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
export function observingPeriods(frames) {
  return [...new Set(frames.map(periodKey))].sort((a, b) => a === "unknown" ? 1 : b === "unknown" ? -1 : a - b).map((id) => {
    const rows = frames.filter((f) => periodKey(f) === id), times = rows.map(timeOf).filter((t) => t != null);
    const lo = times.length ? Math.min(...times) : null, hi = times.length ? Math.max(...times) : null;
    const dates = lo == null ? "Dates unavailable" : date(lo) === date(hi) ? date(lo) : `${date(lo)} – ${date(hi)}`;
    return { id, label: id === "unknown" ? "Undated observations" : `Visit ${id}`, dates,
      usable: rows.filter(usable).length, total: rows.length };
  });
}

/** All eligible visit pairs, with the closest later wavelength for each earlier observation.
 * Missing error estimates remain unknown; they are not displayed as zero uncertainty.
 */
export function matchedChanges(frames) {
  const ok = frames.filter((f) => usable(f) && f.flux_ujy > 0 && f.epoch != null && Number.isFinite(f.epoch));
  const epochs = [...new Set(ok.map((f) => f.epoch))].sort((a, b) => a - b), out = [];
  epochs.forEach((e1, i) => epochs.slice(i + 1).forEach((e2) => {
    const later = ok.filter((f) => f.epoch === e2);
    for (const a of ok.filter((f) => f.epoch === e1)) {
      const b = later.filter((x) => Math.abs(x.wavelength_um - a.wavelength_um) <=
        0.5 * Math.min(a.bandwidth_um ?? .05, x.bandwidth_um ?? .05) + 1e-12)
        .sort((x, y) => Math.abs(x.wavelength_um - a.wavelength_um) - Math.abs(y.wavelength_um - a.wavelength_um))[0];
      if (!b) continue;
      const ratio = b.flux_ujy / a.flux_ujy;
      if (!Number.isFinite(ratio)) continue;
      const knownErrors = measurementError(a) != null && measurementError(b) != null;
      const estimated = knownErrors ? 100 * ratio * Math.hypot(a.err_ujy / a.flux_ujy, b.err_ujy / b.flux_ujy) : null;
      const err = Number.isFinite(estimated) ? estimated : null;
      out.push({ a, b, pct: (ratio - 1) * 100, err, wavelength: (a.wavelength_um + b.wavelength_um) / 2, key: `${e1}→${e2}` });
    }
  }));
  out.omitted = 0;
  return out;
}
export function comparisonGroups(changes) {
  return [...new Set(changes.map((c) => c.key))].map((key) => {
    const rows = changes.filter((c) => c.key === key);
    return { key, changes: rows, earlier: rows[0].a.epoch, later: rows[0].b.epoch, median: median(rows.map((c) => c.pct)) };
  }).sort((a, b) => b.changes.length - a.changes.length || a.earlier - b.earlier || a.later - b.later);
}

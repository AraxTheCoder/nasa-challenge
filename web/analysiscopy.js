// Measurement-led summaries; interpretation remains explicitly tentative.
const um = (v) => Number.isFinite(v) ? Number(v.toFixed(2)).toString() : '?';
const pct = (v) => `${v >= 0 ? '+' : ''}${Math.round(v)}%`;
export const LIMITS = 'A model deviation is not an object or molecule identification. Blending, calibration, position errors and variability can affect the spectrum.';

export function outlierCopy(it) {
  const d = it.deviations?.[0];
  const frame = it.wavelength_frame === 'rest' ? ' (rest frame)' : '';
  return {
    brief: d ? `${pct(d.pct)} vs peers at ${um(d.um_min)}–${um(d.um_max)} µm · tentative` : 'Spectral difference · tentative',
    detail: [d ? `Largest flagged deviation${frame}: ${pct(d.pct)} across ${d.n_bands ?? '?'} bands; ${d.epochs_agree ?? '?'}/${d.epochs_seen ?? '?'} epochs agree. Model significance ${d.z ?? '?'}σ; this is not an identification probability.` : '',
      it.peer_group !== 'galaxies' && d?.meaning ? `Possible wavelength-based interpretation: ${d.meaning}.` : '',
      ...(it.caveats ?? []), LIMITS].filter(Boolean).join(' '),
  };
}

export function anomalyCopy(a) {
  const kinds = { spike: 'Possible spike', dip: 'Possible dip', level: 'Brightness difference', shape: 'Shape difference' };
  const where = Number.isFinite(a.wavelength_um) ? ` at ${um(a.wavelength_um)} µm` : '';
  const amount = Number.isFinite(a.change_pct) ? ` · ${pct(a.change_pct)}` : '';
  const known = a.known?.length ? ` A catalogue object (${a.known[0].name}) was nearby; proximity does not establish the cause.` : '';
  return { brief: `${kinds[a.type] ?? 'Possible change'}${where}${amount}`,
    detail: `Flagged by a numerical comparison${a.epoch != null ? ` in epoch ${a.epoch}` : ''}${a.epochs ? ` between epochs ${a.epochs.join(' and ')}` : ''}; model significance ${a.sigma ?? '?'}σ. ${a.bands != null ? `${a.bands} wavelength bands compared. ` : ''}An apparent change may reflect intrinsic variability, a passing source, blending or an instrumental effect.${known}` };
}

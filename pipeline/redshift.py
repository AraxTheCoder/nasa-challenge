"""Experimental emission-feature redshifts from shared spectra (no image/network I/O).

Weighted continuum + nonnegative Gaussian feature fits, using measured channel widths.
This is a restricted feature-template search, not a calibrated photometric-redshift
pipeline. Search penalties and aliases are reported; uncertainty intervals are local
fit intervals only. Catalogue values take priority over these estimates.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.optimize import nnls

from .chemistry import FEATURES, PRESETS, Z_MAX
from .spectral_outliers import _clean, _sep, peer_group

VERSION = 1
GRID_STEP = .004                 # in log(1+z), finer than the shortest-wavelength channels
MIN_SCORE = 20.0                 # BIC gain after a conservative grid-search penalty
MIN_PEAK_GAP = 10.0
MATCH_ARCSEC = 3.0
TEMPLATES = [p for p in PRESETS if p.get('needs_z')]
METHOD = ('Experimental emission-feature fit, z=0–1; weighted continuum and nonnegative feature amplitudes, '
          'measured channel widths, multiple signed features with epoch agreement, and competing redshift peaks. '
          'No empirical galaxy continuum library; intervals are local fit intervals, not calibrated confidence limits.')


def valid_z(value):
    try:
        z = float(value)
    except (TypeError, ValueError):
        return None
    return z if math.isfinite(z) and 0 <= z <= Z_MAX else None


def catalogue_sources(sources, catalogue):
    """Attach only a unique positional association, never the central object's z to a whole field."""
    galaxies = catalogue.get('galaxies', [])
    out = []
    for source in sources:
        s = dict(source)
        own = valid_z(s.get('redshift', s.get('z')))
        if own is not None:
            s['redshift'] = own
            s.setdefault('redshift_origin', 'label')
        elif peer_group(s) != 'stars':
            hits = [g for g in galaxies if valid_z(g.get('z')) is not None and _sep(s, g) <= MATCH_ARCSEC]
            if len(hits) == 1:
                g = hits[0]
                s.update(redshift=float(g['z']), redshift_origin='SIMBAD', redshift_quality=g.get('quality'),
                         redshift_catalogue_name=g.get('name'), spectral_population='galaxies')
        out.append(s)
    return out


def _prepare(fs, i):
    keep, fl, er, wl = _clean(fs, i)
    keep = [k for k in keep if fl[k] > 0 and math.isfinite(er[k]) and math.isfinite(wl[k]) and wl[k] > 0]
    if len(keep) < 24:
        return None
    w, f, e = (np.array([v[k] for k in keep], float) for v in (wl, fl, er))
    bw = np.array([fs['bandwidth_um'][i][k] or w[j] / 40 for j, k in enumerate(keep)], float)
    good = np.isfinite(bw) & (bw > 0)
    w, f, e, bw = w[good], f[good], e[good], bw[good]
    eps = np.array([fs['exposures'][k]['epoch'] for k, ok in zip(keep, good) if ok])
    if len(w) < 24 or np.ptp(np.log(w)) < .5:
        return None
    y = np.log(f)
    # A separate epoch level absorbs variability without shifting spectral features.
    x = np.log(w / np.median(w))
    C = np.column_stack([*(eps == ep for ep in sorted(set(eps))), x, x*x])
    sw = 1 / np.sqrt((e / f) ** 2 + .03 ** 2)
    Q, _ = np.linalg.qr(C * sw[:, None], mode='reduced')
    yw = y * sw
    residual = yw - Q @ (Q.T @ yw)
    return w, bw, sw, Q, residual


def estimate(fs, i):
    """Return one source's accepted estimate, ambiguous alternatives, or explicit insufficient evidence."""
    source = fs['sources'][i]
    base = {'id': source['id'], 'name': source['name'], 'ra_deg': source['ra_deg'], 'dec_deg': source['dec_deg']}
    prepared = _prepare(fs, i)
    if prepared is None:
        return {**base, 'status': 'insufficient_data', 'origin': 'spectrum', 'alternatives': []}
    w, bw, sw, Q, residual = prepared
    log_grid = np.arange(0., math.log1p(Z_MAX) + GRID_STEP / 2, GRID_STEP)
    log_grid[-1] = min(log_grid[-1], math.log1p(Z_MAX))
    trials = len(log_grid) * len(TEMPLATES)
    candidates = []

    def fit(profile, log_shift):
        z = math.expm1(float(log_shift))
        columns = []
        for fid in profile['features']:
            _, rest, half, _, _ = FEATURES[fid]
            center = rest * (1 + z)
            # Approximate channel response; broad preset bands retain their width.
            sigma = np.sqrt((bw / 2.355) ** 2 + (half * (1 + z)) ** 2)
            offset = (w - center) / sigma
            covered = w.min() <= center <= w.max() and np.count_nonzero(np.abs(offset) < 2) >= 2
            columns.append(np.where(np.abs(offset) <= 4, np.exp(-.5 * offset ** 2), 0.) if covered else np.zeros(len(w)))
        T = np.column_stack(columns) * sw[:, None]
        T -= Q @ (Q.T @ T)
        T[:, np.linalg.norm(T, axis=0) < 1.] = 0.
        if not np.isfinite(T).all():
            return None
        amplitudes, _ = nnls(T, residual)
        active = amplitudes > 1e-8
        if active.sum() < 2:
            return None
        Ta = T[:, active]
        if np.linalg.matrix_rank(Ta) < int(active.sum()):
            return None
        covariance = np.linalg.pinv(Ta.T @ Ta)
        errors = np.sqrt(np.maximum(np.diag(covariance), 1e-20))
        significant = (amplitudes[active] / errors >= 3) & (amplitudes[active] >= math.log1p(.10))
        if significant.sum() < 2:
            return None
        chi2 = float(np.sum((residual - T @ amplitudes) ** 2))
        gain = float(residual @ residual) - chi2
        score = gain - int(active.sum()) * math.log(len(w)) - 2 * math.log(trials)
        return {'z': round(z, 6), 'profile': profile['id'], 'profile_name': profile['name'],
                'score': round(score, 3), 'chi2': chi2,
                'reduced_chi2': round(chi2 / max(1, len(w) - Q.shape[1] - int(active.sum())), 3), 'log_shift': float(log_shift)}

    for profile in TEMPLATES:
        curve = [fit(profile, v) for v in log_grid]
        for k, point in enumerate(curve):
            if point is None or point['score'] < MIN_SCORE:
                continue
            left = curve[k-1]['score'] if k and curve[k-1] else -math.inf
            right = curve[k+1]['score'] if k+1 < len(curve) and curve[k+1] else -math.inf
            if point['score'] < max(left, right):
                continue
            lo, hi = max(0., log_grid[k] - GRID_STEP), min(math.log1p(Z_MAX), log_grid[k] + GRID_STEP)
            refined = [fit(profile, v) for v in np.linspace(lo, hi, 17)]
            best = max((r for r in refined if r), key=lambda r: r['score'])
            # Independently require local continuum evidence and epoch agreement.
            from .profile_matches import feature_evidence
            evidence = [feature_evidence(fs, i, fid, best['z']) for fid in profile['features']]
            if sum(e['status'] == 'detected' for e in evidence) < 2:
                continue
            h = GRID_STEP / 32
            minus, plus = fit(profile, best['log_shift'] - h), fit(profile, best['log_shift'] + h)
            curvature = ((minus['chi2'] - 2 * best['chi2'] + plus['chi2']) / h**2) if minus and plus else 0.
            radius = math.sqrt(2 / curvature) if curvature > 0 else GRID_STEP
            interval = [math.expm1(max(0., best['log_shift'] - radius)),
                        math.expm1(min(math.log1p(Z_MAX), best['log_shift'] + radius))]
            best.update(features=evidence, z_interval=[round(v, 6) for v in interval])
            candidates.append(best)
    candidates.sort(key=lambda r: -r['score'])
    # Different templates at the same shift are one redshift peak; class may still be uncertain.
    peaks = []
    for candidate in candidates:
        if all(abs(candidate['log_shift'] - p['log_shift']) > .02 for p in peaks):
            peaks.append(candidate)
    if not peaks:
        return {**base, 'status': 'insufficient_evidence', 'origin': 'spectrum', 'alternatives': []}
    best = peaks[0]
    gap = best['score'] - peaks[1]['score'] if len(peaks) > 1 else None
    edge = best['z'] <= .001 or best['z'] >= Z_MAX - .001
    competing = len(peaks) > 1 and (gap < MIN_PEAK_GAP or peaks[1]['score'] >= .5 * best['score'])
    mismatch = best['reduced_chi2'] > 5
    accepted = not edge and not competing and not mismatch
    alternatives = [{k: v for k, v in p.items() if k not in {'log_shift', 'chi2'}} for p in peaks[:3]]
    return {**base, 'status': 'estimated' if accepted else 'ambiguous' if competing or edge else 'insufficient_evidence', 'origin': 'spectrum',
            'z': best['z'] if accepted else None, 'z_interval': best['z_interval'] if accepted else None,
            'peak_gap': round(gap, 3) if gap is not None else None,
            'reason': 'competing shifts' if competing else 'search boundary' if edge else 'template mismatch' if mismatch else 'multiple aligned features',
            'alternatives': alternatives}


def resolve(fs, catalogue):
    sources = catalogue_sources(fs['sources'], catalogue)
    enriched = {**fs, 'sources': sources}
    results = []
    for i, s in enumerate(sources):
        z = valid_z(s.get('redshift', s.get('z')))
        if peer_group(s) == 'stars':
            continue
        if z is not None:
            results.append({'id': s['id'], 'name': s['name'], 'ra_deg': s['ra_deg'], 'dec_deg': s['dec_deg'],
                            'status': 'catalogue', 'origin': s.get('redshift_origin', 'label'), 'z': z,
                            'quality': s.get('redshift_quality'), 'alternatives': []})
        else:
            result = estimate(enriched, i)
            results.append(result)
            if result['status'] == 'estimated':
                s.update(redshift=result['z'], redshift_origin='spectrum', spectral_population='galaxies')
    return enriched, {'version': VERSION, 'sources': results, 'range': [0., Z_MAX], 'method': METHOD,
                      'catalogue_provenance': catalogue.get('provenance')}

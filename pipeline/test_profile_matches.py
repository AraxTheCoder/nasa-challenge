import numpy as np

from pipeline import profile_matches as PM
from pipeline.test_fieldspectra import _field


def spectrum(absorb=True):
    fs = _field(n=1)
    # Dense sampling resolves the narrow on/continuum windows in each epoch.
    w = np.tile(np.linspace(.76, 5, 1400), 3)
    flux = np.full(len(w), 1000.)
    for _, lam, half, _, _ in (PM.FEATURES[f] for f in ('h2o_14', 'h2o_19', 'ch4')):
        flux[np.abs(w - lam) < half] *= .5 if absorb else 1.5
    fs['exposures'] = [{'epoch': 1 + k // 1400} for k in range(len(w))]
    for key, vals in {'wavelength_um': w, 'flux_ujy': flux, 'err_ujy': np.full(len(w), 10.),
                      'bandwidth_um': w / 40, 'masked_fraction': np.zeros(len(w))}.items():
        fs[key] = [vals.tolist()]
    return fs


def test_water_and_methane_match_brown_dwarf():
    out = PM.find_matches(spectrum())
    match = next(m for m in out['matches'] if m['profile'] == 'brown_dwarfs')
    assert all(f['status'] == 'detected' for f in match['features'])
    assert all(f['epochs_agree'] == 3 for f in match['features'])
    assert out['skipped']


def test_emission_does_not_match_absorption_profile():
    assert not any(m['profile'] == 'brown_dwarfs' for m in PM.find_matches(spectrum(False))['matches'])


def test_missing_continuum_and_opposite_epoch_do_not_match():
    fs = spectrum()
    fs['masked_fraction'][0] = [1.] * len(fs['exposures'])
    assert PM.find_matches(fs)['matches'] == []
    fs = spectrum()
    for k, e in enumerate(fs['exposures']):
        if e['epoch'] > 1:
            fs['flux_ujy'][0][k] = 2000 - fs['flux_ujy'][0][k]
    assert not any(m['profile'] == 'brown_dwarfs' for m in PM.find_matches(fs)['matches'])


def test_shared_features_only_computed_once(monkeypatch):
    calls = []
    original = PM.feature_evidence
    def spy(fs, i, fid, z):
        calls.append((i, fid, z))
        return original(fs, i, fid, z)
    monkeypatch.setattr(PM, 'feature_evidence', spy)
    PM.find_matches(spectrum())
    assert len(calls) == len(set(calls))


def test_smooth_spectra_do_not_match_profiles():
    assert PM.find_matches(_field(n=8))['matches'] == []

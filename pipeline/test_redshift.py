import numpy as np
import pytest

from pipeline import redshift as R
from pipeline.chemistry import FEATURES


def field(z=.25, features=('h_alpha', 'pa_beta', 'pa_alpha'), second_z=None, strength=.55):
    rng = np.random.default_rng(21)
    wave = np.tile(np.linspace(.75, 5., 430), 3)
    bw = wave / np.where(wave < 3.8, 41., 110.)
    flux = 2000 * wave ** -1.5
    for shift in ([z] if second_z is None else [z, second_z]):
        for fid in features:
            _, lam, half, _, _ = FEATURES[fid]
            center = lam * (1 + shift)
            sigma = np.sqrt((bw / 2.355)**2 + (half * (1 + shift))**2)
            flux *= np.exp(strength * np.exp(-.5 * ((wave - center) / sigma)**2))
    flux *= np.repeat([1., 1.2, .8], 430)
    err = flux * .015
    flux += rng.normal(size=len(wave)) * err
    return {'sources': [{'id': 'g1', 'name': 'galaxy', 'otype': 'G', 'ra_deg': 10., 'dec_deg': 20., 'mag': 12}],
            'exposures': [{'epoch': 1 + k // 430, 'frame_id': f'f{k}', 'mjd': 60800 + 180 * (k // 430) + .01 * (k % 430), 'detector': 1, 'time_utc': ''} for k in range(len(wave))],
            'flux_ujy': [flux.tolist()], 'err_ujy': [err.tolist()], 'wavelength_um': [wave.tolist()],
            'bandwidth_um': [bw.tolist()], 'masked_fraction': [[0.] * len(wave)]}


def test_recover_quasar_shift_and_local_interval():
    result = R.estimate(field(), 0)
    assert result['status'] == 'estimated', result
    assert result['z'] == pytest.approx(.25, abs=.005)
    assert result['z_interval'][0] <= result['z'] <= result['z_interval'][1]
    assert result['alternatives'][0]['profile'] == 'quasars'


def test_recover_shifted_pah_and_hydrogen():
    result = R.estimate(field(z=.15, features=('pa_beta', 'pah', 'br_alpha')), 0)
    assert result['status'] == 'estimated', result
    assert result['z'] == pytest.approx(.15, abs=.005)
    assert result['alternatives'][0]['profile'] == 'starburst'


def test_noise_and_one_line_have_no_accepted_shift():
    for fs in (field(features=()), field(features=('pa_beta',))):
        assert R.estimate(fs, 0)['status'] != 'estimated'


def test_competing_shifts_are_not_used():
    result = R.estimate(field(z=.25, second_z=.65), 0)
    assert result['status'] == 'ambiguous', result
    assert result['z'] is None
    assert len(result['alternatives']) >= 2


def test_catalogue_priority_unique_spatial_match_and_star_exclusion(monkeypatch):
    fs = field()
    fs['sources'] += [{**fs['sources'][0], 'id': 'far', 'ra_deg': 10.1},
                      {**fs['sources'][0], 'id': 'star', 'otype': '*'}]
    # Catalogue association occurs without a spectrum for the added test sources.
    cat = {'galaxies': [{'name': 'known', 'z': .123, 'ra_deg': 10., 'dec_deg': 20., 'quality': 'A'}]}
    out = R.catalogue_sources(fs['sources'], cat)
    assert out[0]['redshift'] == .123 and out[0]['redshift_origin'] == 'SIMBAD'
    assert 'redshift' not in out[1] and 'redshift' not in out[2]
    cat['galaxies'].append({**cat['galaxies'][0], 'z': .6})
    assert 'redshift' not in R.catalogue_sources(fs['sources'], cat)[0]
    fs = field()
    fs['sources'][0]['redshift'] = .11
    def unexpected(*args):
        raise AssertionError('catalogue source was scanned')
    monkeypatch.setattr(R, 'estimate', unexpected)
    enriched, result = R.resolve(fs, {})
    assert enriched['sources'][0]['redshift'] == .11
    assert result['sources'][0]['status'] == 'catalogue'
    fs['sources'][0].update(otype='*', redshift=None)
    assert R.resolve(fs, {})[1]['sources'] == []


def test_bad_redshifts_and_missing_coverage():
    assert all(R.valid_z(z) is None for z in ('unknown', None, float('nan'), float('inf'), -1, 2))
    fs = field()
    fs['masked_fraction'][0] = [1.] * len(fs['exposures'])
    assert R.estimate(fs, 0)['status'] == 'insufficient_data'


def test_resolved_shift_enables_chemistry_without_image_reads():
    from pipeline.profile_matches import find_matches
    enriched, shifts = R.resolve(field(), {})
    assert shifts['sources'][0]['status'] == 'estimated'
    matches = find_matches(enriched)['matches']
    match = next(m for m in matches if m['profile'] == 'quasars')
    assert match['redshift_origin'] == 'spectrum'
    assert match['z'] == pytest.approx(.25, abs=.005)


def test_gross_template_mismatch_cannot_be_accepted():
    fs = field()
    w = np.array(fs['wavelength_um'][0])
    modulation = np.exp(.7 * np.sin(w * 12))
    fs['flux_ujy'][0] = (np.array(fs['flux_ujy'][0]) * modulation).tolist()
    assert R.estimate(fs, 0)['status'] != 'estimated'

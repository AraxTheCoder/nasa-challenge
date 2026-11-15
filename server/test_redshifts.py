import json

from fastapi.testclient import TestClient

from pipeline import chemistry as C, fieldspectra as FS, photometry
from pipeline.test_redshift import field
from server import redshifts
from server.app import create_app


def test_shared_catalogue_cache_used_by_maps_and_automatic_analysis(tmp_path, monkeypatch):
    monkeypatch.setattr(FS, 'ROOT', tmp_path / 'field_spectra')
    monkeypatch.setattr(photometry, 'SPECTRA_ROOT', tmp_path / 'spectra')
    tid = 'redshift-test'
    d = tmp_path / tid
    d.mkdir()
    target = {'id': tid, 'synthetic': False, 'center': {'ra_deg': 10., 'dec_deg': 20.},
              'size_arcmin': 15, 'frames': [{'id': 'f0', 'mjd': 60800.}],
              'labels': [{'id': 'g1', 'name': 'galaxy', 'otype': 'G', 'source': 'simbad', 'mag': 12.,
                          'positions': [{'frame_id': 'f0', 'ra_deg': 10., 'dec_deg': 20.}]}]}
    (d / 'target.json').write_text(json.dumps(target))
    fs = field()
    sources = FS.sources_of(target)
    fs.update(version=FS.VERSION, target_id=tid, sources=sources, sources_key=FS._key(sources),
              missing=[], seconds=1., n_exposures=len(fs['exposures']), aperture_px=3, annulus_px=[5, 8], note='synthetic test spectra')
    FS._write(FS.cache_path(tid), fs)
    calls = []
    def lookup(target, limit):
        calls.append(limit)
        return {'galaxies': [{'name': 'known galaxy', 'z': .25, 'ra_deg': 10., 'dec_deg': 20., 'quality': 'A'}],
                'provenance': {'service': 'synthetic catalogue fixture'}}
    monkeypatch.setattr(C, 'galaxy_redshifts', lookup)
    client = TestClient(create_app(tmp_path))
    assert client.get(f'/api/targets/{tid}/redshift').json()['galaxies'][0]['z'] == .25
    body = client.get(f'/api/targets/{tid}/spectral-outliers').json()
    assert body['status'] == 'ready'
    source = body['redshifts']['sources'][0]
    assert source['status'] == 'catalogue' and source['origin'] == 'SIMBAD' and source['z'] == .25
    assert any(m['profile'] == 'quasars' and m['redshift_origin'] == 'SIMBAD' for m in body['chemistry_profiles']['matches'])
    assert calls == [200]
    assert client.get(f'/api/targets/{tid}/spectral-outliers').json() == body
    # A catalogue correction invalidates derived analysis but retains aperture spectra.
    path = d / 'chemistry' / 'redshift.json'
    cached = json.loads(path.read_text())
    cached['galaxies'][0]['z'] = .3
    path.write_text(json.dumps(cached))
    changed = client.get(f'/api/targets/{tid}/spectral-outliers').json()
    assert changed['redshifts']['sources'][0]['z'] == .3
    assert calls == [200]


def test_catalogue_failure_backoff_and_recovery(tmp_path, monkeypatch):
    calls = []
    def lookup(*args, **kwargs):
        calls.append(1)
        raise OSError('offline')
    monkeypatch.setattr(C, 'galaxy_redshifts', lookup)
    target = {'id': 'offline', 'center': {'ra_deg': 10., 'dec_deg': 20.}}
    assert redshifts.catalogue(tmp_path, target)['galaxies'] == []
    assert redshifts.catalogue(tmp_path, target)['galaxies'] == []
    assert len(calls) == 1
    key = str(tmp_path / 'chemistry' / 'redshift.json')
    redshifts._retry_at[key] = 0
    monkeypatch.setattr(C, 'galaxy_redshifts', lambda *a, **kw: {'galaxies': [], 'provenance': {'service': 'test'}})
    assert redshifts.catalogue(tmp_path, target)['provenance']
    assert (tmp_path / 'chemistry' / 'redshift.json').is_file()

"""T93: pipeline.chemistry maths on synthetic exposures (no files)."""
import numpy as np

from pipeline import chemistry as C


def _samples(lam0=4.052, bw=0.03, emission=True, n=24, seed=1):
    """n exposures, each with one wavelength across the grid (as if the filter edge were elsewhere): a star with a
    smooth spectrum at (10, 10), emission at the feature in rows 0-4, noise 0.01."""
    rng = np.random.default_rng(seed)
    out = []
    for k in range(n):
        lam = lam0 + (k - n / 2) * bw / 2                    # steps of half a channel through the feature
        f = 0.01 * rng.normal(size=(20, 20))
        f[10, 10] += 5.0 * (lam / lam0) ** -2                # star: smooth, cancels
        if emission and abs(lam - lam0) <= bw / 2:
            f[:5, :] += 0.5                                  # nebula glowing in the line only
        out.append((f, np.full((20, 20), lam), np.full((20, 20), bw)))
    return out


def test_emission_shows_and_the_star_cancels():
    m = C.combine(_samples(), 4.052, 0.0)
    assert np.nanmedian(m["diff"][:5]) > 0.4                 # the line region
    assert abs(m["diff"][10, 10]) < 0.1                      # 5.0 star, smooth spectrum: gone
    assert abs(np.nanmedian(m["diff"][6:])) < 0.02
    assert m["n_on"].max() >= 2 and m["n_blue"].min() >= 1 and m["n_red"].min() >= 1


def test_grey_scale_and_no_data():
    m = C.combine(_samples(), 4.052, 0.0)
    m["diff"][15:, :] = np.nan
    grey, cov, sigma = C.to_grey(m["diff"])
    assert grey[:5].mean() > 200 and abs(grey[6:15].mean() - 128) < 12 and not cov[15:].any() and sigma > 0


def test_continuum_skips_bright_emission_features():
    others = C._other_features(3.05)
    assert any(abs(um - 3.29) < 1e-6 for um, _ in others)          # PAH left out of the ice continuum
    assert not any(abs(um - 4.27) < 1e-6 for um, _ in others)      # ices are not


def test_relevant_exposures_by_detector_range():
    class E:
        def __init__(self, lo, hi):
            self.wave_min_um, self.wave_max_um = lo, hi
    es = [E(0.75, 1.1), E(2.4, 3.8), E(3.8, 4.4), E(4.4, 5.0)]
    r = C.relevant(es, 4.052, 0.0)        # generous: a neighbouring detector may reach the continuum
    assert es[2] in r and es[0] not in r


# --- T96: several features as one colour picture ---

def _map(tmp_path, feature, grey, cov=None):
    from PIL import Image
    (tmp_path / "chemistry").mkdir(exist_ok=True)
    g = np.asarray(grey, np.uint8)
    a = np.full(g.shape, 255, np.uint8) if cov is None else np.where(cov, 255, 0).astype(np.uint8)
    Image.fromarray(np.dstack([g, a]), "LA").save(tmp_path / "chemistry" / f"{feature}.png")


def test_shows_and_combo_order():
    assert C.SHOWS["br_alpha"] == "emission" and C.SHOWS["pah"] == "emission" and C.SHOWS["pa_beta"] == "emission"
    assert C.SHOWS["h2o_ice"] == "absorption" and C.SHOWS["co2_ice"] == "absorption" and C.SHOWS["h2o_19"] == "absorption"
    assert C.combo(["br_alpha", "pah", "h2o_ice"]) == ["h2o_ice", "pah", "br_alpha"]      # by wavelength
    for bad in (["pah"], ["pah", "pah"], ["pah", "gold"]):                         # T108: 4+ features are fine now
        try:
            C.combo(bad)
        except ValueError:
            continue
        raise AssertionError(bad)


def test_strength_floor_and_direction():
    g = np.array([128.0, 128 + 127 * C._FLOOR, 255.0, 0.0])
    em, ab = C.strength(g, "emission"), C.strength(g, "absorption")
    assert em[0] == 0 and em[1] < 1e-6 and em[2] == 1 and em[3] == 0          # 1 noise level or less: black
    assert ab[0] == 0 and ab[2] == 0 and ab[3] > 0.99                         # absorption = darker than 128


def test_combined_map_colours_and_coverage(tmp_path):
    n = 8
    # Br-α (4.05 µm, emission): bright in the left half; H₂O ice (3.05 µm, absorption): dark in the top half
    _map(tmp_path, "br_alpha", np.where(np.arange(n)[None, :] < n // 2, 255, 128).repeat(n, 0))
    ice = np.full((n, n), 128); ice[: n // 2] = 0
    cov = np.ones((n, n), bool); cov[-1, -1] = False
    _map(tmp_path, "h2o_ice", ice, cov)
    rgb, c = C.combined_map(tmp_path, ["br_alpha", "h2o_ice"])                # two: ice (shorter) cyan, Br-α red
    assert rgb.shape == (n, n, 3) and rgb.dtype == np.uint8
    assert tuple(rgb[0, 0]) == (255, 255, 255)                                 # both: red + cyan = white
    assert tuple(rgb[0, -1]) == (0, 255, 255)                                  # ice only: cyan
    assert tuple(rgb[-1, 0]) == (255, 0, 0)                                    # Br-α only: red
    assert tuple(rgb[-1, -2]) == (0, 0, 0)                                     # neither: black
    assert not c[-1, -1] and c.sum() == n * n - 1                              # where all of them have data
    try:
        C.combined_map(tmp_path, ["br_alpha", "pah"])
    except LookupError as e:
        assert "PAH" in str(e)
    else:
        raise AssertionError("missing map not reported")


def test_presets_are_valid_combinations():
    """T107: every preset is a combination the server can make, in colour order, with its reading guide."""
    from pipeline import chemistry as C
    ids = [p["id"] for p in C.PRESETS]
    assert len(ids) == len(set(ids)) and ids
    for p in C.PRESETS:
        assert C.combo(p["features"]) == p["features"]            # valid, already in wavelength order
        assert all(p[k] for k in ("name", "looks_for", "read", "caveats", "tested"))
        assert -90 <= p["try"]["dec"] <= 90 and 0 <= p["try"]["ra"] < 360 and 5 <= p["try"]["size"] <= 210


def test_colours_for_any_number_of_features():
    """T108: 2 and 3 as in T96; from 4 on hues from blue to red, all different."""
    assert C.COMBINE_MAX == len(C.FEATURES)
    assert C.COMBINE_COLOURS[2] == ((0, 1, 1), (1, 0, 0)) and C.COMBINE_COLOURS[3] == ((0, 0, 1), (0, 1, 0), (1, 0, 0))
    for n in range(4, C.COMBINE_MAX + 1):
        cs = C.COMBINE_COLOURS[n]
        assert len(set(cs)) == n and cs[0] == (0, 0, 1) and cs[-1] == (1, 0, 0) and max(map(max, cs)) == 1
    assert C.combo(list(C.FEATURES)) == sorted(C.FEATURES, key=lambda f: C.FEATURES[f][1])


def test_redshift_moves_the_window():
    """T109: Br-α of a galaxy at z = 0.0052 (M100, cz 1 570 km/s) arrives at 4.073 µm: found at that z, missed at z = 0."""
    z = 0.0052
    obs = 4.052 * (1 + z)
    s = _samples(lam0=obs, bw=0.036, n=40)                                   # R ~ 112 at 4 µm
    at_z = C.combine(s, obs, 0.0, z)
    at_rest = C.combine(s, 4.052, 0.0)
    assert np.nanmedian(at_z["diff"][:5]) > 0.4
    assert np.nanmedian(at_rest["diff"][:5]) < 0.5 * np.nanmedian(at_z["diff"][:5])


def test_redshift_keys_and_limits(tmp_path):
    assert C.map_key("pah", 0) == "pah" and C.map_key("pah", 0.02448) == "pah_z245"
    assert C.parse_key("pah_z245") == ("pah", 0.0245) and C.parse_key("h2o_14") == ("h2o_14", 0.0)
    for bad in ("pah_z0", "gold", "gold_z5"):
        try:
            C.parse_key(bad)
        except ValueError:
            continue
        raise AssertionError(bad)
    assert C.combo(["br_alpha_z52", "pah_z52"]) == ["pah_z52", "br_alpha_z52"]
    try:
        C.combo(["br_alpha_z52", "pah"])
    except ValueError as e:
        assert "redshift" in str(e)
    else:
        raise AssertionError("two redshifts in one picture")
    try:                                                                     # CO 4.67 µm at z = 0.1: 5.14 µm
        C.compute(tmp_path, "co_ice", z=0.1)
    except LookupError as e:
        assert "beyond SPHEREx" in str(e)
    else:
        raise AssertionError("beyond 5 µm not reported")
    others = [um for um, _ in C._other_features(4.052 * 1.0052, 0.0052)]       # the galaxy's own lines move too
    assert any(abs(um - 3.29 * 1.0052) < 1e-9 for um in others) and all(abs(um - 4.052 * 1.0052) > 1e-6 for um in others)


def test_redshift_lookup_keeps_only_galaxies(monkeypatch):
    """T112: a Milky Way object with a SIMBAD velocity (ρ Oph: the molecular cloud, otype SFR, z 0.028) is not a
    galaxy: it must not set the field's redshift."""
    import numpy as np
    from pipeline import chemistry as C
    from pipeline import labels as L
    rows = {"main_id": ["NAME Ophiuchus Molecular Cloud", "NGC 6240", "V* XX Oph"], "otype": ["SFR", "SyG", "*"],
            "ra": [247.0, 246.8, 246.7], "dec": [-24.5, -24.5, -24.6], "rvz_redshift": [0.028, 0.02472, 0.002],
            "rvz_qual": ["D", "A", "C"], "galdim_majaxis": [600.0, 2.1, np.nan]}
    monkeypatch.setattr(L, "_tap", lambda url, adql: {k: np.ma.masked_invalid(np.array(v)) if k in ("galdim_majaxis",)
                                                      else np.ma.asarray(np.array(v)) for k, v in rows.items()})
    out = C.galaxy_redshifts({"center": {"ra_deg": 246.79, "dec_deg": -24.54}, "size_arcmin": 30})
    assert [g["name"] for g in out["galaxies"]] == ["NGC 6240"]

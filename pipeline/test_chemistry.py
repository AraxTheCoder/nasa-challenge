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

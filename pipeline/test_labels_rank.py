"""pytest pipeline/test_labels_rank.py (T34): duplicate merging + importance, no network."""
from pipeline.labels import merge_duplicates, rank_importance


def lab(name, ra, dec, source="simbad", named=True, otype="*", mag=None, motion="still"):
    return {"name": name, "source": source, "named": named, "otype": otype, "mag": mag,
            "motion": {"class": motion}, "positions": [{"frame_id": "f0", "ra_deg": ra, "dec_deg": dec, "x": 0, "y": 0}]}


TARGET = {"center": {"ra_deg": 10.0, "dec_deg": 5.0}}


def test_components_and_gaia_twin_merge_into_one():
    ls = merge_duplicates([lab("RW Aur A", 10.0, 5.0), lab("RW Aur", 10.0002, 5.0),
                           lab("Gaia DR3 1", 10.0001, 5.0, source="gaia_dr3", named=False, mag=10.2)])
    assert len(ls) == 1 and ls[0]["name"] == "RW Aur"
    assert set(ls[0]["aliases"]) == {"RW Aur A", "Gaia DR3 1"} and ls[0]["mag"] == 10.2


def test_no_self_alias():
    ls = merge_duplicates([lab("Gaia DR3 7", 10, 5, named=False), lab("Gaia DR3 7", 10, 5, source="gaia_dr3", named=False)])
    assert ls[0]["aliases"] == []


def test_field_object_first_even_with_catalogue_name():
    ls = [lab("WISEA J085510.74-071442.5", 10.0, 5.0, named=False, otype="BD*", motion="proper motion"),
          lab("HD 1", 10.05, 5.0), lab("TYC 2", 10.06, 5.0, named=False), lab("Gaia DR3 3", 10.07, 5.0, source="gaia_dr3", named=False),
          lab("LP 9", 10.08, 5.0, motion="proper motion")]
    rank_importance(ls, TARGET)
    assert [l["importance"] for l in ls] == [0, 2, 3, 4, 1]

"""Write fixtures/discoveries-sample.json (T76): a hand-made discovery index until the survey delivers one (T75).

    python fixtures/make_discoveries_sample.py        # from the repo root; deterministic (same bytes every run)

Real objects at their real positions (taken from web/presets.json and web/discover.json, so the fields open
exactly like the quick picks), but class, score and reason are written by hand from what we know and measured
(T09, T63), not computed by a survey. So the file says "synthetic": true and the viewer labels the list as a
sample. All of them are known objects: they are the survey's validation set (T73: "WISE 0855, Eps Ind B and
known T/Y dwarfs in the pilot must come out as candidates"), which is why each one has "known".
Format: docs/CONTRACTS.md "Discoveries" and docs/discoveries.schema.json.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "fixtures" / "discoveries-sample.json"
STAMP = "2026-11-14T00:00:00Z"
ORDER = 6   # HEALPix order of the survey tiles (T73), nested

# (field name in presets.json / discover.json, class, score, wavelength to look at (µm) or None, reason)
PICKS = [
    ("WISE 0855-0714", "brown_dwarf", 0.95, 4.5,
     "The coldest brown dwarf known (about 250 K, colder than a freezer). Too faint to see at short wavelengths, it "
     "should only show at 4–5 µm, and it moves 8.1″ a year: about 1.3 pixels between the first and the last SPHEREx "
     "epoch here. The survey's first test: if it can't find this one, it can't find new ones."),
    ("Epsilon Indi B", "brown_dwarf", 0.9, 4.0,
     "A pair of brown dwarfs 12 light-years away. Our spectrum check (T63) finds no star shape in any epoch and "
     "3.6–4.7 µm about 5× brighter than a star would be: the cool-atmosphere signature a new brown dwarf would show."),
    ("RW Aurigae", "spectral", 0.85, 4.5,
     "A young star still surrounded by its disk. Its spectrum (T63) is about 15× brighter at 4.0–4.8 µm than the "
     "star alone: warm dust. It also varies: one epoch doesn't fit a single star shape at all."),
    ("R Draconis", "variable", 0.8, 1.6,
     "A Mira variable: it swells and shrinks over about 8 months, so at the same wavelength it should look "
     "clearly brighter or fainter between SPHEREx passes six months apart. Blink two epochs at the same "
     "wavelength. Known (variable-star catalogues), so the survey must flag it and then recognise it."),
    ("Barnard's Star", "mover", 0.75, None,
     "The fastest-moving star in the sky (10.4″ a year), 6 light-years away: about 1.8 SPHEREx pixels between the "
     "first and the last epoch here. It is so bright that its core saturates: a gap that moves with it."),
    ("Kapteyn's star", "mover", 0.6, None,
     "A star from the Milky Way's halo passing close by (13 light-years), moving 8.6″ a year: about 1.5 pixels "
     "across SPHEREx's coverage here. Blink the first against the last epoch."),
    ("SSSPM J1444-2019", "brown_dwarf", 0.55, 4.5,
     "A brown dwarf 56 light-years away moving 3.5″ a year, still only 0.6 px in SPHEREx's coverage here: too "
     "little to see in a blink. The spectrum is the test: a brown dwarf is dim at 1–2 µm and bright at 4–5 µm."),
]


def tile(ra: float, dec: float) -> int:
    import astropy.units as u
    from astropy_healpix import HEALPix
    return int(HEALPix(nside=2 ** ORDER, order="nested").lonlat_to_healpix(ra * u.deg, dec * u.deg))


def main() -> None:
    fields = {}
    for f in ("presets.json", "discover.json"):
        for x in json.loads((REPO / "web" / f).read_text(encoding="utf-8"))["fields"]:
            fields[x["name"]] = x
    candidates = []
    for i, (name, cls, score, lam, reason) in enumerate(PICKS, 1):
        f = fields[name]
        c = {"id": f"sample-{i:02d}", "name": name, "ra_deg": f["ra_deg"], "dec_deg": f["dec_deg"],
             "size_arcmin": f.get("size_arcmin", 10), "class": cls, "score": score, "reason": reason,
             "known": f.get("catalogue_id") or f.get("simbad_id") or name, "tile": {"order": ORDER, "ipix": tile(f["ra_deg"], f["dec_deg"])}}
        if lam:
            c["lam_um"] = lam
        candidates.append(c)
    out = {
        "synthetic": True,
        "survey": "hand-made sample (T76)",
        "description": "A sample discovery index until the survey (T73–T75) delivers one: real, known objects at "
                       "their real positions, with class, score and reason written by hand from our checks (T09, "
                       "T63), not computed. They are the survey's validation set: a working survey must list them too.",
        "generated_utc": STAMP,
        "method": "Positions from web/presets.json and web/discover.json (epoch 2026.0); class, score and reason by hand.",
        "provenance": [{"service": "hand-made (fixtures/make_discoveries_sample.py)", "query": "web/presets.json, web/discover.json",
                        "retrieved_utc": STAMP}],
        "candidates": candidates,
    }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)}: {len(candidates)} candidates")


if __name__ == "__main__":
    main()

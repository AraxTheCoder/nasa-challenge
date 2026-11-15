# T128: Candidates from a chemistry picture (a list of spots, rings on the map)

- **Owner:** Mati  ·  **Status:** review
- **Branch:** `mati/T128-chemistry-candidates`
- **Depends on / feeds:** T93, T96, T107, T122 (select region), T127 (object presets)

## Goal
Select a region, pick a chemistry preset (or tick features): below the picture's note a numbered list of the spots
where the features show, ranked, with the catalogue name if one is there; the same numbers as rings on the map; a
click centres the map on the spot and opens its spectrum. Visualization only (Decision 2026-11-14): spots to look
at, worded as such, nothing classified; the spectrum is how the user judges.

## Plan (agreed with Mati 2026-11-15: per selected region; uncatalogued first, other types next, known last;
## catalogues chosen by the user and asked directly; short texts)
- [x] `pipeline.chemistry.candidates(target_dir, keys)`: strength in noise levels per map in its direction,
      peaks, sharpness pairs / hole rims / edges left out, ranked; extended spots merged and weighted 0.7
- [x] `pipeline/catcheck.py`: SIMBAD (TAP) + Gaia DR3 / CatWISE / AllWISE / 2MASS (VizieR CfA), positions moved by
      proper motion to SPHEREx's date, match 6″, cached per field; tags new / other / untyped / known
- [x] `GET .../chemistry/candidates?maps=...&cats=...&preset=...` (CONTRACTS v0.39), presets `expects`
- [x] viewer: catalogue checkboxes (remembered), list (tags, σ per feature), rings, click = centre + spectrum

## Findings
- On cached maps (no new map computed): Eps Ind B #1 for Brown dwarfs (the Eps Ind A halo below it, "extended",
  "near eps Ind"); 3C 273 #1 for Quasars; NGC 6240 #1 for Star-forming galaxies; ρ Oph protostars: WLY 1-43,
  [GY92] 156, WL 10, WL 22, WL 20 (YSOs) at the top. RW Aur itself not listed (Pa-α too weak once smoothed).
- Catalogue positions are at their own epoch: Eps Ind B (4.7″/yr) is 122″ from its SIMBAD position in 2026 and
  matched nothing at 6″ until positions were moved by proper motion (then SIMBAD + Gaia at 2.8″).
- CDS xMatch and ESA's Gaia TAP did not answer from Mati's machine; SIMBAD (CfA mirror) ~1 s for all spots,
  VizieR (CfA) ~1.5 s per spot and catalogue (6 threads).

## Questions / needs from others

## Handoff
- Testing was light on purpose (Mati's 8 GB machine ran out of memory earlier): unit tests with faked services,
  small real queries for 3 positions; not seen in a browser yet.
- Uncatalogued spots are often artifacts (exposure edges, noise): the list says "uncatalogued", never what it is.

## Notes from others

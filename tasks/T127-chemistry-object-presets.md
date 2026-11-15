# T127: Chemistry presets for objects (brown dwarfs, young stars, Miras, protostars, galaxies, quasars)

- **Owner:** Mati  ·  **Status:** review
- **Branch:** `mati/T127-object-presets`
- **Depends on / feeds:** T93, T96, T107, T108, T109, T121

## Goal
The Chemistry list offers presets for kinds of objects next to the T107 presets for kinds of places, each tried
on a real field and kept only if it shows something there. Objects from the official text ("brown dwarfs,
quasars, comets, asteroids, stars, supernovae and galaxies"; "rich in hydrogen, water, carbon dioxide, carbon
monoxide") and the official test targets. Visualization only (Decision 2026-11-14): nothing is classified.

## Plan (list agreed with Mati 2026-11-15)
- [x] Brown dwarfs: H₂O 1.4 + H₂O 1.9 + CH₄ 3.3 (absorption); Eps Ind B, WISE 0855. CH₄ needs its own feature
      (the PAH / CH₄ map is drawn as emission in pictures)
- [x] Young stars still growing (T Tauri): hydrogen lines at the star; RW Aur
- [x] Pulsating cool giants (Miras): H₂O 1.4 + H₂O 1.9 + CO (absorption), CO 2.3 µm band head as a new feature; R Dra
- [x] Protostars inside ice clouds: ices toward embedded stars; ρ Oph
- [x] Star-forming galaxies: PAH + Br-α + Pa-β at the galaxy's redshift; NGC 6240
- [x] Quasars: Hα / Pa-β / Pa-α at the quasar's redshift (new features Hα, Pa-α); 3C 273
- [x] Presets grouped "Objects" / "Places" in the list; a clicked preset keeps its name even if another has the
      same features
- [x] Not possible with median maps (noted in the list): comets (move between exposures), asteroids, supernovae

## Findings
All maps made with the branch code on fields built through the Live API (2026-11-15 10:42 UTC+1), contact sheets
(3 grey maps + the picture, ring on the object) in the session scratchpad. Per feature: exposures used, median on /
continuum per pixel.
- **Brown dwarfs** (H₂O 1.4 + H₂O 1.9 + CH₄): Eps Ind B (`c3310966-m568007-s15`, 62 / 74 / 25 exposures): dark in
  all three at the centre = white dot. Eps Ind A beside it leaves a big cyan halo. WISE 0855 (`c1337598-…`):
  nothing at all (too faint; T119 needed deep stacks for its motion); its CH₄ map has strong stripes (only ~4
  exposures on the window, each with its own level).
- **Young stars** (Pa-β + Pa-α + Br-α): RW Aur (`c0769566-p304013-s15`): a green (Pa-α) dot on the star; Pa-β a
  dark/bright pair (sharpness), Br-α a dark ring; some other bright stars leave small green dots too. Modest.
- **Cool giants** (H₂O 1.4 + H₂O 1.9 + CO 2.3): R Dra (`c2481672-p667550-s15`, 432 exposures for H₂O 1.9 near the
  ecliptic pole): core saturated (hole); the star's spread light around it shows deep water absorption (green /
  cyan disk); CO 2.3 unclear (dark above, bright below the star).
- **Protostars** (H₂O ice + Br-α + CO₂ ice): ρ Oph (`c2467900-m245400-s30`): red CO₂ ice along the dark filaments,
  magenta dots on them (stars seen through or inside the ice; protostars and background stars alike), the nebula
  top right white; H₂O ice map dominated by exposure-edge stripes (blue stripes).
- **Star-forming galaxies** (Pa-β + PAH + Br-α at z): NGC 6240 (`c2532454-p024009-s15`), SIMBAD z 0.02472:
  yellow-green dot at the centre (PAH + Br-α), Pa-β weak.
- **Quasars** (Hα + Pa-β + Pa-α at z): 3C 273 (`c1872779-p020524-s15`): first run took z = 0.0778 from SIMBAD, a
  galaxy 8.6′ away: `galaxy_redshifts` sorted by size, and 3C 273 (otype BLL, no size) fell off the 8-entry list.
  Fixed (objects at / covering the centre first, REDSHIFT_VERSION 3). At z = 0.15757: a white dot in all three,
  alone in the field.
- Browser check on a branch server (:8001 / :8081, real data): groups "Presets for objects" / "Presets for places",
  9 buttons; Quasars on 3C 273 fills z = 0.1576 and shows the picture; Brown dwarfs on Eps Ind B shows the picture;
  Star-forming galaxies at z = 0 shows the "needs the redshift" note instead of measuring. No page errors, no 5xx.

## Questions / needs from others

## Handoff
- `pipeline.chemistry.PRESETS`: `group` ("object" / "place"), `needs_z`; FEATURES + `h_alpha`, `pa_alpha`,
  `co_23`, `ch4` (CONTRACTS v0.38). `pah` is now just "PAH"; CH₄ has its own map (absorption) at 3.32 µm.
- Hα below z ≈ 0.14: `compute` raises LookupError with the z it needs (→ `no_data` + message).
- Viewer: presets in two groups, a muted line that comets / asteroids can't show in median maps; a clicked preset
  keeps its name when two share features; `needs_z` presets at z = 0 only explain.
- Also fixed (T109 leftover): "use" was offered for the z already in use when SIMBAD's z has 5 decimals.
- Not done: comets (would need one-moment maps), brown dwarfs too faint for single maps (WISE 0855).

## Notes from others

# T107: C: Chemistry presets: tested feature combinations for kinds of objects

- **Owner:** Mati  ·  **Status:** review (not yet seen in a browser)
- **Branch:** `mati/T107-chemistry-presets`
- **Depends on / feeds:** T93 (chemistry maps), T96 (combined maps)

## Goal
Asked by Mati (2026-11-15): ready-made chemistry combinations for interesting kinds of objects, one click in the
Chemistry list. Mature over many: only combinations that were tried on a real field and show something there,
each with what its colours mean, what can fool it and a field to try it on.

Project preferences that apply (checked 2026-11-15):
- Visualization only (Decision 2026-11-14, Mati): a preset says where to look and what the colours mean; it does
  not label anything as a young star, a cloud etc.
- At most 3 features, colours by wavelength (T96, CONTRACTS v0.27); the T93 caveats stay (PAH plateau makes
  water ice look deep inside bright nebulae; star residuals are sharpness differences).

## Plan
- [x] Candidate combinations from the physics of the 10 features
- [x] Make each on a real field, look at the picture, keep only what shows something
- [x] Viewer: presets in the Chemistry list (tick the features in one click), note per preset
- [x] Tests / docs (CONTRACTS v0.34)

## Findings
Three real fields built 2026-11-15 through the Live API (DR1 + QR3, the usual build queries; provenance in each
target.json), the 7 needed feature maps each (27–49 exposures per map), the three combinations looked at by eye:

| Preset | Orion M42 (83.82 −5.39, 20′) | ρ Oph L1688 (246.79 −24.54, 30′) | NGC 7023 (315.40 +68.17, 20′) |
|---|---|---|---|
| Ionised gas: Pa-β + Br-γ + Br-α | M42 white, M43 redder; core saturated | only Br-α (red) at S1, the embedded B star | red halo round HD 200775 (star light: caveat) |
| Ices: H₂O + CO₂ + CO ice | green/blue over the nebula: PAH, not ice | green/yellow along the dense filaments, inside the cloud seen dark at 0.77 µm | blue over the nebula = PAH plateau |
| Cloud edges: PAH + Br-α + CO₂ ice | mixed, saturated: unclear | red ice inside, blue PAH on the side facing the bright stars | blue PAH fills the nebula, red ice in the cloud beside it |

So all three are kept, each with its caveat written from what fooled it here (`PRESETS` in pipeline/chemistry.py):
ices only where green/red show (blue alone = PAH), straight stripes = exposure edges, halos round bright stars.
Not made: a "cool atmospheres" preset (H₂O 1.4 / 1.9 µm, CH₄): those are point sources, the spectrum panel shows
them better than a map.

## Questions / needs from others

## Handoff
Map view panel → **Chemistry ▾** → Presets (top of the list). One click ticks the features and makes the picture;
the note says what to look for, how to read the colours, what can fool it, and links the field where it was tried.
Ticking the same features by hand gives the same note. Presets live in `pipeline/chemistry.py PRESETS`.

## Notes from others

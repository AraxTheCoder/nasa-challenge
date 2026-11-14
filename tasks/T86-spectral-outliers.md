# T86: Spectral outliers

- **Owner:** Joerg  ·  **Status:** doing
- **Branch:** `joerg/T85-field-spectra` (together with T85)
- **Depends on / feeds:** T85 (field spectra), T84 (masking rules), T63 (feature list); feeds T76 (discovery
  index), T75 (HPC survey). Includes idea I23 (Mati) as a second opinion.

## Goal
Find sources whose spectral *shape* doesn't fit what ordinary sources in the same field look like, and say
where and how in plain words ("too bright at 3–5 µm: warm dust?", "dip at 3.0 µm: water ice?").

## Method (Mati's two rules, T75 notes)
1. **Normal comes from the field.** Each spectrum binned into bands and scaled to its own level (shape only:
   immune to the ~10 % calibration, all sources share the same exposures). A few principal shapes learned from
   the field's clean sources (temperature, reddening). Residuals measured against the field's own robust
   scatter per band, not a fixed number.
2. **Only consistent deviations count.** Several neighbouring bands, the same sign in more than one epoch.
   Saturated / flagged exposures are no evidence (T84); sources blended with a brighter neighbour are marked.
3. Second opinion (I23, later): predicted spectrum from Gaia + 2MASS + WISE.

## Plan
- [x] `pipeline/spectral_outliers.py`: band cube (source × epoch × 22 bands), low-rank shape model by
      alternating weighted least squares with missing bands, shapes learned one at a time (a second shape
      learned at once took on the one odd source), trimmed reference, per-band calibrated scatter (≥ 3 %),
      Huber per-source fit (an excess stays in the residuals instead of tilting the source's temperature),
      runs of ≥ 2 bands at ≥ 3σ and ≥ 10 % (or one at ≥ 6σ), same sign in ≥ 2 epochs, plain-words reasons
      (features list as in `web/spectrum.js`; "redder / bluer than ordinary" when both ends are off), caveats
      (blend, known variable, galaxy, jagged residuals)
- [x] Tests: synthetic field of power-law stars with one IR-excess and one water-ice source; saturated
      source not judged and why; caveats
- [x] Real fields checked (findings below)
- [x] Live API + `web/outliers.js` panel "Unusual spectra in this field" (button to start, progress, list
      with a residual chart per source, click opens the spectrum, `outliers:list` event for the map)
- [ ] I23 catalogue prediction as second opinion: not done, moved to T87
- [ ] Visualisation: colour–colour diagram of the field (outliers highlighted, click selects) + selected source's
      band shape vs. its expected ordinary shape and the field's spread

## Findings
- **RW Aur itself can't be judged**: saturated core in 229 of 237 exposures (same as T84). Listed under
  `not_judged` with the reason.
- RW Aur field (Taurus), 137 judged, 80 in the reference: 9 stand out, mostly faint (G ≈ 15) red stars
  ("fainter at 1.3 µm, brighter at 3 µm": reddened or warm dust), a galaxy with +76 % at 4.2–4.6 µm.
- Cross-check against catalogues that weren't used (Gaia BP−RP, AllWISE W1−W2, VizieR CfA mirror): flagged
  3–5 µm excesses have W1−W2 +0.23 median vs −0.02 for ordinary stars; flagged 1.4 µm dips are redder stars
  (BP−RP 1.7 vs 1.2); short-λ excesses are bluer (BP−RP 0.6–0.8). So the measurements are real; with one
  shape most of these were simply the field's hottest / coolest stars, which is why the model now has two.
- High-latitude field RA 180 Dec 0: galaxies dominate the list (correct: they don't look like stars; marked
  "a galaxy" so they're not taken for discoveries). Barnard field: an RR Lyrae on top (colour changes with
  its pulsation; marked "known variable").
- Bugs found on the way: principal shapes started at zero never moved (only the mean shape was fitted);
  1RXS X-ray positions (see T85).
- Limits: shape only (a uniformly brighter or fainter source is not an outlier here: that is T84 / T61);
  22 bands of ~9 % width dilute 1-channel features (PAH 3.3, Br-α); faint sources lose long-λ bands.

## Questions / needs from others

## Handoff
`python -m pipeline.spectral_outliers data/targets/<id>` prints the ranking; the endpoint is in CONTRACTS
v0.15. [to Jonathan] `outliers:list {targetId, items}` fires when the list shows: items have ra/dec, score,
reason, if you want rings on the map. [to Mati] the T76 discovery index could take `items` as "spectral
outlier" candidates; and I23's catalogue prediction is in T87 now, say if you want it.

## Notes from others

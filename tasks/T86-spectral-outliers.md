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
- [ ] `pipeline/spectral_outliers.py`: band vectors, robust shape model, scores, consistency, reasons
- [ ] Tests: synthetic field of power-law stars with one IR-excess and one ice-dip source
- [ ] Real field check: RW Aur should stand out (disk excess), nearly everything else not
- [ ] Live API + a list in the spectrum panel (`web/`), click opens the source's spectrum
- [ ] I23 catalogue prediction as second opinion

## Findings

## Questions / needs from others

## Handoff

## Notes from others

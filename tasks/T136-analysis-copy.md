# T136: Brief analysis text with uncertainty

- **Owner:** Codex (analysis) · **Status:** done
- **Branch:** `main`

## Goal
Make analysis concise initially, with evidence/method/caveats on hover, keyboard focus or tap. Keep tentative interpretations clearly tentative and fix the PAH absorption wording bug.

## Plan
- [x] Shared accessible detail hint with Escape/outside dismissal.
- [x] Short measurement-led copy for spectrum, unusual spectra, chemistry candidates, variability and redshift.
- [x] Correct sign-aware spectral interpretations and avoid asserting identities from a wavelength match.
- [x] Validate interactions, science wording and existing viewer behavior; sync and push.

## Findings
Current measurement summaries mix evidence and fixed physical interpretations, often in long paragraphs. Some legacy strings overstate the inference (e.g. PAH absorbs, a nearby known object necessarily caused a spike). Keep numerical evidence and uncertainty visible; move explanations to optional detail.

## Handoff
Analysis leads with short measured differences and visible tentative/uncertain labels. Spectrum, unusual-source cards/charts, variability, chemistry candidates, redshifts, quality flags and motion use shared optional detail. Hover or keyboard focus shows evidence/method/limitations; click/tap pins it, Escape/outside click closes it. Popovers stay inside the viewport and escape clipped/transformed panel containers. Unresolved redshift rows are collapsed initially. Catalogue lookup misses say "no catalogue match", not a new-object claim.

The individual-spectrum hint function now distinguishes possible methane absorption from PAH emission near 3.3 µm. Numerical measurements, rankings and matching thresholds are unchanged. Old server reasons are not blindly reused to claim that a nearby object caused a spike or that a galaxy has a stellar interpretation.

Validation: all 10 Node suites pass; the existing viewer browser suite finishes with 0 failures. Added a standalone browser regression to CI for hover, focus, click, Escape/outside dismissal, narrow-screen positioning, removed/re-rendered panels and actual unusual-spectra/candidate rendering. Screenshots inspected under /tmp/t136-browser. JS syntax/diff checks pass. No scientific reliability/accuracy calibration is implied by these software checks.

## Notes from others

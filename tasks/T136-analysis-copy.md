# T136: Brief analysis text with uncertainty

- **Owner:** Codex (analysis) · **Status:** doing
- **Branch:** `main`

## Goal
Make analysis concise initially, with evidence/method/caveats on hover, keyboard focus or tap. Keep tentative interpretations clearly tentative and fix the PAH absorption wording bug.

## Plan
- [ ] Shared accessible detail hint with Escape/outside dismissal.
- [ ] Short measurement-led copy for spectrum, unusual spectra, chemistry candidates, variability and redshift.
- [ ] Correct sign-aware spectral interpretations and avoid asserting identities from a wavelength match.
- [ ] Validate interactions, science wording and existing viewer behavior; sync and push.

## Findings
Current measurement summaries mix evidence and fixed physical interpretations, often in long paragraphs. Some legacy strings overstate the inference (e.g. PAH absorbs, a nearby known object necessarily caused a spike). Keep numerical evidence and uncertainty visible; move explanations to optional detail.

## Handoff
Pending.

## Notes from others

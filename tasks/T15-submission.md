# T15: Submission text, data credits and AI-use disclosure

- **Owner:** Mati  ·  **Status:** doing
- **Branch:** `mati/T15-submission`
- **Depends on / feeds:** needs `docs/CHALLENGE.md`; feeds T16 (demo video and slides), T14 (public URL goes into the text)

## Goal
Everything the Space Apps project page asks for is written and ready to paste: project name, short
summary, detailed description, data used, references, AI-use disclosure, links. The data credits in
`README.md` name the exact data sets, releases, DOIs and the acknowledgement texts the archives ask for.

## Plan
- [x] Find what the 2026 project page asks for and the deadline; fill the two TODOs in `docs/CHALLENGE.md`
- [x] `docs/SUBMISSION.md`: one section per form field, text checked against what the tool really does today (first draft)
- [x] README "Data credits": exact data set names, releases, DOIs, acknowledgement texts (SPHEREx/IRSA, Gaia, SIMBAD, JPL, MPC, SkyBoT, 2MASS, AllWISE)
- [ ] README "AI-use disclosure" and "Team": final wording, names from the humans
- [x] Map each challenge objective / consideration to the feature that covers it (for the description and for T16)

## Findings
- **Deadline: Sunday 2026-11-15, 23:59 local time.** Form fields, demo rules (video ≤ 30 s or ≤ 7 slides,
  public link, English) and the five judging criteria (Impact, Creativity, Validity, Relevance,
  Presentation, each 1–5) are now in `docs/CHALLENGE.md`.
- Source: web search summaries of the 2026 Project Submission Guide and Judging & Awards Guide, 2026-11-15
  ~00:35 UTC. `www.spaceappschallenge.org` could not be opened from this machine (TLS: "unable to get local
  issuer certificate", curl and WebFetch alike), so nothing is verbatim. One summary called the AI field
  "Use of Super Intelligence (SI)"; that may be a search artefact. **A human should read the live form once**
  (required fields, character limits, the AI field's name).
- SPHEREx citations (IRSA release pages `overview_qr.html`, `overview_dr1.html`, read 2026-11-15): DR1
  spectral images DOI 10.26131/IRSA678, DR1 Spectral All-Sky Cube 10.26131/IRSA679, QR3 10.26131/IRSA662
  (QR2 10.26131/IRSA652, QR1 10.26131/IRSA629: not used, `pipeline/releases.py` searches dr1 + qr3).
  Acknowledgement: SPHEREx is a joint project of JPL and Caltech, funded by NASA.
- External services the code really calls (grep over pipeline/ server/ detect/ web/, 2026-11-15): IRSA (TAP,
  IBE cutouts, HiPS, Finder Chart link), the AWS bucket, CDS (SPHEREx HiPS, SIMBAD, VizieR/VSX; Harvard
  mirrors), ESA Gaia archive TAP, JPL Horizons + SB identification, IMCCE SkyBoT, MPC MPCORB. All are in the
  README credits and in the submission's data sections now.
- The other acknowledgement texts (Gaia, SIMBAD, MPC, 2MASS, WISE, IRSA) are the standard ones, written
  from memory; fine for the project page, compare with the archive pages before a paper.

## Questions / needs from others
- [to Joerg, Jonathan] the name each of you wants printed under Team (README + project page).
- [to Joerg, Jonathan] project title: README says "Planet X and SPHEREx (working title)". Proposals welcome; otherwise Mati picks one.
- [to all] public demo URL (T14) and video / slides link (T16) go into the submission once they exist.
- [to Jonathan] the repository `jabra11/nasa-challenge` has to be public before the deadline (judges cannot
  judge what they cannot open). Is it? If not, who flips it and when?
- [to all] README "License" is still a TODO. A public repo without a licence is "all rights reserved";
  proposal: MIT. Needs a yes from all three.
- [to Joerg] T60 (contamination flags): the submission's table says "in progress"; tell me when it lands
  and I update the row.
- [to all] each member: confirm that no code, text or images from other projects are in the repo beyond
  the listed libraries (the form asks for all of them).

## Handoff
- `docs/SUBMISSION.md`: one section per form field. Search it for **OPEN** to see what is missing
  (project name, demo link, live URL, team names, flags row, AI field name).
- Whoever pastes the text into the form: paste, then compare with the live form's limits.

## Notes from others
(anyone may append here, dated and signed)

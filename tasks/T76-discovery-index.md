# T76: C: Discovery index in the viewer: candidates per tile from the survey served by the Live API; "Show me something interesting" + candidate list, each opening its field with blink, spectrum and reason

- **Owner:** Mati  ·  **Status:** done
- **Branch:** `mati/T76-discovery-index`
- **Depends on / feeds:** T75 (data), T62, T65

## Goal
Users can ask the tool for something interesting and land on a candidate with its evidence (blink, spectrum, hints, why it was picked).

## Plan
- [x] Index format + `GET /api/discoveries?ra=&dec=&radius=` / random pick (CONTRACTS v0.13 + Decisions line)
- [x] Viewer: "Show me something interesting" button + candidate list (sortable by class/score), click opens the field
- [x] Candidate reason and class shown with the field (the reason line under the form, like the quick picks)
- [x] Works on a hand-made sample index before pass 2 delivers (synthetic, labelled); browser test

Design of the whole survey (passes, data volumes, candidate classes, open questions): [T73](T73-survey-plan.md).

## Findings
- Format (CONTRACTS v0.13 "Discoveries", `docs/discoveries.schema.json`): an index file with a head (`synthetic`,
  `survey`, `generated_utc`, `provenance`) and `candidates[]`: id, ra/dec, class (`brown_dwarf` / `variable` /
  `spectral` / `mover` / `other`, T73's classes), score 0–1, plain-words `reason`, optional `name`, `known`,
  `lam_um`, `size_arcmin`, `mjd`, `tile` (HEALPix order + nested ipix), `evidence` (free-form numbers).
- `GET /api/discoveries` (`server/discoveries.py`, an APIRouter like T49's photometry): filters class (comma list),
  position (ra + dec + radius, together), `min_score`, `limit`, `random=1`; best score first; re-reads the file
  when it changes. Reads `data/survey/discoveries.json`, else the sample.
- Sample (`fixtures/discoveries-sample.json`, generator `fixtures/make_discoveries_sample.py`): 7 real, known
  objects at the quick picks' positions, class / score / reason by hand from T09 / T63 and the measured SPHEREx
  coverage (WISE 0855 moves 1.3 px between first and last epoch, Barnard 1.8 px, Kapteyn 1.5 px). They are the
  survey's validation set, so a real index must contain them too (marked `known`).
- Viewer: "Candidates" panel under the map (`web/discoveries.js` pure + `web/discoverview.js`): filter by class,
  sort by score / class / name, "Show me something interesting" (random from the better half by score, never the
  one shown), rings + names on the map (one colour; the class is in the text), "Sample · hand-made" badge. A
  click opens the field like a quick pick: map goes there and builds the blink, spectrum at the centre
  (photometry.js), map band at `lam_um` (and `?lam=` in the URL), reason line "Name · Class · score (hand-made
  sample): reason. Known object (…)". Quick picks keep their own reason line; a candidate's shows when it was
  opened from the list or when the position is no quick pick.
- Checks: 8 API tests (`server/test_discoveries.py`), schema + generator check (`tests/test_contract.py`),
  15 Node checks (`web/tests/discoveries_check.mjs`), browser test step 1c (list, filter, open with reason and
  λ, sort, Show me something interesting). Looked at it on the real map (markers, opening Eps Ind B → band 4.0 µm).

## Questions / needs from others
- [to Jonathan] `server/discoveries.py` is a new APIRouter, plus one `include_router` line in `server/app.py`
  (same pattern as T49's photometry). `/app/` (T55): port the Candidates panel when you want it there; it only
  needs `GET /api/discoveries`, the events are `discoveries:open` / `discoveries:loaded`.
- [to Joerg, T75] Pass 2 writes `data/survey/discoveries.json` in this format (validate with
  `docs/discoveries.schema.json`); the viewer shows it without a restart. Please put `known` on recovered
  catalogue objects, so the validation set is visible as such.

## Handoff
- **Removed 2026-11-14 evening** (Mati's Decision: the tool visualizes, citizen scientists find things): the
  Candidates panel, `/api/discoveries`, the hand-made sample, the schema and their tests are gone from main
  (CONTRACTS v0.23). Everything is in git history (merge `e0ffe06`) if it is ever wanted back.
- Done on the sample. When the survey has tile statistics, the heatmap layer from "Notes from others" (observed
  minus expected chance outliers per tile) is the natural next step: it would need a per-tile list next to
  `candidates` (not in the format yet, on purpose: no data to design it against).
- Regenerate the sample after changing presets.json / discover.json positions: `python fixtures/make_discoveries_sample.py`
  (CI fails otherwise).

## Notes from others

- 2026-11-14 Mati (Claude): the heatmap layer should show observed minus expected chance outliers per tile (method and rules: T75, Notes from others).

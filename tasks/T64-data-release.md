# T64: A/C: Data release in the UI: release per frame (DR1 / QR3) in target.json, shown in frame info, "newer data available: rebuild" when a cached field is older

- **Owner:** Mati  ·  **Status:** done
- **Branch:** `mati/T64-data-release`
- **Depends on / feeds:** T01, T58 (refresh token)

## Goal
Users see which SPHEREx release each frame comes from, and the tool says when a newer release exists (challenge: "easy to update with the latest data releases").

## Plan
- [x] Pipeline: release per frame from obs_collection into target.json (contract field, Decisions line)
- [x] Viewer: release in frame info + the field line (instead of the footer: the footer is about the API)
- [x] API: flag a cached field that predates the newest release; viewer offers Rebuild (`refresh=1`)
- [x] (Mati's OK, 2026-11-14) image searches pick up new releases: no fixed list of four collections any more

## Findings
From idea I9 in TEAM.md (moved to the Board by Mati, 2026-11-14).

- **The image search could never have seen a new release.** `pipeline/query.py` and the local index harvest
  (`pipeline/mirror.py`) asked IRSA for four fixed collections (`spherex_dr1`, `_dr1_deep`, `_qr3`, `_qr3_deep`).
  Asking IRSA's ObsCore which collections exist scans the whole table (> 5 min, stopped), but the public bucket
  lists one folder per release at its top level in one request (< 1 s): `dr1/`, `qr2/`, `qr3/` on 2026-11-14.
  `pipeline/releases.py` lists it (cached a day in `data/raw/releases.json`; offline: last answer or the known
  list), adds every new folder as `spherex_<rel>` + `spherex_<rel>_deep`, and dedupes an exposure that two
  releases hold (DR over QR, then the higher number). qr / qr2 stay out as before (their data are in DR1).
- Builds write `collection` per frame and `source_exposures` (count, latest exposure, collections, check time)
  per field. `GET /api/targets/<id>/updates` (`server/updates.py`, an APIRouter like T49/T76) compares that with
  the exposure list now and the bucket's folders: newer images (count, dates, new survey passes, new releases),
  `release_note` for unknown release folders, and what it checked against ("the local SPHEREx image index
  (harvested 2026-11-14)" / "IRSA (date)").
- Fields built before this: the release comes from the folder in `source_url` (all 627 cached frames: 448 DR1,
  179 QR3); newer images only count from a new survey pass (> 30 d after the last frame), since frames are a
  selection.
- Viewer: field line "… · 36 frames, 3 epochs · SPHEREx DR1 + QR3", frame info "Release DR1 (spherex_dr1)". When
  there is something new: a line under it ("12 newer SPHEREx images here (…; 1 new survey pass; new release
  QR4). Rebuild to include them.") with "Rebuild now"; up to date stays quiet (tooltip on the field line).
- On the real cache (2026-11-14): every field up to date against the local index harvested today; bucket
  releases dr1, qr2, qr3: nothing new. Note: with the local index, newer data only show after a re-harvest
  (`pipeline.mirror`; the API's data setup harvests only when the index is missing).
- Checks: `pipeline/test_releases.py` (3), `server/test_updates.py` (7), schema, browser test (release in the
  field line + frame info); looked at it on a real field with a faked "newer" answer.

## Questions / needs from others
- [to Joerg] pipeline: `releases.py` (new), `query.find_exposures` (collections default = current releases,
  dedupe), `mirror.jobs()` (was the `JOBS` constant; harvest uses the current releases), `build.py`
  (`collection`, `source_exposures`, helpers `release_name`, `exposure_summary`).
- [to Jonathan] `server/updates.py` is a new APIRouter + one include line in `server/app.py`. Idea for T71's data
  setup: re-harvest the image index when the bucket shows a new release (today it harvests only when missing).

## Handoff
- Rebuild picks up newer images only if the exposure list has them: with the local image index that means a
  re-harvest after a new release (`release_note` tells the user). IRSA TAP searches see them within a day.
- To see the "newer" line without a new release: fake the `/updates` answer in the browser (Playwright
  `page.route("**/updates", …)`), or set a cached target.json's `source_exposures.latest_mjd` back a few days.

## Notes from others

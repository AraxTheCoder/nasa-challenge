# T20: Viewer ↔ Live API

- **Owner:** Mati  ·  **Status:** doing
- **Branch:** `mati/T20-live-api-client`
- **Depends on / feeds:** T11 (viewer), T18 (Live API); feeds T12, T13, T14

## Goal
A user types RA/Dec (decimal or sexagesimal) and a field size, or opens a link with
`?ra=&dec=&size=`, and the viewer requests that field from the Live API, shows build progress, then
blinks it. Matches CONTRACTS v0.3 "Live API" and "Frontend URL".

## Plan
- [ ] Coordinate form: RA, Dec, size (5–60′, default 15), submit → `GET /api/target`
- [ ] Page URL carries `?ra=&dec=&size=`; opening such a link requests the field on load; back/forward work
- [ ] 202 → poll `poll_url` every 2 s with a progress bar (step, done/total, message); 200 → load `target_url`;
      400 / 404 no_data / 500 → clear message
- [ ] Resolve frame images against `target_url`; API base from `?api=` (default `http://localhost:8000`)
- [ ] "Rebuild" (`refresh=1`) to pick up a new data release
- [ ] Quick picks for the five official test fields (coordinates from SIMBAD, query + timestamp recorded)
- [ ] Keep `?data=<folder>` as an offline/dev mode for static target folders (no server needed)
- [ ] Browser test against `python -m server --fixture`

## Findings

## Questions / needs from others

## Handoff

## Notes from others
(anyone may append here, dated and signed)

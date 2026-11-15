# T106: The mover search reaches every field, not only offline runs

- **Owner:** Mati  ·  **Status:** done
- **Branch:** `mati/T106-movers-on-old-fields`
- **Depends on / feeds:** T06, T51, T54

## Goal
Fields opened in the viewer get T06's detections: new builds and fields built before T06.

## Plan
- [x] Early lookup on the build stub: known objects only (`detect_target(..., movers=False)`)
- [x] `/objects` on a field with known objects but no T06 provenance: mover search + classify only (~3 s)
- [x] Viewer asks `/objects` for such fields once more
- [x] Tests; checked on the real Barnard field

## Findings
Found 2026-11-15 after T06 landed, two holes:
1. Fields with `objects_requested: true` were never asked again (server and viewer), so no field built before
   T06 would ever get detections.
2. Worse, for new builds: since T54 the Live API runs `detect_target` early on a stub, while the images are
   still downloading. The mover search there found no cached images, wrote "mover search (T06) skipped" and
   the field was marked done: **T06 never ran on a field built through the Live API.**
Check on Mati's machine: Barnard field `c2694463-p047682-s15` (objects looked up before T06): `/objects`
answered 202, then `{"status":"ready","n":1}`; target.json now ends with `detect.movers (T06)`,
`detect.classify (T08)`, one `unknown` detection; the MPC lookup entry is kept.

## Questions / needs from others

## Handoff
`server/builder.py`: `movers_ran(t)`, `objects()` starts a movers-only job when needed, `_run_objects(...,
movers_only)`, early objects with `movers=False`. `detect/run.py`: `movers` keyword. `web/app.js`: the objects
request also when no provenance entry contains "(T06)". A field is asked once: "skipped" and "failed" count
as ran.

## Notes from others
(anyone may append here, dated and signed)

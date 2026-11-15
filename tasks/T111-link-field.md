# T111: A link to an unbuilt field opens the wrong field

- **Owner:** Joerg  ·  **Status:** done
- **Branch:** `joerg/T111-link-field`
- **Depends on / feeds:** T55 / T90 (automatic tile builds, `decideSource` / `buildTile` in web/app.js), links (?ra=&dec=&size=)

## Findings
- 2026-11-15, live site, fresh browser: `?ra=185.7287&dec=15.8222&size=15` (M100, never built here) requested
  M100, then `target?ra=269.2969&dec=4.7802&size=86&detector=1` (the order-6 tile at the map's default view,
  Barnard's Star); for 2 minutes `currentTarget()` was the Barnard tile field. The M100 build itself was fine
  (ready on the API). Same on NGC 6240 (T109 check): chemistry ran on the Barnard tile field.
- Cause: `loadField(link)` takes the load token and waits for the build; the map sits at its default view, so
  `decideSource` schedules `buildTile` there; `loadField(tile, quiet)` takes a newer token; the link's field
  arrives with a stale token and is dropped (`if (token !== app.loadToken) return`).

## Plan
- [x] No automatic tile build while an asked-for field is loading (`app.explicitLoading` = its load token, cleared
      in `loadField`'s finally); when it arrives the map moves there and `decideSource` runs again
- [x] Browser checks, live site, fresh browser: link to M51 (never built) → only M51 requested, shown after 9 s;
      a Go link without size (RA 121.35 Dec +18.77) → the automatic tile build still runs (82′ tile field, 39 s).
      browser_test 0 failures, web/tests/*.mjs ok

## Notes from others

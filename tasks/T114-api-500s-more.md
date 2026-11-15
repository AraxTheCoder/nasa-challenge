# T114: Bug: three more Live API 500s on bad input (sky-labels / pass-dates with ra=nan, POST settings non-JSON)

- **Owner:** Mati  ·  **Status:** doing
- **Branch:** `main` (input checks only)
- **Depends on / feeds:** T113 (the same probe, every route in openapi.json)

## Goal
`GET /api/sky-labels?ra=nan&dec=0`, `GET /api/pass-dates?ra=nan&dec=0` and `POST /api/settings` with a body that
is not a JSON object answered 500. NaN passes the range checks (only dec was checked, and NaN compares false);
the settings body was parsed without a guard. Now 400.

## Plan
- [ ] finite ra / dec (and radius) in both GET routes; settings: body must parse and be an object
- [ ] tests; probe again

## Findings

## Handoff

## Notes from others

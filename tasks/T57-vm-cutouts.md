# T57: Cutouts via the US VM (faster "Show")

- **Owner:** Jonathan  ·  **Status:** doing
- **Branch:** `jonathan/T57-vm-cutouts`
- **Depends on / feeds:** T33 (S3 Range reads), T47 (VM), T49 (photometry reads the local cutouts)

## Goal
A new field after "Show" is ready as fast as possible. The team VM in `us-east4` (next to the
AWS bucket) cuts the SPHEREx images and sends only the small cutout FITS (gzip) back; build,
detection, photometry and caches stay local and unchanged. Fallback: direct S3, then IRSA.

## Plan
- [ ] tilegen: `GET /cutout?url=&ra=&dec=&size=` → gzip FITS, cached on the VM
- [ ] pipeline: `fetch()` asks the VM first (`--cutouts-remote`, default = team VM)
- [ ] Caddy on the VM lets `/cutout` through; deploy
- [ ] Measure before/after on a fresh field

## Findings
- 2026-11-14, fresh field RA 271.3 Dec 6.2, 15', 44 images, direct S3 from Europe: download
  ~36 s, align+render ~8 s. Each read takes whole detector rows (~2–3 MB per image) but keeps
  1/8 of the columns; the stored cutout is 478 kB, 203 kB gzipped.
- VM → here: 30 MB in 13.6 s over one ssh connection (incl. login), i.e. ≥3 MB/s per connection.

## Questions / needs from others
- [to Joerg] T57 touches only `fetch()` in `pipeline/build.py` (plus `pipeline/s3.py`); T54 works in
  `build_target`, so no overlap expected.

## Handoff

## Notes from others

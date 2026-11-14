# T57: Cutouts via the US VM (faster "Show")

- **Owner:** Jonathan  ·  **Status:** done
- **Branch:** `jonathan/T57-vm-cutouts`
- **Depends on / feeds:** T33 (S3 Range reads), T47 (VM), T49 (photometry reads the local cutouts)

## Goal
A new field after "Show" is ready as fast as possible. The team VM in `us-east4` (next to the
AWS bucket) cuts the SPHEREx images and sends only the small cutout FITS (gzip) back; build,
detection, photometry and caches stay local and unchanged. Fallback: direct S3, then IRSA.

## Plan
- [x] tilegen: `GET /cutout?url=&ra=&dec=&size=` → gzip FITS, cached on the VM (`data/vm_cutouts/`)
- [x] pipeline: `fetch()` asks the VM first (`python -m server --cutouts-remote`, default = team VM)
- [x] Caddy on the VM lets `/cutout` through; deployed
- [x] Align each image while the others still download (2 threads)
- [x] Wrong derived paths (l2b_retry): list the bucket (1.3 s) before TAP (20-40 s)
- [x] deploy: `data/` on the VM really survives updates (was rebuilt every deploy)
- [x] Measure before/after on a fresh field

## Findings
- 2026-11-14, before (direct S3 from Europe): fresh field RA 271.3 Dec 6.2, 15', 44 images:
  download ~36 s, align+render ~8 s. Each read takes whole detector rows (~2-3 MB per image)
  but keeps 1/8 of the columns; the stored cutout is 478 kB, 203 kB gzipped.
- The bottleneck is the line to this PC (~2.5-3 MB/s), not AWS: 8.1 MB of cached cutouts from the
  VM took 3.3 s at 8 parallel, 6.3 s at 24 → builds use 8 parallel requests to the VM.
- VM side: one cutout 0.6 s (7 sequential range requests at ~50 ms), ~7 cutouts/s on the 2 vCPUs.
- Same PC, same code, fresh 15' fields with 36 images, 2026-11-14 ~16:00 UTC:
  `--cutouts-remote none` (direct S3): **52.8 s** (download ~35 s);
  via the VM: **19.9 s** (download ~10 s).
- One image with a wrong derived path (reprocessed `l2b_retry`) used to cost 38 s (TAP lookup) and,
  as a 502, paused the VM for all other images. Now: VM answers `X-Cutout: missing`, the VM stays in
  use, and `s3.find_in_bucket` finds the real path by listing the bucket (2 requests, 1.3 s).
- Image search: weeks the local index has no processing version for went to TAP (one build waited
  145 s in a fresh worktree). Now `mirror.learn_weeks_from_bucket` lists the bucket (0.7 s per week,
  parallel), TAP only as fallback. Jonathan's main checkout knows all 151 weeks, so it never hit this;
  fresh checkouts / new data releases do. Re-measured after that: fresh field 22.4 s.
- The VM's `data/` was a fresh folder after every deploy (`data/.gitkeep` in the archive made tar
  create it, so the link went to `data/data`): image index rebuilt (~2 min) and all caches lost.

## Questions / needs from others
- [to Joerg] T57 touched `fetch()`, the download loop and the T31 retry in `pipeline/build.py`
  (align now runs in a pool during the download); T54's early hook is unchanged.

## Handoff
- Nothing to do: `python web/dev.py` / `python -m server` use the VM by default.
  `GET /api/settings` shows `cutouts: remote|s3`; `--cutouts-remote none` turns it off.
- If the VM is down or old, builds read S3 directly (VM paused for 60 s after a failure), then IRSA.
- Frames cut on the VM have `;via=team-vm-us-east4` in `source_url` (provenance).
- VM health: `https://136-107-125-170.sslip.io/cutout/health` (count, cache hits, mean cut time).
- After changing `tilegen/` or `pipeline/s3.py`: `GCLOUD=<path to gcloud> deploy/deploy.sh`.
- Faster still would need fewer bytes (line-limited): e.g. lossy quantisation of IMAGE like fpack,
  or rendering frames on the VM (photometry would then need the cutouts lazily). Not done.

## Notes from others

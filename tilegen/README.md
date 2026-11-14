# tilegen/ — live deep-zoom tile generator (T42, T47)

Renders HiPS tiles at orders 6-7 (6.4"/px, 3.2"/px) anywhere on the sky from SPHEREx level-2 images
in the AWS Open Data bucket (us-east-1). Below order 6 the map uses IRSA's all-sky cube.

| File | What |
|---|---|
| `render.py` | one tile: pick images (pipeline.mirror), read row chunks (pipeline.s3), sample, stretch |
| `app.py` | the service: `GET /tiles/live/Norder<k>/Dir<d>/Npix<p>[_<slice>].png`, `GET /health` |
| `client.py` | used by the Live API: `local` (in-process) or `remote` (HTTP to a tilegen service) |

As its own service (on the Google Cloud VM next to the bucket, see `deploy/`):

    python -m tilegen --port 8100            # TILEGEN_IMAGES=3 when S3 is fast

The Live API in Europe / on your PC uses it with

    python -m server --tiles-remote https://136-107-125-170.sslip.io [--use-remote]

and the viewer's "Tiles" switch (or `POST /api/settings {"tiles": "remote"|"local"}`) flips between
local and remote rendering. Needs the local image index (`python -m pipeline.mirror harvest`, `build`).
Tests: `python -m pytest tilegen`.

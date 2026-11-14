# pipeline/reference/wide_stitch: wide per-epoch stitching test (T39)

Reference code, not part of the pipeline or the Live API. It answers "what does real per-epoch
stitching over several degrees look like?" before it is built into the product (that is Jonathan's
area: T32 per-epoch HiPS, T36 own sky map).

What it does:

1. `fetch_full.py`: full SPHEREx detector images (3.5 deg each, ~64 MB) from the AWS Open Data mirror
   `nasa-irsa-spherex` (same paths as IRSA, ~4x faster than IRSA on 2026-11-14), N per epoch spread
   over the epoch so they come from different pointings.
2. `make_wide.py`: zodi subtracted, hardware flags masked, `reproject_and_coadd` (mean, background
   matching) of each epoch onto one shared TAN grid fitted to all images, then
   `reproject.hips.reproject_to_hips` (FITS tiles, 256 px, order 7 = ~6.4"/px).
3. `labels_wide.py`: SIMBAD objects over the whole region that are notable (fast proper motion
   > 0.2"/yr or a notable type: variables, white dwarfs, brown dwarfs, ...) plus the 40 brightest
   stars, each moved to each epoch's date.
4. `page_wide/index.html`: Aladin Lite (pinned npm 3.8.2, as in `web/explore.js`) over the IRSA/CDS
   SPHEREx background, our epoch mosaics as overlay layers switched by opacity (instant blink),
   names for the strongest objects, dots + popups for the rest, real traces through the epochs and
   arrows with one shared factor (100 years of motion, labelled not to scale). Colour maps are false
   colour: one detector carries intensity only.

`make_field_hips.py` + `page_field/` are the earlier 1.2 deg version from 1 deg cutouts.

Run: `pipeline/reference/wide_stitch/run.sh data/bake/<id>/query.json` (or any `pipeline.query`
output). Data goes to `data/` (gitignored): ~360 MB of images and ~150 MB of tiles for 6 images.

Measured on Barnard's Star's region, detector 1, 2 images per epoch (2026-11-14):

| Step | Time |
|---|---|
| download 6 full images from AWS (6 in parallel) | ~3 min (IRSA: ~3-4x slower) |
| stitch one epoch (2 images onto a 5.5 x 6.8 deg grid) | 3 s |
| HiPS tiles for one epoch (130-230 tiles) | 5-6 s |
| SIMBAD labels for the 3.6 deg radius (1,600 objects) | ~17 s |

Coverage: 22 deg² per epoch with 2 pointings (13 deg² where they overlap more). The bottleneck is
the download, not the stitching: with Jonathan's HTTP Range reads (T33) only the IMAGE/FLAGS rows of
the region are needed, which would cut it further.

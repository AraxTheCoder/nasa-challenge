# Submission: text for the Space Apps project page

One section per field of the project form, ready to paste. Task: `tasks/T15-submission.md`.
Everything marked **OPEN** still needs a human. Deadline: **Sunday, November 15, 2026, 11:59 PM local
time** (form fields, limits and deadline: see `docs/CHALLENGE.md`, "Submission requirements and deadline").

Before pasting, check on the live form: which fields are required, and any character limits (we could not
open the official guide from this machine, see `tasks/T15-submission.md`, Findings).

## Project name

**OPEN** (Mati picks; the README still says "working title"). Proposals:

- SPHEREx Blink
- Blink the Infrared Sky

## High-level project summary

SPHEREx photographs the whole sky every six months in 102 colours of infrared light. Our tool lets anyone
look at that data in a web browser. Type the coordinates of a patch of sky, or pick one from a list, and
the tool fetches the real SPHEREx images of that spot, lines them up and plays them like a short video.
You can flip between two dates, subtract one image from another, or add images together to see fainter
things. Known stars, asteroids and comets are named on the picture, so anything that moves or changes
without a name stands out. A click on any point shows its spectrum, made on the spot from all 102 colours.
A map of the whole sky lets you zoom from the full sphere down to single SPHEREx pixels. Nothing is
pre-selected: every position on the sky works, and new SPHEREx data releases are picked up automatically.

## Link to project demo

**OPEN** (T16). A video of 30 seconds or less, or a slide deck of up to 7 slides, on a public link
(YouTube, Google Drive, …). If the video is not in English it needs English subtitles.

## Link to final project

- Code: <https://github.com/jabra11/nasa-challenge> (**OPEN:** the repository must be public before the deadline)
- Live tool: **OPEN** (T14, public URL)

## Detailed project description

### What it does

Our tool is a blink comparator for SPHEREx: the method that found Pluto, in a browser, on live data.

1. **Pick a patch of sky.** Type Right Ascension and declination (decimal degrees or 08h55m10.8s
   −7d14m42.5s) and a field of view from 5 to 210 arcminutes, pick one of the five official test targets
   or one of 20 more (the fastest-moving stars, brown dwarfs bright enough for a spectrum), or press
   "Surprise me". A guided tour walks through the five official targets and says what to watch for.
2. **Watch it change.** The tool finds every SPHEREx image that covers the spot, cuts out the field,
   aligns all cutouts north up on one grid and shows them as a series. Blink between two frames, play
   the whole series like a video, or show the difference A − B. A timeline shows the survey passes.
3. **Compare like with like.** No two SPHEREx images are taken at the same wavelength, so a star looks
   different in every frame even if nothing changed. The tool pairs frames from different survey passes
   whose wavelengths match, and can jump to the frames closest to a wavelength you type.
4. **See fainter.** Add together all frames of one survey pass (all six detectors, about 3.5 times
   deeper), all frames of one detector, or shift the frames along a known object or a guessed motion
   before adding (shift-and-stack), so a faint moving object adds up while the stars smear.
5. **Know what is already known.** Names from SIMBAD and Gaia DR3 follow the stars, including their
   proper motion; variable stars show type, period and range (AAVSO VSX). Known asteroids and comets
   are marked at the position where SPHEREx saw them (Minor Planet Center orbits, IMCCE SkyBoT, JPL).
   What moves without a label is the interesting part.
6. **Read the spectrum.** Click any point for its spectrum and light curve, measured on the spot from
   the SPHEREx images. A baseline shows what a plain star would give; points that leave it are ringed
   and explained in plain words (warm dust, cool atmosphere, ices, hydrogen lines). A panel ranks the
   sources of a field by how unusual their spectrum is.
7. **See the chemistry.** For the shown field, map one chemical feature minus its surroundings: water,
   CO₂ and CO ice, PAH dust, hydrogen lines. Tick up to three and get one colour picture.
8. **Explore the whole sky.** A pan-and-zoom map shows the SPHEREx all-sky maps in any of the 102
   channels or in false colour, with 2MASS and AllWISE for comparison, and computes deeper zoom levels
   from the original images while you zoom. "Blink this spot" turns any view into a field.

Every view has a link: `?ra=…&dec=…&size=…` opens a field directly, so the tool can be linked or
embedded from other sites.

### How it works

- **Data on request.** A small Python service (FastAPI, astropy, reproject) looks up the SPHEREx images
  for a position at NASA/IPAC IRSA, reads only the needed parts of each image from the AWS Open Data
  bucket (HTTP range requests, no full downloads), aligns them and caches the result. The
  browser shows the progress of the build.
- **Always the latest data.** The service lists the release folders of the SPHEREx bucket itself, so a
  new release is searched without a code change. A field built earlier says so when newer images exist
  and offers "Rebuild now". Each field records which release every image came from, with query and time.
- **The viewer** is plain HTML and JavaScript without a build step; the sky map is our own renderer for
  HiPS tiles.
- **Honest about the data.** Pixels without data are hatched, not black. The demo runs on real SPHEREx
  data; the small simulated fields we use for tests are labelled as synthetic in the data and in the UI.

### How it answers the challenge

| The challenge asks for | In the tool |
|---|---|
| Public web tool, enter RA and Dec | Field form, any position on the sky |
| A series of images like a little video | Blink, Play, timeline of survey passes |
| Test on Barnard's Star, Eps Indi B, WISE 0855, RW Aur, R Dra | The first five quick picks and the stops of the tour |
| Easy to update with new data releases | Releases found automatically; "Rebuild now" on older fields |
| Show the 102 bands, add detector data together | Band slider, type a wavelength, false colour, stacks per detector and per survey pass, chemistry maps |
| Spectra on the fly | Click any point: spectrum and light curve |
| Add or subtract images from different times | Difference A − B, wavelength-matched pairs, four kinds of stack |
| Choose the field of view | 5 to 210 arcminutes |
| Overlay data from Gaia, WISE | Gaia DR3 and SIMBAD names with proper motion; 2MASS and AllWISE map layers |
| Coordinates in the URL | `?ra=&dec=&size=`, also `?lam=` for a wavelength |
| Metadata such as contamination flags | Release, time, detector and wavelength per frame; flags: **OPEN** (T60, in progress) |
| Use existing tools (astropy, Aladin) | astropy, reproject, pyvo; map tiles in the HiPS format of CDS |

### What we found while testing

- **Barnard's Star**, the fastest star in the sky, moves about 1.8 SPHEREx pixels in the data so far
  (pixels are 6.15″, the data span about 1.4 years). The motion is visible in the blink and the tool
  measures it.
- **Epsilon Indi B** shows a brown-dwarf spectrum (no star-like shape, bright near 4 µm) without being
  told what it is.
- **RW Aurigae** is 15 times brighter at 4–5 µm than a plain star of its colour: its dust disk.
- **WISE 0855** moves about 1.3 pixels in the data so far.
- The asteroid **(29) Amphitrite** was found at its predicted position in 19 of 19 exposures (median
  offset 0.7″), which checks the whole chain from orbit to pixel.

### Limits we know about

- A single SPHEREx exposure reaches about visual magnitude 14–15. Fainter movers need stacking.
- With 6″ pixels and under two years of data, only the fastest stars move visibly; the tool is ready for
  the longer baseline of the coming releases.
- The tool shows and measures; it does not claim discoveries. Finding things is left to the people
  using it.

### Tools and languages

Python 3.12 (astropy, astropy-healpix, reproject, pyvo, numpy, scipy, Pillow, FastAPI, uvicorn),
JavaScript and HTML/CSS without a framework, pytest, GitHub Actions.

## NASA data

- **SPHEREx Data Release 1 (DR1), spectral images**, NASA/IPAC Infrared Science Archive (IRSA),
  DOI [10.26131/IRSA678](https://www.ipac.caltech.edu/doi/10.26131/IRSA678): the images of every field.
- **SPHEREx DR1 Spectral All-Sky Cube**, IRSA, DOI [10.26131/IRSA679](https://www.ipac.caltech.edu/doi/10.26131/IRSA679): the all-sky map.
- **SPHEREx Quick Release 3 (QR3)**, IRSA, DOI [10.26131/IRSA662](https://www.ipac.caltech.edu/doi/10.26131/IRSA662): the newest images, used next to DR1.
- The same SPHEREx images on **AWS Open Data**, bucket `nasa-irsa-spherex`
  (<https://registry.opendata.aws/spherex-qr/>).
- **IRSA services:** TAP (image search), image cutouts, HiPS maps of SPHEREx, 2MASS and AllWISE.
- **JPL Solar System Dynamics:** Horizons (where the SPHEREx spacecraft was at each exposure) and the
  Small-Body Identification API (known asteroids and comets in a field).
- **2MASS** and **AllWISE** all-sky maps (NASA / IPAC), as comparison layers.
- **WiseView** (from the challenge resources) as the model for the blink.

## Space agency partner data and other references

- **Gaia DR3** (ESA): star positions, proper motions and parallaxes for the labels.
- **SIMBAD** and **VizieR** (CDS, Strasbourg; Harvard mirrors): object names and types;
  **AAVSO VSX** through VizieR: variable-star types, periods and ranges.
- **CDS HiPS** of SPHEREx per detector, and the HiPS format itself (Fernique et al. 2015).
- **Minor Planet Center** orbit catalogue MPCORB; **IMCCE SkyBoT** (Berthier et al. 2006).
- Open-source software: astropy, astropy-healpix, reproject, pyvo, numpy, scipy, Pillow, FastAPI, uvicorn.
- **OPEN (each member confirms):** no code, text or images from other projects are in the repository
  beyond the libraries above.

Acknowledgement texts the archives ask for are in `README.md`, "Data credits".

## Use of AI

**Check the exact name and wording of this field on the live form.**

We used Claude (Anthropic) through Claude Code for planning, writing code, tests and documentation, and
for keeping the three team members' work in sync. Each team member worked with their own Claude Code
session; the rules those sessions follow are public in the repository (`CLAUDE.md`), and so is the task
board with a log of who did what (`TEAM.md`). The team decided what to build, reviewed the results and
checked them on real data in the browser.

No AI-generated images, video or audio are in the project. Every image the tool shows is computed from
SPHEREx data (or from the other surveys named above). The only made-up data are two small test fields,
labelled "synthetic" in the data and with a badge and watermark in the viewer.

**OPEN:** if the demo video or slides use AI-generated pictures or voice, they need a visible mark.

## Team

**OPEN:** names as each member wants them printed (asked in `TEAM.md`).

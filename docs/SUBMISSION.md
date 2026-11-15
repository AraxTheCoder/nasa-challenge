# Submission: text for the Space Apps project form

One section per field of the live form (seen 2026-11-15 evening), ready to paste. Task: `tasks/T15-submission.md`.
Every claim was checked against the code on main and the task files; every Objective and Potential Consideration of
the challenge (`docs/CHALLENGE.md`) is answered under "How it answers the challenge"; every link below was opened on
2026-11-15. Deadline: **Sunday, November 15, 2026, 23:59 local time** (CET, 22:59 UTC).

## Still open before submitting (humans)

1. **Project link = the deployed tool** (T14): its public URL goes into the form's "Project" field and into the
   first line of "Project Details".
2. **The AI tool that made the demo video and its sound**: its name and link go into the last row of "Space Agency
   Partner & Other Data".

# Form section "Project Summary"

## Project Name

SPHEREx Blink

(Spelled like the mission: "SPHEREx", as in the video and the tool.)

## Summary

Plain text field, limit 1500 characters, 50–200 words suggested. This text: 1,133 characters, 200 words (pasted as one paragraph).

SPHEREx Blink is a free, open-source web tool that lets anyone see how the sky changes in NASA's SPHEREx data. Type the
coordinates of any patch of sky, or pick one of the five test targets. The tool fetches the real SPHEREx images of
that spot from NASA's archive, lines them up and plays them like a short video. Anything that moves or changes
between SPHEREx's visits stands out. This is the blink method that found Pluto, run on live data in a browser.
Known stars, asteroids and comets are labelled, so whatever moves without a label is the interesting part. SPHEREx
sees in 102 infrared colours, so a click on any point shows its spectrum. Chemistry maps show where water ice, CO₂
ice or glowing hydrogen are. A sky map zooms from the whole sky down to single SPHEREx pixels. A community space
lets volunteers discuss what they find and ask others for a second look. New data releases are picked up without
code changes. This matters because SPHEREx returns images of more than a billion objects, far more than any team
can inspect. Volunteers comparing images in this way have already found most known comets and brown dwarfs.

# Form section "Project Links"

## Project Demonstration

https://cdn.jsdelivr.net/gh/AraxTheCoder/nasa-challenge@725e92de1f5096d53af127496fad0ee5df47f2c9/docs/demo/spherex-blink-demo-30s.mp4

The 30-second video (1920×1080; picture and sound AI-generated, marked "AI-generated video and audio" for its whole
length) plays in the browser, no login. It is `docs/demo/spherex-blink-demo-30s.mp4` in the public repository,
served by jsDelivr and pinned to one commit, so the link never changes. Checked 2026-11-15: HTTP 200, `video/mp4`,
identical bytes.

## Project

**OPEN:** the public URL of the deployed tool (T14).

# Form section "Project Information"

## Project Details

Rich-text field. Paste from the rendered page (see Handoff in `tasks/T15-submission.md`) so headings, lists and bold
survive.

**Try it:** OPEN (the deployed tool's URL) · **Source code** (GNU GPL v3 or later):
https://github.com/AraxTheCoder/nasa-challenge

### What it does

1. **Pick a patch of sky.** Type Right Ascension and declination (decimal degrees, or 08h55m10.8s −7d14m42.5s) and
   a field size from 5 to 210 arcminutes. You can also drag a rectangle on the sky map, or pick one of the five
   official test targets. There are 20 more picks: ten of the fastest-moving stars and ten brown dwarfs. "Surprise
   me" opens a random one. A guided tour visits the five official targets and says what to look for.
2. **Watch it change.** The sky map blinks by itself between the dates SPHEREx imaged the spot. Zoomed in on one
   spot, it blinks that spot's own aligned images. For a field you build, you can blink two images A and B, play
   all images like a film, or show the difference A − B. In the difference, steady stars cancel and a mover shows
   as a light and dark pair. A timeline shows every visit.
3. **Compare like with like.** SPHEREx takes every image at a slightly different wavelength, so a star can look
   different between two images even when nothing changed. The tool pairs images from different visits that have
   matching wavelengths, and jumps to the images closest to a wavelength you type.
4. **See fainter.** In the frame view (add `&frames=1` to a link), you can add together all images of one visit
   (all six detectors) or all images of one detector. You can also shift the images along a selected object or a
   guessed motion before adding them (shift-and-stack). A faint mover then adds up while the stars smear. A stack of
   n images shows sources about √n times fainter.
5. **Know what is already known.** Labels come from SIMBAD names, Gaia DR3 stars (moved by their proper motion to
   each image's date) and CatWISE2020 brown dwarfs. Variable stars show their type, period and range (AAVSO VSX).
   Known asteroids and comets are marked where SPHEREx saw them, from its own position in space (Minor Planet Center
   orbits, IMCCE SkyBoT, JPL Horizons).
6. **Measure motion and distance.** For a moving star, the tool measures its motion from the SPHEREx images alone
   and shows the catalogue value next to it. When the fit is reliable, it also gives the star's distance from its
   parallax.
7. **Read the spectrum.** Click any point. The tool measures its brightness in every SPHEREx image of that spot,
   often several hundred, and draws a spectrum for each visit. An optional simple star model shows what a plain star
   would give. Short hints name what can cause a departure from it: warm dust, a cool atmosphere, ices, hydrogen
   lines. "Changes between visits" compares images taken at matching wavelengths. SPHEREx's quality flags at that
   spot are listed by name, in plain words.
8. **Find the unusual.** "Unusual spectra" measures every source in the field, both catalogued ones and sources
   found in SPHEREx's own images. It rings those whose spectrum doesn't look like their neighbours', and lists the
   uncatalogued ones first. It also marks sources whose brightness changes at the same wavelength. Our own search
   marks sources that are there at one moment and gone at others, seen by both detectors that image at the same
   time. Afterglows of bright stars and hot pixels are sorted out as artifacts. All of these are marks for a person
   to check, not discovery claims.
9. **See the chemistry.** For the shown field, the tool maps a chemical feature minus its neighbouring wavelengths.
   There are 14 features: water, CO₂, CO and methanol ice, PAH dust, water and methane in cool atmospheres, the
   CO band at 2.3 µm, and the hydrogen lines Hα, Pa-α, Pa-β, Br-γ and Br-α. Ticking several features gives one colour picture.
   Nine presets were each tried on a real field: brown dwarfs, young stars, pulsating giants, protostars,
   star-forming galaxies, quasars, ionised gas, ices in cold clouds and lit cloud edges. Galaxies can be mapped at
   their redshift, suggested from SIMBAD. "Spots" lists where the picked features show and looks each spot up in
   catalogues, uncatalogued ones first.
10. **Explore the whole sky.** A pan-and-zoom map shows SPHEREx's all-sky data in any of the 102 channels or in
    false colour, with 2MASS and AllWISE as comparison maps. Deeper zoom levels are computed from the original
    SPHEREx images while you zoom. A "Quality flags" layer shows where SPHEREx's own flags make the data unreliable.
11. **Work together.** The Community tab has a discussion for every patch of sky: comments, replies, "look here"
    positions, and requests for a second look with the saved view attached. Feeds show recent and unanswered posts.
    A coverage map shows how many different browsers have looked at each patch, so volunteers can find sky that
    few people have checked.

Every view has a link. `?ra=…&dec=…&size=…` builds a field, `?ra=…&dec=…` centres the map there, `?lam=…` picks a
wavelength and `?tour=1` starts the tour. So the tool can be linked from or embedded in other sites.

### How it works

- **Data on request.** A Python service (FastAPI, astropy, reproject) finds the SPHEREx images of a position in a
  local copy of IRSA's SPHEREx image index, or asks IRSA directly. It reads only the needed pixels of each image from the AWS Open Data copy
  of SPHEREx (HTTP range requests, no full downloads), if needed through a small cloud machine close to the data. It
  aligns the images north up on one grid and caches the result. The browser shows the progress of each build.
- **Always the newest data.** The service reads the list of releases from the SPHEREx data bucket itself, once a
  day, so a new release is searched without a code change. A field built earlier says so when newer images exist,
  and offers "Rebuild now". Every image records its release, query and time.
- **Spectra on the fly.** Aperture photometry on the calibrated SPHEREx images, at the wavelength each image has at
  that position.
- **The sky map** is our own WebGL renderer for HiPS tiles, the CDS standard for sky maps. It replaced Aladin Lite,
  which our first version used.
- **The viewer** is plain HTML and JavaScript without a build step.
- **Honest about the data.** The tool shows SPHEREx's quality flags and says when a star is saturated or too faint
  to measure, instead of showing made-up numbers. The demo runs on real SPHEREx data. The two small simulated
  fields used in tests are labelled "synthetic" in the data and in the viewer.
- **Tested.** GitHub Actions runs the Python tests, the data-format checks, the JavaScript tests and a browser test
  on every push.

### Benefits

- Users need only a web browser: no Python, no FITS files, no astronomy software. The server runs on one machine,
  started with one command.
- Any position on the sky works. Nothing is pre-selected, and new SPHEREx releases appear by themselves.
- Beginners get the tour, quick picks and plain-word hints. Experts get matched wavelengths, stacks, spectra,
  quality flags and measured motion.
- The community space turns single looks into shared, checkable findings.

### Intended impact

SPHEREx maps the whole sky every six months in 102 colours: far more images than any team can inspect. WiseView, a
blink tool for NASA's WISE mission, let the public make hundreds of discoveries. SPHEREx Blink aims to do the same for
SPHEREx: anyone with a browser can check a patch of sky for things that move, change or have an unusual spectrum, and
ask others for a second look. Teachers and the public can watch a star move and see its distance measured from
SPHEREx data. Every new release makes the time span longer, so more motions become visible, and the tool picks up new
releases by itself.

### What is creative about it

- **Blinking at matching wavelengths.** SPHEREx never sees a spot twice at exactly the same wavelength, so a plain
  blink shows stars "changing" that didn't change. The tool pairs images by wavelength, a problem blink tools for
  earlier surveys never had to solve.
- **102 colours made readable.** A spectrum on any click, with plain-word hints, and chemistry maps that show where
  water ice or glowing hydrogen are.
- **Motion and distance from SPHEREx alone**, shown next to Gaia's values, so anyone can check the tool against a
  trusted reference.
- **A map of the community's attention.** It shows how many different people looked at each patch of sky, so
  volunteers go where nobody has looked yet.
- **The whole sky down to single pixels**, with deep zoom levels computed on demand from the original images
  instead of a huge pre-processed copy.

### Factors we considered

- **Honesty about the data.** Real SPHEREx data only; the two simulated test fields are labelled. Quality flags are
  shown, saturated or too-faint stars are named as such, measurements come with their uncertainties, and nothing is
  called a discovery: a second look asks for another opinion, it does not confirm one.
- **Fair comparisons.** Images are compared at matching wavelengths, so a colour difference is not mistaken for a
  change.
- **Care for NASA's archives.** The tool reads only the pixels it needs and caches them; the server has a public
  mode with rate limits and a cache size cap.
- **Speed.** A local copy of the image index, a cloud machine close to the data, and visible progress while a field
  is built.
- **Ease of use.** A guided tour, quick picks, short hints with details on demand, keyboard shortcuts, and layouts
  that work on phone and tablet screens.
- **Data that keeps arriving.** New releases are found by themselves, and every image records where it came from.
- **Openness.** Free software under the GNU GPL, and a link for every view so findings can be shared and checked.

### How it answers the challenge

- **Public web tool where users enter RA and Dec:** field form with decimal or sexagesimal coordinates, for any
  position on the sky.
- **A series of images like a little video:** the map blinks by itself; for a field: Blink A/B, Play all, timeline.
- **Test on Barnard's Star, Epsilon Indi B, WISE 0855, RW Aurigae, R Draconis:** all five are quick picks and tour
  stops; results below.
- **Easy to update with the latest data releases:** releases found automatically; "Rebuild now" on older fields.
- **Make use of the 102 bands; add up each detector's data:** band slider, typed wavelength, false colour, stacks
  per detector and per visit, chemistry maps.
- **Spectra on the fly:** click any point.
- **Add or subtract images taken at different times:** A − B, wavelength-matched pairs, four kinds of stack.
- **Let users choose the field of view:** 5 to 210 arcminutes, typed or dragged on the map.
- **Overlay data from Gaia or WISE:** Gaia DR3 labels with proper motion, CatWISE2020 brown dwarfs; 2MASS and
  AllWISE comparison maps.
- **Coordinates in the URL:** `?ra=&dec=&size=`, also `?lam=` and `?tour=1`; a "Copy link" button.
- **Display metadata like contamination flags:** quality flags by name at any point, a quality-flag map layer;
  release, time, detector and wavelength of every image.
- **Use public tools (astropy, Aladin):** astropy, reproject, pyvo, astropy-healpix; HiPS maps (the CDS standard
  behind Aladin) in our own renderer.

### Results on real SPHEREx data

- **Barnard's Star:** SPHEREx alone measures 10.46 ± 0.19″/yr toward position angle 356° (299 images over 0.98
  years). Gaia gives 10.39″/yr toward 356°. That is about 1.7 SPHEREx pixels a year, visible in the blink. The star
  saturates the detectors in 297 of 298 images, and the quality flags say so.
- **Epsilon Indi B:** 4.60 ± 0.26″/yr (catalogue 4.68″/yr). Its parallax, 0.286 ± 0.022″, puts it at 3.49 pc;
  Gaia puts its host star ε Indi A at 3.64 pc. Its spectrum has no star shape and is about 5 times brighter at
  3.6–4.7 µm than a star fit: a cool atmosphere.
- **WISE 0855:** too faint in single images. Stacks of its 3.8–5 µm images for each visit give 7.22 ± 1.02″/yr
  toward position angle 282° (catalogue 8.15″/yr toward 275°).
- **RW Aurigae:** about 15 times brighter at 4.0–4.8 µm than a plain star fitted to its shorter wavelengths: the
  warm dust around this young star.
- **R Draconis:** this pulsating giant is so bright that it saturates the centre of its image. The tool leaves
  the saturated pixels out instead of showing wrong numbers. The chemistry preset for cool giants shows deep water
  absorption in the star's light around the centre.
- **Known asteroid check:** (29) Amphitrite was found at its predicted position in 19 of 19 images (median offset
  0.7″), with no false finds at 109 control positions. This checks the chain from orbit to pixel.
- **Variable stars:** on two 86′ fields in Ophiuchus, 24 of the 34 sources marked as changing brightness are
  catalogued variables (Miras, eclipsing binaries, RR Lyrae stars and long-period variables).

### Limits we know about

- A single SPHEREx image reaches about visual magnitude 14–15; fainter movers need stacking.
- With 6.15″ pixels and about a year of repeated visits so far, only the fastest stars move visibly. The tool is
  ready for the longer time span of coming releases.
- Bright stars saturate SPHEREx (flagged, not measured).
- The tool shows and measures; it does not claim discoveries. Finding things is left to the people using it.
- Community posts are anonymous (a chosen display name) and not moderated yet.

### Tools, languages and hardware

Python 3.12 (astropy, astropy-healpix, reproject, pyvo, numpy, scipy, Pillow, requests, FastAPI, uvicorn, SQLite);
JavaScript, HTML, CSS and WebGL without a framework; pytest, Playwright, Node.js and GitHub Actions for tests.
Hardware: our own laptops and one small cloud virtual machine close to the data (map tiles, image cutouts). The code
was written with AI coding assistants (see "Use of AI").

# Form section "NASA Data" (Link Text → Link Url)

| Link Text | Link Url |
|---|---|
| SPHEREx Data Release 1: Spectral Images (IRSA) | https://doi.org/10.26131/IRSA678 |
| SPHEREx Data Release 1: Spectral All-Sky Cube (IRSA) | https://doi.org/10.26131/IRSA679 |
| SPHEREx Quick Release 3 (IRSA) | https://doi.org/10.26131/IRSA662 |
| SPHEREx at the NASA/IPAC Infrared Science Archive (IRSA) | https://irsa.ipac.caltech.edu/Missions/spherex.html |
| SPHEREx on the Registry of Open Data on AWS | https://registry.opendata.aws/spherex-qr/ |
| IRSA Table Access Protocol (TAP) service | https://irsa.ipac.caltech.edu/docs/program_interface/TAP.html |
| IRSA HiPS sky maps (SPHEREx, 2MASS, AllWISE) | https://irsa.ipac.caltech.edu/data/hips/list |
| JPL Horizons | https://ssd.jpl.nasa.gov/horizons/ |
| JPL Small-Body Identification API | https://ssd-api.jpl.nasa.gov/doc/sb_ident.html |
| 2MASS (IRSA) | https://irsa.ipac.caltech.edu/Missions/2mass.html |
| AllWISE (IRSA) | https://irsa.ipac.caltech.edu/data/WISE/docs/release/AllWISE/ |
| CatWISE2020 catalogue (from WISE and NEOWISE data) | https://catwise.github.io/ |
| WiseView (our model for the blink) | http://byw.tools/wiseview |

What each is used for: "Project Details" and `README.md`, "Data credits" (acknowledgement texts).

# Form section "Space Agency Partner & Other Data" (Link Text → Link Url)

| Link Text | Link Url |
|---|---|
| Gaia Data Release 3 (ESA) | https://www.cosmos.esa.int/web/gaia/dr3 |
| SIMBAD astronomical database (CDS) | https://simbad.cds.unistra.fr/ |
| VizieR catalogue service (CDS) | https://vizier.cds.unistra.fr/ |
| AAVSO International Variable Star Index (VSX) | https://vsx.aavso.org/ |
| HiPS sky-map standard (IVOA; CDS SPHEREx maps per detector) | https://www.ivoa.net/documents/HiPS/ |
| Minor Planet Center orbit catalogue (MPCORB) | https://minorplanetcenter.net/iau/MPCORB.html |
| IMCCE SkyBoT | https://ssp.imcce.fr/webservices/skybot/ |
| Astropy | https://www.astropy.org/ |
| astropy-healpix | https://github.com/astropy/astropy-healpix |
| reproject | https://reproject.readthedocs.io/ |
| PyVO | https://pyvo.readthedocs.io/ |
| NumPy | https://numpy.org/ |
| SciPy | https://scipy.org/ |
| Pillow | https://python-pillow.org/ |
| Requests | https://requests.readthedocs.io/ |
| FastAPI | https://fastapi.tiangolo.com/ |
| Uvicorn | https://uvicorn.dev/ |
| SQLite | https://www.sqlite.org/ |
| pytest | https://pytest.org/ |
| Playwright | https://playwright.dev/ |
| Node.js | https://nodejs.org/ |
| GitHub Actions | https://github.com/features/actions |
| FFmpeg (AI label on the demo video) | https://ffmpeg.org/ |
| jsDelivr (serves the demo video) | https://www.jsdelivr.com/ |
| Claude Code (Anthropic), AI coding assistant | https://claude.com/product/claude-code |
| OpenAI Codex, AI coding assistant | https://openai.com/codex/ |
| **OPEN:** the AI tool that generated the demo video and its sound | **OPEN** |

All links opened on 2026-11-15 (openai.com shows scripts a bot check; it opens in a browser). The code in the
repository was written for this project, by AI coding assistants under the team's direction; beyond the tools above
we have not knowingly included code, text or images from other projects.

## Use of AI

The code, tests and documentation were written by AI coding assistants under the team's direction: Claude
(Anthropic) through Claude Code, used by all three team members, and OpenAI Codex for some tasks (community
workspace, shared spectral analysis, redshift search, map selection, brightness panel). The assistants also
planned work with us and kept the three team members' work in sync. The rules the Claude Code sessions followed are public in the repository (`CLAUDE.md`), and
so are the task board and a log of who did what (`TEAM.md`, `tasks/`). The team decided what to build, reviewed
the results and checked them on real data in the browser.

The tool contains no AI-generated images, video or audio. Every image it shows is computed from SPHEREx data or
from the other surveys named above. The only simulated data are two small test fields, labelled "synthetic" in
the data and with a badge and watermark in the viewer. The demo video, picture and sound, is AI-generated;
it says so with a visible mark for its whole length ("AI-generated video and audio").

## Team

Team name (exactly these characters, underscores included): `_P$YcHoNaUt$_`

Members: Jonathan, Jörg, Mateusz

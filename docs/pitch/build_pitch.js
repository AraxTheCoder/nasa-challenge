// Builds docs/pitch/local-judging-pitch.pptx (T16): the pitch deck for the local judging.
//
//   npm install pptxgenjs jszip          (anywhere; point NODE_PATH at that node_modules)
//   node docs/pitch/build_pitch.js [out.pptx]
//
// Optional: PPTX_APPLY_THEME=<path to apply_theme.js> writes the palette into the deck's theme, so
// the colours can be changed in one place in PowerPoint (Design > Variants > Colors).
// The dashed boxes named "Video placeholder N" are where the screen recordings go.

const path = require("path");
const pptxgen = require("pptxgenjs");

const OUT = process.argv[2] || path.join(__dirname, "local-judging-pitch.pptx");
const NAME = "SPHEREx Blink"; // working name, see docs/SUBMISSION.md "Project name"

const THEME = {
  name: "SPHEREx Blink",
  headFontFace: "Arial",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "0B1026", // night sky (slide background)
    lt1: "F3F5FB", // text
    dk2: "161E42", // panels
    lt2: "AEB7D3", // muted text
    accent1: "FF7A45", // infrared orange
    accent2: "5CD6E0", // water cyan
    accent3: "FFC857",
    accent4: "8E7CFF",
    accent5: "2B3568", // panel outline
    accent6: "6B7599",
    hlink: "5CD6E0",
    folHlink: "8E7CFF",
  },
};

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5 in
pres.title = NAME + ": pitch for local judging";
pres.author = "Team " + NAME;
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };

const C = pres.SchemeColor;
const BG = C.text1, TEXT = C.background1, PANEL = C.text2, MUTED = C.background2;
const ORANGE = C.accent1, CYAN = C.accent2, OUTLINE = C.accent5;
const W = 13.333, M = 0.6, CW = W - 2 * M;

// ---------- layouts ----------
pres.defineSlideMaster({
  title: "COVER",
  background: { color: BG },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: M, y: 2.35, w: 7.4, h: 1.3, fontSize: 60, bold: true, color: TEXT, align: "left", valign: "middle", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: M, y: 3.7, w: 7.4, h: 0.8, fontSize: 28, color: ORANGE, align: "left", valign: "top", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: BG },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: M, y: 0.45, w: CW, h: 0.95, fontSize: 36, bold: true, color: TEXT, align: "left", valign: "middle", margin: 0 }, text: "" } },
    { text: { text: NAME + "  ·  NASA Space Apps Challenge 2026", options: { x: M, y: 6.95, w: 7, h: 0.3, fontSize: 11, color: MUTED, margin: 0, isTextBox: true } } },
  ],
  slideNumber: { x: W - M - 0.6, y: 6.95, w: 0.6, h: 0.3, fontSize: 11, color: MUTED, align: "right" },
});

// ---------- helpers ----------
let n = 0;
const nm = (s) => s + " " + ++n;
function text(slide, t, o) {
  slide.addText(t, Object.assign({ isTextBox: true, margin: 0, color: TEXT, fontSize: 16, valign: "top", objectName: nm("Text") }, o));
}
function panel(slide, x, y, w, h, o = {}) {
  slide.addShape(pres.ShapeType.roundRect, {
    x, y, w, h, rectRadius: 0.12, fill: { color: o.fill || PANEL },
    line: { color: o.line || OUTLINE, width: o.lineWidth || 1 }, objectName: nm("Panel"),
  });
}
function badge(slide, label, x, y, d = 0.5) {
  slide.addText(label, {
    shape: pres.ShapeType.ellipse, x, y, w: d, h: d, fill: { color: ORANGE }, line: { color: ORANGE, width: 0 },
    color: BG, bold: true, fontSize: 16, align: "center", valign: "middle", margin: 0, objectName: nm("Badge"),
  });
}
/** A numbered row: badge, bold head, muted line below. */
function row(slide, i, head, body, x, y, w) {
  badge(slide, String(i), x, y + 0.03);
  text(slide, head, { x: x + 0.75, y, w: w - 0.75, h: 0.4, fontSize: 20, bold: true });
  text(slide, body, { x: x + 0.75, y: y + 0.42, w: w - 0.75, h: 0.7, fontSize: 15, color: MUTED });
}
/** Dashed 16:9 box that says which recording goes here. */
let videoNo = 0;
function video(slide, x, y, w, what, secs) {
  const h = (w * 9) / 16;
  videoNo += 1;
  slide.addShape(pres.ShapeType.roundRect, {
    x, y, w, h, rectRadius: 0.12, fill: { color: PANEL },
    line: { color: ORANGE, width: 1.5, dashType: "dash" }, objectName: "Video placeholder " + videoNo,
  });
  const cy = y + h / 2 - 0.95;
  slide.addShape(pres.ShapeType.ellipse, { x: x + w / 2 - 0.4, y: cy, w: 0.8, h: 0.8, fill: { color: ORANGE }, line: { color: ORANGE, width: 0 }, objectName: nm("Play circle") });
  slide.addShape(pres.ShapeType.triangle, { x: x + w / 2 - 0.13, y: cy + 0.23, w: 0.34, h: 0.34, rotate: 90, fill: { color: BG }, line: { color: BG, width: 0 }, objectName: nm("Play icon") });
  slide.addText(
    [
      { text: "VIDEO " + videoNo + "  ·  " + secs, options: { bold: true, color: ORANGE, fontSize: 16, breakLine: true } },
      { text: what, options: { color: TEXT, fontSize: 15, breakLine: true } },
      { text: "Insert › Video › This Device, lay it over this box, then delete the box", options: { color: MUTED, fontSize: 12 } },
    ],
    { isTextBox: true, x: x + 0.4, y: cy + 0.95, w: w - 0.8, h: 1.25, align: "center", valign: "top", margin: 0, paraSpaceAfter: 4, objectName: "Video placeholder " + videoNo + " text" },
  );
  return h;
}
function content(title, section) {
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: section });
  s.addText(title, { placeholder: "title" });
  return s;
}

// ---------- 1 cover ----------
pres.addSection({ title: "Problem" });
{
  const s = pres.addSlide({ masterName: "COVER", sectionTitle: "Problem" });
  // a few stars, and one object that has moved between two dates (the blink)
  const stars = [[8.6, 0.9, 0.05], [9.4, 2.1, 0.04], [10.3, 0.7, 0.07], [11.2, 1.6, 0.04], [12.3, 0.9, 0.05], [12.6, 2.6, 0.06], [8.9, 3.3, 0.06], [9.9, 4.6, 0.04], [12.1, 4.3, 0.05], [8.4, 5.4, 0.05], [9.3, 6.3, 0.07], [10.6, 5.9, 0.04], [11.6, 6.5, 0.05], [12.5, 5.7, 0.06], [7.9, 1.8, 0.04], [11.9, 3.2, 0.04], [1.2, 0.8, 0.04], [3.4, 1.2, 0.05], [5.6, 0.7, 0.04], [2.3, 6.3, 0.05], [5.1, 5.9, 0.04], [6.9, 6.6, 0.05]];
  for (const [x, y, d] of stars) {
    s.addShape(pres.ShapeType.ellipse, { x, y, w: d, h: d, fill: { color: MUTED }, line: { color: MUTED, width: 0 }, objectName: nm("Star") });
  }
  s.addShape(pres.ShapeType.ellipse, { x: 9.75, y: 3.2, w: 0.5, h: 0.5, fill: { color: BG }, line: { color: ORANGE, width: 1.5, dashType: "dash" }, objectName: "Object, first date" });
  s.addShape(pres.ShapeType.line, { x: 10.3, y: 3.3, w: 0.75, h: 0, rotate: -16, line: { color: ORANGE, width: 1.5, endArrowType: "triangle" }, objectName: "Motion arrow" });
  s.addShape(pres.ShapeType.ellipse, { x: 11.05, y: 2.82, w: 0.5, h: 0.5, fill: { color: ORANGE }, line: { color: ORANGE, width: 0 }, objectName: "Object, second date" });
  text(s, "May 2025", { x: 9.4, y: 3.8, w: 1.2, h: 0.3, fontSize: 12, color: MUTED, align: "center" });
  text(s, "Oct 2025", { x: 10.7, y: 3.42, w: 1.2, h: 0.3, fontSize: 12, color: MUTED, align: "center" });

  s.addText(NAME, { placeholder: "title" });
  s.addText("Many eyes on the infrared sky", { placeholder: "body" });
  text(s, "NASA Space Apps Challenge 2026  ·  Challenge “Planet X and SPHEREx”", { x: M, y: 5.6, w: 8, h: 0.35, fontSize: 16, color: TEXT });
  text(s, "Team: Joerg  ·  Jonathan  ·  Mati", { x: M, y: 6.0, w: 8, h: 0.35, fontSize: 16, color: MUTED });
  s.addNotes("Hello, we are Joerg, Jonathan and Mati. Our project lets anyone search the newest infrared map of the sky, and lets them do it together. (About 10 seconds, then move on.)");
}

// ---------- 2 every generation sees more ----------
{
  const s = content("Every telescope generation sees more", "Problem");
  const cards = [
    ["1983  ·  IRAS", "0.35", "4 infrared bands", "first infrared survey of the whole sky"],
    ["2010  ·  WISE", "750", "4 infrared bands", "sharper and far more sensitive"],
    ["2025  ·  SPHEREx", "1,000+", "102 infrared bands", "the whole sky, again every 6 months"],
  ];
  const cw = 3.85, gap = (CW - 3 * cw) / 2, y = 1.75, h = 3.85;
  cards.forEach(([head, num, bands, sub], i) => {
    const x = M + i * (cw + gap), last = i === 2;
    panel(s, x, y, cw, h, last ? { line: ORANGE, lineWidth: 2 } : {});
    text(s, head, { x: x + 0.35, y: y + 0.3, w: cw - 0.7, h: 0.35, fontSize: 16, bold: true, color: last ? ORANGE : MUTED });
    text(s, num, { x: x + 0.35, y: y + 0.75, w: cw - 0.7, h: 1.0, fontSize: 60, bold: true, color: last ? ORANGE : TEXT, fontFace: THEME.headFontFace, valign: "middle" });
    text(s, "million objects", { x: x + 0.35, y: y + 1.8, w: cw - 0.7, h: 0.35, fontSize: 16, color: MUTED });
    text(s, bands, { x: x + 0.35, y: y + 2.5, w: cw - 0.7, h: 0.4, fontSize: 22, bold: true });
    text(s, sub, { x: x + 0.35, y: y + 2.95, w: cw - 0.7, h: 0.6, fontSize: 15, color: MUTED });
  });
  text(s, "Each mission multiplies the data. The number of astronomers does not grow with it.", { x: M, y: 5.95, w: CW, h: 0.5, fontSize: 20, color: TEXT });
  s.addNotes("Infrared astronomy in three steps. IRAS in 1983: about 350 thousand sources in four bands. WISE in 2010: about 750 million objects, still four bands. SPHEREx, since 2025: more than a billion objects, in 102 bands, and it maps the whole sky again every six months. Sources: IRAS and AllWISE catalogue sizes (NASA/IPAC), SPHEREx figures from the challenge text. Check the IRAS and WISE numbers once more before presenting.");
}

// ---------- 3 more data, more gets missed ----------
{
  const s = content("More data means more gets missed", "Problem");
  const x = M, w = 6.3;
  row(s, 1, "Algorithms find what they were built to find", "Pipelines search for known kinds of objects with known signatures.", x, 1.85, w);
  row(s, 2, "The unusual falls through", "Objects that overlap, flicker or move a little look like noise to code.", x, 3.2, w);
  row(s, 3, "The gap grows with every data release", "A billion objects in 102 bands, renewed twice a year.", x, 4.55, w);
  const qx = 7.5, qw = W - M - qx;
  panel(s, qx, 1.75, qw, 4.3);
  text(s, "“", { x: qx + 0.4, y: 1.85, w: 1, h: 0.9, fontSize: 72, bold: true, color: ORANGE, fontFace: THEME.headFontFace });
  text(s, "There will be too much data for any one person or even computer code to completely comprehend.", { x: qx + 0.45, y: 2.85, w: qw - 0.9, h: 2.0, fontSize: 24, italic: true, color: TEXT });
  text(s, "NASA, challenge text “Planet X and SPHEREx”", { x: qx + 0.45, y: 5.2, w: qw - 0.9, h: 0.4, fontSize: 14, color: MUTED });
  s.addNotes("More data sounds like more discoveries. But software only finds what it was written to find. Things that overlap, change brightness or move slightly are sorted out as noise or artifacts. NASA says it in the challenge itself: too much data for any one person, or even computer code. So with every release, more goes unseen.");
}

// ---------- 4 human eyes ----------
{
  const s = content("Discoveries still need human eyes", "Problem");
  text(s, [
    { text: "SPHEREx needs volunteers.", options: { color: TEXT, breakLine: true } },
    { text: "Volunteers need a tool.", options: { color: ORANGE } },
  ], { x: M, y: 2.2, w: 5.9, h: 2.6, fontSize: 32, bold: true, fontFace: THEME.headFontFace, valign: "middle" });
  const x = 6.75, w = W - M - x;
  const cards = [
    ["1930", "Pluto is found by one astronomer who blinks between two photographs of the same patch of sky."],
    ["Today", "Most known comets and brown dwarfs were discovered by volunteers, hundreds of thousands of them, in projects like Backyard Worlds."],
  ];
  cards.forEach(([head, body], i) => {
    const y = 1.75 + i * 2.25;
    panel(s, x, y, w, 2.0);
    text(s, head, { x: x + 0.4, y: y + 0.3, w: 1.5, h: 0.5, fontSize: 28, bold: true, color: CYAN, fontFace: THEME.headFontFace });
    text(s, body, { x: x + 2.0, y: y + 0.3, w: w - 2.4, h: 1.4, fontSize: 17, color: TEXT, valign: "middle" });
  });
  text(s, "Source: NASA challenge text", { x, y: 6.3, w, h: 0.3, fontSize: 12, color: MUTED });
  s.addNotes("This is not new. Pluto was found in 1930 by a person flipping between two photographs. And today, most known comets and brown dwarfs were found by volunteers doing the same thing on a screen. People are very good at seeing what does not fit. But they need a tool that makes SPHEREx searchable. That is what we built.");
}

// ---------- 5 solution ----------
pres.addSection({ title: "Solution" });
{
  const s = content(NAME + ": the infrared sky for everyone", "Solution");
  const w = 4.75;
  text(s, "A public web tool on live SPHEREx data. Nothing to install, any position on the sky.", { x: M, y: 1.75, w, h: 1.2, fontSize: 20, color: TEXT });
  const pts = [["Pick", "a patch of sky"], ["Watch", "it change over time"], ["Read", "what it is made of"], ["Share", "what you found"]];
  pts.forEach(([a, b], i) => {
    text(s, [{ text: a + "  ", options: { bold: true, color: ORANGE } }, { text: b, options: { color: TEXT } }], { x: M, y: 3.2 + i * 0.62, w, h: 0.45, fontSize: 22 });
  });
  const vx = 5.75;
  video(s, vx, 1.75, W - M - vx, "Overview: from the whole sky down to one field, survey passes blinking", "15–20 s");
  s.addNotes("Our tool runs in the browser on the real SPHEREx data, fetched live from NASA's archive. Pick any patch of sky, watch how it changes between survey passes, read its chemistry, and share what you found. (Let the overview video play.)");
}

// ---------- 6 navigation ----------
{
  const s = content("Navigation anyone can use", "Solution");
  const vw = 6.6;
  video(s, M, 1.75, vw, "Zoom into the map, drag a region, blink between two dates", "15–20 s");
  const x = M + vw + 0.5, w = W - M - x;
  row(s, 1, "One map of the whole sky", "Zoom from the full sphere down to single SPHEREx pixels.", x, 1.8, w);
  row(s, 2, "Drag a rectangle", "The selected region is fetched and analysed, 5 to 210 arcminutes.", x, 3.0, w);
  row(s, 3, "Blink through time", "Flip, play or subtract the survey passes: what moved, what changed?", x, 4.2, w);
  text(s, "New here? A guided tour visits the five official test targets.", { x: x + 0.75, y: 5.35, w: w - 0.75, h: 0.4, fontSize: 15, color: CYAN });
  s.addNotes("Navigation works like an online map. Zoom from the whole sky down to single pixels. Drag a rectangle and that region is fetched and analysed. Then blink between survey passes, play them as a video or subtract them, and what moved or changed stands out. A guided tour shows newcomers the five official test targets.");
}

// ---------- 7 chemistry ----------
{
  const s = content("Chemistry filters that show where to look", "Solution");
  const w = 5.2;
  text(s, "Every molecule leaves its mark at known wavelengths. With 102 bands, SPHEREx can map it.", { x: M, y: 1.75, w, h: 0.9, fontSize: 20, color: TEXT });
  const chips = ["H₂O", "CO₂ ice", "CO ice", "CH₄", "PAH dust", "Hydrogen"];
  chips.forEach((c, i) => {
    const cx = M + (i % 3) * 1.75, cy = 2.95 + Math.floor(i / 3) * 0.62;
    s.addText(c, { shape: pres.ShapeType.roundRect, rectRadius: 0.2, x: cx, y: cy, w: 1.6, h: 0.45, fill: { color: i === 0 ? CYAN : PANEL }, line: { color: CYAN, width: 1 }, color: i === 0 ? BG : CYAN, bold: true, fontSize: 15, align: "center", valign: "middle", margin: 0, objectName: nm("Chip") });
  });
  const pts = [
    ["Overlay", "one feature or several as a colour layer on the map"],
    ["Presets", "for brown dwarfs, protostars, young stars, quasars"],
    ["Click", "any point for its full spectrum, made on the spot"],
  ];
  pts.forEach(([a, b], i) => {
    text(s, [{ text: a + "  ", options: { bold: true, color: ORANGE } }, { text: b, options: { color: TEXT } }], { x: M, y: 4.45 + i * 0.75, w, h: 0.65, fontSize: 17 });
  });
  const vx = 6.2;
  video(s, vx, 1.75, W - M - vx, "Switch on the water (H₂O) overlay, pick the brown dwarf preset, click a source for its spectrum", "20 s");
  s.addNotes("This is what only SPHEREx can do. Water, CO2, methane, hydrogen: each leaves its mark at known wavelengths. Switch on the water overlay and the map shows where water absorbs. Combine several features, or pick a preset: a brown dwarf, for example, is water plus methane. So a volunteer does not scan a billion dots, they filter for the kind of object they are looking for. A click on any point gives its spectrum.");
}

// ---------- 8 computer assisted ----------
{
  const s = content("The computer assists, the volunteer decides", "Solution");
  const cards = [
    ["Names the known", "Stars, asteroids and comets carry labels. What moves without a label stands out."],
    ["Ranks the unusual", "The sources of a field, sorted by how far they are from a plain star."],
    ["Marks what changes", "What appears, vanishes or brightens between passes; detector artifacts sorted out."],
    ["Measures motion", "Barnard’s Star: 10.46″ per year from SPHEREx alone. Gaia says 10.39."],
  ];
  const cw = 3.0, ch = 2.3, gap = 0.3;
  cards.forEach(([head, body], i) => {
    const x = M + (i % 2) * (cw + gap), y = 1.75 + Math.floor(i / 2) * (ch + gap);
    panel(s, x, y, cw, ch);
    text(s, head, { x: x + 0.3, y: y + 0.25, w: cw - 0.6, h: 0.45, fontSize: 20, bold: true, color: CYAN });
    text(s, body, { x: x + 0.3, y: y + 0.85, w: cw - 0.6, h: 1.2, fontSize: 14, color: TEXT });
  });
  const vx = M + 2 * cw + gap + 0.45;
  const vw = W - M - vx;
  const vh = (vw * 9) / 16;
  video(s, vx, 1.75 + (2 * ch + gap - vh) / 2, vw, "Switch on Labels and Unusual spectra, click a ringed source", "15 s");
  s.addNotes("The computer does the tedious part. It names everything that is already known, so the unlabelled things stand out. It ranks the sources of a field by how unusual their spectrum is. It marks what appears, vanishes or brightens. And it measures motion: for Barnard's Star we get 10.46 arcseconds per year from SPHEREx alone, Gaia says 10.39. But the tool claims no discoveries. The decision stays with the person.");
}

// ---------- 9 collaboration ----------
{
  const s = content("Volunteers work together", "Solution");
  const cards = [
    ["See what was searched", "Every map tile shows how often it was viewed. Go where nobody has looked yet."],
    ["Flag and discuss", "Pin “look here” on a cutout, comment and reply. Recent discussions across the sky."],
    ["Share by link", "Every view is a URL. Copy the link and others open exactly the same patch."],
  ];
  const cw = 3.85, gap = (CW - 3 * cw) / 2, y = 1.65, h = 1.75;
  cards.forEach(([head, body], i) => {
    const x = M + i * (cw + gap);
    panel(s, x, y, cw, h);
    badge(s, String(i + 1), x + 0.3, y + 0.25, 0.45);
    text(s, head, { x: x + 0.95, y: y + 0.25, w: cw - 1.05, h: 0.45, fontSize: 18, bold: true, valign: "middle" });
    text(s, body, { x: x + 0.3, y: y + 0.85, w: cw - 0.6, h: 0.8, fontSize: 14, color: MUTED });
  });
  const vy = 3.65, vw = 5.2;
  video(s, M, vy, vw, "Open a tile’s discussion, post a “look here” comment, copy the link", "20 s");
  const x = M + vw + 0.5, w = W - M - x;
  text(s, "One link, the same patch of sky for everyone", { x, y: vy + 0.15, w, h: 0.4, fontSize: 20, bold: true });
  panel(s, x, vy + 0.75, w, 0.8);
  text(s, "…/?ra=08h55m10.8s&dec=-7d14m42.5s&size=15", { x: x + 0.3, y: vy + 0.75, w: w - 0.6, h: 0.8, fontSize: 13, color: CYAN, fontFace: "Courier New", valign: "middle" });
  text(s, "Many eyes, no patch searched a hundred times while another is never seen.", { x, y: vy + 1.85, w, h: 0.9, fontSize: 17, color: MUTED });
  s.addNotes("Filters and computer help are half of it. The other half is working together. One: every tile of the map shows how often it has been viewed, so volunteers can go where nobody has looked. Two: found something odd? Pin a 'look here' on that spot and discuss it with others. Three: every view is a link. Copy it, send it, and the other person sees exactly the same patch of sky.");
}

// ---------- 10 close ----------
pres.addSection({ title: "Proof" });
{
  const s = content("Tested on real SPHEREx data", "Proof");
  const stats = [
    ["10.46″/yr", "Barnard’s Star", "its motion, measured from SPHEREx alone (Gaia: 10.39)"],
    ["19 of 19", "Asteroid (29) Amphitrite", "found at its predicted position in every exposure"],
    ["15×", "RW Aurigae", "brighter at 4–5 µm than a plain star: its dust disk"],
  ];
  const cw = 3.85, gap = (CW - 3 * cw) / 2, y = 1.75;
  stats.forEach(([num, head, body], i) => {
    const x = M + i * (cw + gap);
    text(s, num, { x, y, w: cw, h: 0.95, fontSize: 48, bold: true, color: ORANGE, fontFace: THEME.headFontFace, valign: "middle" });
    text(s, head, { x, y: y + 1.05, w: cw, h: 0.4, fontSize: 18, bold: true });
    text(s, body, { x, y: y + 1.48, w: cw - 0.2, h: 0.7, fontSize: 15, color: MUTED });
  });
  panel(s, M, 4.45, CW, 2.1, { line: ORANGE, lineWidth: 2 });
  text(s, "Open it, pick a patch of sky, find what the algorithms missed.", { x: M + 0.45, y: 4.7, w: CW - 0.9, h: 0.6, fontSize: 26, bold: true, fontFace: THEME.headFontFace, valign: "middle" });
  text(s, [
    { text: "Live tool  ", options: { color: MUTED } }, { text: "[live URL]", options: { color: CYAN, breakLine: true } },
    { text: "Code  ", options: { color: MUTED } }, { text: "github.com/jabra11/nasa-challenge", options: { color: CYAN } },
  ], { x: M + 0.45, y: 5.45, w: CW - 0.9, h: 0.85, fontSize: 17, paraSpaceAfter: 4 });
  s.addNotes("Does it work? Three checks on real data. We measure the motion of Barnard's Star from SPHEREx alone and land within one percent of Gaia. An asteroid appears exactly where its orbit says, in 19 of 19 exposures. And RW Aurigae shows its dust disk in the spectrum without being told. SPHEREx keeps sending data, and the tool picks up new releases by itself. So: open it, pick a patch of sky, and find what the algorithms missed. Thank you. (Replace [live URL] before presenting.)");
}

(async () => {
  await pres.writeFile({ fileName: OUT });
  if (process.env.PPTX_APPLY_THEME) {
    const { applyTheme } = require(process.env.PPTX_APPLY_THEME);
    await applyTheme(OUT, THEME);
  } else {
    console.warn("PPTX_APPLY_THEME not set: the deck keeps Office's stock theme colours.");
  }
  console.log("wrote", OUT);
})();

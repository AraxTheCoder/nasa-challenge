// T76: checks for web/discoveries.js. Run: node web/tests/discoveries_check.mjs
import { readFileSync } from "node:fs";
import { candidateAt, classLabel, displayName, filterCandidates, pickInteresting, sortCandidates, whyLine } from "../discoveries.js";

let fails = 0;
const check = (ok, msg) => { console.log(`${ok ? "PASS" : "FAIL"} ${msg}`); if (!ok) fails++; };

const L = [
  { id: "a", name: "Zeta", ra_deg: 10, dec_deg: 5, class: "mover", score: 0.4, reason: "r" },
  { id: "b", name: "alpha 10", ra_deg: 359.99995, dec_deg: -20, class: "brown_dwarf", score: 0.9, reason: "r" },
  { id: "c", name: "alpha 9", ra_deg: 200, dec_deg: 60, class: "variable", score: 0.4, reason: "r", known: "R Dra" },
  { id: "d", ra_deg: 120.5, dec_deg: -7.25, class: "spectral", score: 0.7, reason: "r" },
];
const ids = (l) => l.map((c) => c.id).join("");

check(ids(sortCandidates(L)) === "bdac", "by score, ties by id");
check(ids(sortCandidates(L, "class")) === "bcda", "by class: brown dwarf, variable, spectral, mover");
check(ids(sortCandidates(L, "name")) === "cbda" && ids(L) === "abcd", "by name (numeric: alpha 9 < alpha 10), input untouched");
check(ids(filterCandidates(L, "variable")) === "c" && filterCandidates(L, "all").length === 4 && filterCandidates(L, "").length === 4, "filter by class");
check(displayName(L[3]) === "RA 120.500° Dec −7.250°" && displayName(L[0]) === "Zeta", "position as the name when unnamed");
check(classLabel("brown_dwarf") === "Brown dwarf" && classLabel("new_thing") === "new_thing", "class labels");

// "Show me something interesting": better half (>= 3), never the shown one
const seen = new Set();
for (let k = 0; k < 40; k++) seen.add(pickInteresting(L, { rng: () => k / 40 }).id);
check([...seen].sort().join("") === "abd", "random from the top 3 of 4 (not the last of the tie by id)");
check(pickInteresting(L, { exclude: "b", rng: () => 0 }).id === "d", "skips the shown candidate");
check(pickInteresting([L[0]], { exclude: "a" }) === null && pickInteresting([]) === null, "nothing else: null");

check(candidateAt(L, "120.5", "-7.25")?.id === "d" && candidateAt(L, 120.501, -7.25) === null, "candidate at a typed position");
check(candidateAt(L, "0.00005", "-20")?.id === "b", "matches across RA 0/360");
check(candidateAt(L, "", "x") === null, "no position: none");

const w = whyLine(L[2], true);
check(w.head === "Variable · score 0.40 (hand-made sample)" && /Known object \(R Dra\)/.test(w.text), "why line: class, score, sample, known");
check(!/Known/.test(whyLine(L[0]).text) && !/sample/.test(whyLine(L[0]).head), "why line of an unknown survey candidate");

// The committed sample opens like the quick picks and passes these helpers
const sample = JSON.parse(readFileSync(new URL("../../fixtures/discoveries-sample.json", import.meta.url)));
const presets = ["../presets.json", "../discover.json"].flatMap((f) => JSON.parse(readFileSync(new URL(f, import.meta.url))).fields);
check(sample.synthetic === true && sample.candidates.length >= 5 &&
  sample.candidates.every((c) => presets.some((p) => p.ra_deg === c.ra_deg && p.dec_deg === c.dec_deg)),
  "sample: synthetic, every candidate at a quick pick's position");

if (fails) { console.log(`${fails} failed`); process.exit(1); }
console.log("all passed");

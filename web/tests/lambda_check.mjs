// T78: checks for web/lambda.js. Run: node web/tests/lambda_check.mjs
import { framesAt, nearestBand, parseLam } from "../lambda.js";

let fails = 0;
const check = (ok, msg) => { console.log(`${ok ? "PASS" : "FAIL"} ${msg}`); if (!ok) fails++; };

check(parseLam("2.17") === 2.17 && parseLam("2,17") === 2.17 && parseLam(" 2.17 µm ") === 2.17 && parseLam("2170 nm") === 2.17,
  "parses 2.17, 2,17, 2.17 µm and 2170 nm");
check(parseLam("abc") === null && parseLam("12") === null && parseLam("0.3") === null && parseLam("") === null,
  "rejects text and wavelengths outside 0.7-5.1 µm");

const waves = [0.75, 0.76, 1.0, 2.165, 2.2, 4.27, 4.3];
check(nearestBand(waves, 2.17) === 3 && nearestBand(waves, 4.28) === 5 && nearestBand([], 2) === -1, "nearest map band");

// frames like the multi-epoch test target: 3 epochs, detectors 2 (1.2-1.3 µm) and 3 (1.8-2.1 µm)
const F = [["f000", 1, 60790.0, 2, 1.200], ["f001", 1, 60790.5, 2, 1.230], ["f002", 1, 60791.0, 3, 1.800],
  ["f003", 1, 60792.0, 3, 1.830], ["f004", 2, 60970.0, 2, 1.210], ["f005", 2, 60970.5, 2, 1.300],
  ["f006", 2, 60971.0, 3, 1.820], ["f007", 3, 61150.5, 2, 1.235], ["f008", 3, 61151.0, 3, 2.100]]
  .map(([id, epoch, mjd, detector, wavelength_um]) => ({ id, epoch, mjd, detector, wavelength_um, bandwidth_um: 0.03 }));
let r = framesAt(F, 1.23);
check(r.a.id === "f001" && r.b.id === "f007" && r.matched && Math.abs(r.offB - 0.005) < 1e-9, "1.23 µm: A f001 (epoch 1), B f007 (epoch 3), matched");
r = framesAt(F, 1.82);
check(r.a.id === "f003" && r.b.id === "f006" && r.a.detector === 3 && r.b.detector === 3,
  "1.82 µm: same detector; epoch 3's closest (2.10 µm) is too far and skipped");
r = framesAt(F.filter((f) => f.epoch === 1), 1.2);
check(r.a.id === "f000" && r.b === null, "one epoch only: A, no B");
check(framesAt([], 2) === null, "no frames: null");

console.log(fails ? `${fails} failure(s)` : "all lambda checks passed");
process.exit(fails ? 1 : 0);

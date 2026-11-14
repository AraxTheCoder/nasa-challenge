// T63: checks for web/spectrum.js on synthetic spectra with known answers. Run: node web/tests/spectrum_check.mjs
import { analyse, fitBaseline, planckNu } from "../spectrum.js";

let fails = 0;
const check = (ok, msg) => { console.log(`${ok ? "PASS" : "FAIL"} ${msg}`); if (!ok) fails++; };

// SPHEREx-like sampling: 2 frames per detector band per epoch, wavelengths 0.75-5 µm
const UM = [0.8, 0.86, 1.0, 1.08, 1.3, 1.45, 1.7, 1.9, 2.2, 2.4, 2.9, 3.05, 3.4, 3.7, 4.0, 4.2, 4.5, 4.7];
let seed = 3;
const noise = () => { seed = (seed * 16807) % 2147483647; return (seed / 2147483647 - 0.5) * 0.04; }; // ±2 %
const star = (t, scale, extra = () => 1) => UM.map((um, i) => {
  const flux = scale * planckNu(um, t) * extra(um) * (1 + noise());
  return { frame_id: `f${i}`, epoch: 1, wavelength_um: um, flux_ujy: flux, err_ujy: 0.005 * flux, masked: false };
});

// 1. a plain 5,000 K star: right temperature, nothing flagged
const plain = star(5000, 1e9);
const fit = fitBaseline(plain.map((f) => ({ um: f.wavelength_um, flux: f.flux_ujy, err: f.err_ujy })));
check(fit && Math.abs(fit.t - 5000) / 5000 < 0.15 && !fit.poor, `plain star: fitted ${fit && Math.round(fit.t)} K ≈ 5000 K`);
const a1 = analyse(plain);
check(a1.regions.length === 0 && a1.poorEpochs.length === 0, "plain star: no deviations, no poor fit");

// 2. warm dust: a 4,000 K star plus a 700 K blackbody that dominates beyond 3 µm (young star with a disk)
const dusty = star(4000, 1e9, (um) => 1 + (60 * planckNu(um, 700)) / planckNu(um, 4000));
const a2 = analyse(dusty);
const up = a2.regions.find((r) => r.sign > 0);
check(up && up.umMin >= 2.8 && /warm dust/i.test(up.hint.text) && /More light/.test(up.hint.title),
  `warm dust: excess beyond 3 µm explained as dust or a cool source (${up ? up.hint.title : "none"})`);

// 3. water ice: 40 % absorption 2.95-3.15 µm on a 6,000 K star
const icy = star(6000, 1e9, (um) => (um >= 2.95 && um <= 3.15 ? 0.6 : 1));
const ice = analyse(icy.concat(icy.filter((f) => f.wavelength_um === 3.05).map((f) => ({ ...f, frame_id: "f99", wavelength_um: 3.0 }))));
const down = ice.regions.find((r) => r.sign < 0);
check(down && /H₂O ice/.test(down.hint.text), `ice dip near 3.05 µm named as water ice (${down ? down.hint.text.slice(0, 40) : "none"})`);

// 4. a single odd point is not a finding
const one = star(5000, 1e9);
one[15].flux_ujy *= 3;
check(analyse(one).regions.length === 0, "a single outlier point is ignored");

// 5. saturated short wavelengths: no baseline, says why
const sat = star(5000, 1e9).map((f) => (f.wavelength_um <= 2.5 ? { ...f, masked: true, flux_ujy: null } : f));
const a5 = analyse(sat);
check(a5.noFit && a5.saturated, "short wavelengths flagged: no baseline, marked as saturated");

// 6. variable between epochs: temperatures disagree, so no temperature is named in the hint
const ep2 = star(3000, 1e9, (um) => 1 + (60 * planckNu(um, 700)) / planckNu(um, 3000)).map((f) => ({ ...f, epoch: 2, frame_id: f.frame_id + "b" }));
const a6 = analyse(dusty.concat(ep2));
const r6 = a6.regions.find((r) => r.sign > 0);
check(r6 && r6.epochs.length === 2 && /plain star/.test(r6.hint.title), `variable: regions merged over epochs, no temperature named (${r6 && r6.hint.title})`);

console.log(fails ? `${fails} failure(s)` : "all spectrum checks passed");
process.exit(fails ? 1 : 0);

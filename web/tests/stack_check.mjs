// T59: checks for web/stack.js. Run: node web/tests/stack_check.mjs
import { NO_DATA, frameScale, shiftsAlong, shiftsForMotion, stackGroup, stackPixels } from "../stack.js";

let fails = 0;
const check = (ok, msg) => { console.log(`${ok ? "PASS" : "FAIL"} ${msg}`); if (!ok) fails++; };

const W = 64, H = 64;
let seed = 7;
const rnd = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
const gauss = () => Math.sqrt(-2 * Math.log(rnd() + 1e-12)) * Math.cos(2 * Math.PI * rnd());
/** A frame: sky 40 ± 8, a faint source of `amp` at (32, 32), no data where x < nodataX. */
function frame(amp, nodataX = 0) {
  const d = new Uint8ClampedArray(W * H * 4);
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const p = (y * W + x) * 4, r2 = (x - 32) ** 2 + (y - 32) ** 2;
    const v = 40 + 8 * gauss() + amp * Math.exp(-r2 / 2);
    d[p] = d[p + 1] = d[p + 2] = v;
    d[p + 3] = x < nodataX ? 0 : 255;
  }
  return d;
}
const at = (img, x, y) => img.data[(y * W + x) * 4];

const s = frameScale(frame(0));
check(Math.abs(s.med - 40) <= 1 && Math.abs(s.sigma - 8) < 1, `noise scale per frame (median ${s.med}, sigma ${s.sigma.toFixed(1)})`);

// a source at 1 sigma per frame: invisible in one frame, clear in a 16-frame stack (z ~ 4)
const one = stackPixels([frame(8)], W, H), many = stackPixels(Array.from({ length: 16 }, () => frame(8)), W, H);
const sky = (img) => { let t = 0; for (let x = 4; x < 60; x += 4) t += at(img, x, 5); return t / 14; };
check(at(many, 32, 32) - sky(many) > 2.5 * (at(one, 32, 32) - sky(one)) && Math.abs(sky(many) - sky(one)) < 12,
  `faint source grows with the stack, sky level stays (1 frame: +${at(one, 32, 32) - Math.round(sky(one))}, 16 frames: +${at(many, 32, 32) - Math.round(sky(many))})`);

const gaps = stackPixels([frame(0, 20), frame(0, 10)], W, H);
check([...gaps.data.slice((5 * W + 5) * 4, (5 * W + 5) * 4 + 3)].join() === NO_DATA.join() && gaps.n[5 * W + 15] === 1 && gaps.n[5 * W + 30] === 2,
  "no data only where no frame has data; counts per pixel");

// a frame whose left half has a higher sky (another frame edge / stray light): no step left in the stack
const stepped = frame(0);
for (let y = 0; y < H; y++) for (let x = 0; x < 32; x++) stepped[(y * W + x) * 4] += 30;
const flat = stackPixels([stepped, frame(0)], W, H);
const half = (x0) => { let t = 0, k = 0; for (let y = 8; y < 56; y += 2) for (let x = x0; x < x0 + 16; x += 2) { t += at(flat, x, y); k++; } return t / k; };
check(Math.abs(half(4) - half(44)) < 15, `background removed per frame: no step between halves (${half(4).toFixed(0)} vs ${half(44).toFixed(0)})`);

// shift-and-stack: a faint source moving 3 px per frame vanishes in a plain stack but adds up along its motion
const moving = (k, amp) => {
  const d = frame(0);
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const p = (y * W + x) * 4, r2 = (x - (14 + 3 * k)) ** 2 + (y - 32) ** 2;
    d[p] = Math.min(255, d[p] + amp * Math.exp(-r2 / 2));
  }
  return d;
};
const mv = Array.from({ length: 12 }, (_, k) => moving(k, 10));
const plain = stackPixels(mv, W, H), along = stackPixels(mv, W, H, mv.map((_, k) => ({ dx: 3 * k, dy: 0 })));
check(at(along, 14, 32) - sky(along) > 2 * Math.max(1, at(plain, 14, 32) - sky(plain)),
  `shift-and-stack: the mover adds up along its motion (plain +${at(plain, 14, 32) - Math.round(sky(plain))}, along +${at(along, 14, 32) - Math.round(sky(along))})`);
const fr = [{ id: "f0", mjd: 100.0 }, { id: "f1", mjd: 100.5 }, { id: "f2", mjd: 101.0 }];
const along2 = shiftsAlong(fr, [{ frame_id: "f1", x: 10, y: 5 }, { frame_id: "f2", x: 13, y: 9 }]);
check(along2.frames.map((f) => f.id).join() === "f1,f2" && along2.shifts[1].dx === 3 && along2.shifts[1].dy === 4,
  "shifts along an object's positions, relative to its first one");
const m = shiftsForMotion(fr, fr[0], 6.15, 90, 6.15);   // 1 px per hour toward the east (= -x)
check(Math.abs(m[1].dx + 12) < 1e-9 && Math.abs(m[1].dy) < 1e-9 && m[0].dx === 0,
  "guessed motion: 6.15″/h east is -1 px/h in x (12 px after 12 h)");

const F = [{ id: "a", epoch: 1, detector: 2 }, { id: "b", epoch: 1, detector: 5 }, { id: "c", epoch: 2, detector: 2 }];
check(stackGroup(F, F[0], "epoch").map((f) => f.id).join() === "a,b" && stackGroup(F, F[0], "detector").map((f) => f.id).join() === "a,c"
  && stackGroup(F, F[0], "off").length === 0, "groups: same epoch / same detector");

console.log(fails ? `${fails} failure(s)` : "all stack checks passed");
process.exit(fails ? 1 : 0);

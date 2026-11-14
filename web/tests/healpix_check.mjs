// node web/tests/healpix_check.mjs : compares web/healpix.js with astropy_healpix (healpix_ref.json)
import { readFileSync } from "node:fs";
import { ang2pix, nest2xyf, xyf2ang, xyf2nest } from "../healpix.js";

const ref = JSON.parse(readFileSync(new URL("./healpix_ref.json", import.meta.url)));
let bad = 0, n = 0;
for (const c of ref.cases) {
  c.pix.forEach((p, i) => {
    if (ref.dec[i] === 0 && ref.ra[i] % 45 === 0) return;   // exact base-cell vertex: ambiguous
    n++;
    const got = ang2pix(c.order, ref.ra[i], ref.dec[i]);
    if (got !== p) { bad++; if (bad < 6) console.log("ang2pix", c.order, ref.ra[i], ref.dec[i], got, p); }
    const { ix, iy, face } = nest2xyf(c.order, p);
    if (xyf2nest(c.order, ix, iy, face) !== p) bad++;
  });
}
const sep = (a, b, c, d) => {
  const r = Math.PI / 180;
  const x = Math.sin(((d - b) * r) / 2) ** 2 + Math.cos(b * r) * Math.cos(d * r) * Math.sin(((c - a) * r) / 2) ** 2;
  return (2 * Math.asin(Math.sqrt(x)) * 180 * 3600) / Math.PI;
};
let worst = 0;
for (const c of ref.corners) {
  // astropy dx moves along ix? try both conventions and report which matches
  const nside = 2 ** c.order;
  const { ix, iy, face } = nest2xyf(c.order, c.pix);
  const [ra, dec] = xyf2ang((ix + c.dx) / nside, (iy + c.dy) / nside, face);
  worst = Math.max(worst, sep(ra, dec, c.ra, c.dec));
}
console.log(`ang2pix/nest2xyf: ${n - bad}/${n} ok; tile grid points: worst ${worst.toExponential(2)}"`);
process.exit(bad || worst > 0.01 ? 1 : 0);

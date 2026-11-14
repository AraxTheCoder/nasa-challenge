// HEALPix NESTED geometry for drawing HiPS tiles (T36). No dependencies.
// Algorithms follow the HEALPix C++ library (healpix_base: loc2pix, xyf2loc). Checked against
// astropy_healpix by web/tests/healpix_check.mjs.

const JRLL = [2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4];
const JPLL = [1, 3, 5, 7, 0, 2, 4, 6, 1, 3, 5, 7];
const HALFPI = Math.PI / 2;
const DEG = Math.PI / 180;

/** Spread the low 16 bits of v to the even bit positions. */
function spread(v) {
  let r = 0;
  for (let b = 0; b < 26; b++) r += ((Math.floor(v / 2 ** b) % 2) * 2 ** (2 * b));
  return r;
}

/** Nested index from face and in-face ix, iy at nside = 2^order (ix -> even bits). */
export function xyf2nest(order, ix, iy, face) {
  return face * 4 ** order + spread(ix) + 2 * spread(iy);
}

/** Inverse of xyf2nest. */
export function nest2xyf(order, pix) {
  const npface = 4 ** order;
  const face = Math.floor(pix / npface);
  let p = pix - face * npface;
  let ix = 0, iy = 0;
  for (let b = 0; b < order; b++) {
    ix += (p % 2) * 2 ** b;
    p = Math.floor(p / 2);
    iy += (p % 2) * 2 ** b;
    p = Math.floor(p / 2);
  }
  return { ix, iy, face };
}

/** NESTED pixel index containing (ra, dec) in degrees, at nside = 2^order. */
export function ang2pix(order, raDeg, decDeg) {
  const nside = 2 ** order;
  const z = Math.sin(decDeg * DEG);
  const za = Math.abs(z);
  let phi = (raDeg * DEG) % (2 * Math.PI);
  if (phi < 0) phi += 2 * Math.PI;
  const tt = (phi / HALFPI) % 4;            // [0,4)
  let face, ix, iy;
  if (za <= 2 / 3) {
    const temp1 = nside * (0.5 + tt);
    const temp2 = nside * (z * 0.75);
    const jp = Math.floor(temp1 - temp2);  // ascending edge line
    const jm = Math.floor(temp1 + temp2);  // descending edge line
    const ifp = Math.floor(jp / nside);
    const ifm = Math.floor(jm / nside);
    face = ifp === ifm ? (ifp | 4) : ifp < ifm ? ifp : ifm + 8;
    ix = jm & (nside - 1);
    iy = nside - (jp & (nside - 1)) - 1;
  } else {
    const ntt = Math.min(3, Math.floor(tt));
    const tp = tt - ntt;
    const tmp = nside * Math.sqrt(3 * (1 - za));
    let jp = Math.floor(tp * tmp);
    let jm = Math.floor((1 - tp) * tmp);
    jp = Math.min(jp, nside - 1);
    jm = Math.min(jm, nside - 1);
    if (z >= 0) { face = ntt; ix = nside - jm - 1; iy = nside - jp - 1; }
    else { face = ntt + 8; ix = jp; iy = jm; }
  }
  return xyf2nest(order, ix, iy, face);
}

/** Sky position (deg) of continuous face coordinates x, y in [0,1] on a face. */
export function xyf2ang(x, y, face) {
  const jr = JRLL[face] - x - y;
  let nr, z;
  if (jr < 1) { nr = jr; z = 1 - (nr * nr) / 3; }
  else if (jr > 3) { nr = 4 - jr; z = (nr * nr) / 3 - 1; }
  else { nr = 1; z = ((2 - jr) * 2) / 3; }
  let tmp = JPLL[face] * nr + x - y;
  if (tmp < 0) tmp += 8;
  if (tmp >= 8) tmp -= 8;
  const phi = nr < 1e-15 ? 0 : (0.5 * HALFPI * tmp) / nr;
  return [phi / DEG, Math.asin(Math.max(-1, Math.min(1, z))) / DEG];
}

/** (n+1)^2 grid of sky positions over a tile, row-major in u (along ix) then v (along iy).
 *  Returns Float64Array [ra0, dec0, ra1, dec1, ...] and the texture coords that go with them. */
export function tileGrid(order, pix, n) {
  const nside = 2 ** order;
  const { ix, iy, face } = nest2xyf(order, pix);
  const pos = new Float64Array((n + 1) * (n + 1) * 2);
  let k = 0;
  for (let a = 0; a <= n; a++) {
    for (let b = 0; b <= n; b++) {
      const [ra, dec] = xyf2ang((ix + a / n) / nside, (iy + b / n) / nside, face);
      pos[k++] = ra;
      pos[k++] = dec;
    }
  }
  return pos;
}

/** Approximate angular size (deg) of a tile side at this order. */
export const tileSizeDeg = (order) => 58.6323 / 2 ** order;

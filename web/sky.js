// T36 Sky map: our own HiPS renderer (WebGL, no dependencies). Pan, zoom and pinch over the whole
// sky like Google Earth; a base map (SPHEREx all-sky HiPS or a comparison survey) plus overlay
// layers (our per-epoch SPHEREx HiPS, T32), of which one is shown at a time, so blinking is just a
// switch between already loaded textures.
//
// Geometry: HEALPix NESTED tiles (healpix.js), stereographic projection around the view centre
// (conformal, like Aladin's default), north up, east left. Dragging turns the sphere under the
// cursor. Zoomed out, the whole sky comes from each HiPS's Norder3/Allsky mosaic (one image).
// Tile texel (row, col) <-> sub-pixel ix (even bits) = row, iy = col.
//
//   const sky = createSky(container)
//   await sky.setBase(url) ; sky.setOverlays([{url, label, epoch}]) ; sky.showOverlay(i)
//   sky.goTo(ra, dec, fovDeg) ; sky.view() ; sky.on("change", fn) ; sky.addDrawHook(fn(ctx, proj))

import { ang2pix, nest2xyf, tileGrid } from "./healpix.js";

const DEG = Math.PI / 180;
const TEXEL_ARCSEC_ORDER0 = 412.2;        // HiPS texel size at order 0 (512 px tiles)
const MAX_FOV = 240;                      // stereographic shows more than a hemisphere
const BACK_COSC = -0.6;                   // don't draw beyond ~127 deg from the centre
const MIN_FOV = 1 / 60;                   // 1 arcmin
const MAX_TEXTURES = 200;           // 1 MB of GPU memory each
const MAX_PARALLEL_LOADS = 6;             // = what a browser opens per host over HTTP/1.1
const LOAD_TIMEOUT_MS = 45000;        // T101: a tile download without an answer for this long is given up and retried
const SLOW_LOAD_TIMEOUT_MS = 150000;  // ... live-rendered tiles (deep zoom, survey passes) are computed on request
const MAX_SLOW_LOADS = 4;                 // live-rendered tiles; leaves 2 connections for the rest
// T94: float rounding put the order-0 zoom limit at log2 = 1e-16 for ~20% of window widths / pixel ratios, and
// ceil() made that "wants 1": an exact boundary counts as the lower order
const ORDER_EPS = 1e-9;
const FAILED_RETRY_MS = 30000;            // T94: a tile that failed 5 times is asked again after this
const PRELOAD = 1e6;                      // prio >= PRELOAD: preload (other epochs, parent tiles)
const MAX_PRELOADS = 3;                   // preloads in flight at once, and only when nothing visible waits
// Preload tiers, in this order after every visible tile: parent (zoom out), ring around the view
// (pan), children of the centre (zoom in), other epochs (blink).
const PRE_PARENT = PRELOAD, PRE_RING = PRELOAD + 1e4, PRE_CHILD = PRELOAD + 2e4, PRE_EPOCH = PRELOAD + 3e4;
// T55: overlays with meta.eager (survey passes) are what the user waits for: right after the visible
// base tiles, before any preload, only at the order the view needs (within the layer's orders), and from
// one order before the layer starts (the tiles a zoom in at the centre would show).
const EAGER = PRELOAD / 2;

// ---------- HiPS layer ------------------------------------------------------------------------

async function readProperties(url) {
  const res = await fetch(`${url.replace(/\/$/, "")}/properties`);
  if (!res.ok) throw new Error(`${url}/properties: HTTP ${res.status}`);
  const props = {};
  for (const line of (await res.text()).split(/\r?\n/)) {
    const m = line.match(/^\s*([\w.]+)\s*=\s*(.*?)\s*$/);
    if (m) props[m[1]] = m[2];
  }
  return props;
}

class Layer {
  constructor(url, props, opts = {}) {
    this.url = url.replace(/\/$/, "");
    this.maxOrder = Number(props.hips_order ?? 3);
    this.minOrder = Math.max(0, Number(props.hips_order_min ?? 0));
    const formats = (props.hips_tile_format ?? "png").split(/\s+/);
    this.ext = formats.includes("png") ? "png" : formats.includes("jpeg") ? "jpg" : formats[0];
    this.depth = Number(props.hips_cube_depth ?? 1);
    // Cubes: start on the band the HiPS recommends (IRSA's SPHEREx cube: frames 50/51 are blank).
    this.slice = Math.min(this.depth - 1, opts.slice ?? Number(props.hips_cube_firstframe ?? 0));
    this.label = opts.label ?? props.obs_title ?? url;
    this.props = props;
    this.tiles = new Map();     // key -> {state: "loading"|"ok"|"missing", tex, used}
    // Our per-epoch field HiPS cover only the field: hips_initial_* describe it (size*2 = fov).
    if ((props.creator_did ?? "").startsWith("ivo://spherex-blink/") && props.hips_initial_fov) {
      this.region = { ra: Number(props.hips_initial_ra), dec: Number(props.hips_initial_dec),
        radius: Number(props.hips_initial_fov) / 2 * 0.75 };
    }
    // Orders a server renders on demand (our live deep zoom): slow, so only a few at a time.
    this.slowOrders = new Set((props.x_live_orders ?? "").split(/\s+/).filter(Boolean).map(Number));
  }
  /** T89: at the live orders a tile only depends on the detector (17 channels each), so all channels of a
   *  detector use its first slice: one download and one texture instead of 17. */
  sliceAt(order) {
    return this.slowOrders.has(order) ? Math.floor(Math.min(this.slice, 101) / 17) * 17 : this.slice;
  }
  tileUrl(order, pix) {
    const sl = this.sliceAt(order);
    const s = this.depth > 1 && sl > 0 ? `_${sl}` : "";
    return `${this.url}/Norder${order}/Dir${Math.floor(pix / 10000) * 10000}/Npix${pix}${s}.${this.ext}`;
  }
  key(order, pix) { return `${this.sliceAt(order)}/${order}/${pix}`; }
  allskyUrl() {
    const s = this.depth > 1 && this.slice > 0 ? `_${this.slice}` : "";
    return `${this.url}/Norder3/Allsky${s}.${this.ext}`;
  }
}

// ---------- WebGL ----------------------------------------------------------------------------

const VS = `attribute vec2 a_pos; attribute vec2 a_uv; varying vec2 v_uv;
void main() { v_uv = a_uv; gl_Position = vec4(a_pos, 0.0, 1.0); }`;
const FS = `precision mediump float; varying vec2 v_uv; uniform sampler2D u_tex; uniform float u_alpha;
void main() { vec4 c = texture2D(u_tex, v_uv); gl_FragColor = vec4(c.rgb, c.a * u_alpha); }`;

function makeGl(canvas) {
  const gl = canvas.getContext("webgl", { premultipliedAlpha: false, alpha: false, antialias: false });
  if (!gl) throw new Error("WebGL is not available in this browser");
  const sh = (type, src) => {
    const s = gl.createShader(type);
    gl.shaderSource(s, src);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
    return s;
  };
  const prog = gl.createProgram();
  gl.attachShader(prog, sh(gl.VERTEX_SHADER, VS));
  gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, FS));
  gl.linkProgram(prog);
  gl.useProgram(prog);
  const loc = { pos: gl.getAttribLocation(prog, "a_pos"), uv: gl.getAttribLocation(prog, "a_uv"),
    alpha: gl.getUniformLocation(prog, "u_alpha") };
  const posBuf = gl.createBuffer();
  const uvBuf = gl.createBuffer();
  gl.enable(gl.BLEND);
  gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
  return { gl, loc, posBuf, uvBuf };
}

// ---------- the map ---------------------------------------------------------------------------

export function createSky(container, { ra = 0, dec = 0, fov = 60 } = {}) {
  container.classList.add("sky");
  const canvas = document.createElement("canvas");
  canvas.className = "sky-gl";
  const over = document.createElement("canvas");
  over.className = "sky-overlay";
  container.append(canvas, over);
  const ctx2d = over.getContext("2d");
  const G = makeGl(canvas);
  const { gl } = G;

  const st = { ra, dec, fov, cam: null, w: 1, h: 1, dpr: 1, base: null, overlays: [], overlayCall: 0, shown: -1,
    dirty: true, loads: 0, queue: [], inflight: new Set(), rendering: false, hooks: [], frame: 0, errors: 0, debug: false, stats: null, listeners: { change: [], tiles: [] } };

  // ----- camera + projection -----
  // The camera is a rotation of the sphere, kept as an orthonormal frame: C (view centre), E
  // (screen left; "east" when north is up) and N (screen up). Dragging and zooming turn the whole
  // frame, so the grabbed sky point stays exactly under the cursor anywhere, also over the poles
  // (like Google Earth); the picture may roll there. northUp() / goTo() level it again.
  // Projection: stereographic around C (conformal).
  const vec = ([ra, dec]) => [Math.cos(dec * DEG) * Math.cos(ra * DEG), Math.cos(dec * DEG) * Math.sin(ra * DEG), Math.sin(dec * DEG)];
  const radec = ([x, y, z]) => [((Math.atan2(y, x) / DEG) % 360 + 360) % 360, Math.asin(Math.max(-1, Math.min(1, z))) / DEG];
  const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  const norm = (a) => { const l = Math.hypot(...a) || 1; return a.map((c) => c / l); };

  function setFrame(raDeg, decDeg) {                  // north up, east left
    const C = vec([raDeg, decDeg]);
    let N = [-Math.sin(decDeg * DEG) * Math.cos(raDeg * DEG), -Math.sin(decDeg * DEG) * Math.sin(raDeg * DEG), Math.cos(decDeg * DEG)];
    N = norm(N);
    st.cam = { C, N, E: cross(N, C) };
    syncCentre();
  }
  function syncCentre() { [st.ra, st.dec] = radec(st.cam.C); }

  // Screen px per unit of the projection plane: the view's half width covers fov/2.
  const R = () => (st.w / 2) / (2 * Math.tan((Math.min(st.fov, MAX_FOV) * DEG) / 4));
  function toScreen(raDeg, decDeg) {
    const p = vec([raDeg, decDeg]);
    const { C, E, N } = st.cam;
    const cosc = dot(p, C);
    const k = 2 / Math.max(1e-6, 1 + cosc);
    const r = R();
    return { x: st.w / 2 - k * dot(p, E) * r, y: st.h / 2 - k * dot(p, N) * r, front: cosc > BACK_COSC, cosc };
  }
  function fromScreen(px, py) {
    const r = R();
    const x = -(px - st.w / 2) / r, y = -(py - st.h / 2) / r;
    const rho = Math.hypot(x, y);
    if (rho < 1e-12) return [st.ra, st.dec];
    const c = 2 * Math.atan(rho / 2);
    if (Math.cos(c) <= BACK_COSC) return null;
    const { C, E, N } = st.cam, s = Math.sin(c) / rho;
    return radec(C.map((ci, i) => Math.cos(c) * ci + s * (x * E[i] + y * N[i])));
  }
  setFrame(ra, dec);
  const proj = { toScreen, fromScreen, view: () => api.view() };

  // ----- tiles -----
  function pickOrder(layer) {
    const arcsecPerPx = (st.fov * 3600) / (st.w * st.dpr);
    const k = Math.ceil(Math.log2(TEXEL_ARCSEC_ORDER0 / arcsecPerPx) - ORDER_EPS);
    // T55: while survey passes blink on top, the base map stops one order short (no slow live renders
    // competing with the passes'; it only shows where a pass has no data)
    const max = layer === st.base && st.baseCap != null ? Math.min(layer.maxOrder, st.baseCap) : layer.maxOrder;
    return Math.max(layer.minOrder, Math.min(max, k));
  }

  function visibleTiles(order) {
    const out = new Set();
    if (order <= 3) {
      const n = 12 * 4 ** order;
      for (let p = 0; p < n; p++) {
        const g = tileGrid(order, p, 2);
        for (let i = 0; i < g.length; i += 2) {
          const s = toScreen(g[i], g[i + 1]);
          if (s.front && s.x > -st.w * 0.2 && s.x < st.w * 1.2 && s.y > -st.h * 0.2 && s.y < st.h * 1.2) { out.add(p); break; }
        }
      }
      return [...out];
    }
    const step = 40;
    for (let y = -step; y <= st.h + step; y += step) {
      for (let x = -step; x <= st.w + step; x += step) {
        const s = fromScreen(Math.min(Math.max(x, 0), st.w), Math.min(Math.max(y, 0), st.h));
        if (s) out.add(ang2pix(order, s[0], s[1]));
      }
    }
    return [...out];
  }

  // T41: every render says which tiles it wants (t.want = frame) and how close to the centre they
  // are (prio, px); the queue loads the most central wanted tiles first and drops the stale ones,
  // so after a pan the browser's few connections go to what is on screen now.
  function request(layer, order, pix, prio = 1e9) {
    const k = layer.key(order, pix);
    let t = layer.tiles.get(k);
    if (t) {
      t.used = performance.now();
      // Priority is per frame: the first request in a frame sets it, later ones in the same frame
      // may only raise it (a tile visible last frame but only a preload now must drop back).
      if (t.want !== st.frame) t.prio = prio;
      else t.prio = Math.min(t.prio, prio);
      t.want = st.frame;
      return t;
    }
    t = { state: "queued", tex: null, used: performance.now(), want: st.frame, prio, key: k };
    layer.tiles.set(k, t);
    st.queue.push({ layer, order, pix, t });
    if (!st.rendering) pump();
    return t;
  }

  function requestAllsky(layer) {
    const k = `${layer.slice}/allsky`;
    let t = layer.tiles.get(k);
    if (t) { t.used = performance.now() + 1e9; t.want = st.frame; return t; }   // never evicted first
    t = { state: "queued", tex: null, used: performance.now() + 1e9, want: st.frame, prio: -1, key: k };
    layer.tiles.set(k, t);
    st.queue.push({ layer, url: layer.allskyUrl(), t });
    if (!st.rendering) pump();
    return t;
  }

  /** Zoomed out: all visible order-3 tiles from the Allsky mosaic, one texture, one draw call. */
  function drawAllsky(layer, t) {
    const cols = 27, rows = Math.ceil(768 / cols), n = 4;
    const pos = [], uv = [];
    for (const pix of visibleTiles(3)) {
      const g = tileGrid(3, pix, n);
      const sp = [];
      for (let i = 0; i < g.length; i += 2) sp.push(toScreen(g[i], g[i + 1]));
      const c0 = pix % cols, r0 = Math.floor(pix / cols);
      const vtx = (a, b) => {
        const s = sp[a * (n + 1) + b];
        pos.push((s.x / st.w) * 2 - 1, 1 - (s.y / st.h) * 2);
        uv.push((c0 + b / n) / cols, (r0 + a / n) / rows);
      };
      for (let a = 0; a < n; a++) {
        for (let b = 0; b < n; b++) {
          const q = [sp[a * (n + 1) + b], sp[(a + 1) * (n + 1) + b], sp[a * (n + 1) + b + 1], sp[(a + 1) * (n + 1) + b + 1]];
          if (q.some((p) => !p.front)) continue;
          vtx(a, b); vtx(a + 1, b); vtx(a, b + 1);
          vtx(a + 1, b); vtx(a + 1, b + 1); vtx(a, b + 1);
        }
      }
    }
    drawTriangles(t.tex, pos, uv);
  }

  function drawTriangles(tex, pos, uv) {
    if (!pos.length) return;
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.bindBuffer(gl.ARRAY_BUFFER, G.posBuf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(pos), gl.STREAM_DRAW);
    gl.enableVertexAttribArray(G.loc.pos);
    gl.vertexAttribPointer(G.loc.pos, 2, gl.FLOAT, false, 0, 0);
    gl.bindBuffer(gl.ARRAY_BUFFER, G.uvBuf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(uv), gl.STREAM_DRAW);
    gl.enableVertexAttribArray(G.loc.uv);
    gl.vertexAttribPointer(G.loc.uv, 2, gl.FLOAT, false, 0, 0);
    gl.drawArrays(gl.TRIANGLES, 0, pos.length / 2);
  }

  /** After each frame: only what this frame shows may wait or download. Everything else is taken
   *  out of the queue, its download aborted (frees the connection), and asked again if it comes
   *  back on screen. */
  function prune() {
    st.queue = st.queue.filter((j) => {
      if (j.t.want === st.frame) return true;
      if (j.t.state === "queued") j.layer.tiles.delete(j.t.key);
      return false;
    });
    for (const job of st.inflight) if (job.t.want !== st.frame) job.ctrl.abort();
  }

  // Order of work: visible tiles first (centre outwards), preloads only when no visible tile is
  // waiting and at most MAX_PRELOADS at a time. A waiting visible tile pre-empts a preload download.
  function pump() {
    st.queue = st.queue.filter((j) => j.t.state === "queued");
    st.queue.sort((a, b) => b.t.prio - a.t.prio);           // pop() takes the smallest prio (centre)
    const isPre = (j) => j.t.prio >= PRELOAD;
    const count = (f) => { let n = 0; for (const j of st.inflight) if (f(j)) n++; return n; };
    const skipped = [];
    while (st.loads < MAX_PARALLEL_LOADS && st.queue.length) {
      const job = st.queue.pop();
      if (job.t.state !== "queued") continue;
      job.slow = job.order != null && job.layer.slowOrders.has(job.order);
      const visibleWaiting = st.queue.some((j) => !isPre(j)) || skipped.some((j) => !isPre(j));
      if ((job.slow && count((j) => j.slow) >= MAX_SLOW_LOADS)
          || (isPre(job) && (visibleWaiting || count(isPre) >= MAX_PRELOADS))) {
        skipped.push(job);
        continue;
      }
      job.t.state = "loading";
      st.loads++;
      load(job);
    }
    if (skipped.length) st.queue.push(...skipped.reverse());
    // Pre-empt: a visible tile can't start because connections are busy with preloads -> abort one
    // preload (it is asked again on a later frame, after the visible tiles).
    const blocked = st.queue.filter((j) => !isPre(j));
    if (blocked.length && st.loads >= MAX_PARALLEL_LOADS) {
      for (const j of st.inflight) {
        if (isPre(j)) { j.preempted = true; j.ctrl.abort(); break; }
      }
    }
  }

  // Tiles come via fetch() so we see the HTTP status: 404 = no tile there (final), anything else
  // (timeout, 502/503 from a busy upstream) is retried with back-off instead of being given up.
  async function load(job) {
    const t = job.t;
    job.ctrl = new AbortController();
    job.timedOut = false;
    // T101: fetch never gives up by itself: after a server crash or a dropped connection the download would
    // keep its slot for good (all slots taken = no tile until a reload). Live renders may take a while.
    const limit = setTimeout(() => { job.timedOut = true; job.ctrl.abort(); }, job.slow ? SLOW_LOAD_TIMEOUT_MS : LOAD_TIMEOUT_MS);
    st.inflight.add(job);
    try {
      const res = await fetch(job.url ?? job.layer.tileUrl(job.order, job.pix), { signal: job.ctrl.signal });
      if (res.status === 404) { t.state = "missing"; return; }
      if (res.status === 503) {                 // server not ready yet (e.g. index being built)
        const wait = Math.min(60, Number(res.headers.get("Retry-After")) || 20);
        t.state = "retry";
        setTimeout(() => { if (t.state === "retry") { t.state = "queued"; st.queue.push(job); pump(); markDirty(); } },
          wait * 1000);
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const bmp = await createImageBitmap(await res.blob());
      const tex = gl.createTexture();
      gl.bindTexture(gl.TEXTURE_2D, tex);
      gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, bmp);
      bmp.close?.();
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      t.tex = tex;
      t.state = "ok";
      evict();
      markDirty();
    } catch (e) {
      if (e.name === "AbortError" && !job.timedOut) {   // left the screen: forget it, asked again if it comes back
        t.state = "aborted";
        job.layer.tiles.delete(t.key);
        if (job.preempted) markDirty();          // a preload made room: ask for it again next frame
        return;
      }
      t.tries = (t.tries ?? 0) + 1;
      st.errors++;
      if (t.tries >= 5) {
        // T94: not given up for good (a restarted or briefly busy server left holes until a reload): after a
        // pause the tile is forgotten, so the next frame that still shows it asks again from scratch
        t.state = "failed";
        t.error = job.timedOut ? "no answer in time" : String(e.message ?? e);
        setTimeout(() => {
          if (t.state === "failed" && job.layer.tiles.get(t.key) === t) { job.layer.tiles.delete(t.key); markDirty(); }
        }, FAILED_RETRY_MS);
      }
      else {
        t.state = "retry";
        setTimeout(() => { if (t.state === "retry") { t.state = "queued"; st.queue.push(job); pump(); markDirty(); } },
          500 * 2 ** t.tries);
      }
    } finally {
      clearTimeout(limit);
      st.inflight.delete(job);
      st.loads--;
      pump();
    }
  }

  function evict() {
    const all = [];
    for (const layer of [st.base, ...st.overlays]) {
      if (!layer) continue;
      for (const [k, t] of layer.tiles) if (t.tex) all.push([t.used, layer, k, t]);
    }
    if (all.length <= MAX_TEXTURES) return;
    all.sort((a, b) => a[0] - b[0]);
    for (const [, layer, k, t] of all.slice(0, all.length - MAX_TEXTURES)) {
      gl.deleteTexture(t.tex);
      layer.tiles.delete(k);
    }
  }

  /** Texture to draw for a tile: its own, or the nearest loaded ancestor with a sub-rectangle. */
  function textureFor(layer, order, pix, prio) {
    const own = request(layer, order, pix, prio);
    if (order - 1 >= layer.minOrder) request(layer, order - 1, Math.floor(pix / 4), PRE_PARENT + prio);
    if (own.state === "ok") return { tex: own.tex, d: 0, aOff: 0, bOff: 0 };
    const { ix, iy } = nest2xyf(order, pix);
    for (let d = 1; order - d >= layer.minOrder; d++) {
      const anc = layer.tiles.get(layer.key(order - d, Math.floor(pix / 4 ** d)));
      if (anc?.state === "ok") {
        const m = 2 ** d;
        return { tex: anc.tex, d, aOff: ix % m, bOff: iy % m };
      }
    }
    return null;
  }

  function drawLayer(layer, alpha) {
    if (!layer) return;
    const order = pickOrder(layer);
    gl.uniform1f(G.loc.alpha, alpha);
    // The base overview stays underneath at every zoom. Overlay layers are small fields and
    // have no Allsky endpoint; their transparent pixels must keep revealing the base sky.
    const all = layer === st.base || order <= 3 ? requestAllsky(layer) : null;
    if (order <= 3 && all?.state === "ok") drawAllsky(layer, all);
    const n = order <= 4 ? 8 : 4;
    // Debug stats describe the layer on top: the shown overlay (a survey pass, a field epoch) is drawn after
    // the base and overwrites the base's; the base is named as capped when it stops short for the passes.
    const isTop = layer === st.base || layer === st.overlays[st.shown];
    const name = layer !== st.base ? layer.label
      : st.baseCap != null && layer.maxOrder > st.baseCap ? `base map (capped at ${st.baseCap}: overlays load first)` : "base map";
    const stats = isTop ? { name, order, wanted: wantedOrder(), maxOrder: layer.maxOrder, visible: 0, sharp: 0,
      blurry: 0, empty: 0, outlines: [] } : null;
    const shownTiles = [];
    for (const pix of tilesFor(layer, order)) {
      const g = tileGrid(order, pix, n);
      const sp = [];
      for (let i = 0; i < g.length; i += 2) sp.push(toScreen(g[i], g[i + 1]));
      const mid = sp[Math.floor(sp.length / 2)];
      shownTiles.push([pix, Math.hypot(mid.x - st.w / 2, mid.y - st.h / 2)]);
      // At deep zoom an order-3 tile's coarse mesh can miss the entire viewport. Use the
      // detailed tile's mesh and the matching sub-rectangle of its order-3 Allsky atlas cell.
      let overview = null;
      if (order > 3 && all?.state === "ok") {
        const d = order - 3, m = 2 ** d, parent = Math.floor(pix / 4 ** d);
        const { ix, iy } = nest2xyf(order, pix);
        overview = { tex: all.tex, d, aOff: ix % m, bOff: iy % m,
          atlasCol: parent % 27, atlasRow: Math.floor(parent / 27), atlasCols: 27, atlasRows: 29 };
        drawTile(overview, sp, n);
      }
      const tx = textureFor(layer, order, pix, Math.hypot(mid.x - st.w / 2, mid.y - st.h / 2));
      if (stats) {
        stats.visible++;
        const own = layer.tiles.get(layer.key(order, pix));
        const kind = tx && tx.d === 0 ? "sharp" : tx || overview ? "blurry" : "empty";
        stats[kind]++;
        if (st.debug) {
          const edge = [];
          for (let b = 0; b <= n; b++) edge.push(sp[b]);
          for (let a = 1; a <= n; a++) edge.push(sp[a * (n + 1) + n]);
          for (let b = n - 1; b >= 0; b--) edge.push(sp[n * (n + 1) + b]);
          for (let a = n - 1; a >= 1; a--) edge.push(sp[a * (n + 1)]);
          stats.outlines.push({ kind, state: own?.state, tries: own?.tries ?? 0, edge, mid, pix });
        }
      }
      if (!tx) continue;
      // A loaded tile may have holes (alpha 0: edge of the source image, masked pixels). Draw the
      // nearest loaded coarser tile underneath, so holes show lower-resolution sky, not black.
      if (tx.d === 0 && order > layer.minOrder) {
        const under = ancestorFor(layer, order, pix);
        if (under) drawTile(under, sp, n);
      }
      drawTile(tx, sp, n);
    }
    if (stats) st.stats = stats;
    if (layer === st.base) preloadAround(layer, order, shownTiles);
  }

  /** Preload what the next move will need: a ring of tiles just outside the view (pan) and the
   *  children of the central tiles (zoom in). Lower priority than anything visible. */
  function preloadAround(layer, order, shown) {
    const seen = new Set(shown.map(([p]) => p));
    for (const [pix, d] of ringTiles(order, seen)) request(layer, order, pix, PRE_RING + d);
    if (order + 1 <= layer.maxOrder) {
      const central = [...shown].sort((a, b) => a[1] - b[1]).slice(0, 4);
      for (const [pix, d] of central) {
        for (let c = 0; c < 4; c++) request(layer, order + 1, pix * 4 + c, PRE_CHILD + d);
      }
    }
  }

  /** Tiles in a band one tile wide just outside the screen, with their distance from the centre. */
  function ringTiles(order, exclude) {
    const out = new Map();
    const tilePx = Math.max(64, Math.min(600, (58.6323 / 2 ** order) * DEG * R()));
    const step = 40;
    for (let y = -tilePx; y <= st.h + tilePx; y += step) {
      for (let x = -tilePx; x <= st.w + tilePx; x += step) {
        if (x >= 0 && x <= st.w && y >= 0 && y <= st.h) continue;       // inside: visible already
        const sky = fromScreen(x, y);
        if (!sky) continue;
        const pix = ang2pix(order, sky[0], sky[1]);
        if (!exclude.has(pix) && !out.has(pix)) out.set(pix, Math.hypot(x - st.w / 2, y - st.h / 2));
      }
    }
    return out;
  }

  function ancestorFor(layer, order, pix) {
    const { ix, iy } = nest2xyf(order, pix);
    for (let d = 1; order - d >= layer.minOrder; d++) {
      const anc = layer.tiles.get(layer.key(order - d, Math.floor(pix / 4 ** d)));
      if (anc?.state === "ok") { const m = 2 ** d; return { tex: anc.tex, d, aOff: ix % m, bOff: iy % m }; }
    }
    return null;
  }

  function drawTile(tx, sp, n) {
    {
      const pos = [], uv = [];
      const m = 2 ** tx.d;
      const vtx = (a, b) => {
        const s = sp[a * (n + 1) + b];
        pos.push((s.x / st.w) * 2 - 1, 1 - (s.y / st.h) * 2);
        const u = (tx.bOff + b / n) / m, v = (tx.aOff + a / n) / m;
        // s <- iy (col), t <- ix (row); an Allsky texture packs 768 order-3 cells in 27 columns.
        uv.push((u + (tx.atlasCol ?? 0)) / (tx.atlasCols ?? 1),
          (v + (tx.atlasRow ?? 0)) / (tx.atlasRows ?? 1));
      };
      for (let a = 0; a < n; a++) {
        for (let b = 0; b < n; b++) {
          const q = [sp[a * (n + 1) + b], sp[(a + 1) * (n + 1) + b], sp[a * (n + 1) + b + 1], sp[(a + 1) * (n + 1) + b + 1]];
          if (q.some((s) => !s.front)) continue;
          vtx(a, b); vtx(a + 1, b); vtx(a, b + 1);
          vtx(a + 1, b); vtx(a + 1, b + 1); vtx(a, b + 1);
        }
      }
      drawTriangles(tx.tex, pos, uv);
    }
  }

  /** T94: zoomed out at most until the screen wants HiPS order 0 (one order-0 texel per device pixel): further
   *  out it would want order -1, which no map has. Never more than MAX_FOV. */
  function maxFov() {
    return Math.min(MAX_FOV, (TEXEL_ARCSEC_ORDER0 * st.w * st.dpr) / 3600);
  }

  /** Order the screen would need for 1 texel per device pixel (may exceed what the map has). */
  function wantedOrder() {
    const arcsecPerPx = (st.fov * 3600) / (st.w * st.dpr);
    return Math.ceil(Math.log2(TEXEL_ARCSEC_ORDER0 / arcsecPerPx) - ORDER_EPS);
  }

  // ----- debug overlay (toggle): tile outlines + zoom/loading state -----
  const KIND_COLOUR = { sharp: "rgba(80,220,120,0.9)", blurry: "rgba(255,200,60,0.9)", empty: "rgba(255,90,90,0.9)" };
  function drawDebug(ctx) {
    const s = st.stats;
    if (!s) return;
    ctx.save();
    ctx.lineWidth = 1;
    ctx.font = "11px monospace";
    for (const o of s.outlines) {
      ctx.strokeStyle = KIND_COLOUR[o.kind];
      ctx.beginPath();
      o.edge.forEach((p, i) => (i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y)));
      ctx.closePath();
      ctx.stroke();
      if (o.mid.front) {
        ctx.fillStyle = KIND_COLOUR[o.kind];
        ctx.fillText(`${s.order}/${o.pix} ${o.state ?? "-"}${o.tries ? ` x${o.tries}` : ""}`, o.mid.x - 40, o.mid.y);
      }
    }
    const texel = TEXEL_ARCSEC_ORDER0 / 2 ** s.order;
    const screen = (st.fov * 3600) / (st.w * st.dpr);
    const atMax = s.wanted > s.maxOrder;
    const allSharp = s.visible > 0 && s.sharp > 0 && s.sharp + s.empty === s.visible;
    const noData = s.visible > 0 && s.empty === s.visible;
    const lines = [
      `${s.name}: order ${s.order} of max ${s.maxOrder}  (screen wants ${s.wanted})`,
      `texel ${texel.toFixed(1)}"  screen px ${screen.toFixed(2)}"`,
      atMax ? "MAX ZOOM: the map has no finer tiles here" : "more detail available when zooming in",
      noData ? "NO DATA: no visible tile has data here (blank band or not loaded yet)"
        : allSharp ? "SHARP: all visible tiles at this order loaded" : `loading: ${s.sharp}/${s.visible} sharp, ${s.blurry} blurry, ${s.empty} empty`,
      `in flight ${st.loads} (${[...st.inflight].filter((j) => j.slow).length} live, ${[...st.inflight].filter((j) => j.t.prio >= PRELOAD).length} preload), `
        + `queued ${st.queue.filter((j) => j.t.prio < PRELOAD).length} visible + ${st.queue.filter((j) => j.t.prio >= PRELOAD).length} preload, errors ${st.errors}`,
    ];
    const w = Math.max(330, ...lines.map((l) => ctx.measureText(l).width + 14)), h = 14 * lines.length + 10;
    ctx.fillStyle = "rgba(0,0,0,0.7)";
    ctx.fillRect(8, 8, w, h);
    lines.forEach((l, i) => {
      ctx.fillStyle = i === 2 && atMax ? "#ff9a6c" : i === 3 && noData ? "#ff6b6b" : i === 3 && allSharp ? "#7fe38a" : "#e8eef7";
      ctx.fillText(l, 14, 22 + 14 * i);
    });
    ctx.restore();
  }

  function render() {
    st.dirty = false;
    st.frame++;
    st.rendering = true;
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.clearColor(0.02, 0.03, 0.06, 1);
    gl.clear(gl.COLOR_BUFFER_BIT);
    drawLayer(st.base, 1);
    st.overlays.forEach((l, i) => {
      // T94: an overlay that starts at a deep order (survey passes: 6) has nothing at a much coarser view;
      // drawing it there asked for its first order over the whole sky (233 tiles queued at "screen wants -1")
      if (wantedOrder() < l.minOrder - 1) return;
      if (i === st.shown) drawLayer(l, 1);
      else prefetch(l);                 // keep the other epochs loaded, so a switch is instant
    });
    ctx2d.setTransform(st.dpr, 0, 0, st.dpr, 0, 0);
    ctx2d.clearRect(0, 0, st.w, st.h);
    for (const hook of st.hooks) {
      try { hook(ctx2d, proj); } catch (e) { console.error(e); }
    }
    st.rendering = false;
    prune();
    pump();
    if (st.debug) drawDebug(ctx2d);
    st.listeners.tiles.forEach((fn) => fn(api.stats()));
  }

  /** Other epochs (blink): their tiles on screen inside their field, after the shown ones. */
  function prefetch(layer) {
    if (layer.meta?.eager) {
      const k = eagerOrder(layer);
      for (const [pix, d] of sharpTiles(k)) request(layer, k, pix, EAGER + d);
      return;
    }
    const order = pickOrder(layer);
    for (const pix of tilesFor(layer, order)) request(layer, order, pix, PRE_EPOCH);
  }

  /** Visible tiles of a layer; a layer with a known region (our per-epoch field HiPS) only those
   *  that touch it, so blinking never asks for tiles outside the red box. */
  function tilesFor(layer, order) {
    const all = visibleTiles(order);
    if (!layer.region) return all;
    const { ra, dec, radius } = layer.region;
    const reach = radius + 1.2 * 58.6323 / 2 ** order;     // field radius + tile half-diagonal
    return all.filter((pix) => {
      const g = tileGrid(order, pix, 1);
      const c = [(g[0] + g[6]) / 2, (g[1] + g[7]) / 2];
      const d = Math.acos(Math.min(1, Math.sin(c[1] * DEG) * Math.sin(dec * DEG)
        + Math.cos(c[1] * DEG) * Math.cos(dec * DEG) * Math.cos((c[0] - ra) * DEG))) / DEG;
      return d < reach;
    });
  }

  /** T55: the order an eager overlay is loaded at: the one the view wants, within the layer's orders. */
  function eagerOrder(layer) {
    return Math.max(layer.minOrder, Math.min(layer.maxOrder, wantedOrder()));
  }

  /** T55: tiles of order k an eager overlay needs, with their distance (px) from the centre: the
   *  visible ones once the view shows order k; one order short of it, those a zoom in to order k
   *  at the centre would show (loaded ahead); further out, none. */
  function sharpTiles(k) {
    const want = wantedOrder();
    if (want < k - 1) return [];
    const f = want >= k ? 1 : Math.min(1, api.fovForOrder(k) / st.fov);
    const w = st.w * f, h = st.h * f, x0 = (st.w - w) / 2, y0 = (st.h - h) / 2;
    const out = new Map(), step = Math.max(8, 40 * f);
    for (let y = 0; y <= h + 0.5; y += step) {
      for (let x = 0; x <= w + 0.5; x += step) {
        const px = x0 + Math.min(x, w), py = y0 + Math.min(y, h);
        const sp = fromScreen(px, py);
        if (!sp) continue;
        const pix = ang2pix(k, sp[0], sp[1]), d = Math.hypot(px - st.w / 2, py - st.h / 2);
        if (!out.has(pix) || out.get(pix) > d) out.set(pix, d);
      }
    }
    return [...out];
  }

  function markDirty() {
    if (st.dirty) return;
    st.dirty = true;
    requestAnimationFrame(render);
  }

  function changed() {
    markDirty();
    st.listeners.change.forEach((fn) => fn(api.view()));
  }

  // ----- size -----
  function resize() {
    const r = container.getBoundingClientRect();
    st.dpr = window.devicePixelRatio || 1;
    st.w = Math.max(1, r.width);
    st.h = Math.max(1, r.height);
    for (const c of [canvas, over]) {
      c.width = Math.round(st.w * st.dpr);
      c.height = Math.round(st.h * st.dpr);
    }
    st.fov = Math.min(st.fov, maxFov());   // T94: a smaller window must not leave it below order 0
    st.dirty = false;
    markDirty();
  }
  new ResizeObserver(resize).observe(container);

  // ----- interaction: drag, wheel, pinch, double click, keys -----
  const pointers = new Map();
  let pinch = null;
  const rel = (e) => { const r = canvas.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };

  // ----- navigation = turning the camera frame (no RA/Dec steps: poles behave like anywhere) -----

  /** Turn the camera by the rotation that carries sky point b onto sky point a. Then what was
   *  under b's screen position shows a. */
  function rotateCentre(a, b) {
    const k = cross(b, a);
    const sin = Math.hypot(...k), cos = dot(a, b);
    if (sin < 1e-12) return;
    const u = k.map((c) => c / sin);
    const rot = (v) => { const ud = dot(u, v), uxv = cross(u, v); return v.map((vi, i) => vi * cos + uxv[i] * sin + u[i] * ud * (1 - cos)); };
    const C = norm(rot(st.cam.C));
    let N = rot(st.cam.N);
    N = norm(N.map((ni, i) => ni - dot(N, C) * C[i]));              // keep the frame orthonormal
    st.cam = { C, N, E: cross(N, C) };
    syncCentre();
  }

  /** Drag: the sky point under `from` ends up under `to` (grab-and-turn, works over the poles). */
  function dragTo(from, to) {
    const a = fromScreen(from[0], from[1]), b = fromScreen(to[0], to[1]);
    if (!a || !b) return;
    rotateCentre(vec(a), vec(b));
    changed();
  }

  /** Move the content by (dx, dy) px, anchored at the screen centre (keys). */
  function panBy(dx, dy) { dragTo([st.w / 2, st.h / 2], [st.w / 2 + dx, st.h / 2 + dy]); }

  /** Zoom by factor, keeping the sky point under (px, py) in place. */
  function zoomAt(factor, px, py) {
    const before = fromScreen(px, py);
    st.fov = Math.max(MIN_FOV, Math.min(maxFov(), st.fov * factor));
    const after = fromScreen(px, py);
    if (before && after) rotateCentre(vec(before), vec(after));
    changed();
  }

  over.style.pointerEvents = "none";
  canvas.style.touchAction = "none";
  canvas.addEventListener("pointerdown", (e) => {
    canvas.setPointerCapture(e.pointerId);
    pointers.set(e.pointerId, rel(e));
    if (pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      pinch = { d: Math.hypot(a[0] - b[0], a[1] - b[1]) };
    }
  });
  canvas.addEventListener("pointermove", (e) => {
    if (!pointers.has(e.pointerId)) {
      const p = fromScreen(...rel(e));
      st.listeners.change.forEach((fn) => fn(api.view(), p));
      return;
    }
    const prev = pointers.get(e.pointerId), now = rel(e);
    pointers.set(e.pointerId, now);
    if (pointers.size === 1) dragTo(prev, now);
    else if (pinch && pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      const d = Math.hypot(a[0] - b[0], a[1] - b[1]);
      const mid = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
      if (pinch.mid) dragTo(pinch.mid, mid);           // two fingers move the map as well
      if (d > 0) zoomAt(pinch.d / d, mid[0], mid[1]);
      pinch.d = d;
      pinch.mid = mid;
    }
  });
  const up = (e) => { pointers.delete(e.pointerId); if (pointers.size < 2) pinch = null; };
  canvas.addEventListener("pointerup", up);
  canvas.addEventListener("pointercancel", up);
  canvas.addEventListener("wheel", (e) => {
    e.preventDefault();
    const [x, y] = rel(e);
    zoomAt(Math.exp(e.deltaY * (e.deltaMode === 1 ? 0.05 : 0.0015)), x, y);
  }, { passive: false });
  canvas.addEventListener("dblclick", (e) => zoomAt(0.5, ...rel(e)));
  canvas.tabIndex = 0;
  canvas.addEventListener("keydown", (e) => {
    const step = 60;
    const keys = { ArrowLeft: () => panBy(step, 0), ArrowRight: () => panBy(-step, 0), ArrowUp: () => panBy(0, step),
      ArrowDown: () => panBy(0, -step), "+": () => zoomAt(0.7, st.w / 2, st.h / 2), "=": () => zoomAt(0.7, st.w / 2, st.h / 2),
      "-": () => zoomAt(1 / 0.7, st.w / 2, st.h / 2), n: () => api.northUp() };
    if (keys[e.key]) { e.preventDefault(); e.stopPropagation(); keys[e.key](); }
  });

  /** An overlay layer from {url, label, epoch, eager?}; cubes start on the base's band. */
  async function makeOverlay(l) {
    try {
      const layer = Object.assign(new Layer(l.url, await readProperties(l.url), { slice: st.base?.slice, ...l }), { meta: l });
      return layer;
    } catch (e) { console.warn(e); return null; }
  }

  // ----- public API -----
  const api = {
    async setBase(url, opts) {
      const layer = new Layer(url, await readProperties(url), opts);
      if (st.base) for (const t of st.base.tiles.values()) if (t.tex) gl.deleteTexture(t.tex);
      st.base = layer;
      markDirty();
      return layer;
    },
    setSlice(i) {
      if (!st.base || st.base.depth <= 1) return;   // (false-colour map: no bands)
      st.base.slice = Math.max(0, Math.min(st.base.depth - 1, i));
      for (const l of st.overlays) if (l.depth > 1) l.slice = Math.min(l.depth - 1, st.base.slice);   // T82: pass layers
      markDirty();
    },
    /** layers: [{url, label, epoch}] — all are prefetched, one is drawn (showOverlay). */
    async setOverlays(layers) {
      const call = ++st.overlayCall;
      for (const l of st.overlays) for (const t of l.tiles.values()) if (t.tex) gl.deleteTexture(t.tex);
      st.overlays = [];
      st.shown = -1;
      markDirty();
      const made = await Promise.all(layers.map(makeOverlay));
      if (call !== st.overlayCall) return [];
      st.overlays = made.filter(Boolean);
      markDirty();
      return st.overlays.map((l) => l.meta);
    },
    /** T55: how far overlay i is loaded for this view: {total, done, ok} tiles (done = loaded or none there). */
    overlayProgress(i) {
      const l = st.overlays[i];
      if (!l) return null;
      const k = l.meta?.eager ? eagerOrder(l) : pickOrder(l);
      const pixs = l.meta?.eager ? sharpTiles(k).map(([p]) => p) : tilesFor(l, k);
      let done = 0, ok = 0;
      for (const pix of pixs) {
        const t = l.tiles.get(l.key(k, pix));
        if (t?.state === "ok") { ok++; done++; } else if (t?.state === "missing" || t?.state === "failed") done++;
      }
      return { total: pixs.length, done, ok };
    },
    /** T81: append overlays (e.g. an A − B layer) without reloading the others; returns their indexes. */
    async addOverlays(layers) {
      const call = st.overlayCall;
      const made = (await Promise.all(layers.map(async (l) => {
        const opts = { slice: st.base?.slice, ...l };          // cube overlays (T82 passes) start on the base's band
        try { return Object.assign(new Layer(l.url, await readProperties(l.url), opts), { meta: l }); }
        catch (e) { console.warn(e); return null; }
      }))).filter(Boolean);
      if (call !== st.overlayCall) return [];
      const first = st.overlays.length;
      st.overlays.push(...made);
      markDirty();
      return made.map((_, k) => first + k);
    },
    showOverlay(i) { st.shown = i; markDirty(); },
    /** T55: highest order the base map draws (null = its own maximum). */
    setBaseCap(k) { if (st.baseCap !== k) { st.baseCap = k; markDirty(); } },
    setDebug(on) { st.debug = !!on; markDirty(); },
    /** {order, wanted, maxOrder, visible, sharp, blurry, empty, atMax, allSharp, loads, queued, errors} */
    stats() {
      const s = st.stats;
      if (!s) return null;
      return { order: s.order, wanted: s.wanted, maxOrder: s.maxOrder, visible: s.visible, sharp: s.sharp,
        blurry: s.blurry, empty: s.empty, atMax: s.wanted > s.maxOrder,
        allSharp: s.visible > 0 && s.sharp + s.empty === s.visible, loads: st.loads, queued: st.queue.length, errors: st.errors };
    },
    goTo(ra, dec, fov) {
      setFrame(((Number(ra) % 360) + 360) % 360, Math.max(-90, Math.min(90, Number(dec))));
      if (fov) st.fov = Math.max(MIN_FOV, Math.min(maxFov(), fov));
      changed();
    },
    /** T55: like goTo, but the sky point (ra, dec) ends up under screen point (x, y) instead of the centre. */
    placeAt(ra, dec, x, y, fov) {
      api.goTo(ra, dec, fov);
      dragTo([st.w / 2, st.h / 2], [x, y]);
    },
    /** T55: the field of view (deg) at which the map shows HiPS order k at one texel per screen pixel. */
    fovForOrder(k) {
      return ((TEXEL_ARCSEC_ORDER0 / 2 ** k) * st.w * st.dpr) / 3600;
    },
    /** Level the picture again: north up, east left, same centre and zoom. */
    northUp() { setFrame(st.ra, st.dec); changed(); },
    view: () => {
      // roll: angle of true north from screen-up (0 = north up), for a compass / reset button
      const P = [0, 0, 1], C = st.cam.C;
      const n = P.map((pi, i) => pi - dot(P, C) * C[i]);
      const roll = Math.hypot(...n) < 1e-9 ? 0 : Math.atan2(dot(n, st.cam.E), dot(n, st.cam.N)) / DEG;
      return { ra: st.ra, dec: st.dec, fov: st.fov, width: st.w, height: st.h, roll };
    },
    on(ev, fn) { st.listeners[ev]?.push(fn); },
    addDrawHook(fn) { st.hooks.push(fn); markDirty(); },
    redraw: markDirty,
    get base() { return st.base; },
    proj,
    _dragTo: dragTo, _zoomAt: zoomAt,       // for web/tests/projection_check.mjs
  };
  resize();
  return api;
}

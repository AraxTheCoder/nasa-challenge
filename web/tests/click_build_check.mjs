// T142: a map click builds a field only when needed; T138's "a click analyses the clicked place" stays (a new field
// is centred exactly on the click, old results are cleared, the selection goes into the URL).
// Same harness as field_focus_check.mjs: the real app.js with controlled I/O and timers, no browser.
import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';
import { readFileSync } from 'node:fs';
import { ang2pix } from '../healpix.js';
const noop = () => {};
const nodes = new Map();
const element = () => ({ hidden: false, textContent: '', value: '', classList: { toggle: noop, add: noop, remove: noop },
  replaceChildren: noop, append: noop, setAttribute: noop, addEventListener: noop, style: {} });
nodes.set('#field-form', { ...element(), ra: { value: '' }, dec: { value: '' }, size: { value: '14' } });
globalThis.document = { querySelector: (key) => {
  if (!nodes.has(key)) nodes.set(key, element()); return nodes.get(key);
}, dispatchEvent: noop };
globalThis.location = { href: 'http://test/web/', search: '' };
globalThis.history = { pushState: noop, replaceState: noop };
globalThis.CustomEvent = class { constructor(type, data) { Object.assign(this, data); } };
globalThis.setInterval = () => 0;
globalThis.clearInterval = noop;
globalThis.clearTimeout = noop;
globalThis.setTimeout = () => 0;
const calls = [], shown = [], marked = [], targets = {};
const view = { ra: 10, dec: 20, fovArcmin: 40, heightArcmin: 25 };
let mode = 'passes';
globalThis.__focusAdapters = {
  'api.js': { DEFAULT_API: 'http://test', ApiError: class extends Error {},
    requestField: (api, req) => new Promise((resolve) => calls.push({ req, resolve })) },
  'util.js': { $: document.querySelector, el: element },
  'viewer.js': { checkTarget: () => [], showTarget: (target) => shown.push(target) },
  'healpix.js': { ang2pix },
  'explore.js': { view: () => view, detector: () => 1, getSky: () => ({}), setFieldLayers: async (l) => l,
    showEpoch: noop, hideEpochs: noop, goTo: () => assert.fail('a click must not move the camera'),
    markField: (ra, dec, size) => marked.push([ra, dec, size]), hideOverlay: noop },
  'autoblink.js': { sharp: () => true, passesOn: () => true, colour: () => false, mode: () => mode,
    monthSpan: () => 'date', setMode: (m) => { mode = m; }, setPaused: noop, setStill: noop },
};
process.on('unhandledRejection', (e) => { console.error('unhandled:', e); process.exit(1); });
const appURL = new URL('../app.js', import.meta.url).href;
const source = readFileSync(new URL(appURL), 'utf8');
const named = new Map();
for (const match of source.matchAll(/import\s*\{([^}]+)\}\s*from\s*"\.\/([^"]+)"/g)) {
  named.set(match[2], match[1].split(',').map((s) => s.trim()));
}
const hook = registerHooks({
  resolve(specifier, context, next) {
    if (context.parentURL === appURL && specifier.startsWith('./')) return { url: `click-stub:${specifier.slice(2)}`, shortCircuit: true };
    return next(specifier, context);
  },
  load(url, context, next) {
    if (url.startsWith('click-stub:')) {
      const key = url.slice('click-stub:'.length);
      const names = new Set([...(named.get(key) ?? []), ...Object.keys(globalThis.__focusAdapters[key] ?? {})]);
      return { format: 'module', shortCircuit: true, source: [...names].map((name) =>
        `export const ${name} = globalThis.__focusAdapters[${JSON.stringify(key)}]?.[${JSON.stringify(name)}] ?? (() => {});`).join('\n') };
    }
    if (url === appURL) return { format: 'module', shortCircuit: true,
      source: source.replace(/\nmain\(\);\s*$/, '\nexport { app, focusAnalysis };') };
    return next(url, context);
  },
});
const { app, focusAnalysis } = await import(appURL);
hook.deregister();
app.api = 'http://test';
// target.json of a requested field: centred where it was asked for (as the Live API builds it)
globalThis.fetch = async (url) => {
  const id = String(url).match(/targets\/([^/]+)\/target\.json/)?.[1];
  const body = id ? targets[id] : { status: 'ready' };
  return { ok: true, status: 200, json: async () => body };
};
const finish = async (k, id) => {
  const { req, resolve } = calls[k];
  targets[id] = { id, synthetic: false, center: { ra_deg: Number(req.ra), dec_deg: Number(req.dec) },
    size_arcmin: Number(req.size), labels_requested: true, objects_requested: true,
    provenance: [{ service: 'test (T06)' }], frames: [] };
  resolve({ id, targetUrl: `http://test/api/targets/${id}/target.json` });
  for (let i = 0; i < 30; i++) await new Promise((r) => setImmediate(r));
};
const cos20 = Math.cos((20 * Math.PI) / 180);
const east = (ra, arcmin) => ra + arcmin / 60 / cos20;

// A first click: a field centred exactly there (T138).
focusAnalysis(10, 20);
assert.equal(calls.length, 1);
assert.deepEqual([calls[0].req.ra, calls[0].req.dec, calls[0].req.size], ['10.00000', '20.00000', 14]);
// Another click 1' away while it builds: well inside that field, no second one.
focusAnalysis(east(10, 1), 20);
assert.equal(calls.length, 1, 'a click well inside the field being built: no second field');
// Two clicks far away while it builds: one field at a time, the newest waits, the one in between is skipped.
focusAnalysis(10.5, 20);
focusAnalysis(11, 20);
assert.equal(calls.length, 1, 'one click field builds at a time');
assert.deepEqual(marked.at(-1), [11, 20, 14], 'the waiting region is outlined at once');
await finish(0, 'f10');
assert.equal(shown.length, 0, 'a build overtaken by a newer click is cached, not shown');
assert.equal(calls.length, 2);
assert.equal(calls[1].req.ra, '11.00000', 'the newest click is built next, the one in between never');
await finish(1, 'f11');
assert.equal(app.shownTarget?.id, 'f11');
// A click well inside the shown full field: only its spectrum (opened by the caller), no new field.
focusAnalysis(east(11, 2), 20 + 2 / 60);
assert.equal(calls.length, 2, 'well inside the shown field: it covers the click');
assert.equal(app.shownTarget?.id, 'f11', 'and it stays');
// Inside the field but not well inside (5' east of its centre): a new field centred exactly on the click.
focusAnalysis(east(11, 5), 20);
assert.equal(calls.length, 3);
assert.equal(calls[2].req.ra, east(11, 5).toFixed(5));
// Back near the first click (0.5' from it): the field built for it again (same centre = the server's cached field),
// after the build running now.
focusAnalysis(east(10, 0.5), 20 + 0.5 / 60);
assert.equal(calls.length, 3);
await finish(2, 'f11e');
assert.equal(calls.length, 4);
assert.deepEqual([calls[3].req.ra, calls[3].req.dec], ['10.00000', '20.00000'], 'the earlier click field is reused');
await finish(3, 'f10');
assert.equal(app.shownTarget?.id, 'f10');
// A one-band automatic tile field shown (id …-d1): a click inside it still selects a full field.
app.shownTarget = { id: 'tile-s86-d1', synthetic: false, center: { ra_deg: 12, dec_deg: 20 }, size_arcmin: 14 };
focusAnalysis(12, 20);
assert.equal(calls.length, 5, 'a one-band tile field does not cover a click for analysis');
console.log('PASS click builds: exact centre kept, reuse inside the shown / an earlier click field, one build at a ' +
  'time with the newest click next');

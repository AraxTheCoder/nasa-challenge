// Exercise the page controller with controlled I/O, timers and neighbouring view centres.
// The Node load hook skips page boot and supplies service/DOM adapters; controller functions are unmodified.
import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';
import { readFileSync } from 'node:fs';
import { ang2pix } from '../healpix.js';
const noop = () => {};
const nodes = new Map();
const element = () => ({ hidden: false, textContent: '', classList: { toggle: noop }, replaceChildren: noop,
  append: noop, setAttribute: noop, addEventListener: noop });
globalThis.document = { querySelector: (key) => {
  if (!nodes.has(key)) nodes.set(key, element()); return nodes.get(key);
}, dispatchEvent: noop };
globalThis.location = { href: 'http://test/', search: '' };
globalThis.CustomEvent = class { constructor(type, data) { Object.assign(this, data); } };
const intervals = new Map();
let nextTimer = 0, picks = [], shown = [], mode = 'epochs', view = { ra: 10, dec: 20 };
let deferred = null;
globalThis.setInterval = (fn) => { intervals.set(++nextTimer, fn); return nextTimer; };
globalThis.clearInterval = (id) => intervals.delete(id);
globalThis.clearTimeout = noop;
globalThis.setTimeout = () => ++nextTimer;
globalThis.__focusAdapters = {
  'api.js': { DEFAULT_API: 'http://test', ApiError: class extends Error {} },
  'util.js': { $: document.querySelector, el: element },
  'viewer.js': { checkTarget: () => [], showTarget: (target) => shown.push(target) },
  'healpix.js': { ang2pix },
  'explore.js': { view: () => view, detector: () => 1, getSky: () => ({}),
    setFieldLayers: async (layers) => layers, showEpoch: (i) => picks.push(i), hideEpochs: noop,
    goTo: () => assert.fail('a background field must not recenter the map'), markField: noop },
  'autoblink.js': { sharp: () => true, passesOn: () => true, colour: () => false, mode: () => mode,
    monthSpan: () => 'date', setMode: (m) => { mode = m; } },
};
const appURL = new URL('../app.js', import.meta.url).href;
const source = readFileSync(new URL(appURL), 'utf8');
const named = new Map();
for (const match of source.matchAll(/import\s*\{([^}]+)\}\s*from\s*"\.\/([^"]+)"/g)) {
  named.set(match[2], match[1].split(',').map((s) => s.trim()));
}
const hook = registerHooks({
  resolve(specifier, context, next) {
    if (context.parentURL === appURL && specifier.startsWith('./')) return { url: `focus-stub:${specifier.slice(2)}`, shortCircuit: true };
    return next(specifier, context);
  },
  load(url, context, next) {
    if (url.startsWith('focus-stub:')) {
      const key = url.slice('focus-stub:'.length);
      const names = new Set([...(named.get(key) ?? []), ...Object.keys(globalThis.__focusAdapters[key] ?? {})]);
      return { format: 'module', shortCircuit: true, source: [...names].map((name) =>
        `export const ${name} = globalThis.__focusAdapters[${JSON.stringify(key)}]?.[${JSON.stringify(name)}] ?? (() => {});`).join('\n') };
    }
    if (url === appURL) return { format: 'module', shortCircuit: true, source: source.replace(/\nmain\(\);\s*$/, '\nexport { app, autoField, openTarget, onBlinkSource, showEpochLayers, fieldKey, decideSource };') };
    return next(url, context);
  },
});
const controller = await import(appURL);
hook.deregister();
const { app, autoField, openTarget, showEpochLayers, onBlinkSource, fieldKey } = controller;
const metadata = { layers: [{ epoch: 1, url: '/epoch1' }, { epoch: 2, url: '/epoch2' }] };
globalThis.fetch = async (url) => {
  if (deferred) { const take = deferred; deferred = null; return await new Promise((resolve) => take(resolve)); }
  return { ok: true, json: async () => metadata };
};
const target = { id: 'focused', center: { ra_deg: 10, dec_deg: 20 }, size_arcmin: 15, labels_requested: true };
app.shownTarget = target;
autoField.explicit = target;
await showEpochLayers(target);
assert.deepEqual(picks, [0]);
assert.equal(intervals.size, 1);
const oldTick = [...intervals.values()][0];
view = { ra: 12, dec: 20 };
oldTick();
assert.deepEqual(picks, [0], 'queued timer from an off-focus field cannot change imagery');
view = { ra: 10, dec: 20 };
oldTick();
assert.deepEqual(picks, [0, 1], 'a focused current field still blinks');
mode = 'passes';
onBlinkSource('passes');
assert.equal(intervals.size, 0, 'source change stops the timer immediately');
oldTick();
assert.deepEqual(picks, [0, 1]);

// The target JSON itself returns late, after navigation to another tile/band.
autoField.explicit = null;
const oldKey = fieldKey();
autoField.building = oldKey;
let finish;
deferred = (resolve) => { finish = resolve; };
const request = openTarget('http://test/old/target.json', 'old', app.loadToken, undefined, oldKey);
view = { ra: 30, dec: 20 };
assert.notEqual(fieldKey(), oldKey);
finish({ ok: true, json: async () => ({ ...target, id: 'old' }) });
await request;
assert.equal(shown.length, 0, 'off-focus background target is not published');
assert.equal(app.shownTarget, target, 'the analysis target stays current');
assert.equal(autoField.ready.get(oldKey).id, 'old', 'the completed result remains cached for returning');
assert.equal(autoField.building, null);

// An explicit selection or map tool also owns the view when a background result arrives.
view = { ra: 10, dec: 20 };
app.manualMap = true;
autoField.building = fieldKey();
globalThis.fetch = async () => ({ ok: true, json: async () => ({ ...target, id: 'tool-waiter' }) });
await openTarget('http://test/tool/target.json', 'tool-waiter', app.loadToken, undefined, fieldKey());
assert.equal(shown.length, 0);
assert.equal(app.shownTarget, target);

// In-flight epoch metadata cannot restart a timer after switching sources.
app.manualMap = false;
autoField.explicit = target;
mode = 'epochs';
let finishMetadata;
globalThis.fetch = async () => await new Promise((resolve) => { finishMetadata = resolve; });
const pendingEpoch = showEpochLayers(target);
mode = 'passes';
onBlinkSource('passes');
finishMetadata({ ok: true, json: async () => metadata });
await pendingEpoch;
assert.equal(intervals.size, 0);
assert.deepEqual(picks, [0, 1]);
// A pinned analysis selection also wins over cached/background fields at the current view centre.
app.analysisFocus = { key: 'selected-analysis' };
app.shownTarget = target;
app.manualMap = false;
autoField.explicit = null;
const currentKey = fieldKey();
autoField.ready.set(currentKey, { ...target, id: 'background-cached' });
controller.decideSource();
assert.equal(app.shownTarget, target, 'cached automatic fields cannot replace selected analysis');
globalThis.fetch = async () => ({ ok: true, json: async () => ({ ...target, id: 'background-late' }) });
await openTarget('http://test/background/target.json', 'background-late', app.loadToken, undefined, currentKey);
assert.equal(app.shownTarget, target, 'completed automatic fields cannot replace selected analysis');
assert.equal(shown.length, 0);
app.analysisFocus = null;
controller.decideSource();
assert.equal(app.shownTarget.id, 'background-late', 'automatic source selection resumes after releasing focus');
console.log('PASS field focus: stale build stays cached, map/tool ownership, old ticks and late epoch metadata');

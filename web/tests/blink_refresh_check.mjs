// T139: a fresh copy of the shown field (its labels or known objects arrived) must not stop its epoch blink, and the
// next view change must not swap the old copy back; T134's checks stay (any other replacement still stops the timer).
// Same harness as field_focus_check.mjs: the real app.js with controlled I/O and timers, no browser.
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
let nextTimer = 0, picks = [], shown = [], mode = 'epochs';
const view = { ra: 10, dec: 20 };
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
    goTo: noop, markField: noop },
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
    if (context.parentURL === appURL && specifier.startsWith('./')) return { url: `refresh-stub:${specifier.slice(2)}`, shortCircuit: true };
    return next(specifier, context);
  },
  load(url, context, next) {
    if (url.startsWith('refresh-stub:')) {
      const key = url.slice('refresh-stub:'.length);
      const names = new Set([...(named.get(key) ?? []), ...Object.keys(globalThis.__focusAdapters[key] ?? {})]);
      return { format: 'module', shortCircuit: true, source: [...names].map((name) =>
        `export const ${name} = globalThis.__focusAdapters[${JSON.stringify(key)}]?.[${JSON.stringify(name)}] ?? (() => {});`).join('\n') };
    }
    if (url === appURL) return { format: 'module', shortCircuit: true,
      source: source.replace(/\nmain\(\);\s*$/, '\nexport { app, autoField, showEpochLayers, refreshShown, decideSource };') };
    return next(url, context);
  },
});
const { app, autoField, showEpochLayers, refreshShown, decideSource } = await import(appURL);
hook.deregister();
const metadata = { layers: [{ epoch: 1, url: '/epoch1' }, { epoch: 2, url: '/epoch2' }, { epoch: 3, url: '/epoch3' }] };
let deferred = null;
globalThis.fetch = async () => {
  if (deferred) { const take = deferred; deferred = null; return await new Promise((resolve) => take(resolve)); }
  return { ok: true, json: async () => metadata };
};
const tick = () => [...intervals.values()].at(-1)();

// An explicitly built field blinks.
const field = { id: 'barnard', center: { ra_deg: 10, dec_deg: 20 }, size_arcmin: 14, labels_requested: true };
app.shownTarget = field;
autoField.explicit = field;
await showEpochLayers(field);
tick();
assert.deepEqual(picks, [0, 1], 'the field blinks');

// Its known objects (or labels) arrive: a fresh copy of the same field is handed over; the blink goes on.
const fresh = { ...field, objects: [{ name: '(1) Ceres' }] };
refreshShown(fresh);
assert.equal(shown.at(-1).objects, fresh.objects, 'the fresh copy is published (Labels off: as a copy without labels)');
assert.equal(app.shownTarget, fresh);
assert.equal(autoField.explicit, fresh, 'the field "here" is the fresh copy');
tick();
assert.deepEqual(picks, [0, 1, 2], 'the blink goes on after the fresh copy arrived (froze before T139)');

// The next view change keeps the fresh copy (the old one was swapped back, dropping the known objects).
const published = shown.length;
decideSource();
assert.equal(app.shownTarget, fresh, 'a view change does not swap the old copy back');
assert.equal(shown.length, published, 'nothing is published again');
tick();
assert.deepEqual(picks, [0, 1, 2, 0]);

// T134 stays: a replacement without the hand-over (another object) stops the old timer.
app.shownTarget = { ...fresh };
tick();
assert.deepEqual(picks, [0, 1, 2, 0], 'an unannounced replacement still stops the old timer');
// ... and a "fresh copy" of another field hands nothing over.
app.shownTarget = fresh;
refreshShown({ ...fresh, id: 'other' });
assert.equal(autoField.explicit, fresh, 'another field is not handed over');
tick();
assert.deepEqual(picks, [0, 1, 2, 0], 'nor does its timer go on');

// The fresh copy arrives while the epoch metadata is still loading: the blink starts for it.
picks = [];
app.shownTarget = field;
autoField.explicit = field;
let finish;
deferred = (resolve) => { finish = resolve; };
const pending = showEpochLayers(field);
refreshShown(fresh);
finish({ ok: true, json: async () => metadata });
await pending;
tick();
assert.deepEqual(picks, [0, 1], 'a fresh copy during loading: the blink starts and goes on');
console.log('PASS blink refresh: fresh copies of the field keep its blink and stay shown; other replacements stop the timer');

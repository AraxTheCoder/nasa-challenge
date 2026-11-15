import assert from 'node:assert/strict';
import { outlierCopy, anomalyCopy } from '../analysiscopy.js';
const data = { peer_group: 'stars', deviations: [{ pct: -45, um_min: 3.2, um_max: 3.4, z: 7,
  n_bands: 2, epochs_seen: 3, epochs_agree: 3, meaning: 'methane absorption: a brown dwarf?' }], caveats: ['blended'] };
const outlier = outlierCopy(data);
assert.match(outlier.brief, /-45% vs peers/);
assert.match(outlier.brief, /tentative/);
assert.ok(!outlier.brief.includes('brown dwarf'), 'physical interpretation is optional detail');
assert.match(outlier.detail, /3\/3 epochs agree/);
assert.match(outlier.detail, /not an identification probability/);
assert.match(outlier.detail, /blended/);
const galaxy = outlierCopy({ ...data, peer_group: 'galaxies', wavelength_frame: 'rest' });
assert.match(galaxy.detail, /rest frame/);
assert.ok(!galaxy.detail.includes('brown dwarf'), 'galaxy residuals do not get stellar interpretations');
const anomaly = anomalyCopy({ type: 'spike', wavelength_um: 3.3, change_pct: 80, sigma: 6,
  known: [{ name: 'test asteroid' }] });
assert.match(anomaly.brief, /Possible spike/);
assert.match(anomaly.detail, /proximity does not establish the cause/);
assert.ok(!anomaly.detail.includes('it passed through'));
console.log('PASS brief analysis copy: measured evidence, tentative identity and association uncertainty');

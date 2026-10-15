import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {summarizeResults, filterResults, validateReport, objectResultStatus} from '../dist/compliance.js';
import {english} from '../dist/i18n.js';
const read = name => JSON.parse(fs.readFileSync(new URL('../dist/data/' + name, import.meta.url), 'utf8'));
const laws = read('regulations.json').laws;
const model = read('ifcopenhouse.json');
const report = read('compliance-ifcopenhouse.json');

test('Real reports bind source hashes and model GlobalIds; candidate links never become PASS', () => {
  for (const {id} of read('models.json')) {
    const checked = validateReport(read(`compliance-${id}.json`), read(`${id}.json`), laws);
    const stats = summarizeResults(checked.results);
    const ruleCount = read('check-contracts.json').rules.length;
    assert.equal(stats.rule_count, ruleCount); assert.equal(stats.PASS, 0); assert.equal(stats['NOT CHECKABLE'], ruleCount);
    assert.equal(stats.completed_determination_rate, 0); assert.equal(stats.determined_pass_rate, null);
  }
  assert.equal(report.results.find(r => r.rule_id === 'egress-door-clear-width').where.global_ids[0], '0Tif_$wI1FwAwq$OJt24I8');
});
test('Coverage, pass rate, exclusions and instance totals use distinct denominators', () => {
  const fixture = ['PASS', 'FAIL', 'NOT CHECKABLE', 'NOT_APPLICABLE'].map(display_status => ({rule_id:'fixture', display_status}));
  const stats = summarizeResults(fixture);
  assert.equal(stats.rule_count, 1); assert.equal(stats.instance_count, 4);
  assert.equal(stats.completed_determination_rate, 2/3); assert.equal(stats.determined_pass_rate, 1/2);
  for (const rows of [[], [{rule_id:'excluded', display_status:'NOT_APPLICABLE'}]]) {
    assert.equal(summarizeResults(rows).completed_determination_rate, null);
    assert.equal(summarizeResults(rows).determined_pass_rate, null);
  }
});
test('Chapter, rule, state, topic, storey and reverse element filters intersect', () => {
  assert.equal(filterResults(report.results, {chapters:[10]}).length, 1);
  assert.equal(filterResults(report.results, {chapters:[]}).length, 0);
  const rid = 'egress-door-clear-width', guid = '0Tif_$wI1FwAwq$OJt24I8';
  assert.equal(filterResults(report.results, {chapters:[10], ruleId:rid, status:'NOT CHECKABLE', globalId:guid, topic:'Egress'}).length, 1);
  assert.equal(filterResults(report.results, {status:'PASS'}).length, 0);
  assert.ok(filterResults(report.results, {globalId:guid}).length >= 3);
  const fixture = structuredClone(report.results[0]); fixture.where.objects[0] = {storey:{global_id:'fixture-storey'}};
  assert.equal(filterResults([fixture], {storey:'fixture-storey'}).length, 1);
});
test('Stale model, altered clause, unknown object and absent reason are rejected', () => {
  for (const mutate of [r => r.model_sha256 = '0'.repeat(64), r => r.results[0].why.text = 'changed',
    r => r.results[0].where.global_ids = ['missing'], r => r.results[0].what.reason_code = null]) {
    const bad = structuredClone(report); mutate(bad); assert.throws(() => validateReport(bad, model, laws));
  }
});
test('Object coloring uses reviewed results and preserves all individual findings', () => {
  const fixture = ['PASS', 'FAIL', 'NOT CHECKABLE'].map(display_status => ({display_status, where:{global_ids:['fixture'], target_binding:'reviewed'}}));
  assert.equal(objectResultStatus(fixture, 'fixture'), 'FAIL');
  assert.equal(objectResultStatus(report.results, '0Tif_$wI1FwAwq$OJt24I8'), null);
});
test('Compliance interface labels have English translations', () => {
  const source = fs.readFileSync(new URL('../dist/compliance-panel.js', import.meta.url), 'utf8');
  for (const key of [...source.matchAll(/\bt\('([^']+)'/g)].map(m => m[1])) assert.ok(Object.hasOwn(english, key), key);
});

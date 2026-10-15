import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {ruleClassLabel, validateReport} from '../dist/compliance.js';

const read = name => JSON.parse(fs.readFileSync(new URL('../dist/data/' + name, import.meta.url), 'utf8'));
test('Six residential contracts expose class and preserve pending review gates', () => {
  const rules = read('check-contracts.json').rules.filter(r => r.check_function === 'residential_check');
  assert.equal(rules.length, 6);
  assert.deepEqual(rules.map(r => ruleClassLabel(r)), ['Class 1', 'Class 1', 'Class 2', 'Class 2', 'Class 3', 'Class 3']);
  for (const rule of rules) {
    assert.ok(rule.class_basis && rule.dsl_sources.length);
    assert.equal(rule.review_status, 'PENDING'); assert.equal(rule.execution_ready, false);
  }
  assert.equal(ruleClassLabel({}), ''); assert.equal(ruleClassLabel({rule_class:9}), '');
});
test('New residential results retain class and missing real evidence stays NOT CHECKABLE', () => {
  const laws = read('regulations.json').laws;
  for (const {id} of read('models.json')) {
    const report = validateReport(read(`compliance-${id}.json`), read(`${id}.json`), laws);
    const rules = report.results.filter(r => r.rule_id.startsWith('residential-'));
    assert.equal(rules.length, 6);
    for (const result of rules) {
      assert.match(ruleClassLabel(result), /^Class [123]$/);
      assert.equal(result.display_status, 'NOT CHECKABLE');
      assert.ok(result.why.dsl_sources.length);
    }
  }
});

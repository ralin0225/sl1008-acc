import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import crypto from 'node:crypto';
import {buildChapterIndex, relatedLaws} from '../dist/core.js';
import {validateReport} from '../dist/compliance.js';
import {english} from '../dist/i18n.js';
const read = relative => JSON.parse(fs.readFileSync(new URL(relative, import.meta.url), 'utf8'));

test('All registered models have exported geometry, localized labels and version-bound ACC snapshots', () => {
  const catalog = read('../../models/catalog.json').models;
  const manifest = read('../dist/data/models.json');
  const laws = read('../dist/data/regulations.json').laws;
  assert.deepEqual(manifest.map(m => m.id), catalog.map(m => m.id));
  assert.ok(catalog.some(m => m.id === 'duplex'));
  for (const entry of catalog) {
    const data = read(`../dist/data/${entry.id}.json`);
    const source = fs.readFileSync(new URL(`../../models/${entry.id}/${entry.filename}`, import.meta.url));
    assert.equal(crypto.createHash('sha256').update(source).digest('hex'), data.sha256);
    assert.equal(manifest.find(m => m.id === entry.id).recordCount, data.records.length);
    assert.equal(data.records.filter(r => r.geometry).length, data.precheck.checks.geometry.generated);
    assert.equal(data.records.filter(r => r.geometryError).length, data.precheck.checks.geometry.failed.length);
    assert.ok(english[entry.name]);
    validateReport(read(`../dist/data/compliance-${entry.id}.json`), data, laws);
  }
});

test('Duplex retains IFC2X3 profile mismatch, all door metadata and both chapters without approving compliance', () => {
  const data = read('../dist/data/duplex.json'), laws = read('../dist/data/regulations.json').laws;
  assert.equal(data.schema, 'IFC2X3');
  assert.equal(data.precheck.checks.schema.status, 'FAIL');
  const doors = data.records.filter(r => r.type === 'IfcDoor');
  assert.equal(doors.length, 14);
  for (const chapter of [10,11]) {
    const index = buildChapterIndex(data.records, [], laws, [chapter]);
    for (const door of doors) assert.ok(relatedLaws(index, door.id).length);
  }
  const report = read('../dist/data/compliance-duplex.json');
  assert.equal(report.summary['NOT CHECKABLE'], read('../dist/data/check-contracts.json').rules.length);
  assert.equal(report.summary.PASS, 0);
  assert.equal(report.is_synthetic, false);
});

test('Villa Patio is registered for both chapter links and ACC without inferring spaces or approvals', () => {
  const data = read('../dist/data/villa-patio.json'), laws = read('../dist/data/regulations.json').laws;
  assert.equal(data.schema, 'IFC2X3');
  const doors = data.records.filter(r => r.type === 'IfcDoor');
  assert.equal(doors.length, 24);
  assert.equal(data.records.filter(r => r.type === 'IfcSpace').length, 0);
  for (const chapter of [10,11]) {
    const index = buildChapterIndex(data.records, [], laws, [chapter]);
    for (const door of doors) assert.ok(relatedLaws(index, door.id).length);
  }
  const report = validateReport(read('../dist/data/compliance-villa-patio.json'), data, laws);
  assert.equal(report.summary['NOT CHECKABLE'], read('../dist/data/check-contracts.json').rules.length);
  assert.equal(report.summary.PASS, 0);
  assert.equal(report.is_synthetic, false);
});

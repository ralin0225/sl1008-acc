import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {buildIndex, relatedLaws, relatedElements, searchLaw, validateCustomLinks} from '../dist/core.js';

const read = name => JSON.parse(fs.readFileSync(new URL(`../dist/data/${name}.json`, import.meta.url), 'utf8'));
const regulations = read('regulations');
const models = read('models').map(m => read(m.id));
test('Every model-regulation link is symmetric and targets real evidence', () => {
  const lawIds = new Set(regulations.laws.map(l => l.id));
  for (const model of models) {
    const index = buildIndex(model.records);
    for (const record of model.records) for (const lawId of relatedLaws(index, record.id)) {
      assert.ok(lawIds.has(lawId));
      assert.ok(relatedElements(index, lawId).includes(record.id));
    }
    for (const [lawId, ids] of index.byLaw) for (const id of ids) assert.ok(relatedLaws(index, id).includes(lawId));
  }
});
test('Door uses source mappings and returns the same IFC GUID when querying 1105.1', () => {
  const model = models[1], door = model.records.find(r => r.type === 'IfcDoor');
  const index = buildIndex(model.records);
  assert.ok(relatedLaws(index, door.id).includes('ibc2021-1105.1'));
  assert.deepEqual(relatedElements(index, 'ibc2021-1105.1'), [door.id]);
  assert.ok(door.links.every(x => x.status === 'proposed_requires_review'));
});
test('Failed geometry remains in metadata and successful meshes equal precheck coverage', () => {
  for (const model of models) {
    assert.equal(model.records.filter(r => r.geometry).length, model.precheck.checks.geometry.generated);
    const failed = model.records.filter(r => r.geometryError);
    assert.equal(failed.length, model.precheck.checks.geometry.failed.length);
    failed.forEach(r => assert.equal(r.geometry, null));
  }
});
test('All structured clauses, exceptions and table evidence stay searchable, including unlinked items', () => {
  assert.equal(regulations.laws.filter(l => l.chapter === 11).length, 305);
  const index = buildIndex(models[0].records);
  const unlinked = regulations.laws.find(l => !relatedElements(index, l.id).length);
  assert.ok(unlinked && searchLaw(unlinked, unlinked.id));
  assert.ok(regulations.laws.some(l => l.type === 'exception'));
  assert.ok(Object.keys(regulations.tables).length > 0);
  assert.equal(regulations.laws.find(l => l.id === 'ibc2021-1106.2').tables[0].cells[1][1], '1');
  assert.ok(regulations.laws.every(l => l.text && l.sha256 && l.fragments.length));
});
test('Manual links require matching model hash, GUID and existing law; update both directions', () => {
  const m = models[1], r = m.records.find(r => r.type === 'IfcDoor');
  const link = {modelId:m.id, modelSha256:m.sha256, elementId:r.id, lawId:'ibc2021-1106.2'};
  assert.equal(validateCustomLinks([link, link], models, regulations.laws).length, 1);
  assert.throws(() => validateCustomLinks([{...link, modelSha256:'wrong'}], models, regulations.laws));
  assert.throws(() => validateCustomLinks([{...link, elementId:'wrong'}], models, regulations.laws));
  assert.throws(() => validateCustomLinks([{...link, lawId:'invented'}], models, regulations.laws));
  const index = buildIndex(m.records, [link]);
  assert.ok(relatedLaws(index, r.id).includes(link.lawId));
  assert.ok(relatedElements(index, link.lawId).includes(r.id));
});

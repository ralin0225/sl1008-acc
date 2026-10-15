import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {filterLawsByChapter, buildChapterIndex, relatedLaws, relatedElements, lawPdfUrl} from '../dist/core.js';
const data = JSON.parse(fs.readFileSync(new URL('../dist/data/regulations.json', import.meta.url), 'utf8'));
const model = JSON.parse(fs.readFileSync(new URL('../dist/data/ifcopenhouse.json', import.meta.url), 'utf8'));

test('Chapter identities are disjoint; both, either, and no checkbox selection are supported', () => {
  const all = data.laws, ch10 = filterLawsByChapter(all, [10]), ch11 = filterLawsByChapter(all, [11]);
  assert.equal(new Set(all.map(l => l.id)).size, all.length);
  assert.equal(ch11.length, 305);
  assert.ok(ch10.length > 1000);
  assert.equal(filterLawsByChapter(all, [10, 11]).length, all.length);
  assert.equal(filterLawsByChapter(all, []).length, 0);
  for (const chapter of data.chapters) assert.equal(chapter.lawCount, filterLawsByChapter(all, [chapter.id]).length);
});

test('Door links and reverse highlighting respect selected chapters without changing stored links', () => {
  const door = model.records.find(r => r.type === 'IfcDoor');
  const before = JSON.stringify(door.links);
  for (const chapters of [[10], [11], [10, 11], []]) {
    const index = buildChapterIndex(model.records, [], data.laws, chapters);
    const ids = relatedLaws(index, door.id);
    assert.equal(ids.includes('ibc2021-1010'), chapters.includes(10));
    assert.equal(ids.includes('ibc2021-1105.1'), chapters.includes(11));
    for (const id of ids) assert.ok(relatedElements(index, id).includes(door.id));
    if (!chapters.length) assert.equal(ids.length, 0);
  }
  assert.equal(JSON.stringify(door.links), before);
});

test('Each chapter opens its own actual PDF and excerpt page, including the door-width provision', () => {
  const door = data.laws.find(l => l.id === 'ibc2021-1010.1.1');
  assert.ok(door.text.includes('32 inches'));
  assert.equal(door.sourceFile, 'IBC2021_10MeansOfEngress.pdf');
  assert.equal(lawPdfUrl(door), './data/IBC2021_Chapter10.pdf#page=13');
  assert.equal(door.fragments[0].source_pdf_page, 316);
  assert.ok(lawPdfUrl(data.laws.find(l => l.id === 'ibc2021-1105.1')).startsWith('./data/IBC2021_Chapter11.pdf#page='));
  for (const chapter of data.chapters) assert.ok(fs.existsSync(new URL('../dist/data/' + chapter.pdfFile, import.meta.url)));
});

test('Imported manual links to Chapter 10 remain hidden until that chapter is selected', () => {
  const door = model.records.find(r => r.type === 'IfcDoor');
  const link = {elementId:door.id, lawId:'ibc2021-1031.1'};
  assert.ok(relatedLaws(buildChapterIndex(model.records, [link], data.laws, [10]), door.id).includes(link.lawId));
  assert.ok(!relatedLaws(buildChapterIndex(model.records, [link], data.laws, [11]), door.id).includes(link.lawId));
});

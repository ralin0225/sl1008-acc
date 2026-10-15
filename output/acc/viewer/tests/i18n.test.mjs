import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {english, t, setLanguage, getLanguage, linkReason} from '../dist/i18n.js';

test('Language switching preserves interpolation values and falls back to Chinese for unsupported locales', () => {
  setLanguage('en');
  assert.equal(getLanguage(), 'en');
  assert.equal(t('条款 {code} → {n} 个关联对象', {code:'1105.1', n:1}), 'Clause 1105.1 → 1 linked object');
  assert.equal(t('GUID'), 'GUID');
  setLanguage('zh');
  assert.equal(t('条款 {code} → {n} 个关联对象', {code:'1105.1', n:1}), '条款 1105.1 → 1 个关联对象');
  setLanguage('unsupported');
  assert.equal(getLanguage(), 'zh');
});

test('Every declared interface string has English coverage and matching interpolation fields', () => {
  const app = fs.readFileSync(new URL('../dist/app.js', import.meta.url), 'utf8');
  const html = fs.readFileSync(new URL('../dist/index.html', import.meta.url), 'utf8');
  const keys = [...app.matchAll(/\bt\('([^']+)'/g), ...html.matchAll(/data-i18n(?:-(?:aria-label|placeholder|title))?="([^"]+)"/g)].map(m => m[1]);
  keys.forEach(key => assert.ok(Object.hasOwn(english, key), `Missing translation: ${key}`));
  const fields = s => [...s.matchAll(/\{(\w+)\}/g)].map(m => m[1]).sort();
  for (const [zh,en] of Object.entries(english)) assert.deepEqual(fields(zh), fields(en), zh);
});

test('Real candidate mapping explanations translate without changing clause numbers or IFC identities', () => {
  setLanguage('en');
  const manifest = JSON.parse(fs.readFileSync(new URL('../dist/data/models.json', import.meta.url), 'utf8'));
  for (const {id:key} of manifest) {
    const model = JSON.parse(fs.readFileSync(new URL(`../dist/data/${key}.json`, import.meta.url), 'utf8'));
    for (const r of model.records) for (const link of r.links) {
      const reason = linkReason(link.reason);
      assert.ok(!/[\p{Script=Han}]/u.test(reason), reason);
      if (link.kind === 'direct') assert.ok(reason.includes('Ifc'));
    }
  }
  setLanguage('zh');
});

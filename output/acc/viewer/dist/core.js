export function buildIndex(records, custom = []) {
  const byElement = new Map(records.map(r => [r.id, []]));
  const byLaw = new Map();
  const add = (id, link) => {
    if (!byElement.has(id)) return;
    byElement.get(id).push(link);
    if (!byLaw.has(link.lawId)) byLaw.set(link.lawId, new Set());
    byLaw.get(link.lawId).add(id);
  };
  records.forEach(r => r.links.forEach(link => add(r.id, link)));
  custom.forEach(link => add(link.elementId, {...link, kind: 'manual', status: 'user_linked_requires_review', reason: '用户补充关联；尚未作法规适用性审批'}));
  return {byElement, byLaw};
}
export function relatedLaws(index, id) {
  return [...new Set((index.byElement.get(id) || []).map(x => x.lawId))];
}
export function relatedElements(index, lawId) { return [...(index.byLaw.get(lawId) || [])]; }
export function filterLawsByChapter(laws, chapters) {
  const selected = new Set([...chapters].map(Number));
  return laws.filter(law => selected.has(Number(law.chapter ?? 11)));
}
export function buildChapterIndex(records, custom, laws, chapters) {
  const ids = new Set(filterLawsByChapter(laws, chapters).map(law => law.id));
  return buildIndex(records.map(record => ({...record, links:record.links.filter(link => ids.has(link.lawId))})),
    custom.filter(link => ids.has(link.lawId)));
}
export function lawPdfUrl(law) {
  const file = law.pdfFile ?? 'IBC2021_Chapter11.pdf';
  if (!/^IBC2021_Chapter\d+\.pdf$/.test(file)) throw new Error('Invalid chapter PDF filename');
  const page = law.fragments?.[0]?.pdf_page_number;
  return Number.isInteger(page) && page > 0 ? `./data/${file}#page=${page}` : null;
}
export function searchLaw(law, query) {
  const q = query.trim().toLowerCase();
  return !q || `${law.id} ${law.label || ''} ${law.heading || ''} ${law.text}`.toLowerCase().includes(q);
}
export function validateCustomLinks(value, models, laws) {
  if (!Array.isArray(value)) throw new Error('关联文件须为 JSON 数组');
  const lawIds = new Set(laws.map(x => x.id));
  const result = [];
  for (const link of value) {
    if (!link || typeof link.modelId !== 'string' || typeof link.modelSha256 !== 'string' ||
        typeof link.elementId !== 'string' || typeof link.lawId !== 'string' || !lawIds.has(link.lawId)) {
      throw new Error('关联文件包含无效字段或法规编号');
    }
    const model = models.find(m => m.id === link.modelId);
    if (!model || model.sha256 !== link.modelSha256 || !model.records.some(r => r.id === link.elementId)) {
      throw new Error('模型哈希或构件 GUID 与当前模型不匹配');
    }
    if (!result.some(x => x.modelId === link.modelId && x.elementId === link.elementId && x.lawId === link.lawId)) result.push(link);
  }
  return result;
}

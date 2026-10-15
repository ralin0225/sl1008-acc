// Actual ACC results remain separate from proposed regulation links.
export const resultColors = {'PASS': 0x23864a, 'FAIL': 0xc43c3c, 'NOT CHECKABLE': 0xd29c27};
export function ruleClassLabel(rule) {
  return Number.isInteger(rule?.rule_class) && rule.rule_class >= 1 && rule.rule_class <= 4 ? `Class ${rule.rule_class}` : '';
}
export function summarizeResults(results) {
  const counts = Object.fromEntries(['PASS', 'FAIL', 'NOT CHECKABLE', 'NOT_APPLICABLE'].map(s => [s, results.filter(r => r.display_status === s).length]));
  const decided = counts.PASS + counts.FAIL, applicable = decided + counts['NOT CHECKABLE'];
  return {rule_count: new Set(results.map(r => r.rule_id)).size, instance_count: results.length, ...counts,
    completed_determination_rate: applicable ? decided / applicable : null,
    determined_pass_rate: decided ? counts.PASS / decided : null};
}
export function filterResults(results, {chapters, ruleId = '', status = '', storey = '', globalId = '', topic = ''} = {}) {
  const selected = chapters == null ? null : new Set([...chapters].map(Number));
  return results.filter(r => (!selected || selected.has(r.chapter)) && (!ruleId || r.rule_id === ruleId) &&
    (!status || r.display_status === status) && (!topic || r.topic === topic) &&
    (!globalId || r.where.global_ids.includes(globalId)) &&
    (!storey || r.where.objects.some(o => (o.storey?.global_id || '__unassigned') === storey)));
}
export function validateReport(report, model, laws) {
  if (report?.schema_version !== '1.0.0' || report.model_id !== model.id || report.model_sha256 !== model.sha256 || !Array.isArray(report.results)) throw new Error('检查报告与当前模型版本不匹配');
  const ids = new Set(), objects = new Set(model.records.map(r => r.id));
  const sources = new Map(laws.map(l => [l.id, l]));
  for (const r of report.results) {
    const display = ['PASS', 'FAIL', 'NOT_APPLICABLE'].includes(r.status) ? r.status : 'NOT CHECKABLE';
    const source = sources.get(r.why?.source_node_id);
    if (!source || r.why.sha256 !== source.sha256 || r.why.text !== source.text || r.chapter !== source.chapter || ids.has(r.instance_id) ||
      r.where?.model_id !== model.id || r.where.model_sha256 !== model.sha256 ||
      !Array.isArray(r.where.global_ids) || r.where.global_ids.some(id => !objects.has(id)) ||
      !['PASS', 'FAIL', 'NOT CHECKABLE', 'NOT_APPLICABLE'].includes(r.display_status) || r.display_status !== display ||
      !r.what || r.run?.run_id !== report.run_id || (r.display_status === 'NOT CHECKABLE' && !r.what.reason_code)) throw new Error('检查报告包含无效证据或对象身份');
    ids.add(r.instance_id);
  }
  return report;
}
export function objectResultStatus(results, globalId) {
  const applicable = results.filter(r => r.where.global_ids.includes(globalId) && r.where.target_binding === 'reviewed').map(r => r.display_status);
  return ['FAIL', 'NOT CHECKABLE', 'PASS'].find(s => applicable.includes(s)) || null;
}

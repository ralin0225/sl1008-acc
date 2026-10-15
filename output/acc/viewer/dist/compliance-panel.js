import {filterResults, summarizeResults, validateReport, objectResultStatus, resultColors} from './compliance.js';

export function createCompliancePanel({$, esc, t, getModel, getLaws, getChapters, getElement, highlight, clearResultHighlight, refreshAppearance, openLaw, selectElement}) {
  let report = null, latestReport = null, selected = null, facts = null, contracts = [], history = [], loadToken = 0;
  const percentage = n => n === null ? t('不可计算') : `${(100 * n).toFixed(1)}%`;
  const localTime = value => new Intl.DateTimeFormat('sv-SE', {timeZone:'Europe/Berlin', dateStyle:'short', timeStyle:'medium'}).format(new Date(value)) + ' Europe/Berlin';
  function visible() {
    return filterResults(report?.results || [], {chapters:getChapters(), ruleId:$('check-rule').value,
      status:$('check-status').value, storey:$('check-storey').value, topic:$('check-topic').value,
      globalId:$('check-current-object').checked ? getElement() || '__none' : ''});
  }
  function options() {
    const prior = $('check-rule').value, storey = $('check-storey').value;
    $('check-rule').innerHTML = `<option value="">${t('全部规则')}</option>` + contracts.map(r => `<option value="${esc(r.rule_id)}">${esc(r.rule_id)} · v${esc(r.rule_version)}</option>`).join('');
    if (contracts.some(r => r.rule_id === prior)) $('check-rule').value = prior;
    const levels = new Map();
    for (const result of report?.results || []) for (const obj of result.where.objects) levels.set(obj.storey?.global_id || '__unassigned', obj.storey?.name || obj.storey?.global_id || t('未归属楼层'));
    $('check-storey').innerHTML = `<option value="">${t('全部楼层')}</option>` + [...levels].map(([id,name]) => `<option value="${esc(id)}">${esc(name)}</option>`).join('');
    if (levels.has(storey)) $('check-storey').value = storey;
    $('check-history').innerHTML = `<option value="">${t('当前运行')}</option>` + history.map((r,i) => `<option value="${i}">${esc(localTime(r.timestamp))} · ${esc(r.run_id.slice(0,8))}${r.model_sha256 !== getModel().sha256 ? ` · ${t('其他模型版本')}` : ''}</option>`).join('');
    if (report && report.run_id !== latestReport?.run_id) {
      const viewed = history.findIndex(r => r.run_id === report.run_id);
      if (viewed >= 0) $('check-history').value = String(viewed);
    }
  }
  function render() {
    const results = visible(), stats = summarizeResults(results);
    if (selected && !results.some(r => r.instance_id === selected.instance_id)) {selected = null; clearResultHighlight();}
    $('compliance-summary').innerHTML = `<div class="check-metrics"><div><span>${t('规则数')}</span><b>${stats.rule_count}</b></div><div><span>${t('检查实例数')}</span><b>${stats.instance_count}</b></div></div><div class="check-counts"><span class="pass">PASS ${stats.PASS}</span><span class="fail">FAIL ${stats.FAIL}</span><span class="nc">NOT CHECKABLE ${stats['NOT CHECKABLE']}</span><span>${t('不适用')} ${stats.NOT_APPLICABLE}</span></div><p class="check-rates">${t('完成判定率')} ${percentage(stats.completed_determination_rate)}<br>${t('已判定检查通过率')} ${percentage(stats.determined_pass_rate)}</p>`;
    $('check-input-note').textContent = facts ? t('已载入事实；执行时核验模型、规则和输入事实哈希。') : t('未载入审核事实；缺证据的检查将显示 NOT CHECKABLE。');
    $('check-run-note').textContent = report ? `${report.is_synthetic ? t('合成 fixture，不能作为建筑合规证据') + ' · ' : ''}${t('运行')} ${report.run_id.slice(0,8)} · ${localTime(report.timestamp)} · SHA-256 ${report.model_sha256}` : t('尚无检查报告。执行规则或检查本地数据导出。');
    $('check-list').innerHTML = results.map(r => `<button class="check-card ${selected?.instance_id === r.instance_id ? 'active' : ''}" data-state="${esc(r.display_status)}" data-check="${esc(r.instance_id)}"><strong>${esc(r.rule_id)} · v${esc(r.rule_version)}</strong><span>${esc(r.display_status === 'NOT_APPLICABLE' ? t('不适用') : r.display_status)}</span><small>${esc(r.topic)} · ${esc(r.result_scope)} · ${esc(r.what.reason_code || '')}</small><small>${esc(r.where.scope_id || t('目标集合待审核'))} · ${r.where.global_ids.length} GlobalId</small></button>`).join('') || `<p class="empty">${t('没有匹配检查。清除筛选或执行所选规则。')}</p>`;
  }
  function accept(data, remember = true) {
    report = validateReport(data, getModel(), getLaws());
    if (remember) latestReport = report;
    selected = null; clearResultHighlight();
    options(); render(); refreshAppearance();
  }
  async function load() {
    const token = ++loadToken, model = getModel();
    report = null; latestReport = null; selected = null; facts = null; history = []; $('check-dialog').close();
    $('check-current-object').checked = false; $('check-rule').value = ''; $('check-storey').value = '';
    try {
      const [catalog, snapshot] = await Promise.all([
        fetch('./data/check-contracts.json').then(r => {if (!r.ok) throw Error(t('无法读取规则契约')); return r.json();}),
        fetch(`./data/compliance-${model.id}.json`, {cache:'no-store'}).then(r => {if (!r.ok) throw Error(t('尚无检查报告。执行规则或检查本地数据导出。')); return r.json();})]);
      if (token !== loadToken) return;
      contracts = catalog.rules; accept(snapshot);
      await loadHistory(token);
    } catch (e) { if (token === loadToken) {options(); render(); $('check-run-note').textContent = e.message;} }
  }
  async function loadHistory(token = loadToken) {
    try {
      const response = await fetch(`/api/history?model_id=${encodeURIComponent(getModel().id)}`, {cache:'no-store'});
      if (response.ok) {
        const value = await response.json();
        if (token === loadToken && Array.isArray(value)) {history = value; options();}
      }
    } catch { /* Static snapshots still work without the Python server. */ }
  }
  function detail(result) {
    const r = result, why = r.why, what = r.what;
    const law = getLaws().find(l => l.id === why.source_node_id);
    const pages = why.fragments.map(f => `${f.pdf_page_number} / ${f.source_pdf_page}`).join(', ');
    const pdfUrl = `./data/${why.pdf_file}#page=${why.fragments[0].pdf_page_number}`;
    const value = v => v == null ? '—' : typeof v === 'object' ? JSON.stringify(v) : String(v);
    $('check-detail').innerHTML = `<span class="badge">${esc(r.display_status)} · ${esc(r.result_scope)}</span><h3>${esc(r.rule_id)} · v${esc(r.rule_version)}</h3><section class="check-section"><h3>Why</h3><p>${esc(why.source_node_id)} · ${t('提取页 / 原书页')} ${esc(pages)}</p><p class="law-full">${esc(why.text)}</p><p class="evidence">${esc(why.source_pdf)}<br>SHA-256 ${esc(why.sha256)}<br>${t('规则契约')} ${esc(why.contract_sha256)}</p><a href="${esc(pdfUrl)}" target="_blank" rel="noopener">${t('查看源 PDF')}</a> <button data-check-source="${esc(law.id)}">${t('条件与例外依据')}</button><details><summary>${t('适用性与例外')}</summary><pre class="props">${esc(JSON.stringify(why.applicability, null, 2))}</pre></details></section><section class="check-section"><h3>What</h3><dl class="metadata"><dt>${t('检查函数')}</dt><dd>${esc(what.check_function)}</dd><dt>${t('要求值')}</dt><dd>${esc(value(what.required))}</dd><dt>${t('实际值')}</dt><dd>${esc(value(what.actual))}</dd><dt>${t('单位 / 比较符')}</dt><dd>${esc(what.unit || '—')} / ${esc(what.comparison)}</dd><dt>${t('容差')}</dt><dd>${esc(what.tolerance)} · ${esc(what.tolerance_basis)}</dd><dt>${t('原因')}</dt><dd>${esc(what.reason_code || '—')}</dd></dl><p class="muted">${esc(what.explanation)}</p><p class="muted">${esc(what.remediation || '')}</p><p class="evidence">${t('结论仅覆盖子检查范围；不代表整条款或建筑通过。')}</p></section><section class="check-section"><h3>Where</h3><p class="evidence">${esc(r.where.model_id)} · SHA-256 ${esc(r.where.model_sha256)}<br>${esc(r.where.scope_id || t('目标集合待审核'))} · ${esc(r.where.target_binding)}</p><div class="relation-elements">${r.where.objects.map(o => `<button data-check-object="${esc(o.global_id)}">${esc(o.name || o.ifc_type)} · ${esc(o.ifc_type)}<br>${esc(o.global_id)} · ${esc(o.storey?.name || o.storey?.global_id || t('未归属楼层'))}</button>`).join('')}</div></section><details class="check-section"><summary>${t('运行与输入证据')}</summary><pre class="props">${esc(JSON.stringify(r.run, null, 2))}</pre></details>`;
    if (!$('check-dialog').open) $('check-dialog').showModal();
  }
  function select(id) {
    const result = report?.results.find(r => r.instance_id === id);
    if (!result) return;
    selected = result; highlight(result); render(); detail(result);
  }
  $('compliance-tab').onclick = () => { $('compliance-view').hidden = false; $('candidate-view').hidden = true; $('compliance-tab').setAttribute('aria-selected', true); $('candidates-tab').setAttribute('aria-selected', false); };
  $('candidates-tab').onclick = () => { $('compliance-view').hidden = true; $('candidate-view').hidden = false; $('compliance-tab').setAttribute('aria-selected', false); $('candidates-tab').setAttribute('aria-selected', true); };
  for (const id of ['check-rule', 'check-status', 'check-storey', 'check-topic', 'check-current-object']) $(id).onchange = () => {selected = null; clearResultHighlight(); render(); refreshAppearance();};
  $('close-check').onclick = () => $('check-dialog').close();
  document.addEventListener('click', e => {
    const card = e.target.closest('[data-check]'); if (card) select(card.dataset.check);
    const source = e.target.closest('[data-check-source]'); if (source) {$('check-dialog').close(); openLaw(source.dataset.checkSource);}
    const object = e.target.closest('[data-check-object]'); if (object) {$('check-dialog').close(); selectElement(object.dataset.checkObject);}
  });
  $('load-check-facts').onclick = () => $('check-facts-file').click();
  $('check-facts-file').onchange = async e => {
    const file = e.target.files[0]; if (!file) return;
    try {
      const value = JSON.parse(await file.text());
      if (!value || typeof value !== 'object' || !value.facts_by_rule || Array.isArray(value.facts_by_rule)) throw Error(t('事实文件须包含 facts_by_rule 对象'));
      facts = value; render();
    } catch (error) {$('check-run-note').textContent = error.message;}
    e.target.value = '';
  };
  $('run-checks').onclick = async () => {
    const token = loadToken, model = getModel(), selectedRule = $('check-rule').value;
    const ids = contracts.filter(r => getChapters().has(r.chapter) && (!selectedRule || r.rule_id === selectedRule)).map(r => r.rule_id);
    if (!ids.length) {$('check-run-note').textContent = t('请选择章节及规则后执行。'); return;}
    $('run-checks').disabled = true; $('check-run-note').textContent = t('正在执行 Python 检查…');
    try {
      const response = await fetch('/api/run', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({model_id:model.id, rule_ids:ids, facts})});
      if (response.status === 501 || response.status === 404) throw Error(t('重新检查需从 viewer 目录运行 npm run serve。'));
      const value = await response.json();
      if (!response.ok) throw Error(value.error || t('检查执行失败'));
      if (token === loadToken) {accept(value); await loadHistory(token);}
    } catch (error) {if (token === loadToken) $('check-run-note').textContent = error.message;}
    finally {$('run-checks').disabled = false;}
  };
  $('check-history').onchange = e => {
    try {accept(e.target.value === '' ? latestReport : history[Number(e.target.value)], false);} catch (error) {$('check-run-note').textContent = error.message;}
  };
  $('export-checks').onclick = () => {
    if (!report) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], {type:'application/json'}));
    const a = document.createElement('a'); a.href = url; a.download = `compliance-${report.model_id}-${report.run_id}.json`; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  return {load, render:() => {options(); render(); if ($('check-dialog').open && selected) detail(selected);},
    onElement:() => {selected = null; $('check-current-object').checked = true; render();}, clear:() => {selected = null; $('check-current-object').checked = false; render();},
    colorFor:id => {
      const status = selected && visible().some(r => r.instance_id === selected.instance_id) && selected.where.global_ids.includes(id)
        ? selected.display_status : objectResultStatus(visible(), id);
      return resultColors[status] ?? null;
    }};
}

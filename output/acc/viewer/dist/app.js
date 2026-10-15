import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {t, linkReason, getLanguage, setLanguage, languageStorageKey} from './i18n.js';
import {buildChapterIndex, filterLawsByChapter, lawPdfUrl, relatedLaws, relatedElements, searchLaw, validateCustomLinks} from './core.js';
import {createCompliancePanel} from './compliance-panel.js';

const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const code = law => {
  const id = law.id.replace('ibc2021-', '');
  const parent = laws.get(law.parent);
  const parentLabel = parent?.label || law.parent?.replace('ibc2021-', '') || '';
  if (law.type === 'exception') return `${parentLabel} / ${t('例外')}`;
  if (law.type === 'list_item') return `${parentLabel} / ${t('项 {n}', {n:law.label?.split('-')[0] || ''})}`;
  return law.label || id;
};
let regulations, manifest, model, records = new Map(), laws = new Map(), index;
let selectedElement = null, selectedLaw = null, mode = 'all', selectionMode = null;
let custom = [], highlighted = new Set(), isolate = false, showSpaces = false, ghost = false;
let renderer, scene, camera, controls, group, meshes = new Map(), loadSerial = 0;
const storageKey = 'ifc-regulation-workbench.links.v1';
const modelCache = new Map();
const chapterStorageKey = 'ifc-regulation-workbench.chapters.v1';
let selectedChapters = new Set();
let compliance;
function renderChapterOptions() {
  if (!regulations) return;
  $('chapter-options').innerHTML = regulations.chapters.map(chapter => `<label class="chapter-choice"><input type="checkbox" data-chapter="${chapter.id}" ${selectedChapters.has(chapter.id) ? 'checked' : ''}><span>${esc(t('第 {n} 章 · {title}', {n:chapter.id, title:chapter.title}))}</span><span class="count">${chapter.lawCount}</span></label>`).join('');
}
function changeChapter(chapter, checked) {
  if (checked) selectedChapters.add(chapter); else selectedChapters.delete(chapter);
  try { localStorage.setItem(chapterStorageKey, JSON.stringify([...selectedChapters])); } catch { }
  if (!model) { renderChapterOptions(); return; }
  if (selectedLaw && !selectedChapters.has(laws.get(selectedLaw).chapter)) {
    selectedLaw = null; $('law-dialog').close();
    selectionMode = selectedElement ? 'element' : null;
    highlighted = selectedElement ? (meshes.has(selectedElement) ? new Set([selectedElement]) : descendantIds(selectedElement)) : new Set();
    isolate = false; $('isolate').setAttribute('aria-pressed', 'false');
  }
  compliance?.render(); reindex(); updateAppearance(); renderElements(); renderLaws(); renderInspector(); updateSelectionBar();
}
function applyStaticLanguage() {
  document.documentElement.lang = getLanguage() === 'en' ? 'en' : 'zh-CN';
  document.title = t('IFC · 法规双向查询');
  document.querySelectorAll('[data-i18n]').forEach(el => el.textContent = t(el.dataset.i18n));
  for (const attribute of ['aria-label', 'placeholder', 'title']) {
    document.querySelectorAll(`[data-i18n-${attribute}]`).forEach(el => el.setAttribute(attribute, t(el.getAttribute(`data-i18n-${attribute}`))));
  }
  document.querySelectorAll('[data-language]').forEach(el => el.setAttribute('aria-pressed', el.dataset.language === getLanguage()));
  if ($('type-filter').options.length) $('type-filter').options[0].textContent = t('全部 IFC 类型');
  if (manifest) {
    for (const option of $('model-select').options) option.textContent = t(manifest.find(m => m.id === option.value).name);
  }
  renderChapterOptions();
}
function changeLanguage(value) {
  setLanguage(value);
  try { localStorage.setItem(languageStorageKey, getLanguage()); } catch { /* Switching still works without storage. */ }
  applyStaticLanguage(); $('toast').hidden = true;
  if (model) {
    compliance?.render();
    renderElements(); renderLaws(); renderInspector(); updateSelectionBar();
    if ($('law-dialog').open && selectedLaw) openLaw(selectedLaw);
  }
}
try { setLanguage(localStorage.getItem(languageStorageKey)); } catch { setLanguage('zh'); }
applyStaticLanguage();
document.addEventListener('click', e => {
  const control = e.target.closest('[data-language]');
  if (control) changeLanguage(control.dataset.language);
});
function toast(message) { $('toast').textContent = message; $('toast').hidden = false; clearTimeout(toast.timer); toast.timer = setTimeout(() => $('toast').hidden = true, 4500); }
async function getJSON(url) { const r = await fetch(url, {cache:'no-store'}); if (!r.ok) throw new Error(t('读取失败：{url} ({status})', {url, status:r.status})); return r.json(); }
function initScene() {
  const viewport = $('viewport');
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(38, 1, .01, 10000);
  camera.up.set(0, 0, 1);
  renderer = new THREE.WebGLRenderer({antialias: true, alpha: true});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setClearColor(0x000000, 0);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  viewport.appendChild(renderer.domElement);
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = .08;
  scene.add(new THREE.HemisphereLight(0xffffff, 0x8097a7, 2.4));
  const sun = new THREE.DirectionalLight(0xffffff, 3);
  sun.position.set(15, -20, 30); scene.add(sun);
  const fill = new THREE.DirectionalLight(0xc4e7fa, 1.2); fill.position.set(-12, 10, 6); scene.add(fill);
  new ResizeObserver(() => {
    const w = viewport.clientWidth, h = viewport.clientHeight;
    renderer.setSize(w, h); camera.aspect = w / h; camera.updateProjectionMatrix();
  }).observe(viewport);
  const raycaster = new THREE.Raycaster(), pointer = new THREE.Vector2();
  function pick(event) {
    const rect = renderer.domElement.getBoundingClientRect();
    pointer.set((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1);
    raycaster.setFromCamera(pointer, camera);
    return raycaster.intersectObjects([...meshes.values()].filter(m => m.visible), false)[0]?.object;
  }
  let down = null;
  renderer.domElement.addEventListener('pointerdown', e => { down = {x: e.clientX, y: e.clientY, button: e.button}; });
  renderer.domElement.addEventListener('pointerup', e => {
    if (down && down.button === 0 && Math.hypot(e.clientX - down.x, e.clientY - down.y) < 5) {
      const mesh = pick(e); if (mesh) selectElement(mesh.userData.id);
    }
    down = null;
  });
  renderer.domElement.addEventListener('pointermove', e => {
    const mesh = pick(e), label = $('hover-label');
    label.hidden = !mesh || e.buttons !== 0;
    renderer.domElement.style.cursor = mesh && !e.buttons ? 'pointer' : 'grab';
    if (!label.hidden) {
      const r = records.get(mesh.userData.id), rect = viewport.getBoundingClientRect();
      label.textContent = `${r.name} · ${r.type}`;
      label.style.left = Math.min(e.clientX - rect.left + 12, viewport.clientWidth - 235) + 'px';
      label.style.top = Math.max(4, e.clientY - rect.top - 35) + 'px';
    }
  });
  renderer.domElement.addEventListener('pointerleave', () => $('hover-label').hidden = true);
  renderer.setAnimationLoop(() => { controls.update(); renderer.render(scene, camera); });
}
function baseColor(type) {
  if (type === 'IfcDoor') return 0x548d88;
  if (type === 'IfcWindow') return 0x80acc6;
  if (type === 'IfcSpace') return 0x91d0d9;
  if (type === 'IfcSite') return 0x9daea4;
  if (/Roof|Slab/.test(type)) return 0xb5bcc1;
  return 0xd8dfe3;
}
function makeGeometry() {
  if (group) { scene.remove(group); group.traverse(o => { o.geometry?.dispose(); o.material?.dispose(); }); }
  group = new THREE.Group(); meshes.clear();
  for (const r of model.records) {
    if (!r.geometry?.faces.length) continue;
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(r.geometry.vertices, 3));
    geometry.setIndex(r.geometry.faces); geometry.computeVertexNormals();
    const material = new THREE.MeshStandardMaterial({color: baseColor(r.type), roughness: .8, metalness: .03, side: THREE.DoubleSide});
    const mesh = new THREE.Mesh(geometry, material); mesh.userData.id = r.id;
    group.add(mesh); meshes.set(r.id, mesh);
    const edges = new THREE.LineSegments(new THREE.EdgesGeometry(geometry, 30), new THREE.LineBasicMaterial({color:0x45647a, transparent:true, opacity:.22}));
    mesh.add(edges);
  }
  scene.add(group); updateAppearance();
  const building = model.records.find(r => r.type === 'IfcBuilding');
  const buildingIds = building ? [...descendantIds(building.id)].filter(id => meshes.has(id)) : [];
  fitCamera(buildingIds.length ? buildingIds : [...meshes.keys()]);
}
function descendantIds(id) {
  const found = new Set([id]); let added = true;
  while (added) { added = false; for (const r of model.records) if (!found.has(r.id) && r.parents.some(x => found.has(x))) { found.add(r.id); added = true; } }
  return found;
}
function fitCamera(ids) {
  if (!camera) return;
  const box = new THREE.Box3();
  ids.forEach(id => { const mesh = meshes.get(id); if (mesh) { mesh.updateWorldMatrix(true, false); box.union(new THREE.Box3().setFromObject(mesh)); } });
  if (box.isEmpty()) { toast(t('关联对象没有可显示几何，可在构件列表查看属性。')); return; }
  const center = box.getCenter(new THREE.Vector3()), size = box.getSize(new THREE.Vector3());
  const radius = Math.max(size.length() / 2, .5);
  const distance = radius / Math.sin(THREE.MathUtils.degToRad(camera.fov / 2)) * Math.max(1, 1 / camera.aspect) * 1.08;
  const direction = new THREE.Vector3(1, -1.35, .9).normalize();
  camera.position.copy(center).addScaledVector(direction, distance);
  camera.near = Math.max(.005, radius / 1000); camera.far = Math.max(1000, distance * 100);
  camera.updateProjectionMatrix(); controls.target.copy(center); controls.update();
}
function updateAppearance() {
  for (const [id, mesh] of meshes) {
    const r = records.get(id), hit = highlighted.has(id);
    const complianceColor = compliance?.colorFor(id);
    mesh.visible = !(isolate && highlighted.size && !hit) && (r.type !== 'IfcSpace' || showSpaces || hit) && (r.type !== 'IfcOpeningElement' || hit);
    mesh.material.color.setHex(complianceColor ?? (hit ? 0x00a4a1 : baseColor(r.type)));
    mesh.material.emissive.setHex(hit ? complianceColor ?? 0x003f42 : 0x000000);
    if (hit && complianceColor != null) mesh.material.emissive.multiplyScalar(.12);
    const faded = highlighted.size > 0 && !hit;
    mesh.material.opacity = r.type === 'IfcSpace' ? (hit ? .5 : .15) : ghost ? (hit ? .9 : .16) : faded ? .32 : r.type === 'IfcWindow' ? .65 : 1;
    mesh.material.transparent = mesh.material.opacity < 1;
    mesh.material.depthWrite = mesh.material.opacity >= .6;
    mesh.children.forEach(e => { e.material.opacity = faded || ghost ? .06 : .28; });
  }
}
function reindex() { index = buildChapterIndex(model.records, custom.filter(x => x.modelId === model.id && x.modelSha256 === model.sha256), [...laws.values()], selectedChapters); }
async function loadModel(id) {
  const serial = ++loadSerial; $('loading').hidden = false; $('loading').textContent = t('正在读取真实 IFC 几何…');
  try {
    const data = modelCache.get(id) || await getJSON(`./data/${id}.json`);
    modelCache.set(id, data); if (serial !== loadSerial) return;
    model = data; records = new Map(data.records.map(r => [r.id, r]));
    selectedElement = null; selectedLaw = null; selectionMode = null; highlighted = new Set(); isolate = false;
    $('isolate').setAttribute('aria-pressed', 'false');
    reindex(); $('element-total').textContent = data.records.length; $('schema-label').textContent = data.schema;
    const types = [...new Set(data.records.map(r => r.type))].sort();
    $('type-filter').innerHTML = `<option value="">${t('全部 IFC 类型')}</option>` + types.map(t => `<option>${esc(t)}</option>`).join('');
    $('element-search').value = ''; $('law-dialog').close();
    makeGeometry(); renderElements(); renderLaws(); renderInspector(); updateSelectionBar();
    await compliance?.load();
    $('loading').hidden = true;
  } catch (e) { $('loading').textContent = e.message; toast(e.message); }
}
function renderElements() {
  const q = $('element-search').value.toLowerCase(), type = $('type-filter').value;
  const items = model.records.filter(r => (!type || r.type === type) && `${r.name} ${r.type} ${r.id} ${r.stepId}`.toLowerCase().includes(q));
  $('element-list').innerHTML = items.map(r => `<button class="element-row ${selectedElement === r.id ? 'selected' : ''} ${highlighted.has(r.id) ? 'related' : ''}" data-element="${esc(r.id)}" aria-pressed="${selectedElement === r.id}"><span class="name"><span class="dot ${meshes.has(r.id) ? 'rendered' : 'absent'}"></span>${esc(r.name)}</span><small><span>${esc(r.type)}</span><span>#${r.stepId}</span></small></button>`).join('') || `<div class="empty">${t('没有匹配构件。清除名称或类型筛选后重试。')}</div>`;
}
function lawTitle(law) {
  if (law.heading && !/^\d+(?:\.\d+)*$/.test(law.heading)) return law.heading;
  return law.text.replace(/^\d{4}(?:\.\d+)*\s+/, '').split(/\.(?:\s|$)|\n/)[0].slice(0, 100);
}
function renderLaws() {
  const relevant = new Set(selectedElement ? relatedLaws(index, selectedElement) : []);
  const direct = new Set((index.byElement.get(selectedElement) || []).filter(x => x.kind === 'direct' || x.kind === 'manual').map(x => x.lawId));
  $('related-count').textContent = relevant.size;
  const chapterLaws = filterLawsByChapter([...laws.values()], selectedChapters);
  $('law-total').textContent = chapterLaws.length;
  $('chapter-scope-summary').textContent = selectedChapters.size ? t('已选择 {chapters}；共 {n} 个结构化条目。', {chapters:[...selectedChapters].sort().join(', '), n:chapterLaws.length}) : t('尚未勾选章节。请至少选择一个 IBC 章节。');
  $('related-tab').setAttribute('aria-selected', mode === 'related'); $('all-tab').setAttribute('aria-selected', mode === 'all');
  $('direct-only').disabled = mode !== 'related';
  const matches = chapterLaws.filter(l => searchLaw(l, $('law-search').value) && (mode !== 'related' || relevant.has(l.id)) && (mode !== 'related' || !$('direct-only').checked || direct.has(l.id)));
  $('law-result-count').textContent = t('{n} 条', {n:matches.length});
  $('law-list').innerHTML = matches.map(l => {
    const count = relatedElements(index, l.id).length;
    const kind = direct.has(l.id) ? t('直接候选') : relevant.has(l.id) ? t('上下文候选') : count ? t('候选关联') : t('尚无关联');
    return `<article class="law-card ${selectedLaw === l.id ? 'active' : ''}" data-law-card="${esc(l.id)}"><button class="law-main" data-law="${esc(l.id)}"><span class="law-code">${esc(code(l))}</span><span class="law-chapter">${esc(t('第 {n} 章 · {title}', {n:l.chapter, title:l.chapterTitle}))}</span><h3>${esc(lawTitle(l))}</h3><p>${esc(l.text)}</p></button><div class="law-card-foot"><span class="badge">${kind}</span><span class="law-link-count">${t('{n} 个对象', {n:count})}</span><button data-law-detail="${esc(l.id)}">${t('原文 / 关联')}</button></div></article>`;
  }).join('') || `<div class="empty">${!selectedChapters.size ? t('尚未勾选章节。请至少选择一个 IBC 章节。') : mode === 'related' && !selectedElement ? t('请先在三维视图或左侧列表中选择构件。') : t('没有匹配条目。可切换到全部条目或清除搜索。')}</div>`;
}
function updateSelectionBar() {
  if (selectionMode === 'law' && selectedLaw) {
    const l = laws.get(selectedLaw), ids = relatedElements(index, selectedLaw), drawn = ids.filter(id => meshes.has(id)).length;
    $('selection-title').textContent = t('条款 {code} → {n} 个关联对象', {code:code(l), n:ids.length});
    $('selection-subtitle').textContent = t('{drawn} 个有几何，{other} 个仅有属性 · 候选关联待审核', {drawn, other:ids.length - drawn});
  } else if (selectedElement) {
    const r = records.get(selectedElement);
    $('selection-title').textContent = t('{name} → {n} 个相关条目', {name:r.name, n:relatedLaws(index, r.id).length});
    $('selection-subtitle').textContent = `${r.type} · #${r.stepId} · ${meshes.has(r.id) ? t('已高亮构件') : t('没有可用几何，显示属性与关联')}`;
  } else {
    $('selection-title').textContent = t('选择模型中的构件'); $('selection-subtitle').textContent = t('或点击右侧法规，查看对应构件');
  }
}
function renderInspector() {
  $('test-status').textContent = model.precheck.status;
  if (selectionMode === 'law' && selectedLaw) {
    const l = laws.get(selectedLaw), ids = relatedElements(index, selectedLaw);
    $('element-detail').innerHTML = `<b>${esc(code(l))} · ${esc(lawTitle(l))}</b><p class="muted">${ids.length ? t('相关构件已高亮。点击名称查询构件，或打开原文查看关联依据。') : t('当前模型尚无关联对象。可选择构件后在原文窗口补充关联。')}</p><div class="relation-elements">${ids.map(id => `<button data-element="${esc(id)}">${esc(records.get(id).name)}</button>`).join('')}<button data-law-detail="${esc(l.id)}">${t('查看完整原文')}</button></div>`;
    return;
  }
  if (!selectedElement) {
    const p = model.precheck, g = p.checks.geometry;
    $('element-detail').innerHTML = `<p class="muted">${model.filename} · ${t('全量几何生成 {ok}/{total}', {ok:g.generated, total:g.represented_products})} · Space Boundary ${p.object_inventory.IfcRelSpaceBoundary}</p><p class="muted">${t('模型预检仅评估信息质量；法规结果见合规检查。')}</p><details><summary>${t('来源与文件指纹')}</summary><p class="evidence">${esc(model.source.repository)}<br>SHA-256 ${esc(model.sha256)}</p></details>`;
    return;
  }
  const r = records.get(selectedElement);
  const relevantFailures = model.precheck.checks.ids?.specifications.flatMap(s => (s.failures || []).filter(f => f.guid === r.id).map(f => `${s.name}: ${f.property} — ${f.reason}`)) || [];
  $('element-detail').innerHTML = `<dl class="metadata"><dt>${t('名称 / 类型')}</dt><dd>${esc(r.name)} / ${esc(r.type)}</dd><dt>GUID</dt><dd class="mono">${esc(r.id)}</dd><dt>STEP ID</dt><dd>#${r.stepId}</dd><dt>${t('模型几何')}</dt><dd>${meshes.has(r.id) ? t('生成成功') : r.geometryError ? t('生成失败；未使用替代形状') : t('对象没有可显示几何')}</dd></dl>${relevantFailures.length ? `<p class="muted">IDS: ${esc(relevantFailures.join('; '))}</p>` : ''}${r.geometryError ? `<details><summary>${t('几何错误')}</summary><p class="evidence">${esc(r.geometryError)}</p></details>` : ''}<details><summary>${t('全部属性集与数量')}</summary><pre class="props">${esc(JSON.stringify(r.properties, null, 2))}</pre></details><details><summary>${t('关联依据')}</summary><div class="evidence">${[...new Set(index.byElement.get(r.id).map(x => x.reason))].map(linkReason).map(esc).join('<br>')}</div></details>`;
}
function selectElement(id) {
  if (!records.has(id)) return;
  selectedElement = id; selectedLaw = null; selectionMode = 'element'; mode = 'related';
  highlighted = meshes.has(id) ? new Set([id]) : descendantIds(id);
  $('law-search').value = ''; $('direct-only').checked = false;
  compliance?.onElement();
  updateAppearance(); renderElements(); renderLaws(); renderInspector(); updateSelectionBar();
}
function selectLaw(id) {
  if (!laws.has(id) || !selectedChapters.has(laws.get(id).chapter)) return;
  selectedLaw = id; selectionMode = 'law'; highlighted = new Set(relatedElements(index, id));
  updateAppearance(); renderElements(); renderLaws(); renderInspector(); updateSelectionBar();
}
function openLaw(id) {
  selectLaw(id);
  const law = laws.get(id), ids = relatedElements(index, id), fragments = law.fragments;
  const links = selectedElement ? (index.byElement.get(selectedElement) || []).filter(x => x.lawId === id) : [];
  const tables = law.tables?.length ? law.tables : law.type === 'table' ? Object.values(regulations.tables).filter(t => t.source_pdf_page === fragments[0]?.source_pdf_page) : [];
  $('law-detail').innerHTML = `<span class="badge">${esc(law.type)} · ${t('候选关联待审核')}</span><h3>${esc(code(law))} · ${esc(lawTitle(law))}</h3><div class="law-full">${esc(law.text)}</div>${tables.map(t => `<table>${t.cells.map((row,i) => `<tr>${row.map(c => `<${i ? 'td' : 'th'}>${esc(c)}</${i ? 'td' : 'th'}>`).join('')}</tr>`).join('')}</table>`).join('')}<div class="detail-actions"><button id="highlight-law">${t('高亮 {n} 个关联对象', {n:ids.length})}</button>${selectedElement ? `<button id="link-law">${custom.some(x => x.modelId === model.id && x.elementId === selectedElement && x.lawId === id) ? t('移除补充关联') : t('关联到当前构件')}</button>` : ''}${fragments[0] ? `<a target="_blank" rel="noopener" href="${esc(lawPdfUrl(law))}">${t('查看源 PDF · 原书第 {page} 页 ↗', {page:fragments[0].source_pdf_page})}</a>` : ''}</div><p class="evidence">${t('来源：')}${esc(law.sourceFile)}<br>${t('提取页 {extracted} · 原书页 {book}', {extracted:[...new Set(fragments.map(f => f.pdf_page_number))].join(', '), book:[...new Set(fragments.map(f => f.source_pdf_page))].join(', ')})}<br>SHA-256 ${esc(law.sha256)}${law.quality.requires_review ? `<br>${t('该条目的提取质量需复核')}` : ''}</p><div class="reasons">${links.length ? `<b>${esc(t('与当前构件 {name} 的关联依据', {name:records.get(selectedElement).name}))}</b><br>${[...new Set(links.map(x => x.reason))].map(linkReason).map(esc).join('<br>')}` : t('当前关系来自 IFC 类型候选映射和法规上下文；用途、适用条件及例外尚未审批。未关联不等于不适用。')}</div><div class="relation-elements">${ids.map(e => `<button data-dialog-element="${esc(e)}">${esc(records.get(e).name)} · ${esc(records.get(e).type)}</button>`).join('')}</div>${law.context?.unresolved_references.length ? `<details class="reasons"><summary>${t('尚未解析的跨章节 / 外部引用')}</summary><pre class="props">${esc(JSON.stringify(law.context.unresolved_references, null, 2))}</pre></details>` : ''}`;
  $('highlight-law').onclick = () => { selectLaw(id); $('law-dialog').close(); };
  if (selectedElement) $('link-law').onclick = () => {
    const exists = custom.some(x => x.modelId === model.id && x.elementId === selectedElement && x.lawId === id);
    if (exists) custom = custom.filter(x => !(x.modelId === model.id && x.elementId === selectedElement && x.lawId === id));
    else custom.push({modelId:model.id, modelSha256:model.sha256, elementId:selectedElement, lawId:id});
    try { localStorage.setItem(storageKey, JSON.stringify(custom)); } catch { toast(t('浏览器无法保存关联，请导出 JSON 保留修改。')); }
    reindex(); openLaw(id); toast(exists ? t('已移除补充关联') : t('已补充双向关联；适用性仍需审核'));
  };
  if (!$('law-dialog').open) $('law-dialog').showModal();
}
function bindUI() {
  $('chapter-options').onchange = e => { if (e.target.matches('[data-chapter]')) changeChapter(Number(e.target.dataset.chapter), e.target.checked); };
  $('model-select').onchange = e => loadModel(e.target.value);
  $('element-search').oninput = renderElements; $('type-filter').onchange = renderElements;
  $('law-search').oninput = renderLaws; $('direct-only').onchange = renderLaws;
  $('related-tab').onclick = () => { mode = 'related'; renderLaws(); };
  $('all-tab').onclick = () => { mode = 'all'; renderLaws(); };
  document.addEventListener('click', e => {
    const element = e.target.closest('[data-element]'); if (element) selectElement(element.dataset.element);
    const law = e.target.closest('[data-law]'); if (law) selectLaw(law.dataset.law);
    const detail = e.target.closest('[data-law-detail]'); if (detail) openLaw(detail.dataset.lawDetail);
    const dialogElement = e.target.closest('[data-dialog-element]'); if (dialogElement) { $('law-dialog').close(); selectElement(dialogElement.dataset.dialogElement); fitCamera([...highlighted]); }
  });
  $('close-law').onclick = () => $('law-dialog').close();
  $('fit').onclick = () => fitCamera([...meshes.keys()]);
  $('focus').onclick = () => highlighted.size ? fitCamera([...highlighted]) : toast(t('先选择构件或法规再定位。'));
  $('isolate').onclick = () => { if (!highlighted.size) { toast(t('先选择有几何的关联对象再隔离。')); return; } isolate = !isolate; $('isolate').setAttribute('aria-pressed', isolate); updateAppearance(); };
  $('spaces').onclick = () => { showSpaces = !showSpaces; $('spaces').setAttribute('aria-pressed', showSpaces); updateAppearance(); };
  $('ghost').onclick = () => { ghost = !ghost; $('ghost').setAttribute('aria-pressed', ghost); updateAppearance(); };
  $('clear-selection').onclick = () => {
    selectedElement = null; selectedLaw = null; selectionMode = null; highlighted.clear(); isolate = false;
    compliance?.clear();
    $('isolate').setAttribute('aria-pressed', false); mode = 'all'; updateAppearance(); renderElements(); renderLaws(); renderInspector(); updateSelectionBar();
  };
  $('export-links').onclick = () => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(custom, null, 2)], {type:'application/json'}));
    const a = document.createElement('a'); a.href = url; a.download = 'ifc-regulation-links.json'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    toast(t('已导出 {n} 条补充关联', {n:custom.length}));
  };
  $('import-links').onclick = () => $('import-file').click();
  $('import-file').onchange = async e => {
    const file = e.target.files[0]; if (!file) return;
    try {
      const allModels = await Promise.all(manifest.map(async m => { const data = modelCache.get(m.id) || await getJSON(`./data/${m.id}.json`); modelCache.set(m.id, data); return data; }));
      const imported = validateCustomLinks(JSON.parse(await file.text()), allModels, [...laws.values()]);
      custom = validateCustomLinks([...custom, ...imported], allModels, [...laws.values()]);
      localStorage.setItem(storageKey, JSON.stringify(custom)); reindex();
      if (selectedLaw) selectLaw(selectedLaw); else if (selectedElement) selectElement(selectedElement); else renderLaws();
      toast(t('已导入 {n} 条关联，模型哈希与 GUID 已核对', {n:imported.length}));
    } catch (error) { toast(t(error.message)); }
    e.target.value = '';
  };
}
async function start() {
  try {
    [regulations, manifest] = await Promise.all([getJSON('./data/regulations.json'), getJSON('./data/models.json')]);
    laws = new Map(regulations.laws.map(l => [l.id, l]));
    const available = new Set(regulations.chapters.map(chapter => chapter.id));
    try {
      const saved = JSON.parse(localStorage.getItem(chapterStorageKey));
      selectedChapters = Array.isArray(saved) ? new Set(saved.map(Number).filter(id => available.has(id))) : available;
    } catch { selectedChapters = available; }
    renderChapterOptions();
    try { const value = JSON.parse(localStorage.getItem(storageKey) || '[]'); custom = Array.isArray(value) ? value.filter(x => x && typeof x.modelId === 'string' && typeof x.modelSha256 === 'string' && typeof x.elementId === 'string' && laws.has(x.lawId)) : []; } catch { custom = []; }
    $('model-select').innerHTML = manifest.map(m => `<option value="${esc(m.id)}">${esc(t(m.name))}</option>`).join('');
    initScene(); bindUI();
    compliance = createCompliancePanel({$, esc, t, getModel:() => model, getLaws:() => [...laws.values()],
      getChapters:() => selectedChapters, getElement:() => selectedElement,
      refreshAppearance:updateAppearance, openLaw, selectElement:id => {selectElement(id); fitCamera([id]);},
      clearResultHighlight:() => {if (selectionMode === 'check') {highlighted.clear(); selectionMode = null; renderElements(); renderInspector(); updateSelectionBar();}},
      highlight:result => {
        selectedLaw = null; if (!$('check-current-object').checked) selectedElement = null;
        selectionMode = 'check'; highlighted = new Set(result.where.global_ids);
        updateAppearance(); renderElements(); renderLaws(); renderInspector(); updateSelectionBar(); fitCamera([...highlighted]);
        $('selection-title').textContent = `${result.rule_id} · ${result.display_status}`;
        $('selection-subtitle').textContent = `${result.result_scope} · ${result.where.target_binding}`;
      }});
    await loadModel(manifest[0].id);
  } catch (e) {
    $('loading').innerHTML = `<div class="error-box">${esc(t(e.message))}<br>${t('请使用本地 HTTP 服务打开，或确认浏览器支持 WebGL。')}</div>`;
  }
}
start();

"""Export real IFC geometry and traceable candidate regulation links for Three.js."""
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

VIEWER = Path(__file__).resolve().parent
ACC = VIEWER.parent
ROOT = ACC.parents[1]
sys.path.insert(0, str(ACC / '.python_deps'))
sys.path.insert(0, str(ACC / 'src'))
from model_catalog import model_catalog
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')

def main():
    doc = read(ROOT / 'output/ibe_accessibility_structure/03_structured_document.json')
    contexts = read(ACC / 'rule_review_context.json')
    mappings = read(ACC / 'ibc_ifc_mapping.json')['mappings']
    candidates = read(ROOT / 'output/ibe_accessibility_structure/semantic_rdf/10_semantic_validated.json')['candidates']
    dsl = read(ROOT / 'output/ibe_accessibility_structure/semantic_rdf/10_dsl_rules.json')
    nodes = doc['nodes']
    table_by_number = {}
    for table in doc['tables'].values():
        preceding = []
        for node in nodes.values():
            captions = re.findall(r'\bTABLE\s+(\d{4}(?:\.\d+)*)', node['text_normalized'])
            for fragment in node['source_fragments']:
                if captions and fragment['pdf_page_number'] == table['pdf_page_number']:
                    box = fragment['bbox']
                    if box[0] < table['bbox'][2] and box[2] > table['bbox'][0] and box[1] <= table['bbox'][1]:
                        preceding.append((abs(table['bbox'][1] - box[3]), captions[-1]))
        if preceding:
            number = min(preceding)[1]
            table_by_number[number] = {**table, 'number': number}
    laws = []
    for key, node in nodes.items():
        evidence = contexts['evidence_nodes'][key]
        laws.append({'id': key, 'label': node['label'] or node['heading'] or node['type'],
                     'heading': node['heading'], 'type': node['type'], 'order': node['order'],
                     'parent': node['parent_id'], 'children': node['child_ids'],
                     'text': evidence['text'], 'sha256': evidence['sha256'],
                     'fragments': evidence['source_fragments'], 'quality': node['quality'],
                     'context': contexts['contexts'].get(key),
                     'tables': [table_by_number[n] for n in dict.fromkeys(re.findall(r'\bTABLE\s+(\d{4}(?:\.\d+)*)', evidence['text'], re.I)) if n in table_by_number]})
    save(VIEWER / 'dist/data/regulations.json', {'source': 'IBC 2021 · Chapter 11 Accessibility',
         'scope_note': '全部 305 个已结构化条目；完整 IBC 其他章节尚未结构化。关联为候选，需核验适用条件及例外。',
         'laws': laws, 'tables': doc['tables'], 'mappings': mappings,
         'candidate_count': len(candidates), 'dsl_rule_count': len(dsl.get('rules', []))})
    shutil.copy2(ROOT / 'IBE2021_11Accessibility.pdf', VIEWER / 'dist/data/IBC2021_Chapter11.pdf')
    summaries = []
    for entry in model_catalog():
        key, filename = entry['id'], entry['filename']
        path = ACC / 'models' / key / filename
        model = ifcopenshell.open(str(path))
        products = model.by_type('IfcProduct') + model.by_type('IfcProject') + model.by_type('IfcZone')
        products = {x.id(): x for x in products}.values()
        records = []
        settings = ifcopenshell.geom.settings()
        settings.set(settings.USE_WORLD_COORDS, True)
        for e in products:
            parents = [r.RelatingObject.GlobalId for r in getattr(e, 'Decomposes', ()) if r.is_a('IfcRelAggregates')]
            parents += [r.RelatingStructure.GlobalId for r in getattr(e, 'ContainedInStructure', ())]
            record = {'id': e.GlobalId, 'stepId': e.id(), 'name': e.Name or e.is_a(),
                      'type': e.is_a(), 'parents': list(dict.fromkeys(parents)),
                      'properties': ifcopenshell.util.element.get_psets(e),
                      'geometry': None, 'geometryError': None, 'links': []}
            if getattr(e, 'Representation', None):
                try:
                    shape = ifcopenshell.geom.create_shape(settings, e)
                    g = shape.geometry
                    record['geometry'] = {'vertices': list(g.verts), 'faces': list(g.faces)}
                except Exception as exc:
                    record['geometryError'] = str(exc)
            def link(law, kind, reason, seed):
                if law in nodes and not any(x['lawId'] == law and x['kind'] == kind and x['seed'] == seed for x in record['links']):
                    record['links'].append({'lawId': law, 'kind': kind, 'reason': reason, 'seed': seed,
                                            'status': 'proposed_requires_review'})
            for mapping in mappings:
                if any(e.is_a(t) for t in mapping['ifc_entities']):
                    seed = mapping['source_node_id']
                    link(seed, 'direct', f"现有候选映射：{mapping['ibc_concept']} → {', '.join(mapping['ifc_entities'])}", seed)
                    # Structural descendants retain exceptions and table nodes; numbering adds flattened subsections.
                    descendants = set()
                    todo = [seed]
                    while todo:
                        n = todo.pop()
                        for child in nodes[n]['child_ids']:
                            if child not in descendants:
                                descendants.add(child)
                                todo.append(child)
                    descendants.update(n for n in nodes if n.startswith(seed + '.'))
                    for n in descendants:
                        link(n, 'context', f'条款 {seed.removeprefix("ibc2021-")} 的子条款或例外；需核验用途条件', seed)
                    for n in contexts['contexts'].get(seed, {}).get('evidence_node_ids', []):
                        if n != seed:
                            link(n, 'context', f'条款 {seed.removeprefix("ibc2021-")} 的上位条款、例外或引用上下文', seed)
            # Chapter-wide requirements are retained as review context for all actual products.
            global_scope = {'ibc2021-1101.1', 'ibc2021-1102.1', 'ibc2021-1103.1'}
            global_scope.update(n for n in nodes if n == 'ibc2021-1103.2' or n.startswith('ibc2021-1103.2.'))
            for n in sorted(global_scope):
                link(n, 'scope', '建筑层面的范围、设计要求或适用性核验；不据此判断构件合规', n)
            records.append(record)
        precheck = read(ACC / 'model_tests' / key / 'precheck.json')
        source = read(path.parent / 'source.json')
        save(VIEWER / f'dist/data/{key}.json', {'id': key, 'filename': filename, 'schema': model.schema,
             'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'source': source,
             'records': records, 'precheck': precheck})
        summaries.append({'id': key, 'filename': filename,
                          'name': entry['name'],
                          'recordCount': len(records), 'meshCount': sum(bool(x['geometry']) for x in records)})
        print(key, len(records), 'records,', summaries[-1]['meshCount'], 'meshes')
    save(VIEWER / 'dist/data/models.json', summaries)
    if (ROOT / 'output/ibc_means_of_egress_structure/semantic_rdf/12_validation_report.json').exists():
        from export_chapters import main as merge_chapters
        merge_chapters()
    if (ACC / 'executable_rule_contracts.json').exists():
        from export_compliance import main as export_checks
        export_checks()

if __name__ == '__main__':
    main()

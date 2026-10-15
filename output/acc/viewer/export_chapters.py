"""Merge independently validated chapters without regenerating or fabricating IFC geometry."""
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

VIEWER=Path(__file__).resolve().parent
ROOT=VIEWER.parents[2]
CH10=ROOT/'output/ibc_means_of_egress_structure'
DATA=VIEWER/'dist/data'
sys.path.insert(0, str(VIEWER.parent/'src'))
from model_catalog import model_catalog

def read(path):return json.loads(path.read_text(encoding='utf-8'))
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':')),encoding='utf-8')

def main():
    base=read(DATA/'regulations.json')
    laws11=[law for law in base['laws'] if law.get('chapter',11)==11]
    for law in laws11:
        law.update({'chapter':11,'chapterTitle':'Accessibility','sourceFile':'IBE2021_11Accessibility.pdf',
                    'pdfFile':'IBC2021_Chapter11.pdf'})
    doc=read(CH10/'03_structured_document.json');nodes=doc['nodes']
    sem=read(CH10/'semantic_rdf/10_semantic_validated.json')
    by_node={c['source_node_id']:c for c in sem['candidates']}
    dsl=read(CH10/'semantic_rdf/10_dsl_rules.json')
    validation=read(CH10/'semantic_rdf/12_validation_report.json')
    if validation['overall_status']!='pass':raise ValueError('Chapter 10 failed validation')
    all_node_ids={law['id'] for law in laws11}|set(nodes)
    if len(all_node_ids)!=len(laws11)+len(nodes):raise ValueError('Chapter identities collide')
    table_by_number={}
    for table in doc['tables'].values():
        candidates=[]
        for node in nodes.values():
            captions=re.findall(r'\bTABLE\s+(\d{4}(?:\.\d+)*)',node['text_normalized'],re.I)
            for f in node['source_fragments']:
                if captions and f['pdf_page_number']==table['pdf_page_number']:
                    b=f['bbox']
                    if b[0]<table['bbox'][2] and b[2]>table['bbox'][0] and b[1]<=table['bbox'][1]:
                        candidates.append((abs(table['bbox'][1]-b[3]),captions[-1]))
        if candidates:
            number=min(candidates)[1];table_by_number[number]={**table,'number':number,'chapter':10}
    laws10=[]
    for node in nodes.values():
        text=node['text_normalized'];source=node['id'];candidate=by_node.get(source)
        ancestors=[];parent=node['parent_id']
        while parent:
            if parent in ancestors:raise ValueError('Cycle in Chapter 10 hierarchy')
            ancestors.append(parent);parent=nodes[parent]['parent_id']
        references=[];unresolved=[]
        for ref in (candidate or {}).get('cross_references',[]):
            for target in ref['targets']:
                key=target.get('target_node_id') or 'ibc2021-'+target['identifier']
                if key in all_node_ids:references.append(key)
                else:unresolved.append({'kind':ref['kind'],'identifier':target['identifier'],'expression':ref['expression']})
        exceptions=[x for x in node['child_ids'] if nodes[x]['type']=='exception']
        context={'source_node_id':source,'evidence_node_ids':list(dict.fromkeys([source]+ancestors+references+exceptions)),
                 'structural_and_numbered_ancestor_ids':ancestors,'reference_node_ids':references,
                 'exception_node_ids':exceptions,'unresolved_references':unresolved,'applicability_decided':False}
        laws10.append({'id':source,'chapter':10,'chapterTitle':'Means of Egress','sourceFile':doc['document']['source_file'],
            'pdfFile':'IBC2021_Chapter10.pdf','label':node['label'] or node['heading'] or node['type'],
            'heading':node['heading'],'type':node['type'],'order':node['order'],'parent':node['parent_id'],
            'children':node['child_ids'],'text':text,'sha256':hashlib.sha256(text.encode()).hexdigest(),
            'fragments':node['source_fragments'],'quality':node['quality'],'context':context,
            'semanticReview':candidate['quality'] if candidate else None,
            'tables':[table_by_number[n] for n in dict.fromkeys(re.findall(r'\bTABLE\s+(\d{4}(?:\.\d+)*)',text,re.I)) if n in table_by_number]})
    # Resolve cross-chapter links for navigation only; retain unresolved external standards.
    for law in laws11:
        context=law.get('context')
        if not context:continue
        pending=[]
        for ref in context.get('unresolved_references',[]):
            target='ibc2021-'+ref['identifier']
            if target in nodes:
                context.setdefault('reference_node_ids',[]).append(target)
                context.setdefault('evidence_node_ids',[]).append(target)
            else:pending.append(ref)
        context['unresolved_references']=pending
    mappings=[{'ibc_concept':concept,'ifc_entities':types,'source_node_id':source,
               'status':'proposed_requires_review','applicability_decided':False,
               'basis':'Explicit IFC type and matching source clause; use, occupancy, exceptions and geometry unverified'}
        for concept,types,source in [
            ('Door',['IfcDoor'],'ibc2021-1010'),('Stairway',['IfcStair','IfcStairFlight'],'ibc2021-1011'),
            ('Ramp',['IfcRamp','IfcRampFlight'],'ibc2021-1012'),('OccupantLoad',['IfcSpace'],'ibc2021-1004'),
            ('ExitAccess',['IfcSpace'],'ibc2021-1006')]]
    assert all(m['source_node_id'] in nodes for m in mappings)
    save(VIEWER/'chapter10_mapping.json',{'mappings':mappings,'deterministic_source_check':'pass','legal_expert_approved':False})
    def descendants(seed):
        found=set();todo=[seed]
        while todo:
            for child in nodes[todo.pop()]['child_ids']:
                if child not in found:found.add(child);todo.append(child)
        return found
    for entry in model_catalog():
        model_path = DATA / f"{entry['id']}.json"
        model=read(model_path)
        for record in model['records']:
            record['links']=[x for x in record['links'] if x.get('chapter')!=10]
            def link(key,kind,reason,seed):
                if not any(x['lawId']==key and x['kind']==kind and x.get('seed')==seed for x in record['links']):
                    record['links'].append({'lawId':key,'kind':kind,'reason':reason,'seed':seed,
                                            'chapter':10,'status':'proposed_requires_review'})
            for mapping in mappings:
                if record['type'] not in mapping['ifc_entities']:continue
                seed=mapping['source_node_id']
                link(seed,'direct',f"现有候选映射：{mapping['ibc_concept']} → {', '.join(mapping['ifc_entities'])}",seed)
                for key in sorted(descendants(seed)):
                    link(key,'context',f'条款 {seed.removeprefix("ibc2021-")} 的子条款或例外；需核验用途条件',seed)
            for key in ['ibc2021-1001.1','ibc2021-1003.1']:
                link(key,'scope','建筑层面的范围、设计要求或适用性核验；不据此判断构件合规',key)
        save(model_path,model)
    laws=laws10+laws11
    tables={key:value for key,value in base['tables'].items() if not key.startswith('ch10-')}
    tables.update({key:{**value,'chapter':10} for key,value in doc['tables'].items()})
    chapters=[{'id':10,'title':'Means of Egress','lawCount':len(laws10),'candidateCount':sem['candidate_count'],
               'dslRuleCount':dsl['rule_count'],'sourceFile':doc['document']['source_file'],'pdfFile':'IBC2021_Chapter10.pdf',
               'sourcePdfPageFrom':304,'sourcePdfPageTo':355},
              {'id':11,'title':'Accessibility','lawCount':len(laws11),'candidateCount':289,'dslRuleCount':462,
               'sourceFile':'IBE2021_11Accessibility.pdf','pdfFile':'IBC2021_Chapter11.pdf',
               'sourcePdfPageFrom':356,'sourcePdfPageTo':373}]
    save(DATA/'regulations.json',{**base,'source':'IBC 2021 · Chapters 10 and 11',
         'scope_note':'Chapters 10 and 11 evidence; all candidate links require review. Unlinked does not mean not applicable.',
         'chapters':chapters,'laws':laws,'tables':tables,
         'mappings':[m for m in base['mappings'] if m.get('chapter')!=10]+[{**m,'chapter':10} for m in mappings],
         'candidate_count':sum(c['candidateCount'] for c in chapters),'dsl_rule_count':sum(c['dslRuleCount'] for c in chapters)})
    shutil.copy2(ROOT/doc['document']['source_file'],DATA/'IBC2021_Chapter10.pdf')
    save(VIEWER/'chapter_export_report.json',{'chapters':chapters,'lawCount':len(laws),'uniqueLawIds':len(all_node_ids),
         'geometry_regenerated':False,'compliance_status_changed':False,'mapping_source_validation':'pass'})
    print('Chapters merged:',[(c['id'],c['lawCount']) for c in chapters])

if __name__=='__main__':main()

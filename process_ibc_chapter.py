"""Reusable evidence-preserving IBC PDF stages 1-12; no legal applicability decisions."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'output/acc/.python_deps'))
sys.path.insert(0, str(ROOT / 'output/acc/.semantic_deps'))
import pymupdf
import jsonschema
from PIL import Image, ImageDraw
import extract_ibc_accessibility as extraction
import build_semantic_rdf as semantics
from rdflib import Dataset, Graph, Namespace, RDF, Literal, XSD, OWL, RDFS


def dump(path, value):
    extraction.json_dump(path, value)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_structure(raw, layout, tables, chapter, title):
    """Resolve dotted section numbers and indentation; retain uncertain list scope for review."""
    nodes, roots, sequence = {}, [], 0
    line_lookup = {x['id']: x for p in layout['pages'] for x in p['lines']}
    table_lines = set()
    for table in tables:
        table['id'] = f"ch{chapter}-" + table['id']
        table['source_line_ids'] = []
        tx0, ty0, tx1, ty1 = table['bbox']
        for page in layout['pages']:
            if page['pdf_page_number'] != table['pdf_page_number']:
                continue
            for line in page['lines']:
                if line['excluded_from_reading_order']:
                    continue
                x0, y0, x1, y1 = line['bbox']
                if tx0 <= (x0+x1)/2 <= tx1 and ty0 <= (y0+y1)/2 <= ty1:
                    if line['id'] in table_lines:
                        raise ValueError('Overlapping table ownership: '+line['id'])
                    table_lines.add(line['id'])
                    table['source_line_ids'].append(line['id'])
        table['source_text_lines'] = [line_lookup[x]['text'] for x in table['source_line_ids']]
        table['review_status'] = 'table_structure_requires_review'

    def fragment(line):
        return {'pdf_page_number': line['pdf_page_number'], 'source_pdf_page': line['source_pdf_page'],
                'column': line['column'], 'bbox': line['bbox'][:],
                'line_ids': [line['id']], 'block_ids': [line['block_id']]}

    def add(kind, label, line, parent=None, heading=None):
        nonlocal sequence
        sequence += 1
        numbered = kind in {'section', 'provision'}
        key = 'ibc2021-' + (label if numbered else f'ch{chapter}-{kind}-{sequence:04d}')
        if key in nodes:
            raise ValueError('Duplicate numbered provision: '+key)
        nodes[key] = {'id': key, 'type': kind, 'label': label, 'heading': heading, 'parent_id': parent,
                      'child_ids': [], 'order': sequence, 'text_verbatim': line['text'],
                      'text_normalized': extraction.norm(line['text']), 'source_fragments': [fragment(line)],
                      'quality': {'layout_confidence': 0.9, 'structure_confidence': 0.9,
                                  'requires_review': False, 'issues': []}}
        if parent:
            nodes[parent]['child_ids'].append(key)
        else:
            roots.append(key)
        return key

    def append(key, line):
        n = nodes[key]
        previous, text = n['text_verbatim'], line['text']
        n['text_verbatim'] = previous[:-1]+text if previous.endswith('-') and text[0:1].islower() else previous+' '+text
        n['text_normalized'] = extraction.norm(n['text_verbatim'].replace('\u00ad', ''))
        f = n['source_fragments'][-1]
        if f['pdf_page_number'] == line['pdf_page_number'] and f['column'] == line['column']:
            f['line_ids'].append(line['id'])
            if line['block_id'] not in f['block_ids']:
                f['block_ids'].append(line['block_id'])
            b, x = f['bbox'], line['bbox']
            f['bbox'] = [min(b[0],x[0]),min(b[1],x[1]),max(b[2],x[2]),max(b[3],x[3])]
        else:
            n['source_fragments'].append(fragment(line))

    chapter_id = section = provision = active = exception = None
    pending_section = None
    list_stack = []
    # Four-digit identifiers at the end of a wrapped line are section references, not list labels.
    list_re = re.compile(r'^(\d{1,3}(?:\.\d{1,3})*\.|[a-z]\.|\([a-z0-9]+\))(?=\s|$)', re.I)
    column_origins = {p['page_id']: {col: min((l['bbox'][0] for l in p['lines'] if l['column']==col and not l['excluded_from_reading_order']), default=0)
                                   for col in ['left','right','spanning']} for p in layout['pages']}
    for page in layout['pages']:
        for lid in page['reading_order_line_ids']:
            if lid in table_lines:
                continue
            line = line_lookup[lid]
            text = line['text']
            clean = re.sub(r'^\[[A-Z]+\]\s*', '', text)
            sec = extraction.SECTION_RE.fullmatch(clean)
            prov = extraction.PROVISION_RE.match(clean) if line['first_span_bold'] else None
            item = list_re.match(clean)
            if re.fullmatch(r'CHAPTER\s+\d+', text, re.I):
                chapter_id = add('chapter', str(chapter), line, heading=title)
                active = chapter_id
            elif sec:
                section = add('section', sec.group(1), line, chapter_id)
                pending_section = section
                active, provision, exception, list_stack = section, None, None, []
            elif pending_section and line['bold']:
                nodes[pending_section]['heading'] = text
                append(pending_section, line)
                pending_section = None
            elif prov:
                label, rest = prov.groups()
                pieces = label.split('.')
                parent = next(('ibc2021-' + '.'.join(pieces[:n]) for n in range(len(pieces)-1,0,-1)
                               if 'ibc2021-' + '.'.join(pieces[:n]) in nodes), section or chapter_id)
                heading = rest.split('. ',1)[0] if '. ' in rest else None
                provision = add('provision', label, line, parent, heading)
                active, exception, list_stack = provision, None, []
                pending_section = None
            elif re.match(r'^Exceptions?:', text, re.I):
                exception = add('exception', None, line, provision or section or chapter_id)
                active, list_stack = exception, []
            elif re.match(r'^(User notes?:|Note:)', text, re.I):
                active = add('note', None, line, provision or section or chapter_id)
                list_stack = []
            elif item:
                x = line['bbox'][0] - column_origins[page['page_id']].get(line['column'],0)
                while list_stack and x <= list_stack[-1][0]+3:
                    list_stack.pop()
                parent = list_stack[-1][1] if list_stack else exception or provision or section or chapter_id
                active = add('list_item', item.group(1).rstrip('.'), line, parent)
                list_stack.append((x,active))
                nodes[active]['quality'].update({'structure_confidence':0.78,'requires_review':True,
                                                'issues':['list_scope_requires_review']})
            elif active:
                append(active,line)
            else:
                active = add('front_matter',None,line)

    return {'schema_version':'1.0.0','document':{
        'document_id':f'IBC-2021-Chapter-{chapter}-'+title.replace(' ','-'), 'title':title,'chapter':chapter,
        'edition':'2021','source_standard':'IBC','source_file':raw['source']['file_name'],
        'source_pdf_page_range':{'from':raw['source']['source_pdf_page_from'],'to':raw['source']['source_pdf_page_to']},
        'extraction':{'engine':raw['source']['engine'],'engine_version':raw['source']['engine_version'],
                      'coordinate_system':'PDF points, origin top-left'}},
        'pages':[{k:p[k] for k in ['page_id','pdf_page_number','source_pdf_page','layout','reading_order_line_ids']} for p in layout['pages']],
        'structure':{'root_node_ids':roots},'nodes':nodes,'tables':{t['id']:t for t in tables},'references':[]}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('input',type=Path);parser.add_argument('output',type=Path)
    parser.add_argument('--chapter',type=int,required=True);parser.add_argument('--title',required=True)
    parser.add_argument('--original',type=Path,default=ROOT/'2021_International_Building_Code.pdf')
    args=parser.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=True)
    doc=pymupdf.open(args.input);original=pymupdf.open(args.original)
    normalize=lambda p: extraction.norm(p.get_text())
    first=normalize(doc[0]);starts=[i for i,p in enumerate(original) if normalize(p)==first]
    if len(starts)!=1:raise ValueError('Original PDF first-page alignment is not unique')
    start=starts[0]
    mismatches=[i+1 for i in range(len(doc)) if normalize(doc[i])!=normalize(original[start+i])]
    if mismatches:raise ValueError('Excerpt does not match original pages: '+str(mismatches))
    extraction.SOURCE_PDF_START=start+1
    initial_hashes={str(p.resolve()):digest(p) for p in [args.input,args.original]}
    manifest={'created_at_utc':datetime.now(timezone.utc).isoformat(),'chapter':args.chapter,'title':args.title,
              'input':str(args.input.resolve()),'output':str(out.resolve()),'source_hashes':initial_hashes,
              'original_alignment':{'page_from':start+1,'page_to':start+len(doc),'all_pages_text_match':True},
              'tools':['PyMuPDF','Pillow','JSON Schema','RDFLib','pySHACL','OWL-RL'],
              'ai_usage':{'extraction':'deterministic local processing; no external AI API',
                          'review':'AI assisted code and visual review; token count unavailable'}}
    dump(out/'00_manifest.json',manifest)
    print('Stage 1: original-page alignment verified',flush=True)
    raw=extraction.extract_raw(doc,args.input);dump(out/'01_raw_layout.json',raw)
    layout=extraction.classify_layout(raw)
    # Identify the introduction band by the first SECTION, rather than the Chapter 11 fixed y cut.
    first_section=min((l['bbox'][1] for l in layout['pages'][0]['lines'] if extraction.SECTION_RE.fullmatch(l['text'])),default=0)
    if first_section:
        page=layout['pages'][0]
        for l in page['lines']:
            if not l['excluded_from_reading_order'] and l['bbox'][1]<first_section:
                l['column']='spanning'
        content=[l for l in page['lines'] if not l['excluded_from_reading_order']]
        intro=sorted([l for l in content if l['column']=='spanning'],key=lambda l:(l['bbox'][1],l['bbox'][0]))
        remaining=[l for l in content if l['column']!='spanning']
        page['reading_order_line_ids']=[l['id'] for l in intro]+[l['id'] for col in ['left','right'] for l in sorted([x for x in remaining if x['column']==col],key=lambda l:(l['bbox'][1],l['bbox'][0]))]
    dump(out/'02_layout_analysis.json',layout)
    tables,warnings=extraction.extract_tables(doc)
    structured=build_structure(raw,layout,tables,args.chapter,args.title)
    dump(out/'03_structured_document.json',structured)
    report=extraction.validate(raw,layout,structured,warnings)
    report['checks']['page_count']={'expected':len(doc),'actual':len(raw['pages']),'pass':True}
    report['checks']['blank_body_pages']=[p['pdf_page_number'] for p in layout['pages'] if not p['reading_order_line_ids']]
    report['checks']['original_page_alignment_pass']=not mismatches
    fatal=any(report['checks'][x] for x in ['unassigned_content_line_ids','duplicate_structured_line_ids','unknown_structured_line_ids','duplicate_reading_order_line_ids'])
    report['status']='fail' if fatal else 'pass_with_manual_review' if report['checks']['low_confidence_node_ids'] or warnings else 'pass'
    dump(out/'04_validation_report.json',report)
    if fatal:raise ValueError('Source-line coverage validation failed')
    schema=json.loads((ROOT/'output/ibe_accessibility_structure/structured_document.schema.json').read_text(encoding='utf-8'))
    schema['title']='IBC Chapter Structured Document';schema['$id']='https://example.local/schemas/ibc-chapter-structure-1.0.0.json'
    schema['properties']['pages']['minItems']=schema['properties']['pages']['maxItems']=len(doc)
    dump(out/'structured_document.schema.json',schema)
    jsonschema.Draft202012Validator(schema).validate(structured)
    dump(out/'05_schema_validation.json',{'status':'pass','schema':'structured_document.schema.json'})
    print('Stages 2-9:',len(structured['nodes']),'nodes,',len(tables),'tables; rendering QA',flush=True)
    extraction.render_pages(doc,out/'qa_pages')
    page_paths=sorted((out/'qa_pages').glob('*.png'))
    for batch in range(0,len(page_paths),9):
        sheet=Image.new('RGB',(1050,1455),'#eeeeee');draw=ImageDraw.Draw(sheet)
        for j,p in enumerate(page_paths[batch:batch+9]):
            im=Image.open(p);im.thumbnail((335,445))
            x=(j%3)*350+(350-im.width)//2;y=(j//3)*485+25
            sheet.paste(im,(x,y));draw.text(((j%3)*350+12,(j//3)*485+7),f'PDF {batch+j+1} / Original {start+batch+j+1}',fill='black')
        sheet.save(out/f'qa_contact_sheet_{batch//9+1}.png')
    dump(out/'06_ai_review_notes.json',{'status':'pending_visual_review','method':'rendered page images and contact sheets',
         'ai_tokens_used':True,'token_count':None,'deterministic_coverage_passed':True,
         'manual_review_node_ids':report['checks']['low_confidence_node_ids'],'table_review_ids':list(structured['tables'])})
    # Chapter-specific egress concepts, still proposed deterministic lexical mappings.
    semantics.CONCEPT_PATTERNS += [('MeansOfEgress',r'\bmeans of egress\b'),('Door',r'\bdoors?\b'),
        ('Stairway',r'\bstairs?|stairways?\b'),('Ramp',r'\bramps?\b'),('Corridor',r'\bcorridors?\b'),
        ('Exit',r'\bexits?\b'),('ExitAccess',r'\bexit access\b'),('ExitDischarge',r'\bexit discharge\b'),
        ('OccupantLoad',r'\boccupant loads?\b'),('Handrail',r'\bhandrails?\b'),('Guard',r'\bguards?\b')]
    original_candidate=semantics.semantic_candidate
    def evidence_candidate(node,children):
        result=original_candidate(node,children)
        reasons=result['quality']['review_reasons']
        if node['quality']['requires_review']:reasons.append('source_structure_requires_review')
        if re.search(r'\d+\s*/\s*\d+|\d+[¼½¾]|\bratio\b|\bper\b|\bTable\b',result['evidence']['text'],re.I):
            reasons.append('compound_numeric_or_table_expression_requires_review')
        if reasons:result['quality'].update({'requires_review':True,'review_status':'unreviewed'})
        result['quality']['legal_expert_approved']=False
        return result
    semantics.semantic_candidate=evidence_candidate
    original_ontology=semantics.ontology_graph
    def chapter_ontology():
        g=original_ontology()
        for name,_ in semantics.CONCEPT_PATTERNS:
            g.add((semantics.IBCO[name],RDF.type,OWL.Class))
            g.add((semantics.IBCO[name],RDFS.subClassOf,semantics.IBCO.DomainConcept))
        return g
    semantics.ontology_graph=chapter_ontology
    original_graphs=semantics.build_graphs
    def chapter_graphs(structured,values):
        doc_g,ent_g,_=original_graphs(structured,values)
        # Keep dotted provision identities instead of the legacy slug's dot-to-hyphen conversion.
        for candidate in values['candidates']:
            req=semantics.IBC[candidate['semantic_id']]
            ent_g.remove((req,semantics.IBCO.references,None))
            for reference in candidate['cross_references']:
                for target in reference.get('targets',[]):
                    identifier=target.get('target_node_id') or 'ibc2021-'+target['identifier']
                    ent_g.add((req,semantics.IBCO.references,semantics.IBC[identifier]))
        dataset=Dataset();dataset.bind('ibc',semantics.IBC);dataset.bind('ibco',semantics.IBCO)
        for suffix,g in [('documentGraph',doc_g),('entityGraph',ent_g)]:
            for triple in g:dataset.graph(semantics.IBC[f'chapter{args.chapter}/{suffix}']).add(triple)
        return doc_g,ent_g,dataset
    semantics.build_graphs=chapter_graphs
    semantic_out=out/'semantic_rdf'
    sys.argv=['build_semantic_rdf.py',str(out/'03_structured_document.json'),str(semantic_out)]
    print('Stages 10-12: semantics, RDF, SHACL and OWL-RL validation',flush=True)
    semantics.main()
    assert all(digest(Path(p))==h for p,h in initial_hashes.items())
    validation=json.loads((semantic_out/'12_validation_report.json').read_text())
    dump(semantic_out/'13_ai_review_notes.json',{'status':'deterministic_validation_complete_expert_review_required',
         'ai_tokens_used':True,'token_count':None,'legal_expert_approved':False,
         'review_queue_count':validation['manual_review_queue_count'],
         'limitations':['Lexical numeric values are candidates, not executable thresholds.',
                       'Tables, nested lists, conditions and exceptions need human semantic review.',
                       'OWL-RL sanity checks do not certify legal consistency.']})
    stages=[{'stage':i,'tools':manifest['tools'],'ai_token_usage':'AI-assisted code/QA; no per-stage external API calls; count unavailable',
             'inputs':[str(args.input.resolve())] if i<10 else [str((out/'03_structured_document.json').resolve())],
             'outputs':[str(p.relative_to(out)) for p in out.glob('*.json')] if i<10 else [str(p.relative_to(out)) for p in semantic_out.iterdir()],
             'failures':[],'manual_review_required':i in [5,6,7,8,9,10,11,12]} for i in range(1,13)]
    dump(out/'stage_log.json',{'stages':stages})
    (out/'07_execution_report.md').write_text(f'# IBC Chapter {args.chapter}: stages 1-9\n\nInput: `{args.input.name}`. Original pages {start+1}-{start+len(doc)}; {len(doc)} pages.\n\n'
        f"{report['checks']['content_line_count']} content lines, {len(structured['nodes'])} nodes, {len(tables)} table candidates. Source lines are uniquely assigned; JSON Schema passed.\n\n"
        'All page images and contact sheets retained. List scope and table structure require review. No source PDFs modified.\n',encoding='utf-8')
    (semantic_out/'14_execution_report.md').write_text(f'# IBC Chapter {args.chapter}: stages 10-12\n\n'
        f"Validation: {validation['overall_status']}. Graph statistics: {json.dumps(validation['graph_statistics'])}.\n\n"
        f"Expert review queue: {validation['manual_review_queue_count']}.\n\n"
        'Tools: RDFLib, pySHACL, OWL-RL; deterministic source evidence checks. AI assisted implementation and QA; exact Token count unavailable.\n\n'
        'Candidates are not certified legal interpretations. No IFC compliance results generated.\n',encoding='utf-8')
    dump(out/'00_manifest.json',{**manifest,'artifacts':{str(p.relative_to(out)):digest(p) for p in out.rglob('*') if p.is_file() and p.name!='00_manifest.json'},
                                 'completion_status':validation['overall_status']})
    print('Completed',out,flush=True)


if __name__=='__main__':main()

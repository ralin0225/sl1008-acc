"""Reproduce integration checks on the downloaded, unmodified GitHub IFC samples."""
from pathlib import Path
import collections
import hashlib
import json
import subprocess
import sys
import time

ACC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ACC / '.python_deps'))
sys.path.insert(0, str(ACC / 'src'))
import ifcopenshell
import ifcopenshell.validate
from precheck_ifc import check
from ifc_inventory import extract

SAMPLES = [
    ('buildingsmart-simple-scene', 'Building-Architecture_IFC4.ifc',
     'buildingSMART/Certification-datasets', '80d976a9b193a26a8e928c3e79bff67af1de68a8',
     'IFC 4.0.2.1 (IFC 4 ADD2 TC1)/Simple-Scene/Building-Architecture.ifc',
     'CC BY 4.0; copyright buildingSMART International Ltd.'),
    ('ifcopenhouse', 'IfcOpenHouse_IFC4.ifc', 'aothms/IfcOpenHouse',
     'f1de8b04e37803113a11e8b9c4f598863b6d2785', 'IfcOpenHouse_IFC4.ifc',
     'No explicit license file found in the source snapshot; retained for local testing.'),
]

def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def main():
    summary = []
    for key, filename, repo, commit, upstream_path, license_note in SAMPLES:
        model_path = ACC / 'models' / key / filename
        out = ACC / 'model_tests' / key
        out.mkdir(parents=True, exist_ok=True)
        start = time.perf_counter()
        source = {'repository': 'https://github.com/' + repo, 'commit': commit,
                  'path': upstream_path, 'license_note': license_note,
                  'bytes': model_path.stat().st_size,
                  'sha256': hashlib.sha256(model_path.read_bytes()).hexdigest(),
                  'model_modified': False}
        save(model_path.parent / 'source.json', source)
        precheck = check(model_path, geometry_sample=100000)
        inventory = extract(model_path)
        save(out / 'precheck.json', precheck)
        save(out / 'inventory.json', inventory)
        logger = ifcopenshell.validate.json_logger()
        ifcopenshell.validate.validate(ifcopenshell.open(str(model_path)), logger)
        save(out / 'schema_validation.json', {
            'scope': 'IFC attribute and inverse constraints; EXPRESS rules not executed',
            'statement_count': len(logger.statements), 'statements': logger.statements})
        # Model evidence is real; unverified legal facts and approvals stay empty.
        facts = json.loads((ACC / 'normalized_facts.template.json').read_text(encoding='utf-8'))
        facts['note'] = 'Real GitHub IFC evidence attached; legal facts and approvals unavailable.'
        for rule in facts['facts_by_rule'].values():
            rule['model_evidence'] = inventory['model_evidence']
        save(out / 'normalized_facts.json', facts)
        subprocess.run([sys.executable, str(ACC / 'src/acc_engine.py'),
                        str(out / 'normalized_facts.json'), '--output',
                        str(out / 'subchecks.json')], check=True)
        subchecks = json.loads((out / 'subchecks.json').read_text(encoding='utf-8'))
        summary.append({'sample': key, 'source': source, 'precheck_status': precheck['status'],
                        'inventory': precheck['object_inventory'],
                        'geometry': precheck['checks']['geometry'],
                        'schema_validation_statements': len(logger.statements),
                        'records_with_acc_properties': sum(bool(r['declared_properties']) for r in inventory['records']),
                        'candidate_edges': len(inventory['topology_candidates']['edges']),
                        'subcheck_statuses': dict(collections.Counter(r['status'] for r in subchecks['results'])),
                        'elapsed_seconds': round(time.perf_counter() - start, 3)})
    tests = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s',
                            str(ACC / 'tests'), '-v'], capture_output=True, text=True)
    (ACC / 'model_tests/regression.log').write_text(tests.stdout + tests.stderr, encoding='utf-8')
    save(ACC / 'model_tests/summary.json', {'samples': summary, 'regression_exit_code': tests.returncode,
                                         'ifcopenshell_version': ifcopenshell.version,
                                         'full_clause_compliance_evaluated': False})
    print(ACC / 'model_tests/summary.json')
    if tests.returncode:
        raise SystemExit(tests.returncode)

if __name__ == '__main__':
    main()

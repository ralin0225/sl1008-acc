"""Import original named graphs and compare every explicit RDF statement."""
import datetime
import hashlib
import json
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = pathlib.Path(__file__).resolve().parent
ROOT = BASE.parents[2]
sys.path.insert(0, str(BASE.parent / '.python_deps'))
from rdflib import Dataset

SERVER = 'http://localhost:7200'
REPOSITORY = 'ibc2021-accessibility'
SOURCE = ROOT / 'output/ibe_accessibility_structure/semantic_rdf/11_combined_graph.trig'

def request(path, data=None, headers=None, method=None):
    req = urllib.request.Request(SERVER + path, data=data, headers=headers or {}, method=method)
    with urllib.request.urlopen(req, timeout=120) as response:
        return response.read()

def query(text):
    data = urllib.parse.urlencode({'query': text, 'infer': 'false'}).encode()
    return json.loads(request('/repositories/' + REPOSITORY, data,
        {'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'application/sparql-results+json'}))

if __name__ == '__main__':
    for attempt in range(30):
        try:
            version = request('/rest/info/version').decode()
            break
        except (urllib.error.URLError, TimeoutError):
            time.sleep(2)
    else:
        raise RuntimeError('GraphDB did not become ready')
    print('GraphDB version: ' + version, flush=True)
    repositories = json.loads(request('/rest/repositories'))
    if not any(r['id'] == REPOSITORY for r in repositories):
        boundary = 'IBCGraphDBRepositoryConfig'
        config = (BASE / 'repository_config.ttl').read_bytes()
        body = ('--' + boundary + '\r\nContent-Disposition: form-data; name="config"; filename="repository_config.ttl"\r\nContent-Type: text/turtle\r\n\r\n').encode() + config + ('\r\n--' + boundary + '--\r\n').encode()
        request('/rest/repositories', body, {'Content-Type': 'multipart/form-data; boundary=' + boundary})
        print('Repository created', flush=True)
    source_bytes = SOURCE.read_bytes()
    source_graph = Dataset()
    source_graph.parse(data=source_bytes.decode(), format='trig')
    source_quads = set(source_graph.quads((None, None, None, None)))
    remote_before = query('SELECT (COUNT(*) AS ?count) WHERE { GRAPH ?g { ?s ?p ?o } }')['results']['bindings'][0]['count']['value']
    if int(remote_before) == 0:
        request('/repositories/' + REPOSITORY + '/statements', source_bytes, {'Content-Type': 'application/trig'})
        print('Original TriG imported', flush=True)
    exported = request('/repositories/' + REPOSITORY + '/statements?infer=false', headers={'Accept': 'application/trig'})
    actual_graph = Dataset()
    actual_graph.parse(data=exported.decode(), format='trig')
    actual_quads = set(actual_graph.quads((None, None, None, None)))
    missing = source_quads - actual_quads
    extra = actual_quads - source_quads
    assert not missing and not extra, f'RDF mismatch: {len(missing)} missing, {len(extra)} unexpected'
    counts = query('SELECT ?g (COUNT(*) AS ?count) WHERE { GRAPH ?g { ?s ?p ?o } } GROUP BY ?g')
    license_info = None
    try:
        license_info = json.loads(request('/rest/license'))
    except (urllib.error.URLError, json.JSONDecodeError):
        pass
    report = {'verified_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'version_response': version,
        'repository': REPOSITORY, 'server': SERVER, 'source': str(SOURCE),
        'source_sha256': hashlib.sha256(source_bytes).hexdigest(), 'explicit_quad_count': len(source_quads),
        'all_explicit_quads_match': True, 'missing_quad_count': len(missing), 'extra_quad_count': len(extra),
        'graph_counts': counts['results']['bindings'], 'license_info': license_info,
        'ruleset': 'empty', 'model_compliance_results_generated': False}
    (BASE / 'import_verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2), flush=True)

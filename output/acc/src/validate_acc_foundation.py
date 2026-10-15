"""Validate source integrity, partitions, mappings, IDS, and synthetic regressions."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import time
import unittest
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ACC = ROOT / "output/acc"
SOURCE = ROOT / "output/ibe_accessibility_structure"
sys.path[:0] = [str(ACC / "src"), str(ACC / ".python_deps")]
import ifcopenshell
from rdflib import Graph, Namespace
from ids_support import load_ids
from ifctester.ids import get_schema


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write(name, data):
    (ACC / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def model_files():
    files = []
    for directory, folders, names in os.walk(ROOT):
        folders[:] = [x for x in folders if x not in {".python_deps", ".git", "__pycache__"}]
        files.extend(str((Path(directory) / name).relative_to(ROOT)) for name in names if name.lower().endswith(".ifc"))
    return sorted(files)


def validate():
    clauses = read(SOURCE / "semantic_rdf/10_semantic_validated.json")["candidates"]
    by_node = {x["source_node_id"]: x for x in clauses}
    original = read(SOURCE / "semantic_rdf/10_dsl_rules.json")["rules"]
    nodes = read(SOURCE / "03_structured_document.json")["nodes"]
    scope = read(ACC / "acc_scope.json")
    by_rule = {r["dsl_rule_id"]: r for r in scope["rules"]}
    assert len(by_rule) == len(scope["rules"]) == len(original) == 462, "Missing or duplicate scope rules"
    assert set(by_rule) == {r["dsl_rule_id"] for r in original}, "Scope/source rule IDs differ"
    partition = read(ACC / "computable_rules.json")["rules"] + read(ACC / "deferred_rules.json")["rules"]
    assert len(partition) == len(by_rule) and {r["dsl_rule_id"] for r in partition} == set(by_rule), "Invalid partition"
    for r in partition:
        assert r == by_rule[r["dsl_rule_id"]], "Partition content differs from scope"
    for rule in scope["rules"]:
        c = by_node[rule["source_node_id"]]
        assert rule["source_node_id"] in nodes
        assert not rule["execution_ready"], "Triage must not authorize execution"
        assert rule["evidence"]["text"] == c["evidence"]["text"]
        assert rule["evidence"]["sha256"] == hashlib.sha256(c["evidence"]["text"].encode()).hexdigest()
        assert rule["evidence"]["fragments"] == c["evidence"]["source_fragments"]
        for fragment in rule["evidence"]["fragments"]:
            assert fragment["source_pdf_page"] == fragment["pdf_page_number"] + 355
            assert 1 <= fragment["pdf_page_number"] <= 18 and len(fragment["bbox"]) == 4
    mapping = read(ACC / "ibc_ifc_mapping.json")["mappings"]
    schema = ifcopenshell.ifcopenshell_wrapper.schema_by_name("IFC4")
    graph = Graph().parse(ACC / "ibc_ifc_mapping.ttl", format="turtle")
    document_graph = Graph().parse(SOURCE / "semantic_rdf/11_document_graph.ttl", format="turtle")
    prov, ibc = Namespace("http://www.w3.org/ns/prov#"), Namespace("https://example.org/ibc/2021/")
    for m in mapping:
        assert m["source_node_id"] in by_node and m["status"] == "proposed_requires_review"
        assert list(graph.subjects(prov.wasDerivedFrom, ibc[m["source_node_id"]]))
        assert list(document_graph.predicate_objects(ibc[m["source_node_id"]])), "Mapping source URI missing from document graph"
        for entity in m["ifc_entities"]:
            assert schema.declaration_by_name(entity) is not None
    catalog = read(ACC / "mvp_rule_catalog.json")
    from build_rule_context import build
    contexts = read(ACC / "rule_review_context.json")
    assert contexts == build(read(SOURCE / "03_structured_document.json"), clauses), "Rule context no longer matches source"
    assert len(catalog["rules"]) == 8
    for rule in catalog["rules"]:
        assert rule["evidence"] == by_node[rule["source_node_id"]]["evidence"]
        assert rule["full_clause_compliance_evaluated"] is False
        assert rule["review_context"]["sha256"] == contexts["contexts"][rule["source_node_id"]]["sha256"]
        definition = {"expression": rule["expression"], "source_sha256": rule["evidence"]["sha256"],
                      "inventory_kind": rule["inventory_kind"], "result_scope": rule["result_scope"],
                      "review_context_sha256": rule["review_context"]["sha256"]}
        if rule["rule_id"] == "parking-minimum":
            definition["table_sha256"] = catalog["parking_table"]["sha256"]
        assert rule["definition_sha256"] == hashlib.sha256(json.dumps(definition, sort_keys=True).encode()).hexdigest()
        if rule["kind"] != "information":
            assert rule["execution_gate"] == "requires_explicit_scope_review"
    # Numeric bindings are checked against the actual source, not remembered thresholds.
    assert "at least 60 percent" in by_node["ibc2021-1105.1"]["evidence"]["text"]
    assert "For every six or fraction of six accessible parking spaces" in by_node["ibc2021-1106.6"]["evidence"]["text"]
    assert "at least one accessible entrance" in by_node["ibc2021-1105.1.7"]["evidence"]["text"].lower()
    text = by_node["ibc2021-1108.6.2.2.1"]["evidence"]["text"]
    assert "more than 20" in text and "at least 2 percent" in text
    table = read(SOURCE / "03_structured_document.json")["tables"]["table-p004-01"]
    for field in table:
        assert catalog["parking_table"][field] == table[field], "Parking table source changed"
    assert catalog["parking_table"]["sha256"] == hashlib.sha256(json.dumps(table, sort_keys=True).encode()).hexdigest()
    assert get_schema().is_valid(str(ACC / "ibc_accessibility.ids"))
    ids_model = load_ids(ACC / "ibc_accessibility.ids")
    trace = read(ACC / "ids_traceability.json")["specifications"]
    assert len(ids_model.specifications) == len(trace) == 6
    for spec, record in zip(ids_model.specifications, trace):
        assert spec.identifier == record["source_node_id"] and spec.name == record["name"]
        assert record["evidence"] == by_node[spec.identifier]["evidence"]
    return {"source_rule_count": len(original), "scope_partition_valid": True, "source_evidence_valid": True,
            "mapping_count": len(mapping), "mapping_triples": len(graph), "ifc4_entities_valid": True,
            "mvp_candidate_count": 8, "review_context_count": len(contexts["contexts"]), "rule_fingerprints_valid": True,
            "ids_schema_valid": True, "ids_traceability_valid": True}


def main():
    started = time.perf_counter()
    report = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "status": "FAIL", "errors": []}
    try:
        report.update(validate())
        suite = unittest.defaultTestLoader.discover(str(ACC / "tests"))
        result = unittest.TextTestRunner(verbosity=1).run(suite)
        write("test_report.json", {"synthetic_tests_only": True, "tests_run": result.testsRun,
                                    "failures": [str(x[0]) for x in result.failures], "errors": [str(x[0]) for x in result.errors],
                                    "successful": result.wasSuccessful(), "actual_model_compliance_evaluated": False})
        if not result.wasSuccessful():
            raise RuntimeError("Synthetic regression suite failed")
        report["tests_run"] = result.testsRun
        report["status"] = "PASS"
    except Exception as exc:
        report["errors"].append(f"{type(exc).__name__}: {exc}")
    report["ifc_model_files"] = model_files()
    report["actual_model_compliance_evaluated"] = False
    report["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    write("foundation_validation_report.json", report)
    inputs = [SOURCE / "03_structured_document.json", *(SOURCE / "semantic_rdf" / name for name in ["10_semantic_validated.json", "10_dsl_rules.json", "10_manual_review_queue.json"]), ROOT / "IBE2021_11Accessibility.pdf"]
    outputs = [p for p in ACC.rglob("*") if p.is_file() and ".python_deps" not in p.parts and "__pycache__" not in p.parts and p.name not in {"manifest.json"}]
    write("manifest.json", {"created_at_utc": datetime.now(timezone.utc).isoformat(),
                            "python": platform.python_version(), "platform": platform.platform(),
                            "packages": {n: version(n) for n in ["ifctester", "ifcopenshell", "rdflib", "xmlschema"]},
                            "inputs": [{"path": str(p.relative_to(ROOT)), "sha256": sha(p)} for p in inputs],
                            "outputs": [{"path": str(p.relative_to(ROOT)), "sha256": sha(p)} for p in sorted(outputs)]})
    print(json.dumps(report))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

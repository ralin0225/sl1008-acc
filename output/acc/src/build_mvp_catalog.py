"""Create an evidence-backed MVP catalog. Approval is never inferred from triage."""
from __future__ import annotations

import json
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ACC = ROOT / "output/acc"
SOURCE = ROOT / "output/ibe_accessibility_structure"


def main():
    candidates = json.loads((SOURCE / "semantic_rdf/10_semantic_validated.json").read_text(encoding="utf-8"))["candidates"]
    by_node = {x["source_node_id"]: x for x in candidates}
    document = json.loads((SOURCE / "03_structured_document.json").read_text(encoding="utf-8"))
    contexts = json.loads((ACC / "rule_review_context.json").read_text(encoding="utf-8"))["contexts"]
    definitions = [
        ("parking-minimum", "Parking count per facility", "ibc2021-1106.2", "count", "table_1106_2", ["total", "accessible"], "COUNT_ONLY"),
        ("van-parking-minimum", "Van-accessible parking count", "ibc2021-1106.6", "count", "ceil_total_div_6", ["total", "accessible"], "COUNT_ONLY"),
        ("public-entrance-minimum", "Accessible public entrance count", "ibc2021-1105.1", "count", "ceil_total_times_60_percent", ["total", "accessible"], "COUNT_ONLY"),
        ("tenant-entrance-minimum", "Accessible entrance count for one tenant", "ibc2021-1105.1.7", "count", "at_least_one", ["accessible"], "COUNT_ONLY"),
        ("type-a-unit-minimum", "Type A unit count for approved site scope", "ibc2021-1108.6.2.2.1", "count", "ceil_total_times_2_percent_over_20", ["total", "accessible"], "COUNT_ONLY"),
        ("site-route-connectivity", "Verified accessible connectivity on one site", "ibc2021-1104.2", "topology", "verified_graph_connected", ["nodes", "edges", "targets"], "CONNECTIVITY_ONLY"),
        ("required-accessibility-pset", "Project accessibility properties", "ibc2021-1102.1", "information", "ids_precheck", [], "INFORMATION_ONLY"),
        ("space-use-classification", "Project space use classification", "ibc2021-1110.2", "information", "ids_precheck", [], "INFORMATION_ONLY"),
    ]
    rules = []
    inventory_kinds = {
        "parking-minimum": "parking_facility_total_and_accessible_spaces",
        "van-parking-minimum": "accessible_parking_and_van_accessible_spaces",
        "public-entrance-minimum": "public_entrances_and_accessible_public_entrances",
        "tenant-entrance-minimum": "one_tenant_accessible_entrances",
        "type-a-unit-minimum": "reviewed_site_units_and_type_a_units",
        "site-route-connectivity": "reviewed_site_accessible_targets_and_routes",
    }
    for identifier, name, source, kind, expression, required, scope in definitions:
        c = by_node[source]
        rules.append({
            "rule_id": identifier, "name": name, "source_node_id": source,
            "kind": kind, "expression": expression, "required_fields": required,
            "inventory_kind": inventory_kinds.get(identifier),
            "result_scope": scope, "origin": "project_data_contract" if kind == "information" else "IBC_candidate_subcheck",
            "execution_gate": "requires_explicit_scope_review" if kind != "information" else "precheck_only",
            "source_review_required": c["quality"]["requires_review"],
            "exception_node_ids": c.get("exception_node_ids", []),
            "evidence": c["evidence"],
            "conditions_and_references": {"conditions": c.get("conditions", []), "references": c.get("cross_references", [])},
            "interpretation_author": "AI-assisted implementation; pending scope review",
            "full_clause_compliance_evaluated": False,
            "review_context": {"file": "rule_review_context.json", "source_node_id": source, "sha256": contexts[source]["sha256"]},
        })
    table = document["tables"]["table-p004-01"]
    assert table["header_names"][0].startswith("TOTAL PARKING")
    caption_nodes = [n["id"] for n in document["nodes"].values() if "TABLE 1106.2" in n["text_normalized"]]
    assert caption_nodes and "Table 1106.2" in by_node["ibc2021-1106.2"]["evidence"]["text"]
    table_hash = hashlib.sha256(json.dumps(table, sort_keys=True).encode()).hexdigest()
    for rule in rules:
        definition = {"expression": rule["expression"], "source_sha256": rule["evidence"]["sha256"],
                      "inventory_kind": rule["inventory_kind"], "result_scope": rule["result_scope"]}
        definition["review_context_sha256"] = rule["review_context"]["sha256"]
        if rule["rule_id"] == "parking-minimum":
            definition["table_sha256"] = table_hash
        rule["definition_sha256"] = hashlib.sha256(json.dumps(definition, sort_keys=True).encode()).hexdigest()
    catalog = {"schema_version": "0.1.0", "rules": rules,
               "parking_table": {**table, "source_node_id": "ibc2021-1106.2", "caption_node_ids": caption_nodes, "sha256": table_hash,
                                 "source_pdf": "IBE2021_11Accessibility.pdf", "binding_method": "Table number in clause and caption plus source page; scope review required"},
               "external_standard_deferrals": [
                   {"concept": "Door clear opening width", "source_node_id": "ibc2021-1102.1", "status": "requires_external_standard", "threshold": None},
                   {"concept": "Ramp slope", "source_node_id": "ibc2021-1102.1", "status": "requires_external_standard", "threshold": None},
               ],
               "note": "PASS applies only to result_scope. Accessible declarations cannot establish compliant design."}
    (ACC / "mvp_rule_catalog.json").write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    template = {"schema_version": "0.1.0", "is_synthetic": False, "note": "Blank review template; does not contain model facts or approvals", "facts_by_rule": {}}
    for rule in rules:
        template["facts_by_rule"][rule["rule_id"]] = {
            "model_evidence": None, "scope_id": None, "inventory_kind": rule["inventory_kind"],
            "applicable": None, "applicability_evidence": None, "inventory_complete": None,
            "accessible_design_verified": None, "accessible_design_evidence": None,
            "scope_review": {"resolution": "PENDING", "reviewer": None, "rationale": None,
                             "source_sha256": rule["evidence"]["sha256"], "definition_sha256": rule["definition_sha256"]},
            **{field: None for field in rule["required_fields"]},
        }
    (ACC / "normalized_facts.template.json").write_text(json.dumps(template, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Created {len(rules)} MVP candidates; all regulatory subchecks require explicit scope review")


if __name__ == "__main__":
    main()

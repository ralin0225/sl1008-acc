"""Versioned ACC contracts. No legal approval is created by this builder."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ACC = Path(__file__).resolve().parents[1]
VERSION = "1.0.0"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def build_contracts():
    legacy = read(ACC / "mvp_rule_catalog.json")
    laws = {x["id"]: x for x in read(ACC / "viewer/dist/data/regulations.json")["laws"]}
    types = {
        "parking-minimum": ["IfcSpace"], "van-parking-minimum": ["IfcSpace"],
        "public-entrance-minimum": ["IfcDoor"], "tenant-entrance-minimum": ["IfcDoor"],
        "type-a-unit-minimum": ["IfcSpace", "IfcZone"],
        "site-route-connectivity": ["IfcSpace", "IfcDoor", "IfcRamp", "IfcStair", "IfcRampFlight", "IfcStairFlight"],
        "required-accessibility-pset": ["IfcDoor", "IfcRamp", "IfcStair", "IfcSpace"],
        "space-use-classification": ["IfcSpace"], "egress-door-clear-width": ["IfcDoor"],
    }
    rules = []
    seeds = list(legacy["rules"]) + [{"rule_id": "egress-door-clear-width", "name": "Egress door clear opening width",
        "kind": "dimension", "source_node_id": "ibc2021-1010.1.1", "result_scope": "CLEAR_WIDTH_ONLY",
        "required_fields": ["clear_width"], "inventory_kind": "reviewed_egress_doors"}]
    for seed in seeds:
        law = laws[seed["source_node_id"]]
        if seed.get("evidence") and seed["evidence"]["sha256"] != law["sha256"]:
            raise ValueError("Legacy source text differs from viewer evidence")
        kind = seed["kind"]
        fields = seed["required_fields"] if kind != "information" else ["Accessible" if seed["rule_id"] == "required-accessibility-pset" else "UseCode"]
        contract = {
            "rule_id": seed["rule_id"], "rule_version": VERSION, "name": seed["name"], "kind": kind,
            "chapter": law["chapter"], "topic": "Egress" if law["chapter"] == 10 else "Accessibility",
            "source_node_id": seed["source_node_id"],
            "evidence": {"text": law["text"], "sha256": law["sha256"], "source_pdf": law["sourceFile"],
                         "pdf_file": law["pdfFile"], "fragments": law["fragments"],
                         "context": law["context"], "tables": [legacy["parking_table"]] if seed["rule_id"] == "parking-minimum" else []},
            "applicability": {"method": "evidence_bound_manual_review", "scope": seed.get("inventory_kind") or "reviewed_project_information_targets",
                "exceptions": law["context"]["exception_node_ids"], "conditions": seed.get("conditions_and_references", {}),
                "dimension_branches": ["general_32_inch", "i2_bed_movement_41_5_inch"] if kind == "dimension" else [],
                "note": "Review ancestors, exceptions, occupancy and target scope; candidate entity matches do not establish applicability."},
            "required_ifc_data": [{"field": f, "data_type": "integer" if kind == "count" else "length" if kind == "dimension" else "graph" if kind == "topology" else "boolean" if f == "Accessible" else "classification",
                "unit": "m" if kind == "dimension" else "count" if kind == "count" else None,
                "methods": ["reviewed_manual_input", "occurrence_pset"] if kind != "topology" else ["reviewed_space_relationships"],
                "entities": types[seed["rule_id"]], "independent_verification_required": kind != "information"} for f in fields],
            "target_selector": {"entities": types[seed["rule_id"]], "method": "reviewed_GlobalId_set",
                "inventory_kind": seed.get("inventory_kind"), "complete_inventory_required": True,
                "zero_targets_result": "NOT_CHECKABLE", "candidate_selection_only": True},
            "check_function": "legacy_count" if kind == "count" else "legacy_connectivity" if kind == "topology" else "required_information" if kind == "information" else "clear_width",
            "parameters": {"expression": seed.get("expression"), "comparison": ">=" if kind in ("count", "dimension") else "verified_reachable" if kind == "topology" else "present_and_valid",
                "thresholds": {"general_32_inch": 0.8128, "i2_bed_movement_41_5_inch": 1.0541} if kind == "dimension" else {},
                "threshold_source": "IBC 2021 1010.1.1 inch values converted exactly at 0.0254 m/in; printed rounded mm retained in source" if kind == "dimension" else "versioned legacy expression and source table",
                "tolerance": 0, "tolerance_basis": "No regulatory relaxation; exact comparison"},
            "result_scope": seed["result_scope"], "full_clause_compliance_evaluated": False,
            "review_status": "PENDING", "review_evidence": [], "execution_ready": False,
            "execution_gate": "source_and_contract_hash_bound_scope_review",
            "test_cases": {"file": "tests/test_compliance.py", "states": ["PASS", "FAIL", "MISSING_DATA", "NOT_APPLICABLE"]},
            "legacy_definition_sha256": seed.get("definition_sha256"),
        }
        if kind == "count":
            contract["required_ifc_data"].append({"field": "accessible_global_ids", "data_type": "GlobalId_set", "unit": None,
                "methods": ["reviewed_manual_input"], "entities": types[seed["rule_id"]], "independent_verification_required": True})
        if kind == "dimension":
            contract["required_ifc_data"][0].update({"property": "ACC_Accessibility.ClearOpeningWidth",
                "measurement_definition": "Swinging door: face of leaf to stop at 90 degrees; double leaf without mullion: one leaf; source exceptions reviewed",
                "prohibited_substitutes": ["IfcDoor.OverallWidth", "bounding_box_width"]})
        contract["contract_sha256"] = digest(contract)
        rules.append(contract)
    return {"schema_version": VERSION, "rules": rules, "note": "Draft contracts; no model or legal approval inferred. Project information results are not IBC compliance."}


def load_contracts():
    catalog = read(ACC / "executable_rule_contracts.json")
    from compliance_schema import validate
    validate("rule_contract", catalog)
    for rule in catalog["rules"]:
        payload = {k: v for k, v in rule.items() if k != "contract_sha256"}
        if digest(payload) != rule["contract_sha256"]:
            raise ValueError(f"Stale contract hash: {rule['rule_id']}")
        if hashlib.sha256(rule["evidence"]["text"].encode()).hexdigest() != rule["evidence"]["sha256"]:
            raise ValueError("Source text hash mismatch")
    return catalog


if __name__ == "__main__":
    save(ACC / "executable_rule_contracts.json", build_contracts())
    print("Built 9 draft contracts; execution gates retained")

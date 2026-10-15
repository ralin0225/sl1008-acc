"""Prepare review inputs and current hashes; never grant APPROVED status."""
import argparse
from pathlib import Path
from compliance_contract import ACC, load_contracts, read, save
from compliance_runner import facts_hash
from ifc_requirements import extract_requirements


def prepare(path, model_id, inputs=None):
    extraction = extract_requirements(path, model_id)
    rules = load_contracts()["rules"]
    inputs = inputs or {"schema_version": "1.0.0", "is_synthetic": False, "facts_by_rule": {}}
    for rule in rules:
        value = inputs["facts_by_rule"].get(rule["rule_id"])
        if value is None:
            value = {"model_evidence": {"ifc_sha256": extraction["model_sha256"], "ifc_path": extraction["ifc_path"]},
                "applicable": None, "applicability_evidence": None, "scope_id": None, "inventory_complete": False,
                "inventory_kind": rule["target_selector"]["inventory_kind"], "target_global_ids": [],
                **{d["field"]: None for d in rule["required_ifc_data"] if rule["kind"] in ("count", "topology")}}
            if rule["kind"] == "count":
                value.update(accessible_design_verified=False, accessible_design_evidence=None)
            if rule["kind"] == "dimension":
                value.update(width_branch=None, clear_width_semantics_verified=False, measurement_definition_evidence=None)
        instances = value if isinstance(value, list) else [value]
        for facts in instances:
            old = facts.get("scope_review") or {}
            facts["scope_review"] = {"resolution": "PENDING", "reviewer": old.get("reviewer"), "rationale": old.get("rationale"),
                "source_sha256": rule["evidence"]["sha256"], "contract_sha256": rule["contract_sha256"],
                "definition_sha256": rule["legacy_definition_sha256"], "facts_sha256": facts_hash(facts)}
        inputs["facts_by_rule"][rule["rule_id"]] = value
    return inputs


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ifc", type=Path)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--facts", type=Path, help="Existing completed facts; hashes refreshed and all approvals reset to PENDING")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    save(args.output, prepare(args.ifc, args.model_id, read(args.facts) if args.facts else None))
    print(args.output)

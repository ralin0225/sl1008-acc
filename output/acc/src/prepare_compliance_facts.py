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
                if rule["rule_id"] == "egress-door-clear-width":
                    value.update(width_branch=None, clear_width_semantics_verified=False, measurement_definition_evidence=None)
            if rule["check_function"] == "residential_check":
                value.update(residential_profile={"code_basis": None, "occupancy": None, "stories_above_grade": None,
                    "single_dwelling": None, "evidence": None}, exceptions_reviewed=False)
                if rule["rule_class"] == 1:
                    value.update(measurements={}, measurement_semantics_verified=False, measurement_definition_evidence=None)
                    if rule["rule_id"] == "residential-tread-depth":
                        value["rectangular_treads_verified"] = False
                elif rule["rule_id"] == "residential-stair-uniformity":
                    value["flight_dimensions"] = {"inventory_complete": False, "evidence": None,
                        "rectangular_treads_verified": False, "riser_count": None, "tread_count": None,
                        "riser_heights": [], "tread_depths": []}
                elif rule["rule_id"] == "residential-escape-opening":
                    value["opening_dimensions"] = {"shape": None, "normal_operation_verified": False, "evidence": None,
                        "branch": None, "branch_evidence": None, "net_width": None, "net_height": None, "sill_height": None}
                elif rule["rule_id"] == "residential-stair-headroom":
                    value["clearance_surface"] = {"representation": "piecewise_planar_full_clearance", "full_surface_verified": False,
                        "scope_covers_required_headroom": False, "evidence": None, "source_global_id": None,
                        "geometry_source_global_ids": [], "unit": None, "x": [], "y": [], "nosing_z": [], "overhead_z": [],
                        "domain_length": None, "domain_width": None}
                else:
                    value["route_graph"] = {"inventory_complete": False, "evidence": None, "exit_discharge_verified": False,
                        "exit_evidence": None, "nodes": [], "edges": [], "starts": [], "exits": []}
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
    parser.add_argument("--residential-only", action="store_true", help="Prepare only the six residential subchecks")
    args = parser.parse_args()
    prepared = prepare(args.ifc, args.model_id, read(args.facts) if args.facts else None)
    if args.residential_only:
        residential_ids = {r["rule_id"] for r in load_contracts()["rules"] if r["check_function"] == "residential_check"}
        prepared["facts_by_rule"] = {rid: value for rid, value in prepared["facts_by_rule"].items() if rid in residential_ids}
    save(args.output, prepared)
    print(args.output)

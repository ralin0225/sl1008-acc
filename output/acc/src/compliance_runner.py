"""Regulation-driven deterministic runner with Why/What/Where and immutable runs."""
from __future__ import annotations

import argparse
import hashlib
import math
import uuid
from datetime import datetime, timezone
from pathlib import Path

from acc_engine import evaluate
from compliance_contract import ACC, VERSION, digest, read, save, load_contracts, build_contracts
from ifc_requirements import extract_requirements
from residential_checks import residential_check

REASONS = {"MISSING_DATA", "INVALID_DATA", "INVALID_GEOMETRY", "UNKNOWN_APPLICABILITY",
           "INCOMPLETE_TARGET_SET", "UNRESOLVED_REFERENCE", "REQUIRES_MANUAL_REVIEW", "CHECK_ERROR"}
FUNCTIONS = {}


def facts_hash(facts):
    return digest({k: v for k, v in facts.items() if k != "scope_review"})


def summary(results):
    counts = {key: sum(r["display_status"] == key for r in results) for key in ("PASS", "FAIL", "NOT CHECKABLE", "NOT_APPLICABLE")}
    decided = counts["PASS"] + counts["FAIL"]
    applicable = decided + counts["NOT CHECKABLE"]
    return {"rule_count": len({r["rule_id"] for r in results}), "instance_count": len(results), **counts,
            "completed_determination_rate": decided / applicable if applicable else None,
            "determined_pass_rate": counts["PASS"] / decided if decided else None}


def review_valid(rule, facts):
    review = facts.get("scope_review")
    return (isinstance(review, dict) and review.get("resolution") == "APPROVED"
            and isinstance(review.get("reviewer"), str) and bool(review["reviewer"].strip())
            and isinstance(review.get("rationale"), str) and bool(review["rationale"].strip())
            and review.get("source_sha256") == rule["evidence"]["sha256"]
            and review.get("contract_sha256") == rule["contract_sha256"]
            and review.get("facts_sha256") == facts_hash(facts))


def failure(status, reason_code, reason, **values):
    return {"status": status, "reason_code": reason_code, "reason": reason, **values}


def legacy_check(rule, facts, targets, catalog, extraction):
    legacy = next(r for r in catalog["rules"] if r["rule_id"] == rule["rule_id"])
    if rule["legacy_definition_sha256"] != legacy["definition_sha256"]:
        return failure("MANUAL_REVIEW", "REQUIRES_MANUAL_REVIEW", "Legacy definition changed; rebuild and review contract")
    if rule["kind"] == "count":
        if any(facts.get(field) is None for field in legacy["required_fields"]):
            return failure("UNKNOWN", "MISSING_DATA", "Required scoped count is missing")
        accessible = facts.get("accessible_global_ids")
        target_ids = {r["global_id"] for r in targets}
        if not isinstance(accessible, list):
            return failure("UNKNOWN", "MISSING_DATA" if accessible is None else "INVALID_DATA", "Verified counted objects must be supplied as accessible_global_ids")
        if (any(not isinstance(g, str) for g in accessible) or len(accessible) != len(set(accessible))
                or not set(accessible).issubset(target_ids) or facts.get("accessible") != len(accessible)
                or ("total" in legacy["required_fields"] and facts.get("total") != len(targets))):
            return failure("UNKNOWN", "INVALID_DATA", "Scoped quantities do not agree with the reviewed object inventory")
    if rule["kind"] == "topology":
        nodes = facts.get("nodes")
        if not isinstance(nodes, list) or not nodes:
            return failure("UNKNOWN", "MISSING_DATA", "Reviewed graph nodes are required")
        if any(not isinstance(g, str) for g in nodes) or not set(nodes).issubset({r["global_id"] for r in targets}):
            return failure("UNKNOWN", "INVALID_DATA", "Route node IDs must bind to the reviewed IFC GlobalId set")
    result = evaluate(legacy, facts, catalog["parking_table"])
    status = result["status"]
    code = None
    if status == "MANUAL_REVIEW":
        code = "REQUIRES_MANUAL_REVIEW"
    elif status == "UNKNOWN":
        code = "INVALID_DATA" if any(s in result["reason"] for s in ("integer", "exceeds")) else "MISSING_DATA"
        if rule["kind"] == "topology":
            code = "INVALID_DATA" if result["reason"] in ("graph fields must be lists", "invalid graph identifiers", "at least two explicit graph targets required", "invalid edge endpoint") else "MISSING_DATA"
    return {**result, "reason_code": code, "required": result.get("minimum", "pairwise verified reachability" if rule["kind"] == "topology" else None),
            "unit": "count" if rule["kind"] == "count" else None}


def information_check(rule, facts, targets, catalog, extraction):
    field = rule["required_ifc_data"][0]["field"]
    observations = [target["observations"][field] for target in targets]
    if any(o["missing_reason"] == "MISSING_DATA" for o in observations):
        return failure("UNKNOWN", "MISSING_DATA", "Required project property is absent; this is an information requirement")
    valid = all(o["valid"] for o in observations)
    if field == "UseCode":
        valid = valid and all(o["value"] in {"TOILET_ROOM", "PARKING_SPACE", "DWELLING_UNIT", "SLEEPING_UNIT", "OTHER"} for o in observations)
    return {"status": "PASS" if valid else "FAIL", "reason_code": None if valid else "INVALID_DATA",
            "reason": "Checked project information presence and type; accessible declarations do not establish design compliance",
            "required": "boolean" if field == "Accessible" else "project UseCode enumeration", "actual": [o["value"] for o in observations], "unit": None}


def clear_width_check(rule, facts, targets, catalog, extraction):
    branch = facts.get("width_branch")
    if branch not in rule["parameters"]["thresholds"]:
        return failure("UNKNOWN", "UNKNOWN_APPLICABILITY", "Select and review the general or I-2 bed-movement requirement branch")
    if len(targets) != 1:
        return failure("UNKNOWN", "INVALID_DATA", "Clear width requires exactly one door per check instance")
    observation = targets[0]["observations"]["clear_width"]
    if "clear_width" in facts:
        observation = facts["clear_width"]
        if not isinstance(observation, dict):
            return failure("UNKNOWN", "INVALID_DATA", "Manual clear width must be a typed observation")
        if observation.get("method") != "reviewed_manual_input" or observation.get("source_global_id") != targets[0]["global_id"] or not observation.get("evidence"):
            return failure("UNKNOWN", "INVALID_DATA", "Manual measurement requires target GlobalId, method and measurement evidence")
    if not observation.get("valid"):
        code = observation.get("missing_reason")
        return failure("UNKNOWN", code if code in REASONS else "MISSING_DATA", "Verified clear opening measurement unavailable")
    if facts.get("clear_width_semantics_verified") is not True or not facts.get("measurement_definition_evidence"):
        return failure("UNKNOWN", "MISSING_DATA", "Measurement semantics require independent evidence; OverallWidth and bounding boxes are insufficient")
    factors = {"m": 1, "mm": .001, "inch": .0254}
    value, unit = observation.get("value"), observation.get("unit")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0 or unit not in factors:
        return failure("UNKNOWN", "INVALID_DATA", "Clear width must be a positive finite length with an explicit supported unit")
    actual = value * factors[unit]
    minimum = rule["parameters"]["thresholds"][branch]
    return {"status": "PASS" if actual >= minimum else "FAIL", "reason_code": None,
            "reason": "Compared reviewed clear width against the reviewed source branch; other door requirements remain outside this subcheck",
            "actual": actual, "required": minimum, "unit": "m", "measurement": observation}


FUNCTIONS.update(legacy_count=legacy_check, legacy_connectivity=legacy_check,
                 required_information=information_check, clear_width=clear_width_check, residential_check=residential_check)


def dispatch(rule, facts, extraction, catalog):
    if extraction.get("extraction_error"):
        return failure("CHECK_ERROR", "CHECK_ERROR", extraction["extraction_error"]), [], "unavailable"
    candidates = [r for r in extraction["records"] if set(r.get("entity_types", [r["ifc_type"]])) & set(rule["target_selector"]["entities"])]
    selected = facts.get("target_global_ids") if isinstance(facts, dict) else None
    targets = [r for r in candidates if selected and r["global_id"] in selected] if isinstance(selected, list) else candidates
    if not isinstance(facts, dict):
        return failure("UNKNOWN", "UNKNOWN_APPLICABILITY", "No reviewed applicability facts supplied"), targets, "candidate_unreviewed"
    # Applicability precedes target/data checks. Even exclusions need a current evidence-bound review.
    if not isinstance(facts.get("applicable"), bool) or not facts.get("applicability_evidence"):
        return failure("UNKNOWN", "UNKNOWN_APPLICABILITY", "Applicability and exceptions have not been established"), targets, "candidate_unreviewed"
    evidence = facts.get("model_evidence")
    if not isinstance(evidence, dict) or evidence.get("ifc_sha256") != extraction["model_sha256"]:
        return failure("UNKNOWN", "INVALID_DATA", "Facts do not bind to this model version"), targets, "candidate_unreviewed"
    if not review_valid(rule, facts):
        return failure("MANUAL_REVIEW", "REQUIRES_MANUAL_REVIEW", "Source, contract and input facts require a current evidence-bound review"), targets, "candidate_unreviewed"
    if extraction["schema"] != "IFC4":
        return failure("MANUAL_REVIEW", "REQUIRES_MANUAL_REVIEW", "This rule profile has only been reviewed for IFC4"), targets, "candidate_unreviewed"
    if facts["applicable"] is False:
        return failure("NOT_APPLICABLE", None, "Reviewed evidence excludes this subcheck"), targets, "excluded_reviewed"
    if not extraction["identity_valid"]:
        return failure("UNKNOWN", "INVALID_DATA", "Model GlobalIds are missing or duplicated"), targets, "reviewed"
    if not isinstance(selected, list) or not selected or any(not isinstance(x, str) for x in selected) or len(selected) != len(set(selected)):
        return failure("UNKNOWN", "INCOMPLETE_TARGET_SET", "Nonempty explicit GlobalId target inventory required"), targets, "reviewed"
    if set(selected) != {r["global_id"] for r in targets}:
        return failure("UNKNOWN", "INVALID_DATA", "Targets are absent from the model or incompatible with this rule"), targets, "reviewed"
    if not facts.get("scope_id") or facts.get("inventory_complete") is not True:
        return failure("UNKNOWN", "INCOMPLETE_TARGET_SET", "Complete facility/site/tenant inventory is not confirmed"), targets, "reviewed"
    if facts.get("unresolved_required_references"):
        return failure("UNKNOWN", "UNRESOLVED_REFERENCE", "Required external or cross-clause evidence remains unresolved"), targets, "reviewed"
    if facts.get("geometry_required") and facts.get("geometry_valid") is not True:
        return failure("UNKNOWN", "INVALID_GEOMETRY", "Geometry required by this reviewed measurement is invalid or unavailable"), targets, "reviewed"
    result = FUNCTIONS[rule["check_function"]](rule, facts, targets, catalog, extraction)
    return result, targets, "reviewed"


def run(model_path, model_id, inputs=None, rule_ids=None, persist=True):
    if not isinstance(model_id, str) or not model_id or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for c in model_id):
        raise ValueError("Invalid model_id")
    inputs = inputs or {}
    if not isinstance(inputs, dict) or not isinstance(inputs.get("facts_by_rule", {}), dict):
        raise ValueError("facts_by_rule must be an object")
    rules = load_contracts()["rules"]
    # Bind live source/context/table and legacy definitions, not merely the stored hash.
    current = {r["rule_id"]: r for r in build_contracts()["rules"]}
    if any(r["contract_sha256"] != current[r["rule_id"]]["contract_sha256"] for r in rules):
        raise ValueError("Source or rule definition changed; rebuild contracts and obtain renewed reviews")
    if rule_ids is not None:
        if not isinstance(rule_ids, list) or not rule_ids or len(rule_ids) != len(set(rule_ids)) or set(rule_ids) - set(current):
            raise ValueError("Select one or more known unique rule IDs")
        rules = [r for r in rules if r["rule_id"] in rule_ids]
    try:
        extraction = extract_requirements(model_path, model_id)
    except Exception as exc:
        model_path = Path(model_path)
        if not model_path.is_file():
            raise  # Missing input file is a request error; no model identity exists.
        extraction = {"model_id": model_id, "model_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
                      "records": [], "extraction_error": f"IFC extraction failed: {type(exc).__name__}: {exc}"}
    catalog = read(ACC / "mvp_rule_catalog.json")
    run_id = uuid.uuid4().hex
    timestamp = datetime.now(timezone.utc).isoformat()
    checker_hash = digest({p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__), ACC / "src/acc_engine.py", ACC / "src/ifc_requirements.py", ACC / "src/compliance_contract.py", ACC / "src/residential_checks.py", ACC / "src/residential_contracts.py")})
    input_hash = digest({"facts": inputs, "model_sha256": extraction["model_sha256"], "contracts": [r["contract_sha256"] for r in rules], "checker_sha256": checker_hash})
    results = []
    for rule in rules:
        supplied = inputs.get("facts_by_rule", {}).get(rule["rule_id"])
        instances = supplied if isinstance(supplied, list) else [supplied]
        if not instances:
            instances = [None]  # Never disappear a rule because no instances matched.
        for number, facts in enumerate(instances):
            try:
                answer, targets, binding = dispatch(rule, facts, extraction, catalog)
            except Exception as exc:
                answer = failure("CHECK_ERROR", "CHECK_ERROR", f"{type(exc).__name__}: {exc}")
                targets, binding = [], "unavailable"
            internal = answer["status"]
            display = internal if internal in ("PASS", "FAIL", "NOT_APPLICABLE") else "NOT CHECKABLE"
            where = {"model_id": model_id, "model_sha256": extraction["model_sha256"],
                "global_ids": [r["global_id"] for r in targets],
                "objects": [{k: r[k] for k in ("global_id", "ifc_type", "name", "storey", "location", "step_id")} for r in targets],
                "scope_id": facts.get("scope_id") if isinstance(facts, dict) else None, "target_binding": binding, "camera": None}
            what = {"check_function": rule["check_function"], "required": answer.get("required"),
                "actual": answer.get("actual"), "unit": answer.get("unit"),
                "comparison": rule["parameters"]["comparison"], "tolerance": rule["parameters"]["tolerance"],
                "tolerance_basis": rule["parameters"]["tolerance_basis"], "reason_code": answer.get("reason_code"),
                "explanation": answer["reason"], "calculation": answer,
                "remediation": "Review the source requirement and the measured scoped result, correct the IFC manually and rerun." if internal == "FAIL" else "Provide or review the missing evidence and rerun." if display == "NOT CHECKABLE" else None}
            results.append({"instance_id": f"{rule['rule_id']}:{number}", "rule_id": rule["rule_id"], "rule_version": rule["rule_version"],
                **({"rule_class": rule["rule_class"], "class_basis": rule["class_basis"]} if "rule_class" in rule else {}),
                "chapter": rule["chapter"], "topic": rule["topic"], "status": internal, "display_status": display,
                "result_scope": rule["result_scope"], "full_clause_compliance_evaluated": False,
                "why": {"source_node_id": rule["source_node_id"], "rule_version": rule["rule_version"], "contract_sha256": rule["contract_sha256"], **rule["evidence"], "applicability": rule["applicability"],
                        **({"supporting_sources": rule["supporting_sources"], "dsl_sources": rule["dsl_sources"]} if "dsl_sources" in rule else {})},
                "what": what, "where": where,
                "run": {"run_id": run_id, "timestamp": timestamp, "checker_version": VERSION, "checker_sha256": checker_hash,
                    "input_sha256": input_hash, "review": facts.get("scope_review") if isinstance(facts, dict) else None,
                    "facts": facts if isinstance(facts, dict) else None, "observations": [{"global_id": r["global_id"], "data": r["observations"]} for r in targets]}})
    report = {"schema_version": VERSION, "run_id": run_id, "timestamp": timestamp,
              "model_id": model_id, "model_sha256": extraction["model_sha256"], "input_sha256": input_hash,
              "is_synthetic": inputs.get("is_synthetic", False), "full_clause_compliance_evaluated": False,
              "summary": summary(results), "results": results}
    validate_report(report)
    if persist:
        # A new UUID path for every run; never overwrite historical results.
        save(ACC / "runs" / model_id / f"{run_id}.json", report)
    return report


def validate_report(report):
    from compliance_schema import validate
    validate("compliance_report", report)
    for result in report["results"]:
        if result["display_status"] == "NOT CHECKABLE" and result["what"]["reason_code"] not in REASONS:
            raise ValueError("NOT CHECKABLE requires a specific reason code")
        if result["where"]["model_sha256"] != report["model_sha256"] or result["run"]["run_id"] != report["run_id"]:
            raise ValueError("Result identity does not match run")
    if summary(report["results"]) != report["summary"]:
        raise ValueError("Summary differs from results")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ifc", type=Path)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--facts", type=Path)
    parser.add_argument("--rules", nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.model_id or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for c in args.model_id):
        parser.error("model-id must contain lowercase letters, digits, hyphens or underscores")
    report = run(args.ifc, args.model_id, read(args.facts) if args.facts else None, args.rules)
    save(args.output, report)
    print(args.output)


if __name__ == "__main__":
    main()

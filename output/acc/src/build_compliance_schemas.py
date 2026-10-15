"""JSON Schema for executable rule contracts and Why/What/Where reports."""
from compliance_contract import ACC, save

HASH = {"type": "string", "pattern": "^[a-f0-9]{64}$"}
TEXT = {"type": "string", "minLength": 1}


def obj(properties, required=None):
    return {"type": "object", "properties": properties, "required": required or list(properties)}


def main():
    source = obj({"text": TEXT, "sha256": HASH, "source_pdf": TEXT, "pdf_file": TEXT,
        "fragments": {"type": "array", "minItems": 1, "items": obj({
            "pdf_page_number": {"type": "integer", "minimum": 1}, "source_pdf_page": {"type": "integer", "minimum": 1},
            "bbox": {"type": "array", "minItems": 4, "maxItems": 4, "items": {"type": "number"}}})},
        "context": {"type": "object"}, "tables": {"type": "array"}})
    contract = obj({"rule_id": TEXT, "rule_version": {"const": "1.0.0"}, "source_node_id": TEXT,
        "chapter": {"enum": [10, 11]}, "topic": {"enum": ["Accessibility", "Egress"]}, "kind": {"enum": ["count", "topology", "information", "dimension"]},
        "evidence": source, "applicability": obj({"method": TEXT, "scope": TEXT, "exceptions": {"type": "array"}}),
        "required_ifc_data": {"type": "array", "minItems": 1, "items": obj({"field": TEXT, "data_type": TEXT,
            "unit": {"type": ["string", "null"]}, "methods": {"type": "array", "minItems": 1}, "entities": {"type": "array", "minItems": 1}})},
        "target_selector": obj({"entities": {"type": "array", "minItems": 1}, "method": TEXT, "complete_inventory_required": {"const": True}, "zero_targets_result": {"const": "NOT_CHECKABLE"}}),
        "check_function": {"enum": ["legacy_count", "legacy_connectivity", "required_information", "clear_width"]},
        "parameters": obj({"comparison": TEXT, "thresholds": {"type": "object"}, "threshold_source": TEXT,
            "tolerance": {"type": "number", "minimum": 0}, "tolerance_basis": TEXT}),
        "result_scope": TEXT, "review_status": {"enum": ["PENDING", "APPROVED"]}, "review_evidence": {"type": "array"},
        "execution_ready": {"type": "boolean"}, "execution_gate": TEXT, "test_cases": {"type": "object"},
        "contract_sha256": HASH, "full_clause_compliance_evaluated": {"const": False}})
    result = obj({"instance_id": TEXT, "rule_id": TEXT, "rule_version": TEXT, "chapter": {"enum": [10, 11]},
        "topic": TEXT, "status": {"enum": ["PASS", "FAIL", "UNKNOWN", "MANUAL_REVIEW", "CHECK_ERROR", "NOT_APPLICABLE"]},
        "display_status": {"enum": ["PASS", "FAIL", "NOT CHECKABLE", "NOT_APPLICABLE"]},
        "result_scope": TEXT, "full_clause_compliance_evaluated": {"const": False},
        "why": {**source, "properties": {**source["properties"], "source_node_id": TEXT, "rule_version": TEXT, "contract_sha256": HASH, "applicability": {"type": "object"}}, "required": source["required"] + ["source_node_id", "rule_version", "contract_sha256", "applicability"]},
        "what": obj({"check_function": TEXT, "required": {}, "actual": {}, "unit": {"type": ["string", "null"]},
            "comparison": TEXT, "tolerance": {"type": "number"}, "tolerance_basis": TEXT,
            "reason_code": {"enum": [None, "MISSING_DATA", "INVALID_DATA", "INVALID_GEOMETRY", "UNKNOWN_APPLICABILITY", "INCOMPLETE_TARGET_SET", "UNRESOLVED_REFERENCE", "REQUIRES_MANUAL_REVIEW", "CHECK_ERROR"]},
            "explanation": TEXT, "calculation": {"type": "object"}}),
        "where": obj({"model_id": TEXT, "model_sha256": HASH, "global_ids": {"type": "array", "uniqueItems": True, "items": TEXT},
            "objects": {"type": "array", "items": obj({"global_id": TEXT, "ifc_type": TEXT, "name": {"type": ["string", "null"]}, "storey": {"type": ["object", "null"]}, "location": {"type": ["object", "null"]}, "step_id": {"type": "integer"}})},
            "scope_id": {"type": ["string", "null"]}, "target_binding": {"enum": ["reviewed", "candidate_unreviewed", "excluded_reviewed", "unavailable"]}, "camera": {"type": ["object", "null"]}}),
        "run": obj({"run_id": TEXT, "timestamp": TEXT, "checker_version": TEXT, "checker_sha256": HASH, "input_sha256": HASH,
            "review": {"type": ["object", "null"]}, "facts": {"type": ["object", "null"]}, "observations": {"type": "array"}})})
    result["allOf"] = [{"if": {"properties": {"display_status": {"const": "NOT CHECKABLE"}}},
        "then": {"properties": {"what": {"properties": {"reason_code": {"type": "string"}}}}}}]
    report = obj({"schema_version": {"const": "1.0.0"}, "run_id": TEXT, "timestamp": TEXT, "model_id": TEXT, "model_sha256": HASH,
        "input_sha256": HASH, "is_synthetic": {"type": "boolean"}, "full_clause_compliance_evaluated": {"const": False},
        "summary": obj({**{k: {"type": "integer", "minimum": 0} for k in ("rule_count", "instance_count", "PASS", "FAIL", "NOT CHECKABLE", "NOT_APPLICABLE")},
            **{k: {"type": ["number", "null"], "minimum": 0, "maximum": 1} for k in ("completed_determination_rate", "determined_pass_rate")}}),
        "results": {"type": "array", "items": result}})
    for name, schema in (("rule_contract", obj({"schema_version": {"const": "1.0.0"}, "rules": {"type": "array", "minItems": 1, "items": contract}})), ("compliance_report", report)):
        save(ACC / "schemas" / f"{name}.schema.json", {"$schema": "https://json-schema.org/draft/2020-12/schema", **schema})


if __name__ == "__main__":
    main()

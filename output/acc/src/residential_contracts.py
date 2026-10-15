"""Six evidence-bound IBC 2021 residential subchecks; no approvals are generated."""
import hashlib
import json


SPECS = [
    ("residential-riser-height", "住宅楼梯踢面高度", 1, "dimension", "ibc2021-ch10-list_item-0526", ["IfcStairFlight"],
     ["ibc2021-1011.5.2"], ["dsl-ibc2021-ch10-list_item-0526-1"], "riser_height", {"maximum": 0.19685},
     "Explicit, reviewed flight riser-height attribute; uniformity is checked separately."),
    ("residential-tread-depth", "住宅矩形踏步深度", 1, "dimension", "ibc2021-ch10-list_item-0526", ["IfcStairFlight"],
     ["ibc2021-1011.5.2"], ["dsl-ibc2021-ch10-list_item-0526-1"], "tread_depth", {"minimum": 0.254},
     "Explicit, reviewed rectangular tread-depth attribute; winders are outside this subcheck."),
    ("residential-stair-uniformity", "住宅梯段尺寸一致性", 2, "derived", "ibc2021-1011.5.4", ["IfcStairFlight"],
     ["ibc2021-1011.5.4.1"], ["dsl-ibc2021-1011.5.4-2"], "flight_dimensions", {"maximum_variation": 0.009525},
     "Derives max-minus-min separately from complete per-flight riser and tread inventories."),
    ("residential-escape-opening", "住宅应急逃生开口尺寸", 2, "derived", "ibc2021-1031.3.1", ["IfcWindow", "IfcDoor"],
     ["ibc2021-1031.2", "ibc2021-1031.3.2", "ibc2021-1031.3.3", "ibc2021-ch10-exception-1182"],
     ["dsl-ibc2021-1031.3.1-1", "dsl-ibc2021-ch10-exception-1182-1", "dsl-ibc2021-1031.3.2-1", "dsl-ibc2021-1031.3.2-2", "dsl-ibc2021-1031.3.3-1"],
     "opening_dimensions", {"minimum_width": 0.508, "minimum_height": 0.6096, "minimum_area": 0.529547328,
                            "grade_floor_minimum_area": 0.4645152, "maximum_sill_height": 1.1176},
     "Derives rectangular NET clear area; independently checks width, height and sill height."),
    ("residential-stair-headroom", "住宅楼梯连续净空", 3, "geometry", "ibc2021-1011.3", ["IfcStairFlight"],
     ["ibc2021-ch10-list_item-0518"], ["dsl-ibc2021-1011.3-1", "dsl-ibc2021-1011.3-2", "dsl-ibc2021-1011.3-3"],
     "clearance_surface", {"minimum_headroom": 2.032},
     "Uses a complete reviewed piecewise-planar clearance surface over the full required domain; point samples and bounding boxes cannot establish PASS."),
    ("residential-egress-continuity", "住宅疏散路径连续性", 3, "topology", "ibc2021-1003.6", ["IfcSpace", "IfcDoor", "IfcStair", "IfcStairFlight", "IfcRamp", "IfcRampFlight"],
     [], ["dsl-ibc2021-1003.6-1"], "route_graph", {},
     "Builds a directed, reviewed traversability graph and finds a witness path from every scoped room to a verified exit; not an accessible-route or complete egress certification."),
]


def build_residential_contracts(acc, laws, digest):
    atoms = json.loads((acc.parent / "ibc_means_of_egress_structure/semantic_rdf/10_dsl_rules.json").read_text(encoding="utf-8"))["rules"]
    atoms = {a["dsl_rule_id"]: a for a in atoms}
    rules = []
    for rid, name, cls, kind, source_id, entities, references, atom_ids, field, limits, rationale in SPECS:
        law = laws[source_id]
        supporting = [{"source_node_id": sid, "text": laws[sid]["text"], "sha256": laws[sid]["sha256"],
                       "fragments": laws[sid]["fragments"], "context": laws[sid]["context"]} for sid in references]
        rule = {
            "rule_id": rid, "rule_version": "1.0.0", "name": name, "chapter": 10, "topic": "Egress", "kind": kind,
            "rule_class": cls, "class_basis": rationale, "class_framework": "Solihin & Eastman (2015), computational checking method",
            "source_node_id": source_id,
            "evidence": {"text": law["text"], "sha256": law["sha256"], "source_pdf": law["sourceFile"], "pdf_file": law["pdfFile"],
                         "fragments": law["fragments"], "context": law["context"], "tables": []},
            "supporting_sources": supporting,
            "dsl_sources": [{"dsl_rule_id": aid, "source_node_id": atoms[aid]["source_node_id"],
                             "text": atoms[aid]["evidence_text"], "sha256": hashlib.sha256(atoms[aid]["evidence_text"].encode()).hexdigest(),
                             "atom_sha256": digest(atoms[aid])} for aid in atom_ids],
            "applicability": {"method": "evidence_bound_manual_review", "scope": "reviewed_two_storey_single_dwelling_R3_IBC2021",
                "exceptions": law["context"]["exception_node_ids"], "conditions": {"code_basis": "IBC2021", "occupancy": "R-3", "stories_above_grade": 2},
                "note": "Confirm IBC versus IRC, jurisdiction, residential exceptions, complete targets and measurement definitions. Never infer legal occupancy from names or geometry."},
            "required_ifc_data": [{"field": field, "data_type": "reviewed_structured_measurement", "unit": "m" if cls < 3 else None,
                "methods": ["reviewed_manual_input", "native_ifc_attribute"] if cls == 1 else ["reviewed_manual_input"],
                "entities": entities, "independent_verification_required": True}],
            "target_selector": {"entities": entities, "method": "reviewed_GlobalId_set", "inventory_kind": rid,
                "complete_inventory_required": True, "zero_targets_result": "NOT_CHECKABLE", "candidate_selection_only": True},
            "check_function": "residential_check", "parameters": {"comparison": "scoped_constraints", "thresholds": limits,
                "threshold_source": "IBC 2021 original inch/foot values converted exactly using 0.0254 m/in; no rounded-mm relaxation",
                "tolerance": 0, "tolerance_basis": "No regulatory relaxation; Decimal arithmetic for dimensional comparisons"},
            "result_scope": rid.upper().replace("-", "_") + "_ONLY", "full_clause_compliance_evaluated": False,
            "review_status": "PENDING", "review_evidence": [], "execution_ready": False,
            "execution_gate": "source_and_contract_hash_bound_scope_review", "legacy_definition_sha256": None,
            "test_cases": {"file": "tests/test_residential.py", "states": ["PASS", "FAIL", "MISSING_DATA", "NOT_APPLICABLE"]},
        }
        rule["contract_sha256"] = digest(rule)
        rules.append(rule)
    return rules

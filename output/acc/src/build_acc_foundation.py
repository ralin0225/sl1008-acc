"""Build a conservative, traceable ACC scope and IFC data contract.

This script reads completed Chapter 11 artifacts and never changes them.
"""
from __future__ import annotations

import collections
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "output/ibe_accessibility_structure/semantic_rdf"
OUT = ROOT / "output/acc"


def read(name: str) -> dict:
    return json.loads((SOURCE / name).read_text(encoding="utf-8"))


def write(name: str, value: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def evidence(candidate: dict) -> dict:
    src = candidate["evidence"]
    return {
        "source_node_id": candidate["source_node_id"],
        "source_pdf": "IBE2021_11Accessibility.pdf",
        "text": src["text"],
        "sha256": src["sha256"],
        "fragments": src["source_fragments"],
    }


def classify(rule: dict, candidate: dict) -> tuple[str, list[str]]:
    reasons = []
    source = candidate["evidence"]["text"].lower()
    snippet = (rule.get("evidence_text") or "").lower()
    combined = source + " " + snippet
    review = candidate["quality"]["requires_review"]
    if review:
        reasons.append("source_semantic_candidate_requires_review")
    if rule["statement_type"] in {"exception", "exemption", "permission"}:
        reasons.append("exception_or_permission_needs_parent_context")
        return "manual_review", reasons
    if re.search(r"icc\s*a117\.1|chapter\s+(?!11\b)\d+|section\s+(?!11\d{2})\d{3,4}", combined):
        reasons.append("depends_on_external_standard_or_chapter")
        return "requires_external_standard", reasons
    if any(k in combined for k in ("clear width", "slope", "clearance", "maneuvering")):
        reasons.append("geometric_measurement_and_threshold_interpretation_needed")
        return "computable_with_ifc_geometry", reasons
    if any(k in combined for k in ("accessible route", "connect", "travel distance", "shortest route")):
        reasons.append("accessible_graph_and_applicability_needed")
        return "computable_with_topology", reasons
    if any(k in combined for k in ("percent", "at least one", "not fewer than", "for every", "number of", "table 1106.2")):
        reasons.append("count_or_ratio_candidate; applicability_must_be_confirmed")
        return "directly_computable" if not review else "manual_review", reasons
    if review:
        return "manual_review", reasons
    if rule["statement_type"] in {"obligation", "prohibition"}:
        reasons.append("no_safe_machine_test_identified")
        return "non_computable", reasons
    return "manual_review", ["unclassified_modality"]


def main() -> None:
    candidates = read("10_semantic_validated.json")["candidates"]
    rules = read("10_dsl_rules.json")["rules"]
    queue = read("10_manual_review_queue.json")["items"]
    by_node = {c["source_node_id"]: c for c in candidates}
    queue_ids = {c["source_node_id"] for c in queue}
    assert queue_ids == {c["source_node_id"] for c in candidates if c["quality"]["requires_review"]}
    scoped = []
    for rule in rules:
        candidate = by_node[rule["source_node_id"]]
        category, reasons = classify(rule, candidate)
        scoped.append({
            "dsl_rule_id": rule["dsl_rule_id"],
            "source_node_id": rule["source_node_id"],
            "category": category,
            "reasons": reasons,
            "execution_ready": False,
            "statement_type": rule["statement_type"],
            "modality": rule["modality"],
            "semantic_review_required": candidate["quality"]["requires_review"],
            "exception_node_ids": candidate.get("exception_node_ids", []),
            "conditions": candidate.get("conditions", []),
            "cross_references": candidate.get("cross_references", []),
            "full_design_compliance_dependency": "ibc2021-1102.1 / ICC A117.1; count subchecks do not certify accessible design",
            "evidence": evidence(candidate),
        })
    counts = dict(collections.Counter(x["category"] for x in scoped))
    write("acc_scope.json", {
        "schema_version": "0.1.0", "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "method": "deterministic_conservative_keyword_triage; categories are planning labels, not approved rules",
        "source_files": ["10_semantic_validated.json", "10_dsl_rules.json", "10_manual_review_queue.json"],
        "rule_count": len(scoped), "category_counts": counts, "rules": scoped,
    })
    write("computable_rules.json", {
        "schema_version": "0.1.0", "status": "candidates_only",
        "rules": [x for x in scoped if x["category"] in {"directly_computable", "computable_with_ifc_geometry", "computable_with_topology"}],
    })
    write("deferred_rules.json", {
        "schema_version": "0.1.0",
        "rules": [x for x in scoped if x["category"] in {"requires_external_standard", "manual_review", "non_computable"}],
    })

    profile = {
        "schema_version": "0.1.0", "target_schema": "IFC4", "compatible_schema_for_reading": ["IFC4", "IFC4X3"],
        "ifc4x3_execution_status": "mapping_review_required",
        "units": {"source": "IfcUnitAssignment", "internal_length": "m", "internal_area": "m2", "internal_slope": "ratio", "missing_or_ambiguous": "UNKNOWN"},
        "required_spatial_hierarchy": ["IfcProject", "IfcSite", "IfcBuilding", "IfcBuildingStorey"],
        "object_types": ["IfcDoor", "IfcRamp", "IfcStair", "IfcSpace", "IfcZone", "IfcOpeningElement", "IfcRelSpaceBoundary"],
        "classification": {"system": "project_defined", "required_codes": ["TOILET_ROOM", "PARKING_SPACE", "DWELLING_UNIT", "SLEEPING_UNIT", "PUBLIC_ENTRANCE"], "absence": "UNKNOWN"},
        "space_boundary": {"preferred": "IfcRelSpaceBoundary2ndLevel", "fallback": "IfcRelSpaceBoundary", "absence_for_topology": "UNKNOWN"},
        "identity": {"guid": "IfcRoot.GlobalId required and unique", "accessible_route": "explicit project convention plus verified graph", "no_inference_from_name_alone": True},
        "geometry": {"required_for_geometry_checks": True, "generation_failure": "UNKNOWN", "bounding_box_alone_sufficient_for_clear_width": False},
        "missing_data_result": "UNKNOWN", "manual_review_result": "MANUAL_REVIEW",
        "result_states": ["PASS", "FAIL", "UNKNOWN", "NOT_APPLICABLE", "MANUAL_REVIEW"],
        "not_applicable_requires_evidence": True,
    }
    write("ifc_profile.json", profile)
    conventions = {
        "schema_version": "0.1.0", "status": "proposed_project_convention; requires_model_author_agreement",
        "pset_name": "ACC_Accessibility", "properties": {
            "Accessible": {"type": "IfcBoolean", "applies_to": ["IfcDoor", "IfcRamp", "IfcStair", "IfcSpace"], "meaning": "declared accessible; requires independent verification"},
            "UseCode": {"type": "IfcLabel", "applies_to": ["IfcSpace"], "allowed": ["TOILET_ROOM", "PARKING_SPACE", "DWELLING_UNIT", "SLEEPING_UNIT", "OTHER"]},
            "UnitType": {"type": "IfcLabel", "applies_to": ["IfcSpace", "IfcZone"], "allowed": ["ACCESSIBLE", "TYPE_A", "TYPE_B", "NONE"]},
            "EntranceType": {"type": "IfcLabel", "applies_to": ["IfcDoor"], "allowed": ["PUBLIC", "TENANT", "SERVICE", "OTHER"]},
            "ParkingFacilityId": {"type": "IfcIdentifier", "applies_to": ["IfcSpace", "IfcZone"], "meaning": "count parking separately by facility"},
            "ParkingIsVanAccessible": {"type": "IfcBoolean", "applies_to": ["IfcSpace"], "meaning": "van accessible declaration"},
            "RouteNodeId": {"type": "IfcIdentifier", "applies_to": ["IfcSpace", "IfcDoor", "IfcRamp", "IfcStair"], "meaning": "project route graph reference"},
            "ClearOpeningWidth": {"type": "IfcPositiveLengthMeasure", "applies_to": ["IfcDoor"], "meaning": "verified clear opening width in IFC project length unit"},
            "RunningSlope": {"type": "IfcRatioMeasure", "applies_to": ["IfcRamp"], "meaning": "rise divided by horizontal run"},
        },
        "missing_property_status": "UNKNOWN", "ids_failure_is_information_gap": True,
    }
    write("ifc_property_conventions.json", conventions)

    mapping_specs = [
        ("Building", ["IfcBuilding"], "object", "ibc2021-1101.1"),
        ("Storey", ["IfcBuildingStorey"], "object", "ibc2021-1104.4"),
        ("Door/Entrance", ["IfcDoor"], "object_plus_entrance_classification", "ibc2021-1105.1"),
        ("Ramp", ["IfcRamp"], "object_plus_geometry", "ibc2021-1104.4"),
        ("Stair", ["IfcStair"], "object_plus_route_context", "ibc2021-1104.4"),
        ("Toilet Room", ["IfcSpace"], "classification_UseCode_TOILET_ROOM", "ibc2021-1110.2"),
        ("Parking Space", ["IfcSpace", "IfcZone"], "classification_plus_facility_grouping", "ibc2021-1106.2"),
        ("Dwelling Unit", ["IfcSpace", "IfcZone"], "space_aggregation_plus_UnitType", "ibc2021-1108.6.2.2.1"),
        ("Accessible Route", ["IfcSpace", "IfcDoor", "IfcRamp", "IfcStair"], "verified_topology_graph", "ibc2021-1104.2"),
        ("Clear Width", ["IfcDoor"], "proposed_property_or_geometry; threshold_requires_ICC_A117.1", "ibc2021-1102.1"),
        ("Slope", ["IfcRamp"], "proposed_property_or_geometry; threshold_requires_ICC_A117.1", "ibc2021-1102.1"),
    ]
    mappings = []
    for concept, entities, method, node in mapping_specs:
        mappings.append({"ibc_concept": concept, "ifc_entities": entities, "mapping_method": method,
                         "source_node_id": node, "evidence": evidence(by_node[node]), "status": "proposed_requires_review",
                         "is_normative_ifc_mapping": False})
    write("ibc_ifc_mapping.json", {"schema_version": "0.1.0", "status": "proposed", "mappings": mappings})
    write("mapping_review_queue.json", {"schema_version": "0.1.0", "items": [
        {"ibc_concept": m["ibc_concept"], "source_node_id": m["source_node_id"],
         "question": "Confirm IFC representation, model authoring convention, applicability and evidence sufficiency.",
         "evidence": m["evidence"]} for m in mappings]})
    ttl = ["@prefix acc: <https://example.org/acc/ibc2021/mapping/> .", "@prefix ibc: <https://example.org/ibc/2021/> .", "@prefix ifc: <https://standards.buildingsmart.org/IFC/DEV/IFC4/ADD2/OWL#> .", "@prefix prov: <http://www.w3.org/ns/prov#> .", "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .", ""]
    for i, m in enumerate(mappings, 1):
        ttl += [f"acc:m{i:02d} a acc:ConceptMapping ;", f"  acc:ibcConcept {json.dumps(m['ibc_concept'])} ;",
                f"  prov:wasDerivedFrom ibc:{m['source_node_id']} ;",
                f"  acc:sourceNodeId {json.dumps(m['source_node_id'])} ;",
                f"  acc:sourceSha256 {json.dumps(m['evidence']['sha256'])} ;",
                f"  acc:mappingMethod {json.dumps(m['mapping_method'])} ;",
                f"  acc:status \"proposed_requires_review\" ;",
                "  acc:ifcEntity " + ", ".join(f"ifc:{v}" for v in m["ifc_entities"]) + " .", ""]
    (OUT / "ibc_ifc_mapping.ttl").write_text("\n".join(ttl), encoding="utf-8")
    assert len(scoped) == len(rules)
    assert set(x["dsl_rule_id"] for x in scoped) == set(x["dsl_rule_id"] for x in rules)
    print(json.dumps({"rules": len(scoped), "categories": counts, "mappings": len(mappings)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

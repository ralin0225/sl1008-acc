"""Extract declared IFC data and candidate space-door adjacency, without approval."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

ACC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ACC / ".python_deps"))
import ifcopenshell
import ifcopenshell.util.element


def extract(path):
    model = ifcopenshell.open(str(path))
    evidence = {"ifc_path": str(path.resolve()), "ifc_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    records = []
    for entity_type in ("IfcDoor", "IfcRamp", "IfcStair", "IfcSpace", "IfcZone"):
        for entity in model.by_type(entity_type):
            pset = ifcopenshell.util.element.get_psets(entity, psets_only=True, should_inherit=False).get("ACC_Accessibility", {})
            declarations = {k: v for k, v in pset.items() if k != "id"}
            records.append({"guid": entity.GlobalId, "ifc_type": entity.is_a(), "step_id": entity.id(),
                            "name": entity.Name, "declared_properties": declarations,
                            "property_origin": "occurrence_pset_only", "classification_verified": False,
                            "design_accessibility_verified": False})
    facilities = defaultdict(list)
    unidentified = []
    for record in records:
        if record["ifc_type"] == "IfcSpace" and record["declared_properties"].get("UseCode") == "PARKING_SPACE":
            identifier = record["declared_properties"].get("ParkingFacilityId")
            if isinstance(identifier, str) and identifier.strip():
                facilities[identifier].append(record)
            else:
                unidentified.append(record["guid"])
    parking = []
    for facility, spaces in sorted(facilities.items()):
        declarations = [s["declared_properties"] for s in spaces]
        parking.append({"facility_id": facility, "guids": [s["guid"] for s in spaces], "declared_total": len(spaces),
                        "declared_accessible": sum(p.get("Accessible") is True for p in declarations),
                        "declared_van_accessible": sum(p.get("ParkingIsVanAccessible") is True for p in declarations),
                        "missing_accessible": sum(not isinstance(p.get("Accessible"), bool) for p in declarations),
                        "missing_van_accessible": sum(not isinstance(p.get("ParkingIsVanAccessible"), bool) for p in declarations),
                        "inventory_complete": False, "status": "UNKNOWN",
                        "reason": "Only declared IfcSpace parking found; facility scope, alternate representations and accessible design remain unverified"})
    # A door directly referenced by boundaries in two spaces suggests adjacency.
    # Wall boundaries do not automatically identify which opening can be traversed.
    door_spaces = defaultdict(set)
    excluded_boundaries = 0
    for boundary in model.by_type("IfcRelSpaceBoundary"):
        space, element = boundary.RelatingSpace, boundary.RelatedBuildingElement
        if space and element and element.is_a("IfcDoor"):
            door_spaces[element.GlobalId].add(space.GlobalId)
        else:
            excluded_boundaries += 1
    candidate_edges = []
    for door, spaces in sorted(door_spaces.items()):
        if len(spaces) == 2:
            start, end = sorted(spaces)
            candidate_edges.append({"from": start, "to": end, "door_guid": door,
                                    "accessible_verified": None, "bidirectional": None,
                                    "evidence": {**evidence, "derivation": "two direct IfcDoor space boundaries"}})
    return {"schema_version": "0.1.0", "scope": "DECLARED_INVENTORY_AND_TOPOLOGY_CANDIDATES",
            "model_evidence": evidence, "compliance_evaluated": False, "execution_ready": False,
            "records": records, "parking_facilities": parking, "parking_without_facility_id": unidentified,
            "topology_candidates": {"nodes": sorted(s.GlobalId for s in model.by_type("IfcSpace")),
                                    "edges": candidate_edges, "excluded_boundaries": excluded_boundaries,
                                    "inventory_complete": False, "status": "UNKNOWN"},
            "limitations": ["Names alone are not used to infer legal use or accessibility", "No automatic approval of property declarations",
                            "IfcZone parking/unit aggregation remains a mapping review item", "No vertical route or door clear opening geometry derived"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ifc", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.ifc.is_file():
        parser.error("IFC file does not exist")
    try:
        report = extract(args.ifc)
    except Exception as exc:
        parser.exit(1, f"IFC inventory failed: {exc}\n")
    output = args.output or ACC / f"inventory_{args.ifc.stem}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()

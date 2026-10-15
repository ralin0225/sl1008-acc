"""Generate and schema-validate the ACC information requirements IDS."""
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "output/acc"
sys.path.insert(0, str(OUT / ".python_deps"))
from ifctester import ids  # noqa: E402


def add_spec(model: ids.Ids, name: str, entity: str, props: list[tuple[str, str]], source: str,
             applicability_property: tuple[str, str] | None = None) -> None:
    spec = ids.Specification(
        name=name, ifcVersion=["IFC4"], minOccurs=0, maxOccurs="unbounded",
        identifier=source, description=f"Proposed project information requirement; evidence: {source}",
        instructions="A missing property is an information gap (UNKNOWN) for ACC; IDS does not prove regulatory compliance.",
    )
    spec.applicability.append(ids.Entity(name=entity.upper()))
    if applicability_property:
        key, value = applicability_property
        spec.applicability.append(ids.Property(propertySet="ACC_Accessibility", baseName=key, value=value))
    for key, datatype in props:
        enumerations = {
            "EntranceType": ["PUBLIC", "TENANT", "SERVICE", "OTHER"],
            "UseCode": ["TOILET_ROOM", "PARKING_SPACE", "DWELLING_UNIT", "SLEEPING_UNIT", "OTHER"],
            "UnitType": ["ACCESSIBLE", "TYPE_A", "TYPE_B", "NONE"],
        }
        value = ids.Restriction({"enumeration": enumerations[key]}) if key in enumerations else None
        spec.requirements.append(ids.Property(propertySet="ACC_Accessibility", baseName=key, dataType=datatype, value=value))
    model.specifications.append(spec)


def main() -> None:
    model = ids.Ids(
        title="IBC 2021 Chapter 11 ACC project information requirements",
        version="0.1.0", description="Proposed IFC4 data contract. Geometric, topological and legal checks are outside IDS.",
        purpose="Identify missing data before ACC evaluation.",
    )
    add_spec(model, "Door accessibility declaration", "IfcDoor", [("Accessible", "IFCBOOLEAN"), ("EntranceType", "IFCLABEL")], "ibc2021-1105.1")
    add_spec(model, "Space use classification", "IfcSpace", [("UseCode", "IFCLABEL")], "ibc2021-1110.2")
    add_spec(model, "Parking space information", "IfcSpace", [("ParkingFacilityId", "IFCIDENTIFIER"), ("Accessible", "IFCBOOLEAN"), ("ParkingIsVanAccessible", "IFCBOOLEAN")], "ibc2021-1106.2", ("UseCode", "PARKING_SPACE"))
    add_spec(model, "Dwelling unit information", "IfcSpace", [("UnitType", "IFCLABEL")], "ibc2021-1108.6.2.2.1", ("UseCode", "DWELLING_UNIT"))
    add_spec(model, "Ramp accessibility declaration", "IfcRamp", [("Accessible", "IFCBOOLEAN")], "ibc2021-1104.4")
    add_spec(model, "Stair accessibility declaration", "IfcStair", [("Accessible", "IFCBOOLEAN")], "ibc2021-1104.4")
    output = OUT / "ibc_accessibility.ids"
    valid = model.to_xml(str(output))
    if not valid:
        raise RuntimeError("Generated IDS failed schema validation")
    from ids_support import load_ids
    parsed = load_ids(output)
    if len(parsed.specifications) != len(model.specifications):
        raise RuntimeError("IDS round trip lost specifications")
    report = {"schema_valid": True, "round_trip_valid": True, "specification_count": len(parsed.specifications),
              "ifc_version": "IFC4", "note": "No model validation performed; no IFC file supplied."}
    source = ROOT / "output/ibe_accessibility_structure/semantic_rdf/10_semantic_validated.json"
    candidates = {c["source_node_id"]: c for c in json.loads(source.read_text(encoding="utf-8"))["candidates"]}
    traceability = {"schema_version": "0.1.0", "origin": "proposed project information contract", "specifications": [
        {"name": spec.name, "source_node_id": spec.identifier, "evidence": candidates[spec.identifier]["evidence"],
         "requires_profile_agreement": True, "regulatory_compliance_check": False} for spec in parsed.specifications]}
    (OUT / "ids_traceability.json").write_text(json.dumps(traceability, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (OUT / "ids_validation_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()

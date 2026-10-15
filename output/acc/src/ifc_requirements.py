"""Typed IFC observations, never inferred legal facts or automatic approvals."""
from __future__ import annotations

import hashlib
import math
import re
import sys
from pathlib import Path

ACC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ACC / ".python_deps"))
import ifcopenshell
import ifcopenshell.util.element
import ifcopenshell.util.unit
import ifcopenshell.util.placement


def observation(value, data_type, guid, method, field, unit=None, valid=None, reason=None):
    if valid is None:
        valid = value is not None
    return {"value": value, "data_type": data_type, "unit": unit, "source_global_id": guid,
            "method": method, "field": field, "valid": valid,
            "missing_reason": reason or (None if valid else "MISSING_DATA")}


def extract_requirements(path, model_id):
    path = Path(path)
    model = ifcopenshell.open(str(path))
    scale = None
    try:
        projects = model.by_type("IfcProject")
        units = projects[0].UnitsInContext.Units if len(projects) == 1 and projects[0].UnitsInContext else []
        if len([u for u in units if getattr(u, "UnitType", None) == "LENGTHUNIT"]) == 1:
            scale = ifcopenshell.util.unit.calculate_unit_scale(model)
            if not math.isfinite(scale) or scale <= 0:
                scale = None
    except (AttributeError, ValueError, TypeError):
        pass
    records = []
    for entity in model.by_type("IfcObject"):
        guid = entity.GlobalId
        pset = ifcopenshell.util.element.get_psets(entity, psets_only=True, should_inherit=False).get("ACC_Accessibility", {})
        try:
            container = ifcopenshell.util.element.get_container(entity)
        except (AttributeError, RuntimeError):
            container = None
        props = {}
        for field in ("Accessible", "UseCode", "UnitType", "EntranceType", "ParkingFacilityId", "ParkingIsVanAccessible", "RouteNodeId"):
            value = pset.get(field)
            boolean = field in ("Accessible", "ParkingIsVanAccessible")
            valid = isinstance(value, bool) if boolean else isinstance(value, str) and bool(value.strip())
            props[field] = observation(value, "boolean" if boolean else "string", guid, "occurrence_pset", "ACC_Accessibility." + field,
                                       valid=valid, reason="INVALID_DATA" if value is not None and not valid else None)
        value = pset.get("ClearOpeningWidth")
        valid_number = isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value) and value > 0
        reason = "MISSING_DATA" if value is None or scale is None else "INVALID_DATA" if not valid_number else None
        props["clear_width"] = observation(value * scale if valid_number and scale is not None else None, "length", guid,
            "occurrence_pset", "ACC_Accessibility.ClearOpeningWidth", "m", valid_number and scale is not None, reason)
        props["clear_width"]["source_value"] = value
        props["clear_width"]["source_length_to_metre"] = scale
        props["clear_width"]["semantics_verified"] = False
        classifications = []
        for rel in getattr(entity, "HasAssociations", ()):
            if rel.is_a("IfcRelAssociatesClassification"):
                reference = rel.RelatingClassification
                classifications.append({"relationship_global_id": rel.GlobalId, "ifc_type": reference.is_a(),
                    "identification": getattr(reference, "Identification", None), "name": reference.Name,
                    "source": getattr(getattr(reference, "ReferencedSource", None), "Name", None), "semantics_verified": False})
        props["classifications"] = observation(classifications or None, "classification_list", guid,
            "native_ifc_relationship", "IfcRelAssociatesClassification")
        if entity.is_a("IfcDoor"):
            props["overall_width"] = observation(entity.OverallWidth, "length", guid, "native_ifc_attribute", "IfcDoor.OverallWidth", "project_length")
            props["overall_width"]["usable_as_clear_width"] = False
        location = None
        try:
            placement = getattr(entity, "ObjectPlacement", None)
            if placement and scale is not None:
                vector = ifcopenshell.util.placement.get_local_placement(placement)[:3, 3] * scale
                if all(math.isfinite(float(c)) for c in vector):
                    location = {"coordinates": [float(c) for c in vector], "unit": "m", "method": "IfcLocalPlacement",
                                "coordinate_system": "IFC local placement hierarchy; not georeferenced", "source_global_id": guid}
        except (ValueError, TypeError, AttributeError, RuntimeError):
            pass
        records.append({"global_id": guid, "ifc_type": entity.is_a(), "name": entity.Name,
            "entity_types": [t for t in ("IfcDoor", "IfcRamp", "IfcStair", "IfcSpace", "IfcZone", "IfcRampFlight", "IfcStairFlight") if entity.is_a(t)],
            "step_id": entity.id(), "storey": {"global_id": container.GlobalId, "name": container.Name} if container else None,
            "location": location, "observations": props})
    guids = [r.GlobalId for r in model.by_type("IfcRoot")]
    boundary_candidates = []
    for boundary in model.by_type("IfcRelSpaceBoundary"):
        space, element = boundary.RelatingSpace, boundary.RelatedBuildingElement
        if space and element:
            boundary_candidates.append({"space_global_id": space.GlobalId, "element_global_id": element.GlobalId,
                "relationship_global_id": boundary.GlobalId, "relationship_type": boundary.is_a(),
                "method": "native_ifc_relationship", "traversability_verified": False})
    return {"model_id": model_id, "model_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "ifc_path": str(path.resolve()), "schema": model.schema, "length_to_metre": scale,
            "identity_valid": bool(guids) and all(isinstance(g, str) and re.fullmatch(r"[0-3][0-9A-Za-z_$]{21}", g) for g in guids) and len(guids) == len(set(guids)),
            "records": records, "boundary_candidates": boundary_candidates, "inventory_complete": False, "applicability_inferred": False}

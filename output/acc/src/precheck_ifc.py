"""Read-only IFC precheck. This is model quality assessment, not code compliance."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
ACC = ROOT / "output/acc"
sys.path.insert(0, str(ACC / ".python_deps"))


def check(path: Path, geometry_sample: int = 20) -> dict:
    import ifcopenshell
    import ifcopenshell.geom
    import ifcopenshell.util.unit
    import ifctester

    result = {"schema_version": "0.1.0", "input": str(path.resolve()), "status": "UNKNOWN", "checks": {},
              "compliance_evaluated": False, "scope": "MODEL_INFORMATION_PRECHECK",
              "note": "Precheck findings are information quality results, not Chapter 11 compliance results."}
    try:
        model = ifcopenshell.open(str(path))
        result["input_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    except Exception as exc:
        result["checks"]["parse"] = {"status": "UNKNOWN", "error": str(exc)}
        return result
    result["checks"]["parse"] = {"status": "PASS"}
    schema = model.schema
    result["checks"]["schema"] = {"status": "PASS" if schema == "IFC4" else "MANUAL_REVIEW" if schema.startswith("IFC4X3") else "FAIL", "value": schema}
    roots = model.by_type("IfcRoot")
    guids = [x.GlobalId for x in roots if x.GlobalId]
    duplicate = [k for k, v in collections.Counter(guids).items() if v > 1]
    invalid = [v for v in guids if not re.fullmatch(r"[0-3][0-9A-Za-z_$]{21}", v)]
    result["checks"]["guid"] = {"status": "FAIL" if duplicate or invalid else "UNKNOWN" if not roots or len(guids) != len(roots) else "PASS", "root_count": len(roots), "missing": len(roots)-len(guids), "duplicates": duplicate[:20], "invalid": invalid[:20]}
    try:
        project = model.by_type("IfcProject")
        if len(project) != 1 or not project[0].UnitsInContext:
            raise ValueError("Exactly one IfcProject with UnitsInContext is required")
        length_units = [u for u in project[0].UnitsInContext.Units if getattr(u, "UnitType", None) == "LENGTHUNIT"]
        if len(length_units) != 1:
            raise ValueError("Exactly one explicit LENGTHUNIT is required; default scale 1 is unsafe")
        scale = ifcopenshell.util.unit.calculate_unit_scale(model)
        if not math.isfinite(scale) or scale <= 0:
            raise ValueError("Length unit scale must be positive and finite")
        result["checks"]["units"] = {"status": "PASS", "length_to_metre": scale}
    except Exception as exc:
        result["checks"]["units"] = {"status": "UNKNOWN", "error": str(exc)}
    hierarchy = {entity: len(model.by_type(entity)) for entity in ("IfcProject", "IfcSite", "IfcBuilding", "IfcBuildingStorey")}
    parent_types = {"IfcSite": "IfcProject", "IfcBuilding": "IfcSite", "IfcBuildingStorey": "IfcBuilding"}
    unlinked = []
    for entity_type, parent_type in parent_types.items():
        for entity in model.by_type(entity_type):
            parents = [rel.RelatingObject for rel in entity.Decomposes if rel.is_a("IfcRelAggregates")]
            if len(parents) != 1 or not parents[0].is_a(parent_type):
                unlinked.append({"guid": entity.GlobalId, "entity": entity_type, "expected_parent": parent_type})
    result["checks"]["hierarchy"] = {"status": "PASS" if all(hierarchy.values()) and hierarchy["IfcProject"] == 1 and not unlinked else "UNKNOWN", "counts": hierarchy, "unlinked": unlinked}
    objects = {entity: len(model.by_type(entity)) for entity in ("IfcDoor", "IfcRamp", "IfcStair", "IfcSpace", "IfcZone", "IfcRelSpaceBoundary")}
    result["object_inventory"] = objects
    result["checks"]["space_boundary"] = {"status": "PASS" if objects["IfcRelSpaceBoundary"] else "UNKNOWN", "count": objects["IfcRelSpaceBoundary"], "note": "Presence alone does not prove connectivity."}
    try:
        settings = ifcopenshell.geom.settings()
        geometric_products = [x for x in model.by_type("IfcProduct") if x.Representation]
        missing_representation = [{"guid": x.GlobalId, "ifc_type": x.is_a()} for entity_type in ("IfcDoor", "IfcRamp", "IfcStair", "IfcSpace") for x in model.by_type(entity_type) if not x.Representation]
        products = geometric_products[:geometry_sample]
        ok, failed = 0, []
        for product in products:
            try:
                ifcopenshell.geom.create_shape(settings, product)
                ok += 1
            except Exception as exc:
                failed.append({"guid": product.GlobalId, "error": str(exc)[:200]})
        fully_checked = len(products) == len(geometric_products)
        result["checks"]["geometry"] = {"status": "PASS" if products and not failed and fully_checked and not missing_representation else "UNKNOWN", "represented_products": len(geometric_products), "missing_target_representations": missing_representation, "sampled": len(products), "fully_checked": fully_checked, "generated": ok, "failed": failed, "note": "A sample cannot certify geometry for unchecked objects."}
    except Exception as exc:
        result["checks"]["geometry"] = {"status": "UNKNOWN", "error": str(exc)}
    try:
        from ids_support import load_ids
        ids_model = load_ids(ACC / "ibc_accessibility.ids")
        ids_model.validate(model, should_filter_version=True)
        specs = []
        for spec in ids_model.specifications:
            matched = len(spec.applicable_entities)
            status = "PASS" if spec.status and matched else "UNKNOWN"
            specs.append({"name": spec.name, "source_node_id": spec.identifier, "status": status, "applicable_count": matched, "failed_count": len(spec.failed_entities),
                          "reason": "verified information requirements" if status == "PASS" else "no applicable objects; scope unconfirmed" if not matched else "missing or invalid property data",
                          "failures": [{"guid": f["element"].GlobalId, "property": getattr(facet, "baseName", None), "reason": f["reason"]} for facet in spec.requirements for f in facet.failures]})
        result["checks"]["ids"] = {"status": "PASS" if all(s["status"] == "PASS" for s in specs) else "UNKNOWN", "specifications": specs,
                                     "note": "IDS failure means missing project data, not a failed accessibility rule."}
    except Exception as exc:
        result["checks"]["ids"] = {"status": "UNKNOWN", "error": str(exc)}
    statuses = {x["status"] for x in result["checks"].values()}
    result["status"] = next((s for s in ("FAIL", "MANUAL_REVIEW", "UNKNOWN") if s in statuses), "PASS")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ifc", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--geometry-sample", type=int, default=20, help="Maximum number of represented products to test (sample coverage is recorded).")
    args = parser.parse_args()
    if not args.ifc.is_file():
        parser.error(f"IFC file does not exist: {args.ifc}")
    if args.geometry_sample < 0:
        parser.error("--geometry-sample must be nonnegative")
    report = check(args.ifc, args.geometry_sample)
    output = args.output or ACC / f"precheck_{args.ifc.stem}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()

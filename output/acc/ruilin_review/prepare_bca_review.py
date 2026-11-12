"""Prepare two pending manual-review cases; optionally cross-check slab geometry.

Requires IfcOpenShell and NumPy. Never converts a checker value into manual evidence.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path

TARGETS = ["0Pi72lxqT7rB3T2_y3sKda", "0Pi72lxqT7rB3T2_y3sB$v"]
SOURCE_COMMIT = "439352c224e7a159e169f79760f6eeb01fb3293a"


def prepare(model_path, sheet_path, output):
    import ifcopenshell
    import ifcopenshell.geom
    import numpy as np

    sheet = json.loads(sheet_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(model_path.read_bytes()).hexdigest()
    if digest != sheet["model"]["sha256"]:
        raise ValueError("Model SHA-256 differs from frozen result sheet. Document LF/CRLF provenance; do not bypass the identity check.")
    model = ifcopenshell.open(str(model_path))
    settings = ifcopenshell.geom.settings()
    settings.set(settings.USE_WORLD_COORDS, True)
    cases = []
    for guid in TARGETS:
        row = next(r for r in sheet["results"] if r["schema_id"] == "ibc2021-1011.3-stair-headroom" and guid in r["entity_ids"])
        flight = model.by_guid(guid)
        slab = model.by_guid(row["governing"]["guid"])
        assert flight.is_a("IfcStairFlight") and slab.is_a("IfcSlab")
        geometry = row["measurement_geometry"]
        assert geometry["unit"] == "mm"
        reference = np.asarray(geometry["reference_point"], dtype=float)
        # Independent triangle-plane intersection of the named slab only.
        # The nosing reference and XY are still supplied by the original engine.
        shape = ifcopenshell.geom.create_shape(settings, slab)
        verts = np.asarray(shape.geometry.verts).reshape(-1,3)*1000
        faces = np.asarray(shape.geometry.faces).reshape(-1,3)
        hits = []
        for triangle in verts[faces]:
            a,b,c = triangle
            u,v = b-a,c-a
            if np.cross(u,v)[2] >= -1e-9:
                continue
            det = u[0]*v[1]-u[1]*v[0]
            if abs(det) < 1e-9:
                continue
            delta = reference-a
            alpha = (delta[0]*v[1]-delta[1]*v[0])/det
            beta = (u[0]*delta[1]-u[1]*delta[0])/det
            if alpha >= -1e-8 and beta >= -1e-8 and alpha+beta <= 1+1e-8:
                z = a[2]+alpha*u[2]+beta*v[2]
                if z > reference[2]:
                    hits.append(float(z))
        underside = min(hits) if hits else None
        automated = underside-float(reference[2]) if underside is not None else None
        cases.append({"model":sheet["model"]["file_name"], "model_sha256":digest,
                      "rule":row["schema_id"], "guid":guid, "governing":slab.GlobalId,
                      "flight_name":flight.Name, "slab_name":slab.Name,
                      "engine_verdict":row["verdict"], "engine_measurement_mm":row["measured_value"]["value"],
                      "threshold_mm":row["threshold"]["value"], "engine_point_mm":geometry["point"],
                      "engine_reference_point_mm":geometry["reference_point"],
                      "automated_slab_underside_z_mm":underside, "automated_clearance_at_engine_reference_mm":automated,
                      "automated_difference_mm":automated-row["measured_value"]["value"] if automated is not None else None,
                      "manual_measurement_mm":None, "expected_verdict":None, "solibri_measurement_mm":None,
                      "review_status":"PENDING_MANUAL_MEASUREMENT", "reviewer":None,
                      "limitations":"Only the named slab underside is independently intersected. Nosing line, full width, bottom extension, applicability, and absence of other obstructions remain for manual review."})
    output.mkdir(parents=True, exist_ok=True)
    (output/"bca_two_cases.json").write_text(json.dumps({"source_commit":SOURCE_COMMIT, "gold_standard":False, "cases":cases},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    fields = ["model","rule","guid","engine_verdict","engine_measurement_mm","threshold_mm","governing","your_measurement","expected_verdict","solibri_measurement","agree (y/n)","reviewer","evidence_file","comment"]
    with (output/"manual_check_ruilin.csv").open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=fields)
        writer.writeheader()
        for case in cases:
            writer.writerow({k:case[k] for k in fields if k in case})
    return cases


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model",type=Path,required=True)
    parser.add_argument("--sheet",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(prepare(args.model,args.sheet,args.output),indent=2))

"""Experimental IBC 2021 room-height subchecks on reviewed full-domain surfaces.

This is not an IFC extractor or an addition to the 15 published ACC contracts.
No approvals are generated here. Synthetic fixtures remain labelled in output.
"""
import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re

POLICY = "ibc2021-room-height-review/1"
SOURCE = "https://codes.iccsafe.org/content/IBC2021V2.0/chapter-12-interior-environment"
LOWER_USES = {"bathroom", "toilet_room", "kitchen", "storage_room", "laundry_room", "dwelling_corridor"}
USES = LOWER_USES | {"habitable", "occupiable", "corridor"}
REQUIRED_BASIS = "finished_floor_to_finished_underside"


class Uncheckable(ValueError):
    pass


def require(condition, text):
    if not condition:
        raise Uncheckable(text)


def number(value):
    require(type(value) in (int, float) and math.isfinite(value), "Finite numeric coordinates and elevations required")
    return Fraction(str(value))


def facts_digest(facts):
    """Bind review to all input facts and the exact policy implementation."""
    content = {k: v for k, v in facts.items() if k != "review"}
    encoded = json.dumps(content, sort_keys=True, separators=(",", ":"), allow_nan=False)
    code_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return hashlib.sha256((POLICY + code_hash + encoded).encode()).hexdigest()


def polygon_area(points):
    return abs(sum(a[0]*b[1] - b[0]*a[1] for a, b in zip(points, points[1:] + points[:1]))) / 2


def area_at_least(triangle, threshold):
    """Clip an affine height field on a projected triangle, using exact rationals."""
    out = []
    for a, b in zip(triangle, triangle[1:] + triangle[:1]):
        a_in, b_in = a[2] >= threshold, b[2] >= threshold
        if a_in:
            out.append(a)
        if a_in != b_in:
            t = (threshold - a[2]) / (b[2] - a[2])
            out.append(tuple(a[k] + t*(b[k]-a[k]) for k in range(3)))
    return polygon_area(out) if len(out) >= 3 else Fraction(0)


def evaluate(facts):
    """Evaluate only the declared reviewed surface; missing evidence cannot pass."""
    output = {"policy": POLICY, "source_url": SOURCE, "status": "NOT CHECKABLE",
              "is_synthetic": True, "result_scope": "Room ceiling-height subcheck on the supplied reviewed rectangular full-domain surface; not whole-clause, minimum-room-area or building compliance"}
    try:
        require(isinstance(facts, dict), "Facts must be an object")
        require(type(facts.get("is_synthetic")) is bool, "Explicit synthetic/real provenance required")
        output["is_synthetic"] = facts["is_synthetic"]
        require(facts.get("code_basis") == "IBC2021", "Only IBC2021 is supported")
        require(isinstance(facts.get("model_sha256"), str) and re.fullmatch(r"[0-9a-f]{64}", facts["model_sha256"]), "Current IFC SHA-256 required")
        require(isinstance(facts.get("target_global_id"), str) and re.fullmatch(r"[0-3][0-9A-Za-z_$]{21}", facts["target_global_id"]), "One IFC target GlobalId required")
        require(facts.get("measurement_basis") == REQUIRED_BASIS, "Storey elevation difference, structural slab height and stair-nosing clearance are not room ceiling height")
        review = facts.get("review", {})
        require(isinstance(review, dict), "Review must be an object")
        require(review.get("resolution") == "APPROVED" and isinstance(review.get("reviewer"), str) and review["reviewer"].strip()
                and isinstance(review.get("evidence"), str) and review["evidence"].strip(), "Explicit external scope and evidence review required")
        digest = facts_digest(facts)
        require(review.get("facts_sha256") == digest, "Review is stale or not bound to these facts and this checker")
        require(facts.get("applicability_verified") is True and facts.get("exceptions_reviewed") is True
                and facts.get("unresolved_exceptions") == [], "Applicability and all exceptions must be resolved")
        use, form = facts.get("room_use"), facts.get("ceiling_form")
        require(use in USES, "Explicit supported room use required; mezzanines need Section 505.2 review")
        require(form in {"flat", "sloped", "furred"}, "Mixed slope/furring, beams/girders exceptions and mezzanines require separate analysis")
        if use == "dwelling_corridor":
            require(facts.get("within_group_r_dwelling_or_sleeping_unit") is True, "Dwelling-corridor exception needs reviewed Group R unit context")
        threshold = Fraction("2133.6") if use in LOWER_USES else Fraction(2286)
        surface = facts.get("surface", {})
        require(isinstance(surface, dict), "Surface must be an object")
        require(surface.get("representation") == "rectangular_full_domain_piecewise_planar"
                and surface.get("unit") == "mm" and surface.get("full_domain_verified") is True
                and surface.get("obstructions_resolved") is True and isinstance(surface.get("evidence"), str) and surface["evidence"].strip(), "Reviewed full domain, finished surfaces, and overhead-obstruction evidence required; samples alone are insufficient")
        ids = surface.get("source_global_ids")
        require(isinstance(ids, list) and ids and all(isinstance(g, str) and re.fullmatch(r"[0-3][0-9A-Za-z_$]{21}", g) for g in ids), "IFC geometry source identities required")
        axes = []
        for key, extent in [("x", "length"), ("y", "width")]:
            raw = surface.get(key)
            require(isinstance(raw, list) and len(raw) >= 2, "At least two axis positions required")
            values = [number(v) for v in raw]
            require(values[0] == 0 and all(b > a for a, b in zip(values, values[1:]))
                    and values[-1] == number(surface.get(extent)) and values[-1] > 0, "Axes must exactly cover the reviewed rectangle")
            axes.append(values)
        xs, ys = axes
        matrices = []
        for key in ["finished_floor_z", "finished_underside_z"]:
            raw = surface.get(key)
            require(isinstance(raw, list) and len(raw) == len(xs) and all(isinstance(r, list) and len(r) == len(ys) for r in raw), "Complete elevation matrices required")
            matrices.append([[number(v) for v in row] for row in raw])
        floor, ceiling = matrices
        heights = [[ceiling[i][j]-floor[i][j] for j in range(len(ys))] for i in range(len(xs))]
        minimum = min(v for row in heights for v in row)
        require(minimum >= 0, "Ceiling intersects or is below finished-floor reference")
        qualifying = excluded = Fraction(0)
        for i in range(len(xs)-1):
            for j in range(len(ys)-1):
                a, b, c, d = [(xs[u], ys[v], heights[u][v]) for u, v in [(i,j), (i+1,j), (i+1,j+1), (i,j+1)]]
                for triangle in [[a,b,c], [a,c,d]]:
                    qualifying += area_at_least(triangle, threshold)
                    excluded += polygon_area(triangle) - area_at_least(triangle, Fraction(1524))
        area = xs[-1]*ys[-1]
        if form == "flat":
            passed = minimum >= threshold
            section, fraction = "1208.2", Fraction(1)
        elif form == "sloped":
            require(facts.get("sloped_denominator") == "full_room_projected_area", "Explicit reviewed half-room area denominator required")
            passed = qualifying*2 >= area
            section, fraction = "1208.2 Exception 2", Fraction(1,2)
        else:
            passed = qualifying*3 >= area*2 and minimum >= Fraction("2133.6")
            section, fraction = "1208.2.1", Fraction(2,3)
        output.update(status="PASS" if passed else "FAIL", section=section,
                      model_sha256=facts["model_sha256"], target_global_id=facts["target_global_id"], facts_sha256=digest,
                      minimum_height_mm=float(minimum), prescribed_height_mm=float(threshold),
                      room_projected_area_m2=float(area/1000000), qualifying_area_m2=float(qualifying/1000000),
                      qualifying_fraction=float(qualifying/area), required_fraction=float(fraction),
                      below_5ft_area_m2=float(excluded/1000000) if form == "sloped" else None,
                      note="Exact integration on the supplied affine triangles. Below-5ft area is reported separately; minimum room-area compliance is not evaluated.")
    except (Uncheckable, TypeError, ValueError, OverflowError) as exc:
        output.update(reason_code="REQUIRES_MANUAL_REVIEW", reason=str(exc))
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("facts", type=Path)
    args = parser.parse_args()
    print(json.dumps(evaluate(json.loads(args.facts.read_text(encoding="utf-8"))), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

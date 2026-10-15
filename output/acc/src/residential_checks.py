"""Residential subchecks over explicitly reviewed IFC-bound facts.

Geometry is never inferred from bounding boxes. The headroom representation is an
exact, reviewed full-domain piecewise-planar surface, not a set of clearance samples.
No user facts, source clauses or model classifications are approved here.
"""
from collections import deque
from decimal import Decimal, InvalidOperation


FACTORS = {"m": Decimal(1), "mm": Decimal("0.001"), "inch": Decimal("0.0254"), "ft": Decimal("0.3048")}


class DataError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def require(condition, message, code="MISSING_DATA"):
    if not condition:
        raise DataError(code, message)


def number(value, nonnegative=False):
    require(isinstance(value, (int, float)) and not isinstance(value, bool), "Finite numeric measurement required", "INVALID_DATA")
    try:
        n = Decimal(str(value))
    except InvalidOperation:
        raise DataError("INVALID_DATA", "Invalid numeric measurement")
    require(n.is_finite() and (n >= 0 if nonnegative else n > 0), "Measurement is nonfinite or outside its physical range", "INVALID_DATA")
    return n


def measurement(item, target, nonnegative=False):
    require(item is not None, "Required reviewed measurement is absent")
    require(isinstance(item, dict), "Measurement must be a typed object", "INVALID_DATA")
    require(item.get("valid") is True, "Measurement is unavailable")
    require(item.get("source_global_id") == target["global_id"], "Measurement does not identify this IFC target", "INVALID_DATA")
    require(item.get("method") in {"reviewed_manual_input", "native_ifc_attribute", "occurrence_pset"}, "Unsupported measurement origin", "INVALID_DATA")
    require(item.get("evidence") and item.get("semantics_verified") is True, "Measurement definition and evidence must be reviewed")
    require(item.get("unit") in FACTORS, "Explicit supported length unit required", "INVALID_DATA")
    return number(item.get("value"), nonnegative) * FACTORS[item["unit"]]


def result(passed, reason, actual, required, unit=None, **extra):
    return {"status": "PASS" if passed else "FAIL", "reason_code": None, "reason": reason,
            "actual": actual, "required": required, "unit": unit, **extra}


def profile(facts):
    p = facts.get("residential_profile")
    require(isinstance(p, dict), "Reviewed residential applicability profile required")
    require(p.get("code_basis") == "IBC2021" and p.get("occupancy") == "R-3"
            and type(p.get("stories_above_grade")) is int and p["stories_above_grade"] == 2
            and p.get("single_dwelling") is True and p.get("evidence"),
            "This profile requires reviewed IBC2021, R-3, two-storey single-dwelling applicability", "UNKNOWN_APPLICABILITY")
    require(facts.get("exceptions_reviewed") is True, "Residential and measurement exceptions need explicit review", "UNKNOWN_APPLICABILITY")


def declared_dimension(rule, facts, targets):
    field = rule["required_ifc_data"][0]["field"]
    measured = facts.get("measurements")
    if measured is None:
        measured = {}
    require(isinstance(measured, dict), "measurements must be keyed by target GlobalId", "INVALID_DATA")
    require(not (set(measured) - {t["global_id"] for t in targets}), "Measurements include objects outside this scope", "INVALID_DATA")
    actual = {}
    threshold = rule["parameters"]["thresholds"]
    for target in targets:
        observation = measured.get(target["global_id"])
        if observation is None:
            observation = target["observations"].get(field)
            if observation:
                observation = {**observation, "semantics_verified": facts.get("measurement_semantics_verified"),
                               "evidence": facts.get("measurement_definition_evidence")}
        value = measurement(observation, target)
        # Native observations must agree with the actual model attribute.
        if observation.get("method") == "native_ifc_attribute":
            native = target["observations"].get(field)
            require(native and native.get("valid") and Decimal(str(native["value"])) == value,
                    "Native measurement differs from current IFC attribute", "INVALID_DATA")
        actual[target["global_id"]] = value
    if field == "tread_depth":
        require(facts.get("rectangular_treads_verified") is True, "This subcheck covers rectangular treads only", "UNKNOWN_APPLICABILITY")
    passed = all(v <= Decimal(str(threshold["maximum"])) if "maximum" in threshold else v >= Decimal(str(threshold["minimum"])) for v in actual.values())
    return result(passed, "Compared reviewed declared flight dimensions; per-step uniformity and other stair requirements are separate",
                  {k: float(v) for k, v in actual.items()}, threshold, "m")


def uniformity(rule, facts, target):
    data = facts.get("flight_dimensions")
    require(isinstance(data, dict), "Complete flight_dimensions required")
    require(data.get("inventory_complete") is True and data.get("evidence"), "Full riser and tread inventories require evidence")
    require(data.get("rectangular_treads_verified") is True, "Winders and sloping-landing exceptions need a different branch", "UNKNOWN_APPLICABILITY")
    spreads = {}
    for field, count_field in (("riser_heights", "riser_count"), ("tread_depths", "tread_count")):
        rows = data.get(field)
        require(isinstance(rows, list) and len(rows) >= 2, "At least two reviewed values for every riser/tread series are required")
        expected = data.get(count_field)
        require(type(expected) is int and expected >= 2 and expected == len(rows), "Incomplete or invalid per-flight inventory", "INCOMPLETE_TARGET_SET")
        native = target["observations"].get(count_field)
        if native and native.get("valid"):
            require(native["value"] == expected, "Series count differs from current IFC flight count", "INCOMPLETE_TARGET_SET")
        values = [measurement(item, target) for item in rows]
        spreads[field] = max(values) - min(values)
    limit = Decimal(str(rule["parameters"]["thresholds"]["maximum_variation"]))
    return result(all(v <= limit for v in spreads.values()), "Compared max-minus-min independently for the complete flight riser and tread series",
                  {k: float(v) for k, v in spreads.items()}, {"maximum_variation": float(limit)}, "m")


def escape_opening(rule, facts, target):
    data = facts.get("opening_dimensions")
    require(isinstance(data, dict), "Reviewed opening_dimensions required")
    require(data.get("shape") == "rectangular" and data.get("normal_operation_verified") is True and data.get("evidence"),
            "Only verified rectangular net openings under normal operation are supported", "INVALID_GEOMETRY")
    require(data.get("branch") in {"general", "grade_floor"} and data.get("branch_evidence"), "Grade-floor/general applicability must be reviewed", "UNKNOWN_APPLICABILITY")
    width = measurement(data.get("net_width"), target)
    height = measurement(data.get("net_height"), target)
    sill = measurement(data.get("sill_height"), target, nonnegative=True)
    limits = {k: Decimal(str(v)) for k, v in rule["parameters"]["thresholds"].items()}
    area = width * height
    minimum = limits["grade_floor_minimum_area"] if data["branch"] == "grade_floor" else limits["minimum_area"]
    tests = {"net_width": width >= limits["minimum_width"], "net_height": height >= limits["minimum_height"],
             "net_area": area >= minimum, "sill_height": sill <= limits["maximum_sill_height"]}
    return result(all(tests.values()), "Checked net width, height, derived rectangular area and sill height independently; does not establish opening placement or operability compliance",
                  {"net_width_m": float(width), "net_height_m": float(height), "net_area_m2": float(area), "sill_height_m": float(sill)},
                  {"minimum_width_m": float(limits["minimum_width"]), "minimum_height_m": float(limits["minimum_height"]),
                   "minimum_area_m2": float(minimum), "maximum_sill_height_m": float(limits["maximum_sill_height"])},
                  checks=tests, branch=data["branch"])


def headroom(rule, facts, target, extraction):
    data = facts.get("clearance_surface")
    require(isinstance(data, dict), "Complete headroom clearance surface required")
    require(data.get("representation") == "piecewise_planar_full_clearance", "Point samples or bounding boxes do not prove continuous clearance", "INVALID_GEOMETRY")
    require(data.get("full_surface_verified") is True and data.get("scope_covers_required_headroom") is True and data.get("evidence"),
            "Full width, nosing reference, lower landing extension and overhead surface completeness must be reviewed")
    require(data.get("source_global_id") == target["global_id"], "Clearance domain must bind to this stair flight", "INVALID_DATA")
    ids = data.get("geometry_source_global_ids")
    model_ids = {r["global_id"] for r in extraction["records"]}
    require(isinstance(ids, list) and ids and all(isinstance(g, str) for g in ids) and len(ids) == len(set(ids))
            and target["global_id"] in ids and set(ids).issubset(model_ids), "Clearance geometry sources must identify current IFC objects", "INVALID_DATA")
    require(data.get("unit") in FACTORS, "Clearance geometry requires explicit length units", "INVALID_DATA")
    scale = FACTORS[data["unit"]]
    axes = []
    for field in ("x", "y"):
        values = data.get(field)
        require(isinstance(values, list) and len(values) >= 2, "Full surface domain axes are required", "INVALID_GEOMETRY")
        values = [number(v, nonnegative=True) * scale for v in values]
        require(values[0] == 0 and all(b > a for a, b in zip(values, values[1:])), "Domain axes must start at zero and increase strictly", "INVALID_GEOMETRY")
        axes.append(values)
    length = measurement(data.get("domain_length"), target)
    width = measurement(data.get("domain_width"), target)
    require(axes[0][-1] == length and axes[1][-1] == width, "Clearance cells do not cover the reviewed full domain", "INVALID_GEOMETRY")
    matrices = []
    for field in ("nosing_z", "overhead_z"):
        rows = data.get(field)
        require(isinstance(rows, list) and len(rows) == len(axes[0]), "Incomplete clearance surface rows", "INVALID_GEOMETRY")
        require(all(isinstance(row, list) and len(row) == len(axes[1]) for row in rows), "Incomplete clearance surface columns", "INVALID_GEOMETRY")
        matrix = []
        for row in rows:
            out = []
            for value in row:
                require(isinstance(value, (int, float)) and not isinstance(value, bool), "Finite signed elevation required", "INVALID_GEOMETRY")
                v = Decimal(str(value))
                require(v.is_finite(), "Nonfinite elevation", "INVALID_GEOMETRY")
                out.append(v * scale)
            matrix.append(out)
        matrices.append(matrix)
    # Both surfaces use the SAME fixed cell diagonal (lower-left to upper-right).
    # Their difference is affine on every triangle, so its minimum is at a vertex.
    clearances = [(matrices[1][i][j] - matrices[0][i][j], i, j) for i in range(len(axes[0])) for j in range(len(axes[1]))]
    minimum, i, j = min(clearances)
    require(minimum >= 0, "Overhead surface lies below the reference surface", "INVALID_GEOMETRY")
    limit = Decimal(str(rule["parameters"]["thresholds"]["minimum_headroom"]))
    return result(minimum >= limit, "Computed exact minimum over the complete reviewed triangulated clearance surface; does not generate or approve an IFC clearance surface",
                  float(minimum), float(limit), "m", minimum_at={"x_m": float(axes[0][i]), "y_m": float(axes[1][j])},
                  representation=data["representation"], geometry_source_global_ids=ids)


def route(facts, targets):
    graph = facts.get("route_graph")
    require(isinstance(graph, dict), "Reviewed dwelling route_graph required")
    require(graph.get("inventory_complete") is True and graph.get("evidence"), "Full room, door and vertical-route graph must be reviewed", "INCOMPLETE_TARGET_SET")
    nodes, edges, starts, exits = (graph.get(k) for k in ("nodes", "edges", "starts", "exits"))
    require(isinstance(nodes, list) and nodes and isinstance(edges, list) and isinstance(starts, list) and starts and isinstance(exits, list) and exits,
            "Nodes, edges, room starts and verified exits are required")
    lookup = {r["global_id"]: r for r in targets}
    node_ids = []
    for node in nodes:
        require(isinstance(node, dict) and isinstance(node.get("global_id"), str) and node.get("role") in {"room", "circulation", "stair", "exit"}, "Invalid graph node", "INVALID_DATA")
        node_ids.append(node["global_id"])
    require(len(node_ids) == len(set(node_ids)) and set(node_ids).issubset(lookup), "Graph node identities must be unique IFC targets", "INVALID_DATA")
    require(all(isinstance(g, str) for g in starts + exits) and len(starts) == len(set(starts)) and len(exits) == len(set(exits)), "Invalid start/exit identifiers", "INVALID_DATA")
    rooms = {n["global_id"] for n in nodes if n["role"] == "room"}
    exit_ids = {n["global_id"] for n in nodes if n["role"] == "exit"}
    require(set(starts) == rooms and set(exits) == exit_ids and bool(rooms) and bool(exit_ids), "Starts/exits must cover every reviewed room/exit node", "INCOMPLETE_TARGET_SET")
    require(graph.get("exit_discharge_verified") is True and graph.get("exit_evidence"), "Exit-to-exterior discharge must be independently verified")
    for node in nodes:
        if node["role"] in {"room", "circulation"}:
            require(lookup[node["global_id"]]["ifc_type"] == "IfcSpace", "Room/circulation nodes must identify IfcSpace objects", "INVALID_DATA")
            require((lookup[node["global_id"]].get("storey") or {}).get("global_id"), "Room/circulation nodes need actual IFC storey assignments")
        if node["role"] == "exit":
            require("IfcDoor" in lookup[node["global_id"]]["entity_types"], "Exterior exits must identify reviewed IFC doors", "INVALID_DATA")
    adjacency = {g: [] for g in node_ids}
    represented = set(node_ids)
    for edge in edges:
        require(isinstance(edge, dict) and isinstance(edge.get("from"), str) and isinstance(edge.get("to"), str), "Invalid edge", "INVALID_DATA")
        a, b = edge["from"], edge["to"]
        require(a in adjacency and b in adjacency and a != b, "Invalid edge endpoint", "INVALID_DATA")
        via = edge.get("via_global_ids")
        require(isinstance(via, list) and via and all(isinstance(g, str) for g in via) and len(via) == len(set(via)) and set(via).issubset(lookup), "Edges require actual IFC door/transition identities", "INVALID_DATA")
        allowed = {"IfcDoor", "IfcStair", "IfcStairFlight", "IfcRamp", "IfcRampFlight"}
        require(all(set(lookup[g]["entity_types"]) & allowed for g in via), "Edge transition is not a door, stair or ramp", "INVALID_DATA")
        require(type(edge.get("traversable")) is bool and type(edge.get("bidirectional")) is bool and edge.get("evidence"), "Edge traversability/direction is unverified")
        represented.update(via)
        storeys = [lookup[g].get("storey") or {} for g in (a, b)]
        cross_storey = storeys[0].get("global_id") and storeys[1].get("global_id") and storeys[0]["global_id"] != storeys[1]["global_id"]
        if cross_storey or edge.get("vertical") is True:
            require(edge.get("vertical_verified") is True and any(set(lookup[g]["entity_types"]) & (allowed - {"IfcDoor"}) for g in via),
                    "Cross-storey edge requires a verified stair/ramp transition")
        if edge["traversable"]:
            adjacency[a].append(b)
            if edge["bidirectional"]:
                adjacency[b].append(a)
    require(represented == set(lookup), "Every selected IFC target must occur in the reviewed graph", "INCOMPLETE_TARGET_SET")
    paths, unreachable = {}, []
    for start in starts:
        pending, parent = deque([start]), {start: None}
        goal = None
        while pending:
            current = pending.popleft()
            if current in exit_ids:
                goal = current
                break
            for neighbor in adjacency[current]:
                if neighbor not in parent:
                    parent[neighbor] = current
                    pending.append(neighbor)
        if goal is None:
            unreachable.append(start)
        else:
            path = []
            while goal is not None:
                path.append(goal)
                goal = parent[goal]
            paths[start] = list(reversed(path))
    return result(not unreachable, "Checked directed reachability from each reviewed room to at least one verified exit; widths, locks, fire protection and travel limits are separate",
                  {"witness_paths": paths, "unreachable_room_global_ids": unreachable}, "Every reviewed room reaches at least one verified exterior exit")


def residential_check(rule, facts, targets, catalog, extraction):
    try:
        profile(facts)
        rid = rule["rule_id"]
        if rid in {"residential-riser-height", "residential-tread-depth"}:
            return declared_dimension(rule, facts, targets)
        if rid == "residential-egress-continuity":
            return route(facts, targets)
        require(len(targets) == 1, "Use one flight or one opening per check instance", "INVALID_DATA")
        if rid == "residential-stair-uniformity":
            return uniformity(rule, facts, targets[0])
        if rid == "residential-escape-opening":
            return escape_opening(rule, facts, targets[0])
        if rid == "residential-stair-headroom":
            return headroom(rule, facts, targets[0], extraction)
        raise DataError("INVALID_DATA", "Unknown residential check")
    except DataError as exc:
        return {"status": "UNKNOWN", "reason_code": exc.code, "reason": str(exc)}

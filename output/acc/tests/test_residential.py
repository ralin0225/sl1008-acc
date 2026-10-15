"""Synthetic IFC acceptance cases only; no real design is approved by these tests."""
import copy
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ACC = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ACC / "src"), str(ACC / ".python_deps"), str(ACC / "tests")]
import ifcopenshell
from compliance_contract import load_contracts, build_contracts
from compliance_runner import run, facts_hash
from ifc_requirements import extract_requirements
from prepare_compliance_facts import prepare
from test_precheck import make_model

RULES = {r["rule_id"]: r for r in load_contracts()["rules"] if r["check_function"] == "residential_check"}
FIXTURE = "SYNTHETIC FIXTURE ONLY; no building approval"


class ResidentialAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="acc_residential_synthetic_")
        cls.path = Path(cls.tmp.name) / "synthetic_two_storey.ifc"
        model = make_model()
        ground = model.by_type("IfcBuildingStorey")[0]
        upper = model.create_entity("IfcBuildingStorey", GlobalId=ifcopenshell.guid.new(), Name="SYNTHETIC upper")
        model.create_entity("IfcRelAggregates", GlobalId=ifcopenshell.guid.new(), RelatingObject=model.by_type("IfcBuilding")[0], RelatedObjects=[upper])
        cls.flight = model.create_entity("IfcStairFlight", GlobalId=ifcopenshell.guid.new(), Name=FIXTURE,
            NumberOfRisers=4, NumberOfTreads=3, RiserHeight=0.19, TreadLength=0.26)
        cls.opening = model.create_entity("IfcWindow", GlobalId=ifcopenshell.guid.new(), Name=FIXTURE)
        cls.exit = model.create_entity("IfcDoor", GlobalId=ifcopenshell.guid.new(), Name=FIXTURE)
        cls.beam = model.create_entity("IfcBeam", GlobalId=ifcopenshell.guid.new(), Name=FIXTURE)
        cls.lower_room = model.create_entity("IfcSpace", GlobalId=ifcopenshell.guid.new(), Name=FIXTURE)
        cls.upper_room = model.create_entity("IfcSpace", GlobalId=ifcopenshell.guid.new(), Name=FIXTURE)
        for storey, objects in ((ground, [cls.flight, cls.exit, cls.beam]), (upper, [cls.opening])):
            model.create_entity("IfcRelContainedInSpatialStructure", GlobalId=ifcopenshell.guid.new(), RelatingStructure=storey, RelatedElements=objects)
        for storey, room in ((ground, cls.lower_room), (upper, cls.upper_room)):
            model.create_entity("IfcRelAggregates", GlobalId=ifcopenshell.guid.new(), RelatingObject=storey, RelatedObjects=[room])
        model.write(str(cls.path))
        cls.model_hash = hashlib.sha256(cls.path.read_bytes()).hexdigest()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def measurement(self, value, unit="m", guid=None):
        return {"value": value, "unit": unit, "source_global_id": guid or self.flight.GlobalId,
                "method": "reviewed_manual_input", "valid": True, "semantics_verified": True, "evidence": FIXTURE}

    def sign(self, rid, facts):
        facts = copy.deepcopy(facts)
        rule = RULES[rid]
        facts["scope_review"] = {"resolution": "APPROVED", "reviewer": FIXTURE, "rationale": FIXTURE,
            "source_sha256": rule["evidence"]["sha256"], "contract_sha256": rule["contract_sha256"], "facts_sha256": facts_hash(facts)}
        return facts

    def example(self, rid):
        facts = {"model_evidence": {"ifc_sha256": self.model_hash}, "applicable": True, "applicability_evidence": FIXTURE,
            "scope_id": "SYNTHETIC dwelling", "inventory_complete": True, "target_global_ids": [self.flight.GlobalId],
            "residential_profile": {"code_basis": "IBC2021", "occupancy": "R-3", "stories_above_grade": 2, "single_dwelling": True, "evidence": FIXTURE},
            "exceptions_reviewed": True}
        if rid in {"residential-riser-height", "residential-tread-depth"}:
            facts.update(measurement_semantics_verified=True, measurement_definition_evidence=FIXTURE, rectangular_treads_verified=True)
        elif rid == "residential-stair-uniformity":
            facts["flight_dimensions"] = {"inventory_complete": True, "evidence": FIXTURE, "rectangular_treads_verified": True,
                "riser_count": 4, "tread_count": 3, "riser_heights": [self.measurement(.19) for _ in range(4)],
                "tread_depths": [self.measurement(.26) for _ in range(3)]}
        elif rid == "residential-escape-opening":
            facts["target_global_ids"] = [self.opening.GlobalId]
            facts["opening_dimensions"] = {"shape": "rectangular", "normal_operation_verified": True, "evidence": FIXTURE,
                "branch": "general", "branch_evidence": FIXTURE,
                "net_width": self.measurement(.8, guid=self.opening.GlobalId), "net_height": self.measurement(.7, guid=self.opening.GlobalId),
                "sill_height": self.measurement(1.0, guid=self.opening.GlobalId)}
        elif rid == "residential-stair-headroom":
            facts["clearance_surface"] = {"representation": "piecewise_planar_full_clearance", "full_surface_verified": True,
                "scope_covers_required_headroom": True, "evidence": FIXTURE, "source_global_id": self.flight.GlobalId,
                "geometry_source_global_ids": [self.flight.GlobalId, self.beam.GlobalId], "unit": "m", "x": [0, 1, 2], "y": [0, .5, 1],
                "nosing_z": [[0, 0, 0], [.5, .5, .5], [1, 1, 1]],
                "overhead_z": [[2.032, 2.032, 2.032], [2.532, 2.532, 2.532], [3.032, 3.032, 3.032]],
                "domain_length": self.measurement(2), "domain_width": self.measurement(1)}
        else:
            a, b, e, stair = self.upper_room.GlobalId, self.lower_room.GlobalId, self.exit.GlobalId, self.flight.GlobalId
            facts["target_global_ids"] = [a, b, e, stair]
            facts["route_graph"] = {"inventory_complete": True, "evidence": FIXTURE, "exit_discharge_verified": True, "exit_evidence": FIXTURE,
                "nodes": [{"global_id": a, "role": "room"}, {"global_id": b, "role": "room"}, {"global_id": e, "role": "exit"}],
                "starts": [a, b], "exits": [e], "edges": [
                    {"from": a, "to": b, "via_global_ids": [stair], "traversable": True, "bidirectional": True, "vertical": True, "vertical_verified": True, "evidence": FIXTURE},
                    {"from": b, "to": e, "via_global_ids": [e], "traversable": True, "bidirectional": True, "evidence": FIXTURE}]}
        return self.sign(rid, facts)

    def execute(self, rid, facts):
        return run(self.path, "synthetic-residential", {"is_synthetic": True, "facts_by_rule": {rid: facts}}, [rid], persist=False)["results"][0]

    def edit(self, rid, facts, mutate):
        facts = copy.deepcopy(facts)
        mutate(facts)
        return self.execute(rid, self.sign(rid, facts))

    def test_six_contracts_classes_sources_and_pending_status(self):
        self.assertEqual(len(RULES), 6)
        self.assertEqual([r["rule_class"] for r in RULES.values()], [1, 1, 2, 2, 3, 3])
        self.assertEqual(len(build_contracts()["rules"]), 15)
        for rule in RULES.values():
            self.assertTrue(rule["class_basis"] and rule["dsl_sources"])
            self.assertEqual(rule["review_status"], "PENDING")
            self.assertFalse(rule["execution_ready"])
            for atom in rule["dsl_sources"]:
                self.assertEqual(hashlib.sha256(atom["text"].encode()).hexdigest(), atom["sha256"])

    def test_all_six_pass_missing_excluded_and_review_gates(self):
        for rid, rule in RULES.items():
            with self.subTest(rule=rid):
                result = self.execute(rid, self.example(rid))
                self.assertEqual(result["status"], "PASS", result["what"])
                self.assertEqual(result["rule_class"], rule["rule_class"])
                self.assertEqual(self.execute(rid, None)["display_status"], "NOT CHECKABLE")
                facts = self.example(rid)
                self.assertEqual(self.edit(rid, facts, lambda f: f.update(applicable=False))["status"], "NOT_APPLICABLE")
                self.assertEqual(self.edit(rid, facts, lambda f: f.pop("residential_profile"))["what"]["reason_code"], "MISSING_DATA")
                facts["scope_review"]["resolution"] = "PENDING"
                self.assertEqual(self.execute(rid, facts)["status"], "MANUAL_REVIEW")

    def test_residential_limits_and_unit_boundaries(self):
        for rid, passed, failed in (("residential-riser-height", 7.75, 7.750001), ("residential-tread-depth", 10, 9.999999)):
            for unit, factor in (("inch", 1), ("mm", 25.4), ("m", .0254)):
                for value, status in ((passed, "PASS"), (failed, "FAIL")):
                    facts = self.example(rid)
                    facts["measurements"] = {self.flight.GlobalId: self.measurement(round(value * factor, 12), unit)}
                    self.assertEqual(self.execute(rid, self.sign(rid, facts))["status"], status)
        # R-3's 7.75-inch exception must not be replaced by the 7-inch general rule.
        facts = self.example("residential-riser-height")
        facts["measurements"] = {self.flight.GlobalId: self.measurement(190, "mm")}
        self.assertEqual(self.execute("residential-riser-height", self.sign("residential-riser-height", facts))["status"], "PASS")

    def test_invalid_dimensions_missing_semantics_and_wrong_occupancy(self):
        rid = "residential-riser-height"
        for value, unit in ((True, "m"), (-1, "m"), (float("inf"), "m"), (.19, "unknown")):
            facts = self.example(rid)
            facts["measurements"] = {self.flight.GlobalId: self.measurement(value, unit)}
            # Nonfinite data cannot be hashed as approved JSON either.
            if value == float("inf"):
                with self.assertRaises(ValueError):
                    self.sign(rid, facts)
            else:
                self.assertEqual(self.execute(rid, self.sign(rid, facts))["what"]["reason_code"], "INVALID_DATA")
        facts = self.example(rid)
        self.assertEqual(self.edit(rid, facts, lambda f: f.update(measurement_semantics_verified=False))["display_status"], "NOT CHECKABLE")
        self.assertEqual(self.edit(rid, facts, lambda f: f["residential_profile"].update(occupancy="R-2"))["what"]["reason_code"], "UNKNOWN_APPLICABILITY")
        self.assertEqual(self.edit(rid, facts, lambda f: f.update(exceptions_reviewed=False))["what"]["reason_code"], "UNKNOWN_APPLICABILITY")

    def test_uniformity_exact_boundary_incomplete_series_and_native_count(self):
        rid = "residential-stair-uniformity"
        for difference, status in ((.009525, "PASS"), (.009526, "FAIL")):
            facts = self.example(rid)
            facts["flight_dimensions"]["riser_heights"][-1] = self.measurement(round(.19 + difference, 9))
            self.assertEqual(self.execute(rid, self.sign(rid, facts))["status"], status)
        facts = self.example(rid)
        self.assertEqual(self.edit(rid, facts, lambda f: f["flight_dimensions"]["tread_depths"].pop())["what"]["reason_code"], "INCOMPLETE_TARGET_SET")
        self.assertEqual(self.edit(rid, facts, lambda f: f["flight_dimensions"].update(riser_count=5))["display_status"], "NOT CHECKABLE")
        self.assertEqual(self.edit(rid, facts, lambda f: f["flight_dimensions"].update(rectangular_treads_verified=False))["display_status"], "NOT CHECKABLE")

    def test_opening_minimum_width_and_height_are_insufficient_area(self):
        rid = "residential-escape-opening"
        facts = self.example(rid)
        data = facts["opening_dimensions"]
        data.update(net_width=self.measurement(20, "inch", self.opening.GlobalId), net_height=self.measurement(24, "inch", self.opening.GlobalId))
        answer = self.execute(rid, self.sign(rid, facts))
        self.assertEqual(answer["status"], "FAIL")
        self.assertEqual(answer["what"]["calculation"]["checks"], {"net_width": True, "net_height": True, "net_area": False, "sill_height": True})

    def test_opening_general_grade_floor_branch_and_exact_sill(self):
        rid = "residential-escape-opening"
        facts = self.example(rid)
        data = facts["opening_dimensions"]
        data.update(net_width=self.measurement(2, "ft", self.opening.GlobalId), net_height=self.measurement(2.5, "ft", self.opening.GlobalId),
                    sill_height=self.measurement(44, "inch", self.opening.GlobalId))
        self.assertEqual(self.execute(rid, self.sign(rid, facts))["status"], "FAIL")
        data["branch"] = "grade_floor"
        self.assertEqual(self.execute(rid, self.sign(rid, facts))["status"], "PASS")
        data["sill_height"] = self.measurement(1118, "mm", self.opening.GlobalId)
        self.assertEqual(self.execute(rid, self.sign(rid, facts))["status"], "FAIL")
        self.assertEqual(self.edit(rid, facts, lambda f: f["opening_dimensions"].update(shape="irregular"))["what"]["reason_code"], "INVALID_GEOMETRY")

    def test_headroom_full_surface_interior_low_point_and_sparse_data(self):
        rid = "residential-stair-headroom"
        facts = self.example(rid)
        answer = self.edit(rid, facts, lambda f: f["clearance_surface"]["overhead_z"][1].__setitem__(1, 2.5))
        self.assertEqual(answer["status"], "FAIL")
        self.assertEqual(answer["what"]["actual"], 2.0)
        for mutate in (lambda f: f["clearance_surface"].update(representation="sample_points"),
                       lambda f: f["clearance_surface"].update(x=[0, 1]),
                       lambda f: f["clearance_surface"]["overhead_z"][1].pop(),
                       lambda f: f["clearance_surface"].update(scope_covers_required_headroom=False),
                       lambda f: f["clearance_surface"].update(geometry_source_global_ids=["unknown"])):
            self.assertEqual(self.edit(rid, facts, mutate)["display_status"], "NOT CHECKABLE")

    def test_route_direction_closed_door_cross_floor_and_ifc_binding(self):
        rid = "residential-egress-continuity"
        facts = self.example(rid)
        answer = self.edit(rid, facts, lambda f: f["route_graph"]["edges"][0].update(traversable=False))
        self.assertEqual(answer["status"], "FAIL")
        self.assertEqual(answer["what"]["actual"]["unreachable_room_global_ids"], [self.upper_room.GlobalId])
        self.assertEqual(self.edit(rid, facts, lambda f: f["route_graph"]["edges"][0].update(vertical_verified=False))["display_status"], "NOT CHECKABLE")
        self.assertEqual(self.edit(rid, facts, lambda f: f["route_graph"]["edges"][1].update(traversable=None))["display_status"], "NOT CHECKABLE")
        self.assertEqual(self.edit(rid, facts, lambda f: f["route_graph"].update(starts=[self.lower_room.GlobalId]))["what"]["reason_code"], "INCOMPLETE_TARGET_SET")
        self.assertEqual(self.edit(rid, facts, lambda f: f["route_graph"]["edges"][0].update(via_global_ids=["unknown"]))["what"]["reason_code"], "INVALID_DATA")
        answer = self.execute(rid, facts)
        self.assertEqual(answer["what"]["actual"]["witness_paths"][self.upper_room.GlobalId], [self.upper_room.GlobalId, self.lower_room.GlobalId, self.exit.GlobalId])

    def test_new_facts_change_invalidates_review_and_model_is_bound(self):
        for rid in RULES:
            facts = self.example(rid)
            facts["exceptions_reviewed"] = False
            self.assertEqual(self.execute(rid, facts)["status"], "MANUAL_REVIEW")
            facts["model_evidence"]["ifc_sha256"] = "0" * 64
            self.assertEqual(self.execute(rid, self.sign(rid, facts))["what"]["reason_code"], "INVALID_DATA")

    def test_extraction_and_templates_do_not_invent_approvals(self):
        observed = extract_requirements(self.path, "synthetic-residential")
        flight = next(r for r in observed["records"] if r["global_id"] == self.flight.GlobalId)
        self.assertEqual(flight["observations"]["riser_height"]["value"], .19)
        self.assertEqual(flight["observations"]["tread_depth"]["value"], .26)
        self.assertFalse(flight["observations"]["riser_height"]["semantics_verified"])
        self.assertIn("IfcWindow", next(r for r in observed["records"] if r["global_id"] == self.opening.GlobalId)["entity_types"])
        for rid, facts in prepare(self.path, "synthetic-residential")["facts_by_rule"].items():
            self.assertEqual(facts["scope_review"]["resolution"], "PENDING")
            if rid in RULES:
                self.assertIsNone(facts["residential_profile"]["occupancy"])
                self.assertFalse(facts["exceptions_reviewed"])


if __name__ == "__main__":
    unittest.main()

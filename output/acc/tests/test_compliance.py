"""ACC acceptance tests. All approved facts are SYNTHETIC FIXTURES ONLY."""
import copy
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ACC = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ACC / "src"), str(ACC / ".python_deps")]
import ifcopenshell
from compliance_contract import load_contracts, read, digest
from compliance_runner import run, facts_hash, summary, FUNCTIONS
from ifc_requirements import extract_requirements
from test_precheck import make_model
from test_inventory import add_pset


RULES = {r["rule_id"]: r for r in load_contracts()["rules"]}
LEGACY = {r["rule_id"]: r for r in read(ACC / "mvp_rule_catalog.json")["rules"]}


class ComplianceAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="acc_synthetic_fixture_")
        cls.path = Path(cls.tmp.name) / "synthetic_fixture.ifc"
        model = make_model()
        cls.spaces = [model.create_entity("IfcSpace", GlobalId=ifcopenshell.guid.new(), Name=f"FIXTURE space {i}") for i in range(51)]
        cls.doors = [model.create_entity("IfcDoor", GlobalId=ifcopenshell.guid.new(), Name=f"FIXTURE door {i}", OverallWidth=1.2) for i in range(4)]
        for obj in [*cls.spaces, *cls.doors]:
            add_pset(model, obj, {"Accessible": True, "UseCode": "PARKING_SPACE"})
        cls.bad_space = model.create_entity("IfcSpace", GlobalId=ifcopenshell.guid.new())
        cls.bad_door = model.create_entity("IfcDoor", GlobalId=ifcopenshell.guid.new())
        add_pset(model, cls.bad_space, {"UseCode": "NOT_A_VALID_CODE"})
        add_pset(model, cls.bad_door, {"Accessible": "INVALID_BOOLEAN"})
        cls.missing_space = model.create_entity("IfcSpace", GlobalId=ifcopenshell.guid.new())
        model.write(str(cls.path))
        cls.model_hash = hashlib.sha256(cls.path.read_bytes()).hexdigest()
        cls.space_ids = [s.GlobalId for s in cls.spaces]
        cls.door_ids = [s.GlobalId for s in cls.doors]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def approved(self, rule_id, **values):
        rule = RULES[rule_id]
        facts = {"model_evidence": {"ifc_sha256": self.model_hash}, "applicable": True,
            "applicability_evidence": "SYNTHETIC FIXTURE ONLY", "scope_id": "fixture-scope",
            "inventory_kind": rule["target_selector"]["inventory_kind"], "inventory_complete": True,
            "accessible_design_verified": True, "accessible_design_evidence": "SYNTHETIC FIXTURE ONLY", **values}
        return self.sign(rule_id, facts)

    def sign(self, rule_id, facts):
        facts = copy.deepcopy(facts)
        rule = RULES[rule_id]
        facts["scope_review"] = {"resolution": "APPROVED", "reviewer": "SYNTHETIC FIXTURE ONLY",
            "rationale": "SYNTHETIC FIXTURE ONLY; exceptions and measurement scope simulated",
            "source_sha256": rule["evidence"]["sha256"], "contract_sha256": rule["contract_sha256"],
            "definition_sha256": rule["legacy_definition_sha256"], "facts_sha256": facts_hash(facts)}
        return facts

    def execute(self, rule_id, facts):
        return run(self.path, "fixture", {"is_synthetic": True, "facts_by_rule": {rule_id: facts}}, [rule_id], persist=False)["results"][0]

    def example(self, rule_id, fail=False):
        count_cases = {"parking-minimum": (26, 2), "van-parking-minimum": (7, 2),
            "public-entrance-minimum": (4, 3), "tenant-entrance-minimum": (1, 1), "type-a-unit-minimum": (51, 2)}
        if rule_id in count_cases:
            total, actual = count_cases[rule_id]
            ids = (self.door_ids if "entrance" in rule_id else self.space_ids)[:total]
            actual -= int(fail)
            values = {"target_global_ids": ids, "accessible": actual, "accessible_global_ids": ids[:actual]}
            if rule_id != "tenant-entrance-minimum":
                values["total"] = total
            return self.approved(rule_id, **values)
        if rule_id == "site-route-connectivity":
            ids = self.space_ids[:2]
            return self.approved(rule_id, target_global_ids=ids, nodes=ids, targets=ids,
                edges=[] if fail else [{"from": ids[0], "to": ids[1], "accessible_verified": True,
                    "bidirectional": True, "evidence": "SYNTHETIC FIXTURE ONLY"}])
        if rule_id == "required-accessibility-pset":
            return self.approved(rule_id, target_global_ids=[self.bad_door.GlobalId if fail else self.door_ids[0]])
        if rule_id == "space-use-classification":
            return self.approved(rule_id, target_global_ids=[self.bad_space.GlobalId if fail else self.space_ids[0]])
        return self.width(812.7 if fail else 812.8, "mm")

    def width(self, value, unit, **overrides):
        values = {"target_global_ids": [self.door_ids[0]], "width_branch": "general_32_inch",
            "clear_width": {"value": value, "unit": unit, "method": "reviewed_manual_input", "valid": True,
                "source_global_id": self.door_ids[0], "evidence": "SYNTHETIC FIXTURE ONLY"},
            "clear_width_semantics_verified": True, "measurement_definition_evidence": "SYNTHETIC FIXTURE 90 degree leaf-to-stop"}
        return self.approved("egress-door-clear-width", **{**values, **overrides})

    def test_each_of_nine_rules_pass_fail_missing_excluded(self):
        for rule_id in RULES:
            with self.subTest(rule=rule_id):
                self.assertEqual(self.execute(rule_id, self.example(rule_id))["display_status"], "PASS")
                self.assertEqual(self.execute(rule_id, self.example(rule_id, fail=True))["display_status"], "FAIL")
                self.assertEqual(self.execute(rule_id, None)["display_status"], "NOT CHECKABLE")
                missing = self.example(rule_id)
                if RULES[rule_id]["kind"] == "count":
                    del missing["accessible_global_ids"]
                elif RULES[rule_id]["kind"] == "topology":
                    del missing["edges"]
                elif RULES[rule_id]["kind"] == "dimension":
                    del missing["clear_width"]
                else:
                    missing["target_global_ids"] = [self.missing_space.GlobalId]
                self.assertEqual(self.execute(rule_id, self.sign(rule_id, missing))["what"]["reason_code"], "MISSING_DATA")
                exclusion = self.example(rule_id)
                exclusion["applicable"] = False
                self.assertEqual(self.execute(rule_id, self.sign(rule_id, exclusion))["status"], "NOT_APPLICABLE")

    def test_width_boundaries_units_and_no_relaxation(self):
        for value, unit in [(0.8128, "m"), (812.8, "mm"), (32, "inch")]:
            result = self.execute("egress-door-clear-width", self.width(value, unit))
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["what"]["tolerance"], 0)
        self.assertEqual(self.execute("egress-door-clear-width", self.width(0.8127999, "m"))["status"], "FAIL")
        facts = self.width(1054, "mm", width_branch="i2_bed_movement_41_5_inch")
        self.assertEqual(self.execute("egress-door-clear-width", facts)["status"], "FAIL")
        self.assertEqual(self.execute("egress-door-clear-width", self.width(41.5, "inch", width_branch="i2_bed_movement_41_5_inch"))["status"], "PASS")
        for value, unit in [(True, "m"), (-1, "m"), (1, "unknown")]:
            self.assertEqual(self.execute("egress-door-clear-width", self.width(value, unit))["what"]["reason_code"], "INVALID_DATA")

    def test_overall_width_never_substitutes_for_clear_width(self):
        extraction = extract_requirements(self.path, "fixture")
        door = next(r for r in extraction["records"] if r["global_id"] == self.door_ids[0])
        self.assertEqual(door["observations"]["overall_width"]["value"], 1.2)
        self.assertFalse(door["observations"]["overall_width"]["usable_as_clear_width"])
        facts = self.width(1, "m")
        del facts["clear_width"]
        self.assertEqual(self.execute("egress-door-clear-width", self.sign("egress-door-clear-width", facts))["what"]["reason_code"], "MISSING_DATA")

    def test_review_binds_facts_source_contract_and_model(self):
        rule_id = "parking-minimum"
        for field in ("source_sha256", "contract_sha256", "facts_sha256", "reviewer", "rationale"):
            facts = self.example(rule_id); facts["scope_review"][field] = ""
            self.assertEqual(self.execute(rule_id, facts)["status"], "MANUAL_REVIEW")
        facts = self.example(rule_id); facts["accessible"] = 0
        self.assertEqual(self.execute(rule_id, facts)["status"], "MANUAL_REVIEW")
        facts = self.example(rule_id); facts["model_evidence"]["ifc_sha256"] = "0" * 64
        self.assertEqual(self.execute(rule_id, self.sign(rule_id, facts))["what"]["reason_code"], "INVALID_DATA")

    def test_no_targets_incomplete_inventory_and_count_inconsistency(self):
        rule_id = "parking-minimum"
        for field, value, code in [("target_global_ids", [], "INCOMPLETE_TARGET_SET"), ("inventory_complete", False, "INCOMPLETE_TARGET_SET"),
                                   ("total", 99, "INVALID_DATA"), ("target_global_ids", ["missing"], "INVALID_DATA")]:
            facts = self.example(rule_id); facts[field] = value
            self.assertEqual(self.execute(rule_id, self.sign(rule_id, facts))["what"]["reason_code"], code)

    def test_topology_direction_uncertainty_and_completeness(self):
        rule_id = "site-route-connectivity"
        facts = self.example(rule_id)
        facts["inventory_complete"] = False
        self.assertEqual(self.execute(rule_id, self.sign(rule_id, facts))["what"]["reason_code"], "INCOMPLETE_TARGET_SET")
        facts = self.example(rule_id); facts["edges"][0]["bidirectional"] = False
        self.assertEqual(self.execute(rule_id, self.sign(rule_id, facts))["status"], "FAIL")
        facts["edges"][0]["accessible_verified"] = None
        self.assertEqual(self.execute(rule_id, self.sign(rule_id, facts))["display_status"], "NOT CHECKABLE")
        facts = self.example(rule_id); facts["edges"][0]["from"] = "unknown"
        self.assertEqual(self.execute(rule_id, self.sign(rule_id, facts))["what"]["reason_code"], "INVALID_DATA")

    def test_information_absence_and_false_are_different(self):
        facts = self.approved("space-use-classification", target_global_ids=[self.missing_space.GlobalId])
        self.assertEqual(self.execute("space-use-classification", facts)["what"]["reason_code"], "MISSING_DATA")

    def test_error_reference_geometry_have_specific_codes(self):
        rid = "egress-door-clear-width"
        facts = self.width(1, "m", unresolved_required_references=["unresolved"])
        self.assertEqual(self.execute(rid, facts)["what"]["reason_code"], "UNRESOLVED_REFERENCE")
        facts = self.width(1, "m", geometry_required=True, geometry_valid=False)
        self.assertEqual(self.execute(rid, facts)["what"]["reason_code"], "INVALID_GEOMETRY")
        with patch.dict(FUNCTIONS, clear_width=lambda *a: (_ for _ in ()).throw(RuntimeError("fixture failure"))):
            self.assertEqual(self.execute(rid, self.width(1, "m"))["what"]["reason_code"], "CHECK_ERROR")
        with patch("compliance_runner.extract_requirements", side_effect=RuntimeError("fixture extraction failure")):
            report = run(self.path, "fixture", persist=False)
            self.assertTrue(all(r["what"]["reason_code"] == "CHECK_ERROR" for r in report["results"]))

    def test_repeatable_results_multiple_instances_and_zero_denominators(self):
        rid = "egress-door-clear-width"
        facts = [self.width(1, "m"), self.width(0.8, "m")]
        inputs = {"is_synthetic": True, "facts_by_rule": {rid: facts}}
        reports = [run(self.path, "fixture", inputs, [rid], persist=False) for _ in range(2)]
        self.assertEqual(reports[0]["input_sha256"], reports[1]["input_sha256"])
        self.assertNotEqual(reports[0]["run_id"], reports[1]["run_id"])
        self.assertEqual([r["what"] for r in reports[0]["results"]], [r["what"] for r in reports[1]["results"]])
        self.assertEqual(reports[0]["summary"]["rule_count"], 1)
        self.assertEqual(reports[0]["summary"]["instance_count"], 2)
        self.assertIsNone(summary([])["determined_pass_rate"])
        self.assertIsNone(summary([])["completed_determination_rate"])

    def test_real_ifc_samples_are_not_checkable_and_keep_door_identity(self):
        paths = {"ifcopenhouse": "ifcopenhouse/IfcOpenHouse_IFC4.ifc", "buildingsmart-simple-scene": "buildingsmart-simple-scene/Building-Architecture_IFC4.ifc"}
        for mid, suffix in paths.items():
            report = run(ACC / "models" / suffix, mid, persist=False)
            self.assertEqual(report["summary"]["NOT CHECKABLE"], 9)
            self.assertEqual(report["summary"]["PASS"], 0)
            self.assertFalse(report["is_synthetic"])
            if mid == "ifcopenhouse":
                door = next(r for r in report["results"] if r["rule_id"] == "egress-door-clear-width")
                self.assertIn("0Tif_$wI1FwAwq$OJt24I8", door["where"]["global_ids"])


if __name__ == "__main__":
    unittest.main()

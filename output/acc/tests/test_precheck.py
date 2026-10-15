"""Synthetic regression tests; no project IFC or compliance results are created."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ACC = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ACC / "src"), str(ACC / ".python_deps")]
import ifcopenshell
from precheck_ifc import check


def make_model(length_unit=True, connected=True):
    model = ifcopenshell.file(schema="IFC4")
    project = model.create_entity("IfcProject", GlobalId=ifcopenshell.guid.new(), Name="SYNTHETIC TEST ONLY")
    unit = model.create_entity("IfcSIUnit", UnitType="LENGTHUNIT" if length_unit else "AREAUNIT", Name="METRE" if length_unit else "SQUARE_METRE")
    project.UnitsInContext = model.create_entity("IfcUnitAssignment", Units=[unit])
    chain = [project] + [model.create_entity(t, GlobalId=ifcopenshell.guid.new()) for t in ("IfcSite", "IfcBuilding", "IfcBuildingStorey")]
    if connected:
        for parent, child in zip(chain, chain[1:]):
            model.create_entity("IfcRelAggregates", GlobalId=ifcopenshell.guid.new(), RelatingObject=parent, RelatedObjects=[child])
    return model


def run(model):
    with tempfile.TemporaryDirectory(prefix="acc_synthetic_test_") as directory:
        path = Path(directory) / "synthetic_fixture.ifc"
        model.write(str(path))
        return check(path)


class PrecheckRegression(unittest.TestCase):
    def test_explicit_units_and_connected_hierarchy(self):
        report = run(make_model())
        self.assertEqual(report["checks"]["units"]["status"], "PASS")
        self.assertEqual(report["checks"]["hierarchy"]["status"], "PASS")
        self.assertEqual(report["status"], "UNKNOWN")
        self.assertFalse(report["compliance_evaluated"])

    def test_missing_length_unit_never_defaults_to_metre(self):
        report = run(make_model(length_unit=False))
        self.assertEqual(report["checks"]["units"]["status"], "UNKNOWN")
        self.assertNotIn("length_to_metre", report["checks"]["units"])

    def test_disconnected_hierarchy_is_unknown(self):
        report = run(make_model(connected=False))
        self.assertEqual(report["checks"]["hierarchy"]["status"], "UNKNOWN")
        self.assertEqual(len(report["checks"]["hierarchy"]["unlinked"]), 3)

    def test_empty_ids_applicability_never_passes(self):
        report = run(make_model())
        self.assertEqual(report["checks"]["ids"]["status"], "UNKNOWN")
        self.assertTrue(all(s["status"] == "UNKNOWN" for s in report["checks"]["ids"]["specifications"]))

    def test_missing_door_pset_is_unknown_with_guid(self):
        model = make_model()
        door = model.create_entity("IfcDoor", GlobalId=ifcopenshell.guid.new())
        report = run(model)
        item = next(s for s in report["checks"]["ids"]["specifications"] if s["name"] == "Door accessibility declaration")
        self.assertEqual(item["status"], "UNKNOWN")
        self.assertEqual(item["source_node_id"], "ibc2021-1105.1")
        self.assertEqual(item["failures"][0]["guid"], door.GlobalId)

    def test_duplicate_guid_is_model_quality_failure(self):
        model = make_model()
        guid = ifcopenshell.guid.new()
        model.create_entity("IfcDoor", GlobalId=guid)
        model.create_entity("IfcDoor", GlobalId=guid)
        report = run(model)
        self.assertEqual(report["checks"]["guid"]["status"], "FAIL")
        self.assertFalse(report["compliance_evaluated"])

    def test_false_accessible_is_present_information(self):
        from test_inventory import add_pset
        model = make_model()
        door = model.create_entity("IfcDoor", GlobalId=ifcopenshell.guid.new())
        add_pset(model, door, {"Accessible": False, "EntranceType": "PUBLIC"})
        item = next(s for s in run(model)["checks"]["ids"]["specifications"] if s["name"] == "Door accessibility declaration")
        self.assertEqual(item["status"], "PASS")
        self.assertEqual(item["source_node_id"], "ibc2021-1105.1")

    def test_invalid_entrance_code_is_not_silently_accepted(self):
        from test_inventory import add_pset
        model = make_model()
        door = model.create_entity("IfcDoor", GlobalId=ifcopenshell.guid.new())
        add_pset(model, door, {"Accessible": True, "EntranceType": "UNKNOWN_CODE"})
        item = next(s for s in run(model)["checks"]["ids"]["specifications"] if s["name"] == "Door accessibility declaration")
        self.assertEqual(item["status"], "UNKNOWN")
        self.assertTrue(item["failures"])

    def test_unreadable_input_is_unknown(self):
        with tempfile.TemporaryDirectory(prefix="acc_synthetic_test_") as directory:
            path = Path(directory) / "broken.ifc"
            path.write_text("not an IFC", encoding="utf-8")
            report = check(path)
            self.assertEqual(report["status"], "UNKNOWN")
            self.assertEqual(report["checks"]["parse"]["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()

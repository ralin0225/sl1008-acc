"""Ensure declared facts never become approved compliance facts."""
import sys
import tempfile
import unittest
from pathlib import Path

ACC = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ACC / "src"), str(ACC / ".python_deps")]
import ifcopenshell
from ifc_inventory import extract
from test_precheck import make_model


def add_pset(model, entity, values):
    properties = []
    for name, value in values.items():
        typename = "IfcBoolean" if isinstance(value, bool) else "IfcIdentifier" if name == "ParkingFacilityId" else "IfcLabel"
        properties.append(model.create_entity("IfcPropertySingleValue", Name=name, NominalValue=model.create_entity(typename, value)))
    pset = model.create_entity("IfcPropertySet", GlobalId=ifcopenshell.guid.new(), Name="ACC_Accessibility", HasProperties=properties)
    model.create_entity("IfcRelDefinesByProperties", GlobalId=ifcopenshell.guid.new(), RelatedObjects=[entity], RelatingPropertyDefinition=pset)


class InventoryRegression(unittest.TestCase):
    def test_missing_boolean_and_explicit_false_are_distinct(self):
        model = make_model()
        first = model.create_entity("IfcSpace", GlobalId=ifcopenshell.guid.new())
        second = model.create_entity("IfcSpace", GlobalId=ifcopenshell.guid.new())
        add_pset(model, first, {"UseCode": "PARKING_SPACE", "ParkingFacilityId": "TEST", "Accessible": False, "ParkingIsVanAccessible": False})
        add_pset(model, second, {"UseCode": "PARKING_SPACE", "ParkingFacilityId": "TEST"})
        with tempfile.TemporaryDirectory(prefix="acc_synthetic_test_") as directory:
            path = Path(directory) / "synthetic.ifc"
            model.write(str(path))
            result = extract(path)
        parking = result["parking_facilities"][0]
        self.assertEqual(parking["declared_total"], 2)
        self.assertEqual(parking["missing_accessible"], 1)
        self.assertEqual(parking["declared_accessible"], 0)
        self.assertFalse(parking["inventory_complete"])
        self.assertFalse(result["execution_ready"])

    def test_space_name_does_not_classify_use(self):
        model = make_model()
        model.create_entity("IfcSpace", GlobalId=ifcopenshell.guid.new(), Name="Accessible Parking Space")
        with tempfile.TemporaryDirectory(prefix="acc_synthetic_test_") as directory:
            path = Path(directory) / "synthetic.ifc"
            model.write(str(path))
            result = extract(path)
        self.assertEqual(result["parking_facilities"], [])


if __name__ == "__main__":
    unittest.main()

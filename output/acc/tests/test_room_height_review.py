"""Synthetic boundary and failure cases, never real-model approvals."""
import copy
from fractions import Fraction
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from room_height_review import area_at_least, evaluate, facts_digest

GUID = "0MalxD7nD24Bc1c1qVC3zt"


def fixture(height=2286, use="habitable", form="flat"):
    return {"is_synthetic": True, "code_basis": "IBC2021", "model_sha256": "0"*64,
            "target_global_id": GUID, "measurement_basis": "finished_floor_to_finished_underside",
            "applicability_verified": True, "exceptions_reviewed": True, "unresolved_exceptions": [],
            "room_use": use, "ceiling_form": form, "sloped_denominator": "full_room_projected_area",
            "surface": {"representation": "rectangular_full_domain_piecewise_planar", "unit": "mm",
                        "full_domain_verified": True, "obstructions_resolved": True, "evidence": "SYNTHETIC FULL SURFACE",
                        "source_global_ids": [GUID], "x": [0,3000], "y": [0,4000], "length": 3000, "width": 4000,
                        "finished_floor_z": [[0,0],[0,0]], "finished_underside_z": [[height,height],[height,height]]}}


def reviewed(facts):
    facts = copy.deepcopy(facts)
    facts["review"] = {"resolution": "APPROVED", "reviewer": "SYNTHETIC FIXTURE ONLY", "evidence": "No actual model approval", "facts_sha256": facts_digest(facts)}
    return facts


class RoomHeightTests(unittest.TestCase):
    def test_kitchen_and_habitable_have_different_limits(self):
        self.assertEqual(evaluate(reviewed(fixture(2200, "kitchen")))["status"], "PASS")
        self.assertEqual(evaluate(reviewed(fixture(2200)))["status"], "FAIL")

    def test_exact_imperial_boundary(self):
        self.assertEqual(evaluate(reviewed(fixture(2133.6,"kitchen")))["status"], "PASS")
        self.assertEqual(evaluate(reviewed(fixture(2133.59,"kitchen")))["status"], "FAIL")

    def test_dwelling_corridor_context(self):
        f = fixture(2200,"dwelling_corridor")
        self.assertEqual(evaluate(reviewed(f))["status"], "NOT CHECKABLE")
        f["within_group_r_dwelling_or_sleeping_unit"] = True
        self.assertEqual(evaluate(reviewed(f))["status"], "PASS")

    def test_sloped_half_area_exact_and_under(self):
        f = fixture(form="sloped")
        f["surface"]["finished_underside_z"] = [[1000,1000],[3572,3572]]
        r = evaluate(reviewed(f))
        self.assertEqual(r["status"], "PASS")
        self.assertEqual(r["qualifying_fraction"], .5)
        self.assertGreater(r["below_5ft_area_m2"], 0)
        f["surface"]["finished_underside_z"][1] = [3571,3571]
        self.assertEqual(evaluate(reviewed(f))["status"], "FAIL")

    def test_furred_two_thirds_and_absolute_floor(self):
        f = fixture(form="furred")
        f["surface"]["finished_underside_z"] = [[2133.6,2133.6],[2590.8,2590.8]]
        r = evaluate(reviewed(f))
        self.assertEqual(r["status"], "PASS")
        self.assertAlmostEqual(r["qualifying_fraction"], 2/3)
        f["surface"]["finished_underside_z"][0] = [2100,2100]
        f["surface"]["finished_underside_z"][1] = [4000,4000]
        self.assertEqual(evaluate(reviewed(f))["status"], "FAIL")

    def test_interior_low_point_not_just_corners(self):
        f = fixture()
        f["surface"]["x"] = [0,1500,3000]
        f["surface"]["y"] = [0,2000,4000]
        f["surface"]["finished_floor_z"] = [[0]*3 for _ in range(3)]
        f["surface"]["finished_underside_z"] = [[2500,2500,2500],[2500,2200,2500],[2500,2500,2500]]
        self.assertEqual(evaluate(reviewed(f))["status"], "FAIL")

    def test_reference_elevations_can_be_negative(self):
        f = fixture()
        f["surface"]["finished_floor_z"] = [[-500,-500],[-500,-500]]
        f["surface"]["finished_underside_z"] = [[1786,1786],[1786,1786]]
        self.assertEqual(evaluate(reviewed(f))["status"], "PASS")

    def test_stale_review(self):
        f = reviewed(fixture())
        f["room_use"] = "kitchen"
        self.assertEqual(evaluate(f)["status"], "NOT CHECKABLE")

    def test_missing_and_invalid_evidence(self):
        for field,value in [("unit","m"),("full_domain_verified",False),("obstructions_resolved",False),("representation","samples"),("finished_floor_z",[[0]]),("length",4000),("x",[0,True]),("source_global_ids",[])]:
            f = fixture()
            f["surface"][field] = value
            with self.subTest(field=field):
                self.assertEqual(evaluate(reviewed(f))["status"], "NOT CHECKABLE")

    def test_unreviewed_or_wrong_semantics(self):
        self.assertEqual(evaluate(fixture())["status"], "NOT CHECKABLE")
        for key,val in [("measurement_basis","storey_elevation_difference"),("ceiling_form","sloped_and_furred"),("room_use","mezzanine"),("unresolved_exceptions",["beam"]),("target_global_id","bad")]:
            f = fixture()
            f[key] = val
            self.assertEqual(evaluate(reviewed(f))["status"], "NOT CHECKABLE")

    def test_affine_triangle_clipping_area(self):
        triangle = [(Fraction(0),Fraction(0),Fraction(0)),(Fraction(2),Fraction(0),Fraction(2)),(Fraction(0),Fraction(2),Fraction(2))]
        self.assertEqual(area_at_least(triangle,Fraction(1)),Fraction(3,2))

    def test_invalid_top_level(self):
        for item in [None,[],{}, {"is_synthetic": True, "code_basis": "IRC2021"}]:
            self.assertEqual(evaluate(item)["status"], "NOT CHECKABLE")


if __name__ == "__main__":
    unittest.main()

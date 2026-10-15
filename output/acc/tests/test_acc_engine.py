"""Behavioral tests of quantity boundaries and conservative state handling."""
import copy
import json
import sys
import unittest
from pathlib import Path

ACC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ACC / "src"))
from acc_engine import evaluate, parking_minimum

CATALOG = json.loads((ACC / "mvp_rule_catalog.json").read_text(encoding="utf-8"))
RULES = {r["rule_id"]: r for r in CATALOG["rules"]}
TABLE = CATALOG["parking_table"]


def facts(rule_id, **extra):
    rule = RULES[rule_id]
    return {
        "model_evidence": "SYNTHETIC TEST ONLY", "applicable": True,
        "applicability_evidence": "SYNTHETIC TEST ONLY", "inventory_complete": True,
        "scope_id": "SYNTHETIC TEST SCOPE", "inventory_kind": rule["inventory_kind"],
        "accessible_design_verified": True, "accessible_design_evidence": "SYNTHETIC TEST ONLY",
        "scope_review": {"resolution": "APPROVED", "reviewer": "synthetic-test-reviewer",
                         "rationale": "Synthetic test approval only", "source_sha256": rule["evidence"]["sha256"],
                         "definition_sha256": rule["definition_sha256"]}, **extra,
    }


class CandidateEngineRegression(unittest.TestCase):
    def test_parking_boundaries_and_round_up(self):
        cases = {0: 0, 1: 1, 25: 1, 26: 2, 50: 2, 51: 3, 500: 9, 501: 11, 550: 11, 551: 12, 1000: 20, 1001: 21, 1100: 21, 1101: 22}
        for total, minimum in cases.items():
            with self.subTest(total=total):
                self.assertEqual(parking_minimum(total, TABLE), minimum)

    def test_count_pass_and_fail(self):
        for actual, expected in [(1, "FAIL"), (2, "PASS")]:
            result = evaluate(RULES["parking-minimum"], facts("parking-minimum", total=26, accessible=actual), TABLE)
            self.assertEqual(result["status"], expected)
            self.assertEqual(result["result_scope"], "COUNT_ONLY")
            self.assertFalse(result["full_clause_compliance_evaluated"])

    def test_van_ceiling(self):
        for total, minimum in [(1, 1), (6, 1), (7, 2), (12, 2), (13, 3)]:
            result = evaluate(RULES["van-parking-minimum"], facts("van-parking-minimum", total=total, accessible=minimum), TABLE)
            self.assertEqual(result["minimum"], minimum)

    def test_missing_data_unknown(self):
        original = facts("parking-minimum", total=26, accessible=2)
        for field in ["total", "accessible", "model_evidence", "inventory_complete", "inventory_kind", "scope_id", "applicable", "applicability_evidence", "accessible_design_evidence"]:
            value = copy.deepcopy(original)
            value.pop(field)
            with self.subTest(field=field):
                self.assertEqual(evaluate(RULES["parking-minimum"], value, TABLE)["status"], "UNKNOWN")

    def test_stale_or_absent_review_is_manual(self):
        value = facts("parking-minimum", total=26, accessible=2)
        value["scope_review"]["definition_sha256"] = "stale"
        self.assertEqual(evaluate(RULES["parking-minimum"], value, TABLE)["status"], "MANUAL_REVIEW")

    def test_unreviewed_exemption_does_not_become_not_applicable(self):
        value = facts("parking-minimum", applicable=False)
        value.pop("scope_review")
        self.assertEqual(evaluate(RULES["parking-minimum"], value, TABLE)["status"], "MANUAL_REVIEW")
        self.assertEqual(evaluate(RULES["parking-minimum"], facts("parking-minimum", applicable=False), TABLE)["status"], "NOT_APPLICABLE")

    def test_declared_accessibility_is_insufficient(self):
        value = facts("parking-minimum", total=26, accessible=2, accessible_design_verified=False)
        self.assertEqual(evaluate(RULES["parking-minimum"], value, TABLE)["status"], "UNKNOWN")

    def test_boolean_and_fractional_counts_rejected(self):
        for total in [True, -1, 1.5]:
            self.assertEqual(evaluate(RULES["parking-minimum"], facts("parking-minimum", total=total, accessible=0), TABLE)["status"], "UNKNOWN")

    def test_type_a_scope_threshold(self):
        rule = RULES["type-a-unit-minimum"]
        self.assertEqual(evaluate(rule, facts(rule["rule_id"], total=20, accessible=0), TABLE)["status"], "NOT_APPLICABLE")
        self.assertEqual(evaluate(rule, facts(rule["rule_id"], total=51, accessible=1), TABLE)["status"], "FAIL")

    def test_public_entrance_count_rounds_up(self):
        rule = RULES["public-entrance-minimum"]
        result = evaluate(rule, facts(rule["rule_id"], total=4, accessible=2), TABLE)
        self.assertEqual(result["minimum"], 3)
        self.assertEqual(result["status"], "FAIL")

    def test_topology_unknown_edges_and_directed_paths(self):
        rule = RULES["site-route-connectivity"]
        value = facts(rule["rule_id"], nodes=["a", "b"], targets=["a", "b"], edges=[])
        self.assertEqual(evaluate(rule, value, TABLE)["status"], "FAIL")
        value["edges"] = [{"from": "a", "to": "b", "accessible_verified": None, "bidirectional": True}]
        self.assertEqual(evaluate(rule, value, TABLE)["status"], "UNKNOWN")
        value["edges"][0].update(accessible_verified=True, evidence="SYNTHETIC TEST ONLY", bidirectional=False)
        self.assertEqual(evaluate(rule, value, TABLE)["status"], "FAIL")
        value["edges"][0]["bidirectional"] = True
        self.assertEqual(evaluate(rule, value, TABLE)["status"], "PASS")


if __name__ == "__main__":
    unittest.main()

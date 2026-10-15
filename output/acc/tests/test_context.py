"""Test missing intermediate references and flattened source ancestry."""
import json
import sys
import unittest
from pathlib import Path

ACC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ACC / "src"))
CONTEXT = json.loads((ACC / "rule_review_context.json").read_text(encoding="utf-8"))


class RuleContextRegression(unittest.TestCase):
    def test_reference_range_includes_intermediate_sections(self):
        identifiers = CONTEXT["contexts"]["ibc2021-1105.1"]["expanded_range_node_ids"]
        self.assertEqual(identifiers, [f"ibc2021-1105.1.{x}" for x in range(2, 9)])

    def test_numbered_ancestors_restore_review_context(self):
        ancestors = CONTEXT["contexts"]["ibc2021-1108.6.2.2.1"]["structural_and_numbered_ancestor_ids"]
        self.assertIn("ibc2021-1108.6.2.2", ancestors)
        self.assertIn("ibc2021-1108.6.2", ancestors)

    def test_exceptions_and_reductions_retained_without_deciding_scope(self):
        context = CONTEXT["contexts"]["ibc2021-1108.6.2.2.1"]
        self.assertIn("ibc2021-1108.7.1", context["referenced_subsection_ids"])
        self.assertFalse(context["applicability_decided"])
        self.assertTrue(all(n in CONTEXT["evidence_nodes"] for n in context["evidence_node_ids"]))


if __name__ == "__main__":
    unittest.main()

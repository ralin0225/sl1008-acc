"""Conservative candidate subcheck evaluator for reviewed normalized facts.

No IFC facts are inferred here. Every legal applicability decision is supplied
with an explicit review record. Output is limited to COUNT/CONNECTIVITY subchecks.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import deque
from pathlib import Path

ACC = Path(__file__).resolve().parents[1]


def integer(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def ceiling_ratio(total, numerator, denominator):
    return (total * numerator + denominator - 1) // denominator


def parking_minimum(total, table):
    if not integer(total):
        raise ValueError("total must be a nonnegative integer")
    if total == 0:
        return 0
    for label, minimum in table["cells"][1:]:
        text = label.replace(",", "").strip()
        match = re.fullmatch(r"(\d+) to (\d+)", text)
        if match and int(match[1]) <= total <= int(match[2]):
            if re.fullmatch(r"\d+", minimum.strip()):
                return int(minimum)
            ratio = re.fullmatch(r"(\d+)% of total", minimum.strip())
            if ratio:
                return ceiling_ratio(total, int(ratio[1]), 100)
        match = re.fullmatch(r"(\d+) and over", text)
        if match and total >= int(match[1]):
            # Assert the source cell before applying its explicitly described formula.
            normalized = " ".join(minimum.replace(",", "").split())
            parsed = re.fullmatch(r"(\d+),? plus one for each (\d+),? or fraction thereof,? over (\d+)", normalized)
            if not parsed:
                raise ValueError("Unrecognized final parking table formula")
            return int(parsed[1]) + ceiling_ratio(total - int(parsed[3]), 1, int(parsed[2]))
    raise ValueError("No parking table band matched")


def graph_connectivity(facts):
    nodes, targets, edges = facts["nodes"], facts["targets"], facts["edges"]
    if not isinstance(nodes, list) or not isinstance(targets, list) or not isinstance(edges, list):
        return "UNKNOWN", {"reason": "graph fields must be lists"}
    if any(not isinstance(v, str) or not v for v in nodes + targets) or len(nodes) != len(set(nodes)):
        return "UNKNOWN", {"reason": "invalid graph identifiers"}
    if len(targets) < 2 or not set(targets).issubset(nodes):
        return "UNKNOWN", {"reason": "at least two explicit graph targets required"}
    adjacency = {node: set() for node in nodes}
    uncertain = False
    for edge in edges:
        if not isinstance(edge, dict) or edge.get("from") not in adjacency or edge.get("to") not in adjacency:
            return "UNKNOWN", {"reason": "invalid edge endpoint"}
        verified = edge.get("accessible_verified")
        if not isinstance(edge.get("bidirectional"), bool):
            return "UNKNOWN", {"reason": "edge directionality missing"}
        if verified is True and edge.get("evidence"):
            adjacency[edge["from"]].add(edge["to"])
            if edge.get("bidirectional") is True:
                adjacency[edge["to"]].add(edge["from"])
        elif verified is not False or not edge.get("evidence"):
            uncertain = True
    # Pairwise reachability: one-way routes cannot pass merely from one start node.
    missing = []
    for start in targets:
        seen, pending = {start}, deque([start])
        while pending:
            for neighbor in adjacency[pending.popleft()] - seen:
                seen.add(neighbor)
                pending.append(neighbor)
        missing += [{"from": start, "to": end} for end in targets if end not in seen]
    if not missing:
        return "PASS", {"connected_targets": targets}
    return ("UNKNOWN" if uncertain else "FAIL"), {"unreachable_pairs": missing, "uncertain_edges": uncertain}


def evaluate(rule, facts, table):
    base = {"rule_id": rule["rule_id"], "source_node_id": rule["source_node_id"],
            "source_sha256": rule["evidence"]["sha256"], "result_scope": rule["result_scope"],
            "full_clause_compliance_evaluated": False, "status": "UNKNOWN"}

    def outcome(status, reason, **details):
        return {**base, "status": status, "reason": reason, **details}

    if rule["kind"] == "information":
        return outcome("UNKNOWN", "Use IFC precheck for project information requirements")
    if not isinstance(facts, dict) or not facts.get("model_evidence"):
        return outcome("UNKNOWN", "No model facts with evidence supplied")
    applicable = facts.get("applicable")
    if applicable is not True and applicable is not False:
        return outcome("UNKNOWN", "Applicability not established")
    if not facts.get("applicability_evidence"):
        return outcome("UNKNOWN", "Applicability evidence missing")
    if applicable is True:
        if not facts.get("scope_id") or facts.get("inventory_kind") != rule["inventory_kind"]:
            return outcome("UNKNOWN", "Inventory kind or facility/site/tenant scope not established")
        if facts.get("inventory_complete") is not True:
            return outcome("UNKNOWN", "Model inventory completeness not confirmed")
        if any(field not in facts or facts[field] is None for field in rule["required_fields"]):
            return outcome("UNKNOWN", "Required input field missing")
        if rule["kind"] == "count":
            if any(not integer(facts[field]) for field in rule["required_fields"]):
                return outcome("UNKNOWN", "Counts must be nonnegative integers")
            if facts.get("total") is not None and facts["accessible"] > facts["total"]:
                return outcome("UNKNOWN", "Accessible count exceeds scoped total")
            if facts.get("accessible_design_verified") is not True or not facts.get("accessible_design_evidence"):
                return outcome("UNKNOWN", "Accessible or unit-type designation needs independent evidence")
    review = facts.get("scope_review", {})
    if (not isinstance(review, dict) or review.get("resolution") != "APPROVED"
            or review.get("source_sha256") != rule["evidence"]["sha256"]
            or review.get("definition_sha256") != rule["definition_sha256"]
            or not review.get("reviewer") or not review.get("rationale")):
        return outcome("MANUAL_REVIEW", "Applicability, exceptions and subcheck scope require evidence-bound review")
    if applicable is False:
        return outcome("NOT_APPLICABLE", "Reviewed applicability evidence excludes this subcheck")
    if rule["kind"] == "topology":
        status, details = graph_connectivity(facts)
        return outcome(status, details.pop("reason", "Connectivity in the supplied reviewed graph"), **details)
    total, accessible = facts.get("total"), facts["accessible"]
    expr = rule["expression"]
    if expr == "table_1106_2":
        try:
            minimum = parking_minimum(total, table)
        except (KeyError, TypeError, ValueError) as exc:
            return outcome("MANUAL_REVIEW", f"Parking table cannot be evaluated: {exc}")
    elif expr == "ceil_total_div_6":
        minimum = ceiling_ratio(total, 1, 6)
    elif expr == "ceil_total_times_60_percent":
        minimum = ceiling_ratio(total, 60, 100)
    elif expr == "at_least_one":
        minimum = 1
    elif expr == "ceil_total_times_2_percent_over_20":
        if total <= 20:
            return outcome("NOT_APPLICABLE", "Reviewed scope contains no more than 20 units; this threshold does not apply")
        minimum = max(1, ceiling_ratio(total, 2, 100))
    else:
        return outcome("MANUAL_REVIEW", "Expression unsupported")
    return outcome("PASS" if accessible >= minimum else "FAIL", "Compared verified count against minimum for the reviewed scope", actual=accessible, minimum=minimum)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("facts", type=Path, help="Reviewed normalized facts JSON, not IFC")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    catalog = json.loads((ACC / "mvp_rule_catalog.json").read_text(encoding="utf-8"))
    inputs = json.loads(args.facts.read_text(encoding="utf-8"))
    results = [evaluate(rule, inputs.get("facts_by_rule", {}).get(rule["rule_id"]), catalog["parking_table"]) for rule in catalog["rules"]]
    report = {"schema_version": "0.1.0", "is_synthetic": inputs.get("is_synthetic", False),
              "input_sha256": hashlib.sha256(args.facts.read_bytes()).hexdigest(),
              "full_clause_compliance_evaluated": False, "results": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()

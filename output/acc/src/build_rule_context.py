"""Build deterministic review context; links do not decide legal applicability."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ACC = ROOT / "output/acc"
SOURCE = ROOT / "output/ibe_accessibility_structure"


def build(document, candidates):
    nodes = document["nodes"]
    by_node = {c["source_node_id"]: c for c in candidates}
    evidence = {}
    for identifier, node in nodes.items():
        if identifier in by_node:
            e = by_node[identifier]["evidence"]
            text, fragments, digest = e["text"], e["source_fragments"], e["sha256"]
        else:
            text, fragments = node["text_normalized"], node["source_fragments"]
            digest = hashlib.sha256(text.encode()).hexdigest()
        evidence[identifier] = {"source_node_id": identifier, "text": text, "source_fragments": fragments, "sha256": digest}
    contexts = {}
    globals_ = [x for x in nodes if x == "ibc2021-1102.1" or x == "ibc2021-1103.1" or x.startswith("ibc2021-1103.2")]
    for source, candidate in by_node.items():
        ancestors = set()
        parent = nodes[source]["parent_id"]
        while parent:
            if parent in ancestors:
                raise ValueError("Cycle in source structural hierarchy")
            ancestors.add(parent)
            parent = nodes[parent]["parent_id"]
        # The extracted navigation tree is flatter than section numbering in places.
        # Dotted prefixes supply review context without rewriting that source tree.
        if re.fullmatch(r"ibc2021-\d{4}(?:\.\d+)*", source):
            pieces = source.removeprefix("ibc2021-").split(".")
            for length in range(1, len(pieces)):
                inferred = "ibc2021-" + ".".join(pieces[:length])
                if inferred in nodes:
                    ancestors.add(inferred)
        references, expanded, unresolved, range_review = set(), set(), [], []
        for ref in candidate.get("cross_references", []):
            for target in ref.get("targets", []):
                identifier = target.get("target_node_id")
                if identifier in nodes:
                    references.add(identifier)
                else:
                    unresolved.append({"kind": ref.get("kind"), "identifier": target.get("identifier"), "expression": ref.get("expression")})
            for match in re.finditer(r"(\d{4}(?:\.\d+)*)\s+through\s+(\d{4}(?:\.\d+)*)", ref.get("expression", "")):
                start, end = match.groups()
                a, _, left = start.rpartition(".")
                b, _, right = end.rpartition(".")
                if a == b and a and 0 <= int(right) - int(left) <= 100:
                    for value in range(int(left), int(right) + 1):
                        identifier = f"ibc2021-{a}.{value}"
                        if identifier in nodes:
                            expanded.add(identifier)
                        else:
                            range_review.append({"range": match[0], "missing_node": identifier})
                else:
                    range_review.append({"range": match[0], "reason": "range spans different prefixes or is too broad"})
        exceptions = set(candidate.get("exception_node_ids", []))
        referenced_descendants = set()
        for identifier in references | expanded:
            referenced_descendants.update(x for x in nodes if x.startswith(identifier + "."))
            if identifier in by_node:
                exceptions.update(by_node[identifier].get("exception_node_ids", []))
        for identifier in ancestors | referenced_descendants | set(globals_):
            if identifier in by_node:
                exceptions.update(by_node[identifier].get("exception_node_ids", []))
        linked = sorted({source} | ancestors | references | expanded | exceptions | referenced_descendants | set(globals_))
        context = {"source_node_id": source, "structural_and_numbered_ancestor_ids": sorted(ancestors),
                   "exception_node_ids": sorted(exceptions), "reference_node_ids": sorted(references),
                   "expanded_range_node_ids": sorted(expanded), "referenced_subsection_ids": sorted(referenced_descendants),
                   "global_scope_review_ids": globals_, "unresolved_references": unresolved,
                   "range_review_items": range_review, "evidence_node_ids": linked,
                   "applicability_decided": False}
        context["sha256"] = hashlib.sha256(json.dumps({"context": context, "evidence_hashes": {x: evidence[x]["sha256"] for x in linked}}, sort_keys=True).encode()).hexdigest()
        contexts[source] = context
    return {"schema_version": "0.1.0", "method": "deterministic navigation and same-prefix range expansion; review assistance only",
            "source_pdf": "IBE2021_11Accessibility.pdf", "evidence_nodes": evidence, "contexts": contexts}


def main():
    document = json.loads((SOURCE / "03_structured_document.json").read_text(encoding="utf-8"))
    candidates = json.loads((SOURCE / "semantic_rdf/10_semantic_validated.json").read_text(encoding="utf-8"))["candidates"]
    output = build(document, candidates)
    (ACC / "rule_review_context.json").write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Created review context for {len(output['contexts'])} source clauses; no applicability decisions made")


if __name__ == "__main__":
    main()

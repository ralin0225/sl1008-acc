from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pyshacl import validate
from rdflib import BNode, Dataset, Graph, Literal, Namespace, RDF, RDFS, OWL, URIRef, XSD
from rdflib.namespace import PROV, SH
from owlrl import DeductiveClosure, OWLRL_Semantics


IBC = Namespace("https://example.org/ibc/2021/")
IBCO = Namespace("https://example.org/ibc/ontology/")
QUDT = Namespace("http://qudt.org/schema/qudt/")
UNIT = Namespace("http://qudt.org/vocab/unit/")
SCHEMA_VERSION = "1.0.0"

REFERENCE_RE = re.compile(r"\b(?:Sections?|Tables?|Chapter)\s+([0-9A-Z][0-9A-Z.\-]*(?:\s*(?:through|and|,|or)\s*[0-9A-Z.\-]+)*)", re.I)
NUMBER_UNIT_RE = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>square feet|square foot|sq\.\s*ft\.?|feet|foot|inches|inch|percent|%)\b",
    re.I,
)
FUZZY_TERMS = (
    "readily accessible", "adequate", "sufficient", "where practical", "where technically infeasible",
    "equivalent facilitation", "reasonable", "convenient", "accessible manner",
)
CONCEPT_PATTERNS = [
    ("AccessibleRoute", r"\baccessible routes?\b"),
    ("AccessibleEntrance", r"\baccessible entrances?\b"),
    ("ParkingSpace", r"\bparking spaces?\b"),
    ("PassengerLoadingZone", r"\bpassenger loading zones?\b"),
    ("DwellingUnit", r"\bdwelling units?\b"),
    ("SleepingUnit", r"\bsleeping units?\b"),
    ("TypeAUnit", r"\btype a units?\b"),
    ("TypeBUnit", r"\btype b units?\b"),
    ("AccessibleUnit", r"\baccessible units?\b"),
    ("ToiletRoom", r"\btoilet rooms?\b"),
    ("BathingRoom", r"\bbathing rooms?\b"),
    ("WheelchairSpace", r"\bwheelchair spaces?\b"),
    ("AssistiveListeningSystem", r"\bassistive listening systems?\b"),
    ("Signage", r"\bsigns?|signage\b"),
    ("BuildingOrFacility", r"\bbuildings?\b|\bfacilit(?:y|ies)\b"),
]
TOPOLOGY_TERMS = ("connect", "route", "adjacent", "entrance", "path", "serving", "located", "within", "between")
LOGIC_TERMS = ("where", "if ", "unless", "except", "provided", "only where", "other than")
NEGATIVE_TERMS = ("shall not", "not required", "prohibited", "shall be exempt", "need not")

UNIT_MAP = {
    "inches": "IN", "inch": "IN", "feet": "FT", "foot": "FT",
    "square feet": "FT2", "square foot": "FT2", "sq. ft.": "FT2",
    "percent": "PERCENT", "%": "PERCENT",
}


def dump(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return value or "unnamed"


def strip_prefix(text: str, label: str | None, heading: str | None) -> str:
    result = text.strip()
    if label and result.startswith(label):
        result = result[len(label):].lstrip(" .")
    if heading and result.casefold().startswith(heading.casefold()):
        result = result[len(heading):].lstrip(" .")
    return result


def map_concepts(text: str) -> list[str]:
    return [name for name, pattern in CONCEPT_PATTERNS if re.search(pattern, text, re.I)]


def modality(text: str) -> str:
    patterns = [
        ("shall_not", r"\bshall\s+not\b"), ("shall", r"\bshall\b"),
        ("must_not", r"\bmust\s+not\b"), ("must", r"\bmust\b"),
        ("not_required", r"\b(?:are|is|be)?\s*not\s+required\b|\bneed\s+not\b"),
        ("may", r"\b(?:may|permitted)\b"),
        ("required", r"\b(?:are|is|be)\s+required\b"),
    ]
    matches = []
    for name, pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            matches.append((match.start(), -(match.end() - match.start()), name))
    return min(matches)[2] if matches else "unspecified"


def statement_type(text: str, node_type: str, modal: str | None = None) -> str:
    lower = text.casefold()
    if node_type == "exception" or lower.startswith("exception:"):
        return "exception"
    modal = modal or modality(text)
    if modal in {"shall_not", "must_not"}:
        return "prohibition"
    if modal == "not_required":
        return "exemption"
    if modal in {"shall", "must", "required"}:
        return "obligation"
    if modal == "may":
        return "permission"
    if node_type in {"note", "heading"}:
        return "non_normative"
    return "declarative"


def split_atomic_rules(text: str, source_node_type: str) -> list[dict[str, Any]]:
    normalized = re.sub(r"\bExceptions?:\s*", "\nEXCEPTION_CONTEXT: ", text, flags=re.I)
    parts = re.split(r"(?<=[.;])\s+(?=(?:\d+(?:\.\d+)*\.\s+)?[A-Z])|\n", normalized)
    atomic = []
    exception_context = source_node_type == "exception"
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if part.startswith("EXCEPTION_CONTEXT:"):
            exception_context = True
            part = part[len("EXCEPTION_CONTEXT:"):].strip()
        if re.fullmatch(r"\d+(?:\.\d+)*\.", part):
            continue
        modal = modality(part)
        if modal == "unspecified" and not exception_context:
            continue
        subject, requirement = split_subject_requirement(part, modal)
        atomic.append({
            "atomic_index": len(atomic) + 1,
            "exception_context": exception_context,
            "statement_type": "exception" if exception_context else statement_type(part, source_node_type, modal),
            "modality": modal,
            "subject": subject,
            "requirement": requirement,
            "conditions": extract_conditions(part),
            "measurements": extract_measurements(part),
            "cross_references": extract_references(part),
            "text": part,
        })
    return atomic


def rule_type(text: str) -> list[str]:
    lower = text.casefold()
    result = []
    if NUMBER_UNIT_RE.search(text) or re.search(r"\b(?:minimum|maximum|not less than|not more than|at least)\b", lower):
        result.append("numerical")
    if any(t in lower for t in TOPOLOGY_TERMS):
        result.append("topological")
    if any(t in lower for t in LOGIC_TERMS):
        result.append("logical")
    if any(t in lower for t in FUZZY_TERMS):
        result.append("fuzzy")
    return result or ["categorical"]


def split_subject_requirement(text: str, modal: str) -> tuple[str | None, str]:
    patterns = {
        "shall": r"\bshall\b", "shall_not": r"\bshall\s+not\b", "must": r"\bmust\b",
        "must_not": r"\bmust\s+not\b", "not_required": r"\b(?:are|is|be)?\s*not\s+required\b",
        "required": r"\b(?:are|is|be)\s+required\b", "may": r"\b(?:may|permitted)\b",
    }
    pattern = patterns.get(modal)
    if not pattern:
        return None, text
    match = re.search(pattern, text, re.I)
    if not match:
        return None, text
    subject = text[:match.start()].strip(" ,;:")
    requirement = text[match.end():].strip(" ,;:")
    return subject or None, requirement or text


def extract_conditions(text: str) -> list[dict[str, str]]:
    conditions = []
    for marker in ("where", "if", "unless", "provided that", "other than"):
        for match in re.finditer(rf"\b{re.escape(marker)}\b", text, re.I):
            end = len(text)
            for separator in (";", "."):
                pos = text.find(separator, match.start())
                if pos >= 0:
                    end = min(end, pos + 1)
            conditions.append({"marker": marker, "text": text[match.start():end].strip()})
    return conditions


def extract_measurements(text: str) -> list[dict[str, Any]]:
    values = []
    for match in NUMBER_UNIT_RE.finditer(text):
        before = text[max(0, match.start() - 35):match.start()].casefold()
        if "not less than" in before or "minimum" in before or "at least" in before:
            operator = "greater_than_or_equal"
        elif "not more than" in before or "maximum" in before:
            operator = "less_than_or_equal"
        elif "less than" in before:
            operator = "less_than"
        elif "more than" in before:
            operator = "greater_than"
        else:
            operator = "equal_or_context_dependent"
        unit_raw = match.group("unit").casefold()
        values.append({
            "value": float(match.group("value")),
            "value_lexical": match.group("value"),
            "unit_text": match.group("unit"),
            "unit_code": UNIT_MAP.get(unit_raw),
            "operator": operator,
            "evidence": text[max(0, match.start() - 45):min(len(text), match.end() + 45)].strip(),
        })
    return values


def extract_references(text: str) -> list[dict[str, Any]]:
    refs = []
    for match in REFERENCE_RE.finditer(text):
        kind = match.group(0).split()[0].lower().rstrip("s")
        expression = match.group(1).strip()
        identifiers = re.findall(r"\b\d{4}(?:\.\d+)*(?:-[A-Z])?\b", expression)
        refs.append({"kind": kind, "expression": expression, "identifiers": identifiers})
    return refs


def semantic_candidate(node: dict[str, Any], child_nodes: list[dict[str, Any]]) -> dict[str, Any]:
    body = strip_prefix(node["text_normalized"], node.get("label"), node.get("heading"))
    modal = modality(body)
    subject, requirement = split_subject_requirement(body, modal)
    conditions = extract_conditions(body)
    measurements = extract_measurements(body)
    references = extract_references(body)
    exception_ids = [c["id"] for c in child_nodes if c["type"] == "exception"]
    atomic_rules = split_atomic_rules(body, node["type"])
    ontology_concepts = map_concepts(" ".join(filter(None, [node.get("heading"), subject, body[:500]])))
    issues = []
    confidence = 0.93
    if modal == "unspecified" and node["type"] in {"provision", "list_item", "exception"}:
        issues.append("no_explicit_modality")
        confidence -= 0.12
    if len(re.findall(r"\b(?:shall|must|required|permitted|may)\b", body, re.I)) > 2:
        issues.append("multiple_normative_clauses")
        confidence -= 0.12
    if len(body) > 850:
        issues.append("long_compound_text")
        confidence -= 0.08
    fuzzy = [term for term in FUZZY_TERMS if term in body.casefold()]
    if fuzzy:
        issues.append("fuzzy_terminology")
        confidence -= 0.08
    if conditions and len(conditions) > 2:
        issues.append("nested_or_multiple_conditions")
        confidence -= 0.08
    if node["type"] == "exception":
        confidence -= 0.03
    confidence = round(max(0.4, confidence), 2)
    return {
        "semantic_id": "sem-" + node["id"],
        "source_node_id": node["id"],
        "source_node_type": node["type"],
        "label": node.get("label"),
        "heading": node.get("heading"),
        "statement_type": statement_type(body, node["type"], modal),
        "rule_types": rule_type(body),
        "modality": modal,
        "subject": {"text": subject, "ontology_classes": ontology_concepts} if subject else None,
        "requirement": {"text": requirement, "ontology_property": None},
        "conditions": conditions,
        "exception_node_ids": exception_ids,
        "measurements": measurements,
        "cross_references": references,
        "fuzzy_terms": fuzzy,
        "atomic_rules": atomic_rules,
        "evidence": {
            "text": node["text_normalized"],
            "source_fragments": node["source_fragments"],
            "sha256": hashlib.sha256(node["text_normalized"].encode("utf-8")).hexdigest(),
        },
        "quality": {
            "confidence": confidence,
            "requires_review": confidence < 0.85 or bool(issues),
            "review_reasons": issues,
            "extraction_method": "deterministic_rules_v1",
            "review_status": "unreviewed" if confidence < 0.85 or issues else "rule_validated",
        },
    }


def build_semantics(structured: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    nodes = structured["nodes"]
    label_to_id = {n["label"]: n["id"] for n in nodes.values() if n.get("label")}
    candidates = []
    for node in sorted(nodes.values(), key=lambda n: n["order"]):
        if node["type"] not in {"provision", "list_item", "exception"}:
            continue
        children = [nodes[c] for c in node["child_ids"] if c in nodes]
        candidate = semantic_candidate(node, children)
        for ref in candidate["cross_references"]:
            ref["targets"] = [
                {"identifier": identifier, "resolved": identifier in label_to_id, "target_node_id": label_to_id.get(identifier)}
                for identifier in ref["identifiers"]
            ]
        candidates.append(candidate)
    review = [c for c in candidates if c["quality"]["requires_review"]]
    return ({
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "method": "ontology-ready deterministic candidates with provenance; AI review queue separated",
        "candidate_count": len(candidates),
        "candidates": candidates,
    }, {
        "schema_version": SCHEMA_VERSION,
        "review_item_count": len(review),
        "reason_counts": dict(Counter(r for c in review for r in c["quality"]["review_reasons"])),
        "items": review,
    })


def build_dsl(semantics: dict[str, Any]) -> dict[str, Any]:
    rules = []
    for candidate in semantics["candidates"]:
        for atomic in candidate["atomic_rules"]:
            rules.append({
                "dsl_rule_id": f"dsl-{candidate['source_node_id']}-{atomic['atomic_index']}",
                "source_node_id": candidate["source_node_id"],
                "statement_type": atomic["statement_type"],
                "modality": atomic["modality"],
                "if": atomic["conditions"],
                "then": {"subject": atomic["subject"], "requirement": atomic["requirement"]},
                "unless": [] if not atomic["exception_context"] else [{"exception_context": True}],
                "measurements": atomic["measurements"],
                "references": atomic["cross_references"],
                "evidence_text": atomic["text"],
                "execution_status": "intermediate_representation_only",
            })
    return {"schema_version": SCHEMA_VERSION, "rule_count": len(rules), "rules": rules}


def ontology_graph() -> Graph:
    g = Graph()
    g.bind("ibc", IBC); g.bind("ibco", IBCO); g.bind("prov", PROV); g.bind("qudt", QUDT); g.bind("unit", UNIT)
    g.add((IBCO.BuildingCodeEntity, RDF.type, OWL.Class))
    for cls, parent in {
        "Document": "BuildingCodeEntity", "Chapter": "BuildingCodeEntity", "Section": "BuildingCodeEntity",
        "Provision": "BuildingCodeEntity", "ListItem": "BuildingCodeEntity", "Exception": "BuildingCodeEntity",
        "Table": "BuildingCodeEntity", "Requirement": "BuildingCodeEntity", "Measurement": "BuildingCodeEntity",
        "Condition": "BuildingCodeEntity", "DomainConcept": "BuildingCodeEntity", "AtomicRule": "BuildingCodeEntity",
        "AccessibleRoute": "DomainConcept", "AccessibleEntrance": "DomainConcept", "ParkingSpace": "DomainConcept",
        "PassengerLoadingZone": "DomainConcept", "DwellingUnit": "DomainConcept", "SleepingUnit": "DomainConcept",
        "TypeAUnit": "DomainConcept", "TypeBUnit": "DomainConcept", "AccessibleUnit": "DomainConcept",
        "ToiletRoom": "DomainConcept", "BathingRoom": "DomainConcept", "WheelchairSpace": "DomainConcept",
        "AssistiveListeningSystem": "DomainConcept", "Signage": "DomainConcept", "BuildingOrFacility": "DomainConcept",
    }.items():
        g.add((IBCO[cls], RDF.type, OWL.Class)); g.add((IBCO[cls], RDFS.subClassOf, IBCO[parent]))
    for prop in ("partOf", "hasChild", "precedes", "references", "hasException", "sourceNode", "hasCondition", "hasMeasurement", "appliesTo", "hasAtomicRule"):
        g.add((IBCO[prop], RDF.type, OWL.ObjectProperty))
    for prop, dtype in {
        "label": XSD.string, "heading": XSD.string, "text": XSD.string, "modality": XSD.string,
        "statementType": XSD.string, "ruleType": XSD.string, "confidence": XSD.decimal,
        "sourcePage": XSD.integer, "bbox": XSD.string, "value": XSD.decimal, "operator": XSD.string,
        "unitCode": XSD.string, "reviewStatus": XSD.string,
    }.items():
        g.add((IBCO[prop], RDF.type, OWL.DatatypeProperty)); g.add((IBCO[prop], RDFS.range, dtype))
    return g


def shapes_graph() -> Graph:
    g = Graph()
    g.bind("sh", SH); g.bind("ibco", IBCO)
    shape = IBCO.RequirementShape
    g.add((shape, RDF.type, SH.NodeShape)); g.add((shape, SH.targetClass, IBCO.Requirement))
    for path, min_count, datatype_or_class in (
        (IBCO.sourceNode, 1, IBCO.BuildingCodeEntity),
        (IBCO.text, 1, XSD.string),
        (IBCO.modality, 1, XSD.string),
        (IBCO.statementType, 1, XSD.string),
        (IBCO.confidence, 1, XSD.decimal),
    ):
        p = BNode(); g.add((shape, SH.property, p)); g.add((p, SH.path, path)); g.add((p, SH.minCount, Literal(min_count)))
        if str(datatype_or_class).startswith(str(XSD)):
            g.add((p, SH.datatype, datatype_or_class))
        else:
            g.add((p, SH["class"], datatype_or_class))
    mshape = IBCO.MeasurementShape
    g.add((mshape, RDF.type, SH.NodeShape)); g.add((mshape, SH.targetClass, IBCO.Measurement))
    for path, dtype in ((IBCO.value, XSD.decimal), (IBCO.operator, XSD.string), (IBCO.unitCode, XSD.string)):
        p = BNode(); g.add((mshape, SH.property, p)); g.add((p, SH.path, path)); g.add((p, SH.minCount, Literal(1))); g.add((p, SH.datatype, dtype))
    ashape = IBCO.AtomicRuleShape
    g.add((ashape, RDF.type, SH.NodeShape)); g.add((ashape, SH.targetClass, IBCO.AtomicRule))
    for path in (IBCO.text, IBCO.modality, IBCO.statementType):
        p = BNode(); g.add((ashape, SH.property, p)); g.add((p, SH.path, path)); g.add((p, SH.minCount, Literal(1))); g.add((p, SH.datatype, XSD.string))
    return g


def node_class(node_type: str) -> URIRef:
    return {
        "chapter": IBCO.Chapter, "section": IBCO.Section, "provision": IBCO.Provision,
        "list_item": IBCO.ListItem, "exception": IBCO.Exception, "table": IBCO.Table,
    }.get(node_type, IBCO.BuildingCodeEntity)


def build_graphs(structured: dict[str, Any], semantics: dict[str, Any]) -> tuple[Graph, Graph, Dataset]:
    doc_g = Graph(identifier=IBC.documentGraph)
    ent_g = Graph(identifier=IBC.entityGraph)
    for g in (doc_g, ent_g):
        g.bind("ibc", IBC); g.bind("ibco", IBCO); g.bind("prov", PROV); g.bind("qudt", QUDT); g.bind("unit", UNIT)
    doc_uri = IBC[slug(structured["document"]["document_id"])]
    doc_g.add((doc_uri, RDF.type, IBCO.Document)); doc_g.add((doc_uri, RDFS.label, Literal(structured["document"]["title"])))
    ordered_nodes = sorted(structured["nodes"].values(), key=lambda n: n["order"])
    for i, node in enumerate(ordered_nodes):
        uri = IBC[node["id"]]
        doc_g.add((uri, RDF.type, node_class(node["type"])))
        doc_g.add((uri, IBCO.text, Literal(node["text_normalized"])))
        if node.get("label"): doc_g.add((uri, IBCO.label, Literal(node["label"])))
        if node.get("heading"): doc_g.add((uri, IBCO.heading, Literal(node["heading"])))
        if node.get("parent_id"):
            parent = IBC[node["parent_id"]]; doc_g.add((uri, IBCO.partOf, parent)); doc_g.add((parent, IBCO.hasChild, uri))
        else:
            doc_g.add((uri, IBCO.partOf, doc_uri))
        if i + 1 < len(ordered_nodes): doc_g.add((uri, IBCO.precedes, IBC[ordered_nodes[i + 1]["id"]]))
        for frag in node["source_fragments"]:
            doc_g.add((uri, IBCO.sourcePage, Literal(frag["source_pdf_page"], datatype=XSD.integer)))
            doc_g.add((uri, IBCO.bbox, Literal(json.dumps(frag["bbox"]))))
    for table_id, table in structured["tables"].items():
        uri = IBC[table_id]; doc_g.add((uri, RDF.type, IBCO.Table)); doc_g.add((uri, IBCO.sourcePage, Literal(table["source_pdf_page"], datatype=XSD.integer)))

    for candidate in semantics["candidates"]:
        req = IBC[candidate["semantic_id"]]; source = IBC[candidate["source_node_id"]]
        ent_g.add((req, RDF.type, IBCO.Requirement)); ent_g.add((req, IBCO.sourceNode, source)); ent_g.add((req, PROV.wasDerivedFrom, source))
        ent_g.add((req, IBCO.text, Literal(candidate["evidence"]["text"])))
        ent_g.add((req, IBCO.modality, Literal(candidate["modality"])))
        ent_g.add((req, IBCO.statementType, Literal(candidate["statement_type"])))
        ent_g.add((req, IBCO.confidence, Literal(str(candidate["quality"]["confidence"]), datatype=XSD.decimal)))
        ent_g.add((req, IBCO.reviewStatus, Literal(candidate["quality"]["review_status"])))
        for rt in candidate["rule_types"]: ent_g.add((req, IBCO.ruleType, Literal(rt)))
        if candidate["subject"] and candidate["subject"]["text"]:
            classes = candidate["subject"].get("ontology_classes", [])
            if classes:
                for cls in classes:
                    concept = IBC["concept-" + slug(cls)]
                    ent_g.add((concept, RDF.type, IBCO[cls])); ent_g.add((concept, RDFS.label, Literal(cls)))
                    ent_g.add((req, IBCO.appliesTo, concept))
            else:
                concept = IBC["concept-" + slug(candidate["subject"]["text"])]
                ent_g.add((concept, RDF.type, IBCO.DomainConcept)); ent_g.add((concept, RDFS.label, Literal(candidate["subject"]["text"])))
                ent_g.add((req, IBCO.appliesTo, concept))
        for cond_i, condition in enumerate(candidate["conditions"], 1):
            cond = IBC[f"{candidate['semantic_id']}-condition-{cond_i}"]
            ent_g.add((cond, RDF.type, IBCO.Condition)); ent_g.add((cond, IBCO.text, Literal(condition["text"]))); ent_g.add((req, IBCO.hasCondition, cond))
        for m_i, measurement in enumerate(candidate["measurements"], 1):
            m = IBC[f"{candidate['semantic_id']}-measurement-{m_i}"]
            ent_g.add((m, RDF.type, IBCO.Measurement)); ent_g.add((req, IBCO.hasMeasurement, m))
            ent_g.add((m, IBCO.value, Literal(str(measurement["value"]), datatype=XSD.decimal)))
            ent_g.add((m, IBCO.operator, Literal(measurement["operator"])))
            ent_g.add((m, IBCO.unitCode, Literal(measurement["unit_code"] or measurement["unit_text"])))
        for ref in candidate["cross_references"]:
            for identifier in ref["identifiers"]:
                ent_g.add((req, IBCO.references, IBC["ibc2021-" + slug(identifier)]))
        for exc_id in candidate["exception_node_ids"]: ent_g.add((req, IBCO.hasException, IBC[exc_id]))
        for atomic in candidate["atomic_rules"]:
            atom = IBC[f"{candidate['semantic_id']}-atomic-{atomic['atomic_index']}"]
            ent_g.add((atom, RDF.type, IBCO.AtomicRule)); ent_g.add((req, IBCO.hasAtomicRule, atom))
            ent_g.add((atom, IBCO.text, Literal(atomic["text"])))
            ent_g.add((atom, IBCO.modality, Literal(atomic["modality"])))
            ent_g.add((atom, IBCO.statementType, Literal(atomic["statement_type"])))

    dataset = Dataset()
    dataset.bind("ibc", IBC); dataset.bind("ibco", IBCO); dataset.bind("prov", PROV)
    for triple in doc_g: dataset.graph(IBC.documentGraph).add(triple)
    for triple in ent_g: dataset.graph(IBC.entityGraph).add(triple)
    return doc_g, ent_g, dataset


def fidelity_checks(structured: dict[str, Any], semantics: dict[str, Any], entity_graph: Graph) -> dict[str, Any]:
    nodes = structured["nodes"]
    issues = []
    for c in semantics["candidates"]:
        source = nodes.get(c["source_node_id"])
        if not source:
            issues.append({"semantic_id": c["semantic_id"], "issue": "missing_source_node"})
        elif source["text_normalized"] != c["evidence"]["text"]:
            issues.append({"semantic_id": c["semantic_id"], "issue": "evidence_text_mismatch"})
        for m in c["measurements"]:
            if m["value_lexical"] not in c["evidence"]["text"]:
                issues.append({"semantic_id": c["semantic_id"], "issue": "measurement_not_in_evidence", "value": m["value_lexical"]})
    requirement_count = len(set(entity_graph.subjects(RDF.type, IBCO.Requirement)))
    return {
        "status": "pass" if not issues else "fail",
        "semantic_candidate_count": len(semantics["candidates"]),
        "rdf_requirement_count": requirement_count,
        "candidate_rdf_count_match": requirement_count == len(semantics["candidates"]),
        "issue_count": len(issues),
        "issues": issues,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("structured_json", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    structured = json.loads(args.structured_json.read_text(encoding="utf-8"))

    semantics, review_queue = build_semantics(structured)
    dump(args.output_dir / "10_semantic_candidates.json", semantics)
    dump(args.output_dir / "10_semantic_validated.json", {
        **semantics,
        "validation_status": "evidence_aligned_with_manual_review_queue",
        "manual_review_queue_count": review_queue["review_item_count"],
    })
    dump(args.output_dir / "10_dsl_rules.json", build_dsl(semantics))
    dump(args.output_dir / "10_manual_review_queue.json", review_queue)

    ontology = ontology_graph(); shapes = shapes_graph()
    ontology.serialize(args.output_dir / "10_ibc_minimal_ontology.ttl", format="turtle")
    shapes.serialize(args.output_dir / "12_shapes.ttl", format="turtle")
    doc_g, ent_g, dataset = build_graphs(structured, semantics)
    doc_g.serialize(args.output_dir / "11_document_graph.ttl", format="turtle")
    ent_g.serialize(args.output_dir / "11_entity_graph.ttl", format="turtle")
    dataset.serialize(args.output_dir / "11_combined_graph.trig", format="trig")
    combined_jsonld = doc_g + ent_g
    combined_jsonld.serialize(args.output_dir / "11_combined_graph.jsonld", format="json-ld", indent=2)

    validation_graph = doc_g + ent_g
    conforms, results_graph, results_text = validate(
        data_graph=validation_graph, shacl_graph=shapes, ont_graph=ontology, inference="rdfs", advanced=True,
    )
    results_graph.serialize(args.output_dir / "12_shacl_results.ttl", format="turtle")
    fidelity = fidelity_checks(structured, semantics, ent_g)
    reasoning_graph = ontology + doc_g + ent_g
    reasoning_input_triples = len(reasoning_graph)
    DeductiveClosure(OWLRL_Semantics).expand(reasoning_graph)
    owl_nothing_instances = sorted(str(x) for x in reasoning_graph.subjects(RDF.type, OWL.Nothing))
    owl_report = {
        "profile": "OWL 2 RL",
        "input_triples": reasoning_input_triples,
        "inferred_graph_triples": len(reasoning_graph),
        "inferred_triples_added": len(reasoning_graph) - reasoning_input_triples,
        "owl_nothing_instance_count": len(owl_nothing_instances),
        "owl_nothing_instances": owl_nothing_instances,
        "status": "pass" if not owl_nothing_instances else "fail",
        "note": "This is an OWL-RL consistency sanity check, not full first-order legal rule verification."
    }
    dump(args.output_dir / "12_owl_reasoning_report.json", owl_report)
    resolved_refs = sum(1 for c in semantics["candidates"] for r in c["cross_references"] for t in r.get("targets", []) if t["resolved"])
    unresolved_refs = sum(1 for c in semantics["candidates"] for r in c["cross_references"] for t in r.get("targets", []) if not t["resolved"])
    validation_report = {
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "shacl": {"conforms": bool(conforms), "report_text": results_text},
        "fidelity": fidelity,
        "graph_statistics": {
            "document_graph_triples": len(doc_g), "entity_graph_triples": len(ent_g),
            "combined_triples": len(doc_g) + len(ent_g),
            "requirements": len(set(ent_g.subjects(RDF.type, IBCO.Requirement))),
            "measurements": len(set(ent_g.subjects(RDF.type, IBCO.Measurement))),
            "conditions": len(set(ent_g.subjects(RDF.type, IBCO.Condition))),
        },
        "manual_review_queue_count": review_queue["review_item_count"],
        "cross_reference_resolution": {"resolved": resolved_refs, "unresolved_or_external": unresolved_refs},
        "owl_rl": owl_report,
        "overall_status": "pass" if conforms and fidelity["status"] == "pass" and owl_report["status"] == "pass" else "fail",
    }
    dump(args.output_dir / "12_validation_report.json", validation_report)
    print(json.dumps({
        "semantic_candidates": semantics["candidate_count"],
        "manual_review_queue": review_queue["review_item_count"],
        "review_reasons": review_queue["reason_counts"],
        "document_graph_triples": len(doc_g), "entity_graph_triples": len(ent_g),
        "shacl_conforms": bool(conforms), "fidelity": fidelity["status"],
    }, indent=2))


if __name__ == "__main__":
    main()

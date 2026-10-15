from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pymupdf


SOURCE_PDF_START = 356
SCHEMA_VERSION = "1.0.0"


def json_dump(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def bbox_list(rect: Any) -> list[float]:
    return [round(float(v), 3) for v in rect]


def normalized_bbox(bbox: list[float], width: float, height: float) -> list[float]:
    x0, y0, x1, y1 = bbox
    return [round(x0 / width, 6), round(y0 / height, 6), round(x1 / width, 6), round(y1 / height, 6)]


def span_is_bold(span: dict[str, Any]) -> bool:
    return bool(span.get("flags", 0) & 16) or "bold" in span.get("font", "").lower()


def extract_raw(doc: pymupdf.Document, source: Path) -> dict[str, Any]:
    pages = []
    for page_index, page in enumerate(doc):
        raw = page.get_text("dict", sort=False)
        blocks = []
        for block_index, block in enumerate(raw.get("blocks", [])):
            entry: dict[str, Any] = {
                "id": f"p{page_index + 1:03d}-b{block_index + 1:03d}",
                "block_index": block_index,
                "type": block.get("type"),
                "bbox": bbox_list(block.get("bbox", (0, 0, 0, 0))),
            }
            entry["bbox_normalized"] = normalized_bbox(entry["bbox"], page.rect.width, page.rect.height)
            if block.get("type") == 0:
                lines = []
                for line_index, line in enumerate(block.get("lines", [])):
                    spans = []
                    for span_index, span in enumerate(line.get("spans", [])):
                        spans.append({
                            "id": f"{entry['id']}-l{line_index + 1:03d}-s{span_index + 1:03d}",
                            "text": span.get("text", ""),
                            "bbox": bbox_list(span.get("bbox", (0, 0, 0, 0))),
                            "origin": bbox_list((*span.get("origin", (0, 0)), *span.get("origin", (0, 0)))),
                            "font": span.get("font"),
                            "size": round(float(span.get("size", 0)), 3),
                            "flags": span.get("flags"),
                            "color": span.get("color"),
                            "bold": span_is_bold(span),
                        })
                    line_text = norm("".join(s["text"] for s in spans))
                    line_bbox = bbox_list(line.get("bbox", (0, 0, 0, 0)))
                    lines.append({
                        "id": f"{entry['id']}-l{line_index + 1:03d}",
                        "line_index": line_index,
                        "text": line_text,
                        "bbox": line_bbox,
                        "bbox_normalized": normalized_bbox(line_bbox, page.rect.width, page.rect.height),
                        "direction": [round(float(v), 5) for v in line.get("dir", (1, 0))],
                        "spans": spans,
                    })
                entry["lines"] = lines
                entry["text"] = norm(" ".join(line["text"] for line in lines))
            elif block.get("type") == 1:
                entry.update({
                    "width": block.get("width"),
                    "height": block.get("height"),
                    "extension": block.get("ext"),
                    "image_byte_count": len(block.get("image", b"")),
                })
            blocks.append(entry)

        drawings = []
        for drawing_index, drawing in enumerate(page.get_drawings()):
            drawings.append({
                "id": f"p{page_index + 1:03d}-d{drawing_index + 1:03d}",
                "bbox": bbox_list(drawing.get("rect", (0, 0, 0, 0))),
                "type": drawing.get("type"),
                "fill": drawing.get("fill"),
                "color": drawing.get("color"),
                "width": drawing.get("width"),
                "item_count": len(drawing.get("items", [])),
            })

        pages.append({
            "page_id": f"p{page_index + 1:03d}",
            "pdf_page_index": page_index,
            "pdf_page_number": page_index + 1,
            "source_pdf_page": SOURCE_PDF_START + page_index,
            "width": round(page.rect.width, 3),
            "height": round(page.rect.height, 3),
            "rotation": page.rotation,
            "blocks": blocks,
            "drawings": drawings,
        })

    return {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "file_name": source.name,
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "page_count": doc.page_count,
            "source_pdf_page_from": SOURCE_PDF_START,
            "source_pdf_page_to": SOURCE_PDF_START + doc.page_count - 1,
            "engine": "PyMuPDF",
            "engine_version": pymupdf.__version__,
        },
        "pages": pages,
    }


def line_records(raw: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    for page in raw["pages"]:
        for block in page["blocks"]:
            for line in block.get("lines", []):
                if not line["text"]:
                    continue
                sizes = [s["size"] for s in line["spans"] if s["text"].strip()]
                records.append({
                    "id": line["id"],
                    "block_id": block["id"],
                    "page_id": page["page_id"],
                    "pdf_page_index": page["pdf_page_index"],
                    "pdf_page_number": page["pdf_page_number"],
                    "source_pdf_page": page["source_pdf_page"],
                    "page_width": page["width"],
                    "page_height": page["height"],
                    "text": line["text"],
                    "bbox": line["bbox"],
                    "bbox_normalized": line["bbox_normalized"],
                    "font_size_max": max(sizes, default=0),
                    "font_size_median": sorted(sizes)[len(sizes) // 2] if sizes else 0,
                    "bold": any(s["bold"] for s in line["spans"] if s["text"].strip()),
                    "first_span_bold": next((s["bold"] for s in line["spans"] if s["text"].strip()), False),
                    "fonts": sorted({s["font"] for s in line["spans"] if s["text"].strip()}),
                })
    return records


def classify_layout(raw: dict[str, Any]) -> dict[str, Any]:
    records = line_records(raw)
    repeated = Counter()
    for r in records:
        y0, y1 = r["bbox_normalized"][1], r["bbox_normalized"][3]
        if y1 < 0.10 or y0 > 0.90:
            repeated[norm(r["text"]).casefold()] += 1

    page_results = []
    for page in raw["pages"]:
        page_lines = [r.copy() for r in records if r["page_id"] == page["page_id"]]
        body_lines = []
        for r in page_lines:
            x0, y0, x1, y1 = r["bbox_normalized"]
            key = norm(r["text"]).casefold()
            if y1 < 0.075:
                role = "running_header" if repeated[key] > 1 else "top_matter"
            elif y0 > 0.925:
                role = "page_number" if re.fullmatch(r"\d{1,2}-\d{1,2}", r["text"]) else "running_footer"
            elif repeated[key] >= 3 and (y1 < 0.12 or y0 > 0.88):
                role = "running_header_or_footer"
            else:
                role = "content"
                body_lines.append(r)
            r["region_role"] = role
            r["excluded_from_reading_order"] = role != "content"

        left = sum(1 for r in body_lines if (r["bbox_normalized"][0] + r["bbox_normalized"][2]) / 2 < 0.48 and r["bbox_normalized"][2] < 0.58)
        right = sum(1 for r in body_lines if (r["bbox_normalized"][0] + r["bbox_normalized"][2]) / 2 > 0.52 and r["bbox_normalized"][0] > 0.42)
        spanning = sum(1 for r in body_lines if r["bbox_normalized"][0] < 0.18 and r["bbox_normalized"][2] > 0.82)
        layout = "double_column" if left >= 3 and right >= 3 else "single_column"
        if layout == "double_column" and spanning >= 2:
            layout = "mixed"

        for r in page_lines:
            x0, _, x1, _ = r["bbox_normalized"]
            if r["region_role"] != "content":
                column = "excluded"
            elif page["pdf_page_number"] == 1 and r["bbox_normalized"][1] < 0.38:
                # Chapter title and introductory user note form a single-column band.
                column = "spanning"
            elif x0 < 0.40 and x1 > 0.60:
                column = "spanning"
            elif (x0 + x1) / 2 < 0.5:
                column = "left"
            else:
                column = "right"
            r["column"] = column

        content = [r for r in page_lines if r["region_role"] == "content"]
        bands: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for r in content:
            bands[int(r["bbox"][1] // 12)].append(r)
        ordered = []
        used: set[str] = set()
        for r in sorted([x for x in content if x["column"] == "spanning"], key=lambda x: (x["bbox"][1], x["bbox"][0])):
            preceding = [x for x in content if x["id"] not in used and x["bbox"][1] < r["bbox"][1] and x["column"] != "spanning"]
            for col in ("left", "right"):
                for x in sorted([z for z in preceding if z["column"] == col], key=lambda z: (z["bbox"][1], z["bbox"][0])):
                    ordered.append(x); used.add(x["id"])
            ordered.append(r); used.add(r["id"])
        for col in ("left", "right"):
            for x in sorted([z for z in content if z["id"] not in used and z["column"] == col], key=lambda z: (z["bbox"][1], z["bbox"][0])):
                ordered.append(x); used.add(x["id"])
        for x in sorted([z for z in content if z["id"] not in used], key=lambda z: (z["bbox"][1], z["bbox"][0])):
            ordered.append(x); used.add(x["id"])

        page_results.append({
            "page_id": page["page_id"],
            "pdf_page_number": page["pdf_page_number"],
            "source_pdf_page": page["source_pdf_page"],
            "layout": layout,
            "layout_evidence": {"left_lines": left, "right_lines": right, "spanning_lines": spanning},
            "lines": page_lines,
            "reading_order_line_ids": [r["id"] for r in ordered],
        })

    return {
        "schema_version": SCHEMA_VERSION,
        "method": "deterministic coordinate, repetition, font and regex rules",
        "repeated_margin_text": [{"text_normalized": k, "count": v} for k, v in repeated.most_common() if v > 1],
        "pages": page_results,
    }


SECTION_RE = re.compile(r"^SECTION\s+(\d{4}[A-Z]?)$", re.I)
PROVISION_RE = re.compile(r"^(\d{4}(?:\.\d+)+)\s*(.*)$")
LIST_RE = re.compile(r"^(\d+\.|[a-z]\.|\([a-z0-9]+\))\s+(.*)$", re.I)


def classify_line_role(line: dict[str, Any]) -> str:
    text = line["text"]
    if re.fullmatch(r"CHAPTER\s+\d+", text, re.I):
        return "chapter_label"
    if SECTION_RE.fullmatch(text):
        return "section_label"
    if PROVISION_RE.match(text) and line.get("first_span_bold"):
        return "provision_start"
    if text.casefold().startswith("exception:"):
        return "exception"
    if text.casefold().startswith(("user note:", "note:")):
        return "note"
    if LIST_RE.match(text):
        return "list_item"
    if line["bold"] and text.isupper() and len(text) < 100:
        return "heading"
    if line["bold"] and len(text) < 90:
        return "candidate_heading"
    return "body"


def extract_tables(doc: pymupdf.Document) -> tuple[list[dict[str, Any]], list[str]]:
    tables = []
    warnings = []
    for page_index, page in enumerate(doc):
        try:
            finder = page.find_tables()
            for table_index, table in enumerate(finder.tables):
                extracted = table.extract()
                tables.append({
                    "id": f"table-p{page_index + 1:03d}-{table_index + 1:02d}",
                    "pdf_page_number": page_index + 1,
                    "source_pdf_page": SOURCE_PDF_START + page_index,
                    "bbox": bbox_list(table.bbox),
                    "row_count": table.row_count,
                    "column_count": table.col_count,
                    "header_names": list(table.header.names) if table.header else [],
                    "header_external": bool(table.header.external) if table.header else False,
                    "cells": extracted,
                })
        except Exception as exc:
            warnings.append(f"Page {page_index + 1}: table detection failed: {exc}")
    return tables, warnings


def build_structure(raw: dict[str, Any], layout: dict[str, Any], tables: list[dict[str, Any]]) -> dict[str, Any]:
    line_lookup = {line["id"]: line for page in layout["pages"] for line in page["lines"]}
    nodes: dict[str, dict[str, Any]] = {}
    root_ids = []
    current_section: str | None = None
    current_chapter: str | None = None
    current_provision: str | None = None
    pending_section_label: tuple[str, dict[str, Any]] | None = None
    seq = 0
    table_line_ids: set[str] = set()
    for table in tables:
        tx0, ty0, tx1, ty1 = table["bbox"]
        for page in layout["pages"]:
            if page["pdf_page_number"] != table["pdf_page_number"]:
                continue
            for line in page["lines"]:
                x0, y0, x1, y1 = line["bbox"]
                cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                if tx0 <= cx <= tx1 and ty0 <= cy <= ty1:
                    table_line_ids.add(line["id"])
                    table.setdefault("source_line_ids", []).append(line["id"])

    def add_node(node_type: str, label: str | None, text: str, line: dict[str, Any], parent: str | None) -> str:
        nonlocal seq
        seq += 1
        base = label or f"n{seq:04d}"
        node_id = "ibc2021-" + re.sub(r"[^a-zA-Z0-9.-]+", "-", base).strip("-").lower()
        if node_id in nodes:
            node_id += f"-{seq:04d}"
        nodes[node_id] = {
            "id": node_id,
            "type": node_type,
            "label": label,
            "heading": None,
            "parent_id": parent,
            "child_ids": [],
            "order": seq,
            "text_verbatim": text,
            "text_normalized": norm(text.replace("\u00ad", "")),
            "source_fragments": [{
                "pdf_page_number": line["pdf_page_number"],
                "source_pdf_page": line["source_pdf_page"],
                "column": line["column"],
                "bbox": line["bbox"],
                "line_ids": [line["id"]],
                "block_ids": [line["block_id"]],
            }],
            "quality": {"layout_confidence": 0.9, "structure_confidence": 0.9, "requires_review": False, "issues": []},
        }
        if parent and parent in nodes:
            nodes[parent]["child_ids"].append(node_id)
        else:
            root_ids.append(node_id)
        return node_id

    def append_line(node_id: str, line: dict[str, Any]) -> None:
        node = nodes[node_id]
        text = line["text"]
        previous = node["text_verbatim"]
        joiner = " "
        if previous.endswith("-") and text and text[0].islower():
            node["text_verbatim"] = previous[:-1] + text
        else:
            node["text_verbatim"] = previous + joiner + text
        node["text_normalized"] = norm(node["text_verbatim"].replace("\u00ad", ""))
        frag = node["source_fragments"][-1]
        if frag["pdf_page_number"] == line["pdf_page_number"] and frag["column"] == line["column"]:
            frag["line_ids"].append(line["id"])
            if line["block_id"] not in frag["block_ids"]:
                frag["block_ids"].append(line["block_id"])
            frag["bbox"] = [
                min(frag["bbox"][0], line["bbox"][0]), min(frag["bbox"][1], line["bbox"][1]),
                max(frag["bbox"][2], line["bbox"][2]), max(frag["bbox"][3], line["bbox"][3]),
            ]
        else:
            node["source_fragments"].append({
                "pdf_page_number": line["pdf_page_number"], "source_pdf_page": line["source_pdf_page"],
                "column": line["column"], "bbox": line["bbox"], "line_ids": [line["id"]],
                "block_ids": [line["block_id"]],
            })

    for page in layout["pages"]:
        for line_id in page["reading_order_line_ids"]:
            line = line_lookup[line_id]
            if line_id in table_line_ids:
                continue
            role = classify_line_role(line)
            if role == "chapter_label":
                current_chapter = add_node("chapter", re.sub(r"\D", "", line["text"]), line["text"], line, None)
                current_section = current_chapter
                current_provision = None
            elif role == "section_label":
                pending_section_label = (SECTION_RE.fullmatch(line["text"]).group(1), line)
            elif pending_section_label and role in {"heading", "candidate_heading"}:
                number, section_line = pending_section_label
                current_section = add_node("section", number, section_line["text"], section_line, current_chapter)
                nodes[current_section]["heading"] = line["text"]
                append_line(current_section, line)
                pending_section_label = None
                current_provision = None
            elif role == "provision_start":
                match = PROVISION_RE.match(line["text"])
                label, remainder = match.group(1), match.group(2)
                current_provision = add_node("provision", label, line["text"], line, current_section)
                if remainder and "." in remainder:
                    possible_heading = remainder.split(".", 1)[0]
                    if line["bold"] and len(possible_heading) < 80:
                        nodes[current_provision]["heading"] = possible_heading
            elif role in {"exception", "note", "list_item"}:
                node_type = role
                label = None
                if role == "list_item":
                    label = LIST_RE.match(line["text"]).group(1).rstrip(".")
                parent = current_provision or current_section
                current_provision = add_node(node_type, label, line["text"], line, parent)
            elif role in {"heading", "candidate_heading"} and current_provision is None:
                add_node("heading", None, line["text"], line, current_section)
            else:
                if current_provision:
                    append_line(current_provision, line)
                elif current_section:
                    append_line(current_section, line)
                else:
                    add_node("front_matter", None, line["text"], line, None)

    return {
        "schema_version": SCHEMA_VERSION,
        "document": {
            "document_id": "IBC-2021-Chapter-11-Accessibility",
            "title": "Accessibility",
            "edition": "2021",
            "source_standard": "IBC",
            "source_file": raw["source"]["file_name"],
            "source_pdf_page_range": {"from": raw["source"]["source_pdf_page_from"], "to": raw["source"]["source_pdf_page_to"]},
            "extraction": {"engine": raw["source"]["engine"], "engine_version": raw["source"]["engine_version"], "coordinate_system": "PDF points, origin top-left"},
        },
        "pages": [{
            "page_id": p["page_id"], "pdf_page_number": p["pdf_page_number"], "source_pdf_page": p["source_pdf_page"],
            "layout": p["layout"], "reading_order_line_ids": p["reading_order_line_ids"],
        } for p in layout["pages"]],
        "structure": {"root_node_ids": root_ids},
        "nodes": nodes,
        "tables": {t["id"]: t for t in tables},
        "references": [],
    }


def validate(raw: dict[str, Any], layout: dict[str, Any], structured: dict[str, Any], table_warnings: list[str]) -> dict[str, Any]:
    raw_content_ids = {
        line["id"] for page in layout["pages"] for line in page["lines"] if not line["excluded_from_reading_order"]
    }
    ordered_ids = [line_id for page in layout["pages"] for line_id in page["reading_order_line_ids"]]
    node_used_ids = [line_id for node in structured["nodes"].values() for frag in node["source_fragments"] for line_id in frag["line_ids"]]
    table_used_ids = [line_id for table in structured["tables"].values() for line_id in table.get("source_line_ids", [])]
    used_ids = node_used_ids + table_used_ids
    duplicates = sorted(k for k, v in Counter(used_ids).items() if v > 1)
    missing = sorted(raw_content_ids - set(used_ids))
    unknown = sorted(set(used_ids) - raw_content_ids)
    order_duplicates = sorted(k for k, v in Counter(ordered_ids).items() if v > 1)
    warnings = list(table_warnings)
    if missing:
        warnings.append(f"{len(missing)} content lines were not assigned to structure nodes")
    if duplicates:
        warnings.append(f"{len(duplicates)} content lines were assigned more than once")
    if unknown:
        warnings.append(f"{len(unknown)} structural source lines are not content lines")
    if order_duplicates:
        warnings.append(f"{len(order_duplicates)} reading-order line IDs are duplicated")
    low_conf = [n["id"] for n in structured["nodes"].values() if n["quality"]["structure_confidence"] < 0.8]
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass_with_warnings" if warnings or low_conf else "pass",
        "checks": {
            "page_count": {"expected": 18, "actual": len(raw["pages"]), "pass": len(raw["pages"]) == 18},
            "content_line_count": len(raw_content_ids),
            "reading_order_line_count": len(ordered_ids),
            "structured_source_line_count": len(used_ids),
            "node_source_line_count": len(node_used_ids),
            "table_source_line_count": len(table_used_ids),
            "unassigned_content_line_ids": missing,
            "duplicate_structured_line_ids": duplicates,
            "unknown_structured_line_ids": unknown,
            "duplicate_reading_order_line_ids": order_duplicates,
            "node_count": len(structured["nodes"]),
            "table_count": len(structured["tables"]),
            "low_confidence_node_ids": low_conf,
        },
        "warnings": warnings,
        "manual_review_recommendations": [
            "Review the QA contact sheets for page-region and reading-order errors.",
            "Review all low-confidence nodes before RDF conversion.",
            "Confirm table candidates against the page images.",
        ],
    }


def render_pages(doc: pymupdf.Document, qa_dir: Path) -> None:
    qa_dir.mkdir(parents=True, exist_ok=True)
    matrix = pymupdf.Matrix(1.5, 1.5)
    for page_index, page in enumerate(doc):
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        pix.save(qa_dir / f"page_{page_index + 1:02d}_source_{SOURCE_PDF_START + page_index}.png")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(args.input)
    if doc.page_count != 18:
        raise ValueError(f"Expected 18 pages, found {doc.page_count}")

    manifest = {
        "pipeline": "IBC Accessibility PDF structure extraction, stages 1-9",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "input": str(args.input.resolve()),
        "output": str(args.output.resolve()),
        "ai_usage_policy": {
            "stages_1_to_9_extraction": "No external AI API; deterministic local Python/PyMuPDF",
            "visual_qa": "AI-assisted only after deterministic extraction, recorded separately in execution report",
            "semantic_parsing": "Not performed (stage 10 excluded)",
        },
        "artifacts": ["01_raw_layout.json", "02_layout_analysis.json", "03_structured_document.json", "04_validation_report.json", "qa_pages/"],
    }
    json_dump(args.output / "00_manifest.json", manifest)
    raw = extract_raw(doc, args.input)
    json_dump(args.output / "01_raw_layout.json", raw)
    layout = classify_layout(raw)
    json_dump(args.output / "02_layout_analysis.json", layout)
    tables, table_warnings = extract_tables(doc)
    structured = build_structure(raw, layout, tables)
    json_dump(args.output / "03_structured_document.json", structured)
    report = validate(raw, layout, structured, table_warnings)
    json_dump(args.output / "04_validation_report.json", report)
    render_pages(doc, args.output / "qa_pages")
    print(json.dumps({
        "pages": doc.page_count,
        "raw_blocks": sum(len(p["blocks"]) for p in raw["pages"]),
        "content_lines": report["checks"]["content_line_count"],
        "nodes": report["checks"]["node_count"],
        "tables": report["checks"]["table_count"],
        "validation_status": report["status"],
        "output": str(args.output.resolve()),
    }, indent=2))


if __name__ == "__main__":
    main()

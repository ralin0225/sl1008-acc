# IBC 2021 Chapter 11 PDF Structure Extraction Report

## Result summary

- Input: `IBE2021_11Accessibility.pdf`
- Scope: physical PDF pages 1-18, corresponding to source PDF pages 356-373
- Extraction engine: PyMuPDF 1.28.2
- Raw blocks: 583
- Content lines: 2,166
- Structured nodes: 305
- Tables: 8
- Table source lines: 189
- Non-table structural source lines: 1,977
- Validation: passed with zero missing, duplicate, or unknown source-line references
- JSON Schema: Draft 2020-12 validation passed with zero errors
- Semantic parsing and RDF generation: not performed

## Steps 1-9

### 1. Document inventory and coordinate normalization

Opened the 18-page extracted PDF with PyMuPDF, recorded the file hash, page count, page dimensions, rotation, local PDF page numbers, source PDF page numbers 356-373, and normalized bounding boxes.

- Tool: local Python and PyMuPDF
- AI Token: no
- Important output: `00_manifest.json`, source metadata in `01_raw_layout.json`

### 2. Raw layout extraction

Extracted page, block, line and span structures, including text, bounding boxes, fonts, sizes, style flags, colors, image metadata and drawing metadata. Preserved the original PDF extraction order.

- Tool: PyMuPDF `get_text("dict")` and `get_drawings()`
- AI Token: no
- Important output: `01_raw_layout.json`

### 3. Header, footer and decorative-region classification

Classified top and bottom margin content using relative coordinates and cross-page repetition. Running headers, footers and printed page numbers remain in the layout intermediate state but are excluded from regulatory reading order. Decorative drawings are retained in the raw layout.

- Tool: local coordinate and repetition rules
- AI Token: no for classification; yes later for visual confirmation
- Important output: `02_layout_analysis.json`

### 4. Single-column, double-column and mixed-layout detection

Measured horizontal distributions of content lines. Page 1 was classified as mixed: single-column title/introduction above two-column regulatory text. Pages 2-18 were classified as double-column.

- Tool: local bounding-box rules
- AI Token: yes, to inspect three contact sheets and confirm the detected page types
- AI-assisted correction: the page-1 top band was explicitly assigned to the spanning column
- Important output: `02_layout_analysis.json`, `qa_contact_sheet_1.png` to `qa_contact_sheet_3.png`

### 5. Reading-order reconstruction

Created page-level reading-order line ID lists. For two-column bodies, left-column content precedes right-column content. Spanning title and introduction lines on page 1 are ordered by vertical position before the two-column body.

- Tool: local sorting and column rules
- AI Token: yes, to verify the opening-page order visually and identify the initial title-order issue
- Important output: page `reading_order_line_ids` in `02_layout_analysis.json`

### 6. Line, paragraph and continuation reconstruction

Merged continuation lines into structure nodes, repaired line-end hyphenation when the following line begins in lowercase, preserved verbatim text, and created normalized text alongside it. Cross-page and cross-column source fragments retain separate page, column and bounding-box provenance.

- Tool: local Python rules and regular expressions
- AI Token: no for reconstruction; yes for targeted review of the resulting structure
- Important output: node `text_verbatim`, `text_normalized`, and `source_fragments` in `03_structured_document.json`

### 7. Chapter, section, provision, list, exception and note recognition

Built a Chapter 11 tree with Introduction/User Note and Sections 1101-1112. Recognized provisions from bold numbered starts and classified lists, exceptions, notes and headings. The initial pass was corrected after review so that cross-reference lines were not mistaken for new provisions.

- Tool: typography, numbering patterns, indentation context and local Python rules
- AI Token: yes, to diagnose false provision starts and verify chapter/section hierarchy
- Important output: 305 nodes in `03_structured_document.json`

### 8. Table extraction and separation

Detected eight tables using PyMuPDF, preserved their page locations, dimensions, header names, cells and source line IDs, and prevented 189 table lines from being duplicated into ordinary paragraph nodes.

- Tool: PyMuPDF `Page.find_tables()` and local spatial matching
- AI Token: yes, to compare all eight candidates with page images and confirm they are actual tables
- Important output: `tables` in `03_structured_document.json`

### 9. Structured JSON generation and validation

Generated the final structured JSON, checked that all 2,166 content lines are assigned exactly once to either nodes or tables, checked for duplicated reading-order IDs and invalid references, and validated the result against a Draft 2020-12 JSON Schema.

- Tool: Python, custom integrity checks and `jsonschema`
- AI Token: no for validation; yes to interpret the first-pass findings and select corrections
- Important output: `03_structured_document.json`, `04_validation_report.json`, `05_schema_validation.json`, `structured_document.schema.json`

## AI Token usage record

AI assistance was used only at these decision points:

1. Visual review of all 18 pages through three contact sheets.
2. Confirmation of page 1 mixed layout and pages 2-18 double-column layout.
3. Confirmation that the eight table candidates are real tables.
4. Diagnosis of false provision starts caused by numbered cross-reference lines.
5. Review of Chapter 11 and Section 1101-1112 hierarchy after correction.

All PDF extraction, coordinate calculations, text grouping, table extraction, JSON generation and schema validation ran locally without external AI API calls.

The Codex Plus five-hour usage indicator was approximately 9% before execution and 30% after execution, an observed increase of about 21 percentage points. The weekly indicator moved from approximately 2% to 6%. These account-level percentages include the full interactive work during this period and are not a precise per-step token meter.

## Retained intermediate states

- `01_raw_layout.json`: loss-minimized physical extraction for reprocessing.
- `02_layout_analysis.json`: region labels, column assignments and reading order.
- `qa_pages/`: 18 rendered page images for page-level verification.
- `qa_contact_sheet_1.png` to `qa_contact_sheet_3.png`: compact visual audit of all pages.
- `06_ai_review_notes.json`: machine-readable record of AI-assisted findings and corrections.
- `extract_ibc_accessibility.py`: reproducible extraction script in the workspace root.

## Limitation before RDF use

The result is suitable as a provenance-preserving input to semantic parsing. It is not yet an authoritative legal knowledge graph: cross-references, obligations, permissions, exceptions, quantities and subjects have not been semantically resolved. Those belong to the intentionally excluded stage 10.

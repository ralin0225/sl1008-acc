# Stages 10-12 Semantic Parsing and RDF Report

## Status

The reproducible machine pipeline is complete. The resulting graph is a provenance-preserving candidate knowledge graph suitable for expert review and downstream experimentation. It is not represented as an authoritative legal interpretation.

## Stage 10 - Ontology-constrained semantic parsing

### Work performed

- Created a minimal IBC accessibility ontology and stable namespaces.
- Processed provisions, list items and exceptions from the stage 1-9 structure.
- Generated 289 provision-level semantic candidates.
- Classified statement type, rule type and legal modality.
- Extracted subjects, requirements, conditions, measurements, exceptions and cross-references.
- Preserved exact source text, source node IDs, PDF page provenance and bounding boxes.
- Split compound provisions into 462 atomic rules so that main requirements and exceptions retain separate modalities.
- Mapped 194 candidate subjects to common accessibility-domain concepts while preserving original text.
- Generated a DSL-style intermediate representation.
- Created an 86-item review queue for compound, long, nested or modality-ambiguous content.

### Tools

- Python regular expressions and deterministic rules
- JSON intermediate representations
- PyMuPDF-derived provenance from stages 1-9
- AI-assisted schema design and targeted review of high-risk samples

### Token use

AI Token was used to design the semantic slot structure, inspect low-confidence samples and identify the need for atomic-rule decomposition. Batch extraction, evidence hashing, classification rules and JSON generation were local and did not use an external AI API.

### Outputs

- `10_ibc_minimal_ontology.ttl`
- `10_semantic_candidates.json`
- `10_semantic_validated.json`
- `10_dsl_rules.json`
- `10_manual_review_queue.json`

## Stage 11 - Dual RDF graph construction

### Work performed

- Created a document navigation graph for chapters, sections, provisions, list items, exceptions and tables.
- Created an entity graph for requirements, concepts, conditions and measurements.
- Linked semantic requirements to source structure nodes using `prov:wasDerivedFrom` and `ibco:sourceNode`.
- Preserved source pages and bounding boxes.
- Added normalized unit codes and comparison operators to measurement nodes.
- Added AtomicRule nodes beneath provision-level Requirement nodes.
- Resolved 191 cross-references to nodes in this chapter; retained 11 references as external or unresolved.
- Serialized the graphs as Turtle, TriG and JSON-LD.

### Tools

- RDFLib
- RDF, RDFS, OWL and PROV-O vocabulary
- QUDT-compatible unit namespace
- Named graphs in TriG

### Token use

No AI Token was required for RDF generation or serialization. AI Token was used earlier to review entity-normalization design and prevent unbounded free-text entity fragmentation.

### Outputs

- `11_document_graph.ttl`
- `11_entity_graph.ttl`
- `11_combined_graph.trig`
- `11_combined_graph.jsonld`

### Graph statistics

- Document graph: 2,664 explicit triples
- Entity graph: 6,984 explicit triples
- Combined explicit graph: 9,648 triples
- Requirements: 289
- Atomic rules: 462 in the semantic intermediate layer and corresponding RDF AtomicRule nodes
- Measurements: 110
- Conditions: 174

## Stage 12 - Neuro-symbolic validation

### Work performed

- Validated RDF source links, evidence equality and measurement evidence.
- Verified that the number of semantic candidates matches RDF Requirement nodes.
- Created SHACL Shapes for Requirement, Measurement and AtomicRule nodes.
- Ran SHACL validation over the union of the document and entity graphs.
- Ran OWL 2 RL deductive closure and checked for instances of `owl:Nothing`.
- Preserved SHACL result graphs and a JSON validation summary.

### Tools

- pySHACL
- RDFLib
- OWL-RL reasoner
- Deterministic provenance and fidelity checks

### Token use

SHACL, OWL-RL and fidelity validation did not use AI Token. AI Token was used to diagnose the first SHACL failure as a graph-scope and Shape-design issue rather than a data-generation failure.

### Validation result

- SHACL: passed
- Evidence fidelity: passed
- Candidate-to-RDF count: passed
- OWL 2 RL consistency sanity check: passed
- Instances inferred as `owl:Nothing`: 0
- OWL-RL inferred triples added: 8,244
- Overall machine validation: passed

### Outputs

- `12_shapes.ttl`
- `12_shacl_results.ttl`
- `12_owl_reasoning_report.json`
- `12_validation_report.json`

## AI usage and current plan allowance

During this stage, AI assistance was concentrated on semantic architecture and targeted review rather than bulk text extraction. The Plus five-hour usage indicator was approximately 30% at the end of stages 1-9 and approximately 71% after stages 10-12, an observed increase of about 41 percentage points across this interactive stage. The weekly indicator increased from approximately 6% to 12%. These account-level indicators are not precise per-file token measurements.

## Remaining expert-review boundary

The 86-item manual review queue mainly contains provisions with multiple normative clauses, long embedded exceptions, multiple conditions or no explicit modality. These items are deliberately retained instead of being silently accepted. Legal-expert review is recommended before using the graph for authoritative compliance decisions.

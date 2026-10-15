# SL1008 · Automated Building Code Compliance

IBC 2021 building-code processing and an IFC compliance workbench. The project preserves regulatory source evidence, builds structured DSL/RDF representations, links provisions to IFC objects, and runs evidence-bound deterministic subchecks with a browser Viewer.

## Branches

- `main`: the existing nine-subcheck baseline and its Viewer.
- `feature/residential-six-checks`: the baseline plus six two-storey residential subchecks (Class 1, 2 and 3), for a total of 15 contracts. See [the residential guide](https://github.com/ralin0225/sl1008-acc/blob/feature/residential-six-checks/output/acc/RESIDENTIAL_CHECKS.md).

The Viewer is included as ordinary files under `output/acc/viewer` in both branches. No submodule initialization is required. The original local Viewer repository's Git metadata and hosting metadata are not uploaded.

## Layout

| Path | Contents |
|---|---|
| `process_ibc_chapter.py`, `extract_ibc_accessibility.py` | Regulatory document extraction |
| `build_semantic_rdf.py` | Semantic representations and RDF generation |
| `output/ibc_means_of_egress_structure` | Chapter 10 structured/semantic artifacts |
| `output/ibe_accessibility_structure` | Chapter 11 structured/semantic artifacts |
| `output/acc/src`, `schemas`, `tests` | Compliance contracts, model observations, checks and tests |
| `output/acc/viewer` | Browser Viewer, local HTTP/API server and exported snapshots |

## Local setup

Python 3.12 and Node.js are used in the existing development environment. From the repository root:

```powershell
python -m pip install -r output/acc/requirements.lock.txt --target output/acc/.python_deps
python -m pip install -r output/acc/requirements.compliance.txt --target output/acc/.python_deps
cd output/acc/viewer
npm ci
python serve.py --port 8766
```

Open `http://127.0.0.1:8766/`. Pre-exported model JSON and compliance snapshots are included so the Viewer can display the existing examples. Re-extraction and live checks additionally require the original IFC files at the paths described by `output/acc/models/catalog.json`; obtain the inputs separately or register your own models. Source PDF links and document extraction require the original IBC PDFs. This repository does not distribute original PDFs or IFC files, installed dependencies, local review approvals, hosting metadata, or runtime logs/history.

## Checks and interpretation

```powershell
python -m unittest discover -s output/acc/tests -v
cd output/acc/viewer
npm test
```

Tests that reference the real example IFC files require those inputs locally. The synthetic residential tests on the feature branch generate their own temporary IFC fixtures.

`PASS` and `FAIL` apply only to the explicitly reviewed subcheck scope. Missing applicability, incomplete model information, absent measurement semantics or unreviewed evidence produce `NOT CHECKABLE`; they are not evidence of a compliant or noncompliant building. Model information checks and candidate provision links are distinct from design compliance. No actual model is approved by synthetic tests or by merely adding an `Accessible` property.

See [the ACC documentation](output/acc/README.md) for the existing pipeline, model registration and execution workflow. Historical phase reports retain the counts and limitations from the time they were generated; the branch descriptions above describe the published branch contents.

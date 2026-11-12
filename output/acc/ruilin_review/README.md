# Ruilin: Phase 4 review and room-height extension

Prepared 2026-11-12. Independent contribution branch; not merged into the published ACC baseline.

## Repository update check and team focus

Fetching both remotes on 2026-11-12 found no branch-head change since the 2026-11-09 inventory.
LRZ still has 12 branches. The latest substantive checking branch is Silvan's
`phase3-ibc-rules-v2` at `439352c`, with Chapter 10 stair width (1011.2), door width
(1010.1.1), stair headroom (1011.3), and egress continuity (1003.6). Its other new
branches propose v2 interfaces. Diana's `phase4`/`proposal-phase4-result-sheet-v2`
focus on a kitchen/living-room ceiling-height visualization under 1208.2.
The newest commits are dated 2026-10-28. This indicates code focus, not private Jira activity.

These two height checks have different reference surfaces. Storey-to-storey elevation
difference is structural height. Room height is measured above the finished floor.
Stair headroom uses the tread-nosing reference and an extended flight/landing domain.
One threshold or one bounding-box measurement cannot stand in for all three.

## Jira work prepared

| Assignment | Delivered here | Still requires a person |
|---|---|---|
| Two BCA examples / expected verdict | Two pinned stair-headroom candidates, actual model identity check, independent slab intersections, coordinates and editable CSV | Independent manual dimensions, applicability/exception checks, evidence screenshots, expected verdict and reviewer; Solibri comparison if available |
| Ruilin reviews Phase 4 | Review findings, viewer patch, data-boundary tests and browser checks | Diana/team review, review of visual semantics and agreement on integration |

The SCRUM-12 specification and issue identifiers were not available in the supplied
text or repository. The CSV preserves the existing `your_measurement`, `agree (y/n)`
and comment fields and adds explicit expected-verdict and evidence fields. It is a
preparation package, not a completed SCRUM-12 submission. No Jira item was updated.

See [the BCA walkthrough](BCA_MANUAL_REVIEW.md), [Phase 4 review](PHASE4_REVIEW.md),
and [height-rule guide](ROOM_HEIGHT_GUIDE.md).

## Room-height implementation

`../src/room_height_review.py` is an experimental, standard-library-only evaluator.
It is deliberately separate from the 15 executable contracts and default viewer API.
It accepts a reviewed rectangular full-domain piecewise-planar height representation,
not arbitrary IFC geometry. A signed review binds the facts to the checker contents.
It preserves synthetic provenance and does not create approvals.

Implemented variants: ordinary rooms, kitchens/bathrooms/etc., residential unit
corridors with verified context, sloped-ceiling area fraction and furred-ceiling
area fraction plus absolute minimum. All comparisons use exact rational arithmetic.
Mezzanines, beam/girder exceptions, mixed sloped/furred ceilings, complex room outlines,
and automatic construction of the reviewed surface are left unimplemented and require
separate assessment. The guide lists the evidence needed for the next iteration.

Run from the SL1008 repository root:

```powershell
python -m unittest discover -s output/acc/tests -p test_room_height_review.py -v
python output/acc/src/room_height_review.py output/acc/ruilin_review/room_height_facts.template.json
```

The blank template must return `NOT CHECKABLE`. Read the measurement and review
requirements before populating it. Do not approve a real model using test fixtures.

## Phase 4 patch and validation

`phase4-review.patch` applies to LRZ commit `eb4bd1c` (the v2 viewer proposal). It is
also committed as normal files in Ruilin's separate LRZ branch. It does not alter
Silvan's Phase 3 engine or other members' branches.

Checks completed locally with Python 3.12, Node.js and headless Edge:

- 12 new height-check test methods, including exact boundaries, affine area clipping,
  an internal low point, incomplete surface/evidence, and stale approval rejection.
- 8 Phase 4 data tests: identity, units, provenance, exemption statistics, multi-rule
  reverse lookup, invalid data and HTML escaping.
- Browser checks: bundled demo disclosure, visible read-error with no substitution,
  exempt displayed separately, imported text escaped, model-hash mismatch rejected;
  no page JavaScript errors. The actual xeokit model loaded and a result card rendered.

No Solibri comparison or manual measurement is claimed. These results do not replace
the upstream full test suite or constitute building approval.

## Source basis

IBC 2021 Sections 1208.2 and 1208.2.1, checked against the
[ICC Chapter 12 page](https://codes.iccsafe.org/content/IBC2021V2.0/chapter-12-interior-environment).
The project uses exact conversion from the original feet/inches rather than a rounded
printed millimetre equivalent. Adoption, use classification and exceptions require review.

The patch uses zero-context hunks to preserve whitespace in a portable artifact. Apply only to its pinned base with `git apply --unidiff-zero phase4-review.patch`.

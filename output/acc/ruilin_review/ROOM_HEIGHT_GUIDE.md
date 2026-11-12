# Room-height variants and proposed next steps

This is a scoped implementation note, not a claim that every ceiling rule is automated.
Policy ID: `ibc2021-room-height-review/1`.

| Reviewed context | Implemented subcheck |
|---|---|
| Ordinary habitable/occupiable space or corridor | Full supplied surface at least 2286 mm |
| Kitchen, bathroom, toilet, storage or laundry | Full supplied surface at least 2133.6 mm |
| Corridor within a Group R dwelling/sleeping unit | 2133.6 mm only with explicit unit-context verification |
| Sloped ceiling | At least half the full projected room area reaches the applicable height; separately report area below 1524 mm |
| Furred ceiling | At least two thirds reaches the applicable height; nowhere below 2133.6 mm |

Basis: [IBC 2021 Chapter 12](https://codes.iccsafe.org/content/IBC2021V2.0/chapter-12-interior-environment),
1208.2 and 1208.2.1. Exact imperial conversion is a declared project convention.
The sloped-room denominator is explicitly the reviewed full projected room area.
The below-5ft area is not automatically subtracted from that denominator; assessment
of required minimum room area is a separate check.

## What the surface means

- `x` and `y` are millimetre axes from zero to the declared full rectangular room extents.
- Both elevation matrices have dimensions `[len(x)][len(y)]` in the same datum.
- Each cell is split on its `(i,j)` to `(i+1,j+1)` diagonal for both surfaces.
- Both surfaces and their difference are affine on each triangle. The minimum is at
  a vertex; qualifying projected area is calculated by exact height-plane clipping.
- These are reviewed complete representations, not isolated laser/ray measurements.
  A small beam or duct must be represented by appropriate cells or prevent approval.
- `source_global_ids` identify the geometry sources, but this standalone evaluator
  does not open the model to authenticate their existence or automatically prove coverage.
  The person preparing/reviewing facts must check identity, geometry and completeness.

## Review workflow

1. Duplicate `room_height_facts.template.json`. Identify the actual IFC SHA-256 and target.
2. Establish code basis, room use, finished surfaces, complete domain and all relevant
   exceptions. Resolve overhead beams/ducts, openings and suspended ceilings.
3. Supply the full surface and its evidence. Do not substitute storey elevations,
   `IfcSpace` height or a bounding box for the measurement definition.
4. An independent reviewer checks the evidence. `facts_digest(facts)` computes the
   binding value; it is not an approval function. After reviewing the actual scope,
   the reviewer records identity/evidence, the binding digest and `APPROVED`.
5. Any change in facts or checker invalidates that binding. Re-extract/review as needed.
   Keep `is_synthetic=true` for teaching/test fixtures and false only for actual data.

The evaluator emits a scoped result and quantities; it does not publish a new
production contract or overlay it automatically in SL1008. Add a reviewed contract,
IFC binding and browser report adapter before treating it as an integrated check.

## Depth beyond the current implementation

| Next case | Required information before implementation |
|---|---|
| One/two-family beam or girder exception | Confirm building type, member type, centre spacing and projection; do not exempt ducts or any small low object by name |
| Mezzanine / space below mezzanine | Separate 505.2 applicability, reference surfaces, classification and exceptions |
| Mixed sloped and furred ceiling | Resolve interaction and denominator/absolute-height semantics; do not choose whichever branch passes |
| Nonrectangular rooms or room holes | Verified projected domain partition, non-overlap and coverage checks |
| MEP or small overhead obstructions | Complete underside surface and evidence for whether an exception applies |
| Stairs, spiral stairs, floor-opening projections | Remain separate 1011.3 checks, with nosing datum, full width and landing extension |
| Market/assembly/commercial uses | Review occupancy/use and local adopted code; ordinary-room defaults do not settle market-specific or egress requirements |

The most useful next contribution is a reviewed IFC-to-surface builder plus a small
set of manually measured adversarial cases, rather than more unexplained threshold switches.

# Two BCA stair-headroom candidates — manual review pending

Both are from `BCA_[E-3-3]_v5-OBOS.ifc`, in the upstream candidate list under
`phase3_compliance_execution/review/2026-10-28/manual_check.csv`, at LRZ commit
`439352c224e7a159e169f79760f6eeb01fb3293a`.

| Candidate | Target flight | Governing slab | Engine value / verdict |
|---|---|---|---|
| Failure candidate | `0Pi72lxqT7rB3T2_y3sKda` | `0Pi72lxqT7rB3T2_y3sBTa` | 1833.8 mm / fail |
| Passing candidate | `0Pi72lxqT7rB3T2_y3sB$v` | `0Pi72lxqT7rB3T2_y3sB5E` | 2193.6 mm / pass |

Threshold in the reviewed entry: 2032 mm. These are **engine candidates**, not gold
expected verdicts. `expected_verdict`, `your_measurement`, reviewer and agreement remain
blank in [manual_check_ruilin.csv](evidence/manual_check_ruilin.csv).

## Completed automated checks

The exact snapshot model hash was checked. Each target exists as an `IfcStairFlight`
and each named governing object as an `IfcSlab`. Using IfcOpenShell directly (without
the Phase 3 measurement helper), triangle-plane intersection of the named slab at
the engine XY found underside Z=7800 mm and 10600 mm respectively. Subtracting the
engine's reference Z=5966.2 and 8406.4 reproduces 1833.8 and 2193.6 within floating-point
precision. Results are in [bca_two_cases.json](evidence/bca_two_cases.json).

This cross-check only confirms the named upper surface and numerical subtraction.
The nosing reference still comes from the engine; it is not independent manual evidence
of full-domain clearance or the absence of a smaller obstruction.

## Exact model provenance

- Git blob is LF, 20,157,579 bytes, SHA-256 `1de6eb4aa7c7513e85f0cc52d8620016e73ec258faa759ef47bd6e11ebf36224`.
- The frozen engine report binds CRLF bytes, SHA-256 `e0906e903387c18e21590cc8b39f86f9f61daa512a1188a615ce29a4c61224bc`.
- Replacing LF with CRLF reproduces that exact snapshot hash. No IFC entities were
  edited. Both identities are documented; neither is silently substituted for the other.
- The prepared check used the latter, matching the frozen report. The original IFC is
  not copied into this contribution or uploaded to GitHub.

## What Ruilin should do in an IFC viewer / Solibri

1. Open the exact model revision. Find the flight and slab by the GUIDs above; retain
   a screenshot showing the model identity, selected GUID, and dimension tool.
2. Confirm the entry's applicability and exceptions. The fact that a test model is
   labelled BCA does not establish IBC applicability to a real building.
3. Establish the line connecting tread nosings, not the tread top at an arbitrary point
   or the storey level. Measure vertically to the lowest underside obstruction.
4. Inspect the whole required width, small beams/ducts, sides and one-tread-depth bottom
   extension. Test whether the engine's reported point actually governs the minimum.
5. Record independent minimum, tool, coordinate/reference definition, any exceptions and
   measurement uncertainty. Compare with Solibri if available; otherwise state unavailable.
6. Determine the expected verdict from reviewed applicability and the actual dimension.
   Below 2032 mm gives fail within the general branch, at/above it gives pass only if the
   full domain is covered. Ambiguous applicability or incomplete coverage stays undecided.
7. Fill the CSV, attach evidence and map it to the exact SCRUM-12 format before marking
   the Jira assignment complete. A value near the boundary requires more careful measurement.

Source coordinates for locating each measurement, in model millimetres:

- Failure: XY=(13923.7, 3121.6), reference Z=5966.2, upper Z=7800.
- Pass: XY=(16350.9, 6103.9), reference Z=8406.4, upper Z=10600.

Reproduce automated preparation with `prepare_bca_review.py --model <matching-ifc>
--sheet <BCA__E-3-3__v5-OBOS.result-sheet.v2.json> --output <directory>` after installing
IfcOpenShell/NumPy. It rejects a mismatched raw model hash and never fills manual fields.

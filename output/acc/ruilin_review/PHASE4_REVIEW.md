# Ruilin's Phase 4 review — 2026-11-12

Review target: LRZ `proposal-phase4-result-sheet-v2` at `eb4bd1c` (Diana's viewer
plus Silvan's v2 import proposal). Ruilin is the reviewer, per the supplied review ring.

## Findings fixed in Ruilin's branch

| Priority | Trigger and previous behavior | Result after patch |
|---|---|---|
| P1 | Missing/invalid result JSON silently selected built-in red/green rows | Visible load error, empty results and disabled selection; no substitute verdicts |
| P1 | A v2 report for another IFC could be applied to the configured model | SHA-256 compared with the configured source IFC before accepting rows |
| P1 | Imported note/name/citation text was interpolated into HTML | Escape data inserted into cards/details; malformed values rejected |
| P2 | `exempt` mapped to pass and increased the passed count | Separate neutral status/color/count; no exemption in pass or completion denominators |
| P2 | Only the first target GUID was indexed, and later rows overwrote earlier rules | All targets/governing/contributors indexed to arrays; repeated model selection cycles matching results |
| P2 | Geometry m/mm and quantity units could disagree during drawing | Normalize geometry to mm; convert comparison quantities into a common length unit |
| P2 | Bundled living-room example used kitchen's height threshold | Ordinary habitable-room example uses 2286 mm; kitchen uses exact 2133.6 mm; both remain explicitly hand-written demo data |
| P2 | Missing lookup said no regulation applies | Now says no result available; absence of a result proves no applicability conclusion |

The clearance bar now uses the stated 120% scale consistently; the threshold marker is projected from its actual world coordinate instead of a screen-space ratio.

Rounded display labels do not change measured values, thresholds or verdicts. V1
arrays require explicit demo provenance; v2 outputs state that model binding is not
the same as human validation and disclose input rules below gold tier.

## Integration issues still open

- The configured XKT/IFC pair is the kitchen demo. Hash checking the source IFC does
  not prove how the XKT was generated; add a conversion manifest for arbitrary models.
- Only the clearance renderer exists. Phase 3's `width` and `path` kinds need their
  own renderers and geometry contracts; do not claim all four rules render correctly.
- One generic clearance bar cannot express sloped/furred ceiling area fractions.
  A future area renderer must show qualifying area, total domain, excluded area and
  the absolute-minimum failure separately, using the new experimental evaluator.
- Curved stairs, inferred exits/edges, sampling coverage and quarantine execution
  are upstream evidence issues; Phase 4 must not silently promote them to certainty.
- xeokit and fonts still use external CDNs. An offline integration needs pinned,
  locally served dependencies. Browser validation here used the actual CDN/xeokit.
- The data boundary is targeted validation, not a replacement for the complete
  Phase 3 JSON Schema validator.

## Validation

`node --test tests/result-data.test.mjs`: 8 passing tests. `viewer.browser.cjs` uses
headless Edge/Playwright against a local server and checks demo disclosure, fail-closed
loading, exempt counts, escaping, model hash rejection and absence of page errors.
The two bundled model results remain examples; this is not a manual IFC or Solibri review.

Recommendation: review these fixes as an isolated patch, then agree on model conversion
provenance and non-clearance renderer semantics before merging a full engine integration.

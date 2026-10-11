# SVG H/V Bounds — local regression (2026-10-10)

## Evidence and scope

- Actual branch: `feature/pattern-library-reuse`; HEAD remains `4a1c799255ca71002dc4cd9bae88e38ef0fea69e`. Index empty. All earlier dirty work retained; no commit, push, deployment, dependencies, validator or manufacturing algorithm changes.
- The historical original failed user SVG is unavailable. `tests/fixtures/svg_hv_bounds_regression.svg` and the inline SVGs in `tests/test_svg_hv_bounds.py` are **new regression samples**, not the original file. The earlier `full_design_holes.svg` is also a synthetic fixture, not evidence that the original user file has been recovered.
- Read-only inspection found `_path_bounds` paired all numeric operands as XY, ignoring H/h and V/v command arity and relative displacement. `RECT_PATH_RE` also ignored case, allowing relative h/v to be falsely interpreted as an absolute rectangle.
- Source-before copies and actual test logs: `work/svg-hv-bounds-20261010/` (local ignored evidence, not a Git backup).

## Before the product fix

Command: `xiaomang_pattern_lab/.venv/Scripts/python.exe -m pytest tests/test_svg_hv_bounds.py -q`

Actual result: **19 failed, 3 passed; pytest exit 1** (`before-tests.log`).

New hole path: `M31 83 H55 V107 H31 Z M37 89 V101 H49 V89 Z`.

| Measurement | Before | Expected / after |
|---|---|---|
| Native bounds | (31,37,89,107) | (31,83,55,107) |
| Element center | (60,72) | (43,95) |
| Width × height | 58 × 70 | 24 × 24 |
| Center in mm, factor .5 | (30,36) | (21.5,47.5) |
| Width × height in mm | 29 × 35 | 12 × 12 |
| Ellipse influence centered at (43,95) | misses the element | weight 1 |

Relative `M12 34 h30 v10 h12 z` was falsely recovered as a rectangle; it now remains its actual path, center (33,39), size 42 × 10.

## Minimal fix

- Only production file changed this round: `ppg/foundation/svg_normalizer.py`.
- `_path_bounds` walks command operands for H/V-containing paths, including absolute/relative positions, repeated operands, moveto/subpath state and closepath. H/V update one axis only; mixed curve commands consume their proper arity so subsequent H/V begins at the correct endpoint.
- Rectangle recovery accepts absolute M/H/V only (z/Z closure remains supported), rather than treating lowercase displacement operands as absolute coordinates.
- Non-H/V paths keep the existing bounds policy. This is not an exact general-purpose arc/Bezier extremum implementation or a transform-engine rewrite. Tested transforms are translation and nonuniform scale; rotation/matrix/composed-transform correctness is **NOT TESTED** here.
- Stored `PatternDocument` loading/serialization, base_* fields, source paths, shared polygon parser and evaluation are untouched. Existing saved projects are **not automatically migrated**. Regression verifies exact .pattern.json save/load and preservation of explicit foundation geometry metadata on semantic SVG re-import.

## After / affected regression

1. Product fix first rerun: 21 passed, one newly reached API test failed because this new test omitted the required `schema_version`. The test request was corrected to the existing contract, not the API relaxed (`after-tests.log`).
2. Added legacy application SVG check initially compared all style fields and found existing PathElement SVG exporter drops `fill-rule` (it only preserves this for FilledRegion). This was not changed: the legacy import regression now specifically verifies the intended geometry/base metadata, while exact .pattern.json equality remains enforced. See `after-tests-final.log`. This separate exporter limitation remains **OPEN**, not claimed resolved by the bounds fix.
3. Affected suite command:

   `xiaomang_pattern_lab/.venv/Scripts/python.exe -m pytest tests/test_svg_hv_bounds.py tests/test_web_svg_grid_p0.py tests/test_web_import_wm55.py tests/test_fabric_original_shape.py tests/test_full_design_panel.py tests/test_foundation0.py::Foundation0AcceptanceTests::test_native_svg_primitives_and_reliable_path_recovery -q`

   **51 passed + 7 subtests passed**, exit 0, 27.18 s (`targeted-regression.log`). Covers existing PNG/JPG/SVG import, P0 SVG Grid preparation/application, original-shape Fabric height/holes/base/grid/STL, influence areas and native primitive recovery. Not a full-suite claim.
4. Final new regression after adding local-scope HTTP manufacturing: **25 passed**, exit 0 (`final-new-regression.log`). Counts overlap with the previous batch and are not added together.
5. `git diff --check`: exit 0. Only existing line-ending notices and Starlette/httpx deprecation warning; no dependency upgrade attempted. Frontend unchanged this round, no redundant build/Tk full regression.

New sample actual HTTP upload → import → evaluate → standard manufacturing → STL response saved to test temporary file → existing STLExporter reload → strict MeshValidator PASS. Both unmodified and local .75-size variants are checked:

- Original: bounds (15.5,27.5,0)–(45.5,53.5,2) mm; volume 310 mm³.
- Scoped: bounds (17,27.5,0)–(45.5,52,2) mm; volume 215.5 mm³; outside L shape unchanged; hole retained.
- Both: two valid components, watertight, consistent winding, positive volume, zero degenerate faces; Euler total 2 (one holed solid plus one simply connected solid).

## Boundary / stop

- No historical saved document changed or re-imported, no user draft cleared, no server restarted. Existing already-running services are not claimed to have hot-loaded this import fix; browser/public acceptance is **NOT TESTED** this round.
- The earlier complete-artwork closeout remains BLOCKED pending fresh-version artwork acceptance; old saved incorrect anchors are deliberately not silently corrected.
- No original-user-file reproduction claim, general SVG transform certification, new feature, local stable backup, commit/push/deploy or physical-print claim. STOP after this scoped report.

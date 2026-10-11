# SVG supplemental acceptance — 2026-10-10 (local only)

## Protected baseline and scope

`feature/pattern-library-reuse`, HEAD `4a1c799255ca71002dc4cd9bae88e38ef0fea69e`; index empty, all earlier dirty work preserved. No reset/clean/old patch restoration, commit, push, deploy, production permission/config change, dependency or manufacturing algorithm/validator change.

All samples here are the existing **new regression fixture** `tests/fixtures/svg_hv_bounds_regression.svg` or explicitly generated variations, not the missing original user file. Source-before copies and outputs: `work/svg-final-acceptance-20261010/` (ignored local evidence, not Git backup).

The passed H/h V/v `_path_bounds` implementation was **not changed this round**.

## 1. Transform actual before/after

First run `tests/test_svg_final_acceptance.py`: **13 FAIL**, exit 1; actual log `before.log`. The failures comprise ten parameterized Transform cases, nested Transform composition, and two fill-rule/re-import cases. The faithful round-trip also exposes the foundation SVG's existing unitless calibration boundary (see OPEN below), not another geometric-repair task.

Observed defects:

- `rotate(90)` for the hole: actual first material vertex `(107,-31)` rather than `(-83,31)`; source rotation and editable element rotation both applied. Stored center `(43,95)` also did not follow source origin rotation; expected `(-95,43)`.
- `translate(7 -11) scale(2 3)` should be SVG CTM `T @ S`. Normalized center `(93,274)` was plausible, but actual polygons were `(76,216)–(124,288)` rather than `(69,238)–(117,310)` because the shared legacy source-transform application walked the list in reverse semantic order.
- Matrix Transform was not represented by that legacy path helper.

Minimal scoped correction in `svg_normalizer._normalize_linear_path_transform`:

- **Only new imported closed straight M/L/H/V/Z paths** with rotation/matrix/composed transforms are materialized to world-coordinate path points, once, using standard SVG CTM composition (parent @ child; list left-to-right matrix multiplication).
- Reuses `path_subpaths` and `path_data_from_polygons`. Formatter gains optional `precision=15` here, while its default 7-digit behavior and all existing callers remain unchanged.
- New materialized paths have identity source/edit transform, world bounds/base center, so rendering/Size consumers/manufacturing do not apply source rotation or unit mapping twice.
- Single translate/scale retains the already-verified normalization and primitive recovery. Existing saved JSON and explicit foundation metadata bypass new-import materialization; no shared transform parser or stored project migration was changed.

Final tested oracles: rotation 90° about origin, 90°/45° about explicit center, `translate→scale`, `scale→translate`, affine matrix with shear terms, nested parent translation/child nonuniform scale. Semantic/faithful modes compare every outer vertex, actual Bounds, center and influence weight; applying .75 inside the effect scales about the correct world center, not screen coordinates. Nested export/re-import geometry also matches.

This is **not** general SVG certification: transformed Bezier/Arc, skew commands, open paths and arbitrary primitive transform combinations remain unverified/outside this small straight-path adaptation. Do not claim these passed.

## 2. fill-rule actual semantic impact

`svg_exporter._common_attributes` originally copied fill/stroke/opacity but not `fill-rule` for PathElement (only FilledRegion had a separate preservation branch). Minimal change adds `fill-rule` to the existing common attribute list; no exporter redesign.

Tests cover evenodd holes with both same and opposite winding, multiple subpaths, semantic PathElement and faithful FilledRegion. A same-winding new variation is essential: dropping evenodd defaults to nonzero, which actually fills the inner loop visually and makes the existing conservative manufacturing adapter reject ambiguous nesting.

`tools/svg_final_acceptance_readback.py` runs a **diagnostic-only captured pre-fix exporter** from its source-before copy, without overwriting a live module or restoring a patch. It creates actual `fill-rule-before.svg` and `fill-rule-after.svg`:

| | Captured before | Current after |
|---|---|---|
| Path fill-rule | absent | evenodd |
| Re-imported manufacturing conversion | 1 converted; hole rejected `ambiguous_nonzero_fill` | 2 converted; no skips |
| Hole counts | only outside L shape (0 holes) | hole: 1; outside L: 0 |

Explicit .5 calibration is supplied by this isolated core-export comparison. It is **not** a claim that the foundation editable SVG automatically restores mm units. The browser Web exporter already preserves fill-rule and explicit physical mm/viewBox; that separate real path is tested below.

## 3. Actual current local browser workflow

Read current browser inventory and actual tab `http://127.0.0.1:8797/`; it was still using the older pre-control-panel UI/service. Preserved this page and its storage, did not restart/kill any old service or clear drafts.

Ran a fresh current-source local test instance at `http://127.0.0.1:8801/` (PID 17604, current repository `.venv`/standalone Python, existing `web/dist`, process-only local staging/test flags). Opened it in **the current Codex in-app browser**, not a simulated API/headless substitute. Separate origin avoids replacing the user's other drafts. Bundle actually loaded `/assets/index-BeMizbJw.js`; no frontend code changed this round. Backend release commit remains UNKNOWN; actual fresh process/workspace source is known. The existing 8797 page is **not claimed repaired/reloaded** by this test.

Real mouse/DOM controls:

1. Import the new H/V regression SVG via file chooser (2 objects).
2. Open Size effect → constant driver .5 → min/max .75 → multiple influence areas → one ellipse centered `(21.5,47.5)` mm, diameters 4×4 mm, feather 0.
3. Apply once through the normal button. Hole outer bounds become `(17,43)–(26,52)` mm (9×9); outside L remains unchanged; source positions retain .5 mapping/nonzero origin.
4. Actually download SVG and transparent PNG (not screenshots). Files copied from returned browser download paths into the evidence directory.
5. Enter manufacturing → standard `检查并生成` → actual STL download. It reports two components, correctly as a warning, not an error or forced Fabric singleton.
6. Return to design, **same test tab** imports the downloaded SVG; visible hole and L remain. Download the re-imported SVG/PNG again and independently read both files.

Artifacts:

- `applied-browser.jpg`, `reimported-browser.jpg`: actual browser screenshots.
- `browser-dom-evidence.json`: visible final paths/fill-rule, current URL and script. Re-imported hole has canonical `M17 43 ...` path, `fill-rule=evenodd`, no remaining Transform; L retains a single .5 source scale. No visible role-alert. Direct DOM `getBBox` is not exposed by this browser tool, so numerical Bounds evidence comes from actual downloaded files plus the Python oracle, not a fabricated DOM result.
- `browser-server.log`: all actual HTTP requests 200; 13 POST total (2 assets, 2 imports, 7 evaluate, 1 Fabric design preview, 1 standard manufacturing), STL GET 200. SVG/PNG are real client-side file deliveries, not HTTP STL substitutes. No 429 observed; no concurrency/performance claim beyond the captured operations.
- `browser-design.svg/png/stl`, `reimported-design.svg/png` and `readback-report.json`.

Readback:

- SVG is true vector, physical 60×40 mm, viewBox `(10,20,60,40)`; original source canvas `(20,40,120,80)` × .5 mapped once. Both rounds have exact matching material polygons and the actual inner hole.
- PNG RGBA 1600×1067; hole-center alpha 0, material alpha 255, outside alpha 0. Pixel arrays exactly identical after re-import; vision-skills `pixel_diff.py` reports **0.00%** difference.
- STL 2,684 bytes / 52 triangles, Bounds `(17,27.5,0)–(45.5,52,2)` mm, size 28.5×24.5×2 mm, volume 215.5 mm³; 2 valid components, water-tight, positive volume, consistent winding, zero degenerate faces, Euler total 2. XY vertices agree with the expected material/holes. No repair/deletion or validator weakening.

## Tests (batches overlap; do not sum)

- `before.log`: new initial supplemental tests 13 FAIL before scoped changes.
- `after.log`: supplemental plus prior H/V tests 38 PASS after initial changes.
- `regression.log`: 43 PASS + 2 subtests, before final 45°/same-winding test additions.
- `final-regression.log`: **47 PASS + 2 subtests**, exit 0, 1.66 s:

  `xiaomang_pattern_lab/.venv/Scripts/python.exe -m pytest tests/test_svg_final_acceptance.py tests/test_svg_hv_bounds.py tests/test_web_svg_grid_p0.py tests/test_web_import_wm55.py::WebImportWM55Tests::test_svg_with_hole_and_editable_shapes tests/test_foundation0.py::Foundation0AcceptanceTests::test_native_svg_primitives_and_reliable_path_recovery tests/test_fabric_original_shape.py::test_real_hole_and_size_around_anchor_no_double_rotation tests/test_fabric_original_shape.py::test_original_api_preview_export_and_content_bound_stale_guard -q`
- `tools/svg_final_acceptance_readback.py`: actual browser artifacts and captured before/after attributes PASS.
- `vision-skills/scripts/pixel_diff.py browser-design.png reimported-design.png`: 0.00%.
- `git diff --check`: exit 0. Existing Starlette/httpx deprecation and Git line-ending notices retained, no dependency upgrades.
- Frontend unchanged and already-built production bundle actually used; no redundant frontend build or unrelated Python/Tk full regression.

## OPEN / acceptance boundary

- General curved/open path, arc/skew/root/primitive Transform handling not certified by these straight-path cases.
- Foundation editable SVG's existing unitless dimensions do not automatically restore a document's .5 mm mapping. This remains explicit calibration on that core path; **the tested main-editor physical Web SVG round-trip passes without manual recalibration**.
- Old saved incorrect anchors/transforms are not silently migrated. Old user 8792/8797 pages and the overall artwork closeout are not automatically closed by this isolated-origin acceptance.
- Existing Starlette/httpx warning, other prior OPENs remain. No public/Render/Linux/slicer/physical acceptance this round.
- No commit/push/deploy/backup; STOP after report.

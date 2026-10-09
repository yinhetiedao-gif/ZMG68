# Phase 1A — local implementation and acceptance (2026-10-06)

This is the earlier v1/base-output acceptance record. The subsequent authorized
cells-only/size correction is recorded in [PHASE1A_CELLS_ONLY_ACCEPTANCE.md](PHASE1A_CELLS_ONLY_ACCEPTANCE.md).
Its new recipe v2 defaults supersede v1, without rewriting the historical evidence below.

Local only; awaiting user review. No commit, push, deployment, Production switch
change, new dependency, geometry algorithm change, or Phase 1B implementation.

## 1. State and protection

- Branch: `feature/pattern-library-reuse`.
- Baseline/current Git HEAD: `b5338a9af41d25ccd191d34366115578265920bb`.
- Started clean, index remains empty. Final changes are uncommitted Phase 1A files.
- No stopped Dot patch restored or merged. Initial state contained no such diff.
- Baseline tracked Web source archive: `work/phase1a-20261006/baseline-web.zip`.
- Render Live dashboard remains UNKNOWN; public acceptance NOT TESTED this round.

## 2. Changed files and reasons

Production files (all Web only):

- `web/src/App.tsx`: App-owned compute coordinator, shortcut height commits,
  save-before-recipe/reset, same-frame save guard, pending Layout preservation.
- `web/src/manufacturing/computeRequests.ts`: synchronous single-flight guard for
  the four existing conflicting POST endpoints. UI cancellation does not abort
  the actual HTTP compute request; it drains before releasing the guard.
- `web/src/manufacturing/ManufacturingPanel.tsx`: conflict-button feedback,
  direct uniform/directional height controls and one complete recipe/reset.
- `web/src/manufacturing/FabricPreflightPanel.tsx`, `FabricFusionPanel.tsx`:
  handler checks plus disabled compute buttons; downloads remain result-gated.
- `web/src/manufacturing/useManufacturing.ts`, `useFabricPreview.ts`:
  handler entry checks and complete DTO invalidation, retaining abort/sequences.
- `web/src/api/requestErrors.ts`: flat ErrorDTO, nested error, detail string/
  object/validation-list parsing; truthful HTTP fallback and optional failure ID.
- `web/src/api/fabricCandidate.ts`, `fabricFusion.ts`, `fabricPreview.ts`,
  `manufacturing.ts`: consume that error parser without changing successful DTOs.
- `web/src/document/fabricModifiers.ts`: owned Linear height field, uniform
  disable, world-mm projection and copy isolation for shared references.
- `web/src/document/fabricPresets.ts`: additive version-1 directional recipe;
  original five preset algorithms unchanged.

Tests/tools:

- `web/src/App.phase1a.test.tsx`: editor/Undo/save-failure/pending Layout/late-task
  lifecycle and new controls' transient/release/invalid-range recovery.
- `web/src/manufacturing/computeRequests.test.ts`: duplicate/cross-entry guard,
  cancellation draining, recovery, old/new lock ownership and error formats.
- `web/src/document/fabricHeight.phase1a.test.ts`: ownership/reference isolation,
  recipe Reset/draft, unchanged source and units/assets.
- `web/src/test/phase1aFixture.ts`: small shared frontend test data, not an engine.
- `tests/test_web_staging.py`: verifies the existing backend slot rejects all
  three Fabric endpoints while an ordinary build runs; health remains available.
- `tests/test_phase1a_dimensions.py`: existing API pipeline across scale, pixel
  units, non-square and nonzero origin through actual STL bytes/readback.
- `tools/phase1a_local_smoke.cjs`: isolated Edge + production build, UI actions,
  four screenshots, real downloads, reset/history/refresh and mouse slider.
- `tools/phase1a_readback.py`: unchanged STLExporter reload and MeshValidator.
- This record and `GATE_STATUS.md`: local evidence/boundaries, no stable freeze.

## 3. Request reliability

The guarded endpoints are manufacturing/build, fabric/preview, fabric/candidate
and fabric/fusion. The coordinator lives in App, survives mode/panel switches,
uses a synchronous token, and releases only its own actual finished request.
It does not serialize health/evaluate/diagnostics/STL downloads. Existing old
response rejection remains in the consuming hook/panel. Network failure is not
proof of remote CPU cancellation: a later real server 429 is still possible and
is displayed as busy, not geometry failure. No retries or higher concurrency.

## 4. Height and ownership

Uniform height uses cell.height_mm and disables only the height consumer; no
field creation/deletion and no scale/density/orientation changes. Fixed base
width/depth remain explicitly distinct from follow-pattern and Fabric Scale.

Directional height uses existing LinearField + existing Height mapping. Explicit
choice creates one owned field, complete angle/start/end values from final-mm
projection, one binding and one document revision/Undo. Repeated selection
reuses only the marked field. `web_fabric_height_effect` stores version and ID.
Reference scanning excludes this consumer/ownership metadata, conservatively
checks other Fabric modifiers, document modifiers, Composite and legacy metadata.
If referenced elsewhere, it copies to a new dedicated ID without modifying or
deleting the old field. Advanced field editing remains available.

## 5. Complete recipe

`direction-gradient`, version 1, mm, scope explicitly declared. Pyramid
2.4×2.4×3 mm, Fixed Size, Solid 0.6 mm with 1 mm margin, Pattern Points, Linear
angle 0 with final-geometry projection range, Height 2–6 mm. Other Fabric
consumers disabled; their saved parameters/references preserved. No randomness
is used (seed explicitly null). Runtime metadata records resolved field ID and
complete parameters. Apply and Reset save current draft first, then one normal
commit. Reset rebuilds all declared scope, not only numbers. Unknown metadata,
original elements/Layout/assets stay unchanged. Pending Layout is kept outside
Document and rebased so later Apply cannot erase the Fabric edit.

## 6. Browser and visual evidence

URL: `http://127.0.0.1:8791/`; independent browser context and independent local
FastAPI process, production React dist. Only that process uses the existing
staging/testing export flag. No public requests or existing user draft changes.

Fixed input: 100 squares, actual 2D bounds (10,20)..(70,80) mm, 60×60 mm,
100 Pattern Points, Pyramid, Solid 0.6 mm, 1 mm margin. Default entity style,
1600×1100 viewport, Reset View isometric camera, Z up.

- `default.png`: 0°, 2–6 mm; clear monotonic directional ramp.
- `horizontal-gentle.png`: 0°, 2–4 mm; lower, gentle ramp.
- `diagonal.png`: 45°, 1–6 mm; diagonal corner-to-corner trend.
- `reverse-high.png`: 180°, 2–8 mm; reversed, larger height contrast.

All in `work/phase1a-20261006/`, with actual plan JSON and browser request/response
evidence. Existing image preview inspected actual screenshots; optional glance
CLI unavailable, no dependency installed. Real WebGL canvas rendered, not an
API-only substitute. Fatal page errors: 0. No screenshot pixel-diff claim.

Browser checks: no-Field uniform preview/manufacture/download, explicit recipe,
parameter edits, actual mouse move/release (0 evaluate while moving, 1 on release,
0 automatic final manufacturing), Reset/Undo/Redo plan equality, saved draft
refresh equality and fresh Undo session, stale export disabled, ordinary STL.

## 7. Units and output

Non-square/nonzero-origin API regressions cover mm×1, mm×2 and px×0.25 mm/unit.
Final instance XY = evaluated world-mm XY; fixed cell width/depth remain mm;
base adds a 1 mm margin, not a scaled source-unit margin. Final mesh and STL
bounds match separately. Unmapped pixels are rejected, not guessed. Existing
image sampling/mm registration and asset expiry/reupload regressions pass.

Actual browser download + existing strict readback:

| File | XYZ mm | Components | Bytes | Faces |
| --- | --- | ---: | ---: | ---: |
| uniform-fabric.stl | 62×62×3.6 | 1 | 50684 | 1012 |
| directional-fabric.stl | 62×62×8.5 | 1 | 50684 | 1012 |
| standard.stl | 60×60×2 | 100 | 60084 | 1200 |

All finite, watertight, positive volume, zero degenerate faces, no validator
errors. Standard's multiple-component warning is expected, not a Fabric gate.
Actual files, final reports and `stl-readback.json` are under the evidence dir.

## 8. Commands and results

From web (16 affected files, not all unrelated frontend tests):

```text
npm test -- --maxWorkers=2 src/App.phase1a.test.tsx src/manufacturing/computeRequests.test.ts src/document/fabricHeight.phase1a.test.ts src/document/fabricPresets.test.ts src/document/fabricModifiers.test.ts src/manufacturing/FabricFusionPanel.test.tsx src/manufacturing/FabricPreflightPanel.test.tsx src/manufacturing/useFabricPreview.test.tsx src/App.f1.test.tsx src/App.examples.test.tsx src/App.p2c.test.tsx src/document/realSize.test.ts src/api/imageAssets.test.ts src/document/ParameterPanel.test.tsx src/manufacturing/StlExportButton.test.tsx src/manufacturing/FabricThreePreview.test.ts
```

88/88 PASS. Final error-format change subset: 17/17 PASS.
`npm run build`: PASS, existing large-bundle warning retained.

```text
python -B -m pytest -q tests/test_web_staging.py tests/test_fabric_stl_f5c.py tests/test_fabric_preview_f25.py tests/test_fabric_fields_f3.py tests/test_image_fabric_f4a.py -k "not 5000"
```

34 PASS +13 subtests, 3 deselected (5000 cases deliberately out of scope).

```text
python -B -m pytest -q tests/test_phase1a_dimensions.py tests/test_web_staging.py
```

5 PASS; staging's two tests overlap the prior command, not 39 distinct tests.

`node tools/phase1a_local_smoke.cjs` with existing PLAYWRIGHT_MODULE: PASS.
`python -B tools/phase1a_readback.py` with repository PYTHONPATH: PASS.
`git diff --check`: PASS. No dependency or deployment config changes.

## 9. Failures retained and limits

- Initial refactored 404 parser lost old route guidance: fixed, existing test
  now passes without weakening its assertion.
- New test selectors and one TypeScript inferred test type were corrected;
  failed test/build runs are not counted as PASS.
- Initial hand-written browser fixture lacked official serializer defaults and
  ordinary manufacturing correctly rejected it with 409 stale_revision. Test
  now passes data through the official serializer, like imports/examples. No
  backend consistency guard or geometry changed to bypass that rejection.
- Optional vision CLI unavailable; actual screenshots inspected via existing
  local image preview, not invented image descriptions.
- Existing bundle and TestClient deprecation warnings retained. Original five
  presets retain old behavior, including type-based field reuse: not migrated
  or claimed to have new ownership guarantees.
- No new geometry-core defect identified. No extra scope requested.
- Public/Render acceptance, slicer, physical print: NOT TESTED. Tk full suite,
  5000 geometry fix, three-recipe Phase 1B: intentionally NOT RUN/NOT IMPLEMENTED.
- Local modifications await user review; do not freeze or declare F5 physical PASS.

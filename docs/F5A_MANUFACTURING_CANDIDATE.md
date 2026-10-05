# F5-A — Manufacturing candidate and preflight

Baseline: `7401621d86db3a972bc6f8c870a310dc0f88a04b`.
Feature branch: `feature/f5-fabric-manufacturing`.
Stable reference after acceptance: `backup/f5a-manufacturing-candidate-final`.

## Scope and model

`build_fabric_design` is the existing evaluate/placement/Field pipeline extracted
into one shared, UI-independent entry. Preview retains its existing sampling;
candidate requests a complete plan. Candidate creation consumes that plan without
evaluating any Field, Density, Image, Distance or Orientation again.
Full placement-center bounds are carried by the plan, so display sampling does
not change the Shared Field context. A 6000-point test with an extreme point
omitted from the preview verifies identical retained instance transforms.

`FabricManufacturingCandidate` contains the F1 base mesh, enabled transformed
prototype copies, exact TRS matrices, unfused aggregate mesh and a report.
No candidate is written into PatternDocument, history, manufacturing result store
or STL/GLB exporters. `/api/v1/fabric/candidate` returns only the report, no mesh
download URL. It uses existing asset resolution, revision guard, threadpool and
staging concurrency protection. No new dependency was added.

Prototype creation is cached by existing UnitCellDefinition; transform copies
use final width/depth/height divided by prototype dimensions. Rotation is Z,
translation is final world mm. Pattern Scale and Fabric Scale are not reapplied.
One prototype-component analysis occurs per candidate, not per instance.
Face-area checks use vectorized arithmetic, not N global MeshValidator calls.

## Attachment facts

Read-only STRtree indexes actual F1 extruded top triangles, including Grid holes.
Bottom footprints are measured against nearby material only; penetrated cells
use the actual base-top plane section instead of pretending the bottom footprint
is the contact area. No mesh Boolean, welding, repair or triangle removal occurs.

- Existing distance tolerance: ManufacturingGeometryAdapter `1e-6 mm`.
- Existing triangle area threshold: MeshValidator `1e-12 mm²`; not relaxed.
- ATTACHED: measurable material contact within the existing distance tolerance.
- MARGINAL: near-contact up to `10 × distance tolerance`, contact less than
  `5%` of footprint or below `epsilon × footprint perimeter`.
- DETACHED: no material under footprint/section or larger vertical separation.
- INVALID: nonfinite/invalid transform, effectively zero dimensions/height,
  below-base bottom or degenerate transformed triangles.

All enabled instances retain IDs, source/final geometry IDs, measurements and
severity-coded diagnostics, including invalid cases. Disabled density instances
are not instantiated. Nonfinite candidates have no aggregate mesh/bounds;
finite invalid meshes remain diagnostic candidates, never exportable results.
ATTACHED means contact only: `fused=false`, `export_available=false` always.

Component counts are pre-fusion topology facts. The post-fusion target is a
conservative estimate; cell-to-cell contact and future Boolean effects are not
analyzed. DoubleTower's separate prototype bodies are checked separately.

## Fixtures and parity

Tracked `solid_100_fixture()` in `tests/test_fabric_candidate_f5a.py` is the
60×60×0.6 mm, 10×10 Pyramid fixture, height 3 mm: 100 attached,
actual bounds `[0,0,0]..[60,60,3.6]`, pre-fusion 101 components.
Grid spacing 6 mm / line width 1 mm with the same sampling: 100 detached,
zero contact area. Moving a cell onto Grid material passes; tiny edge contact
is MARGINAL. Penetrated Pyramid section area is independently checked.

All five prototype types are deterministic. Pattern Points plus 2D Size,
Rotation, Position and Image/Distance Height/Scale/Density/Gradient Orientation
match preview instance data; explicit matrix tests verify no double scale.
6000-instance full plans are not silently capped at the 5000 preview limit.
Requests above 50000 instances are explicitly rejected as a check resource
budget; no design setting or instance is silently modified.

## Performance (local Python 3.12, Solid, Pyramid)

Milliseconds; measured single runs, not an SLA. Bounds timing is nested in
transform generation; stages should not be blindly summed. Memory estimates
include mesh numeric buffers, not Python objects, report, spatial index or RSS.

| Enabled | Plan | Base | Prototype parts | Transforms | Contact | Assembly | Bounds | Candidate total | Mesh buffers |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|100|0.55|3.12|0.27|13.05|12.91|3.89|0.92|34.13|53,760 B|
|400|1.37|1.51|0.15|49.99|45.76|22.66|3.71|123.26|212,160 B|
|1000|2.80|1.09|0.15|124.71|138.35|35.45|8.34|307.06|528,960 B|
|5000|15.62|1.42|0.16|688.25|552.21|246.60|42.02|1526.99|2,640,960 B|

Use `tools/profile_fabric_candidate_f5a.py` to repeat. Grid top-material queries
are spatially indexed rather than scanning all holes/cells per instance.
Higher-resolution Cylinder/Cone and penetrated cross sections can cost more;
these figures are not advertised as all-cell/all-base benchmarks.

## Acceptance

- Python affected suite: 103 passed, 43 subtests; exit 0.
- Web: 177/177 passed, 42 files (`--maxWorkers=2`).
- TypeScript/Vite production build passed.
- Production browser smoke: existing built-in project through actual UI,
  Solid 64/64 contact; Grid 64/64 detached; revision change invalidates report;
  no fatal page errors. No project JSON injected into product state.
- Existing 169 Shared Field manufacturing matrix, ordinary manufacturing,
  API, STL round-trip and performance cache regressions passed.

Known limitations: no cell-to-cell connectivity/fusion, printable/watertight
claim, final Fabric STL or physical-print validation. Preview may be simplified
above 5000; complete manufacturing candidate is never the sampled preview mesh.
Sampled instances share full Field context; undisplayed instances do not appear
in the simplified preview. Existing bundle-size and TestClient warnings remain.
No Render deployment or unrelated full Tk regression was performed.

## Changed files / rollback

Modified: fabric_base.py, fabric_plan.py, fabric_preview.py, web/app.py,
fabric_field_modifiers.py (full-plan sampling context only; no algorithm change),
web/src/App.tsx, web/src/manufacturing/ManufacturingPanel.tsx, GATE_STATUS.md.
Added: fabric_candidate.py, test_fabric_candidate_f5a.py, profile and browser
smoke tools, fabricCandidate.ts, FabricPreflightPanel.tsx and its tests, this doc.
Deleted: none. F5-B has not begun.

Non-destructive rollback into a new checkout (destination must not already exist):
`git worktree add --detach ../f5a-baseline-review backup/f4c-orientation-stability-final`

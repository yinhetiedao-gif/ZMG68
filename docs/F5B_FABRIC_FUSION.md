# F5-B — True fabric fusion and final mesh validation

Baseline: `bb58d0d0270f19bb2017ec09da6e6b964a2599bb`.
Branch: `feature/f5-fabric-manufacturing`.
Pre-change protection: `backup/pre-f5b-fabric-fusion`.
Accepted reference: `backup/f5b-fabric-fusion-final`.

## Backend selection and exact contact gate

Initial environment had trimesh 4.12.2 but no available Boolean backend:
manifold3d absent, Blender/OpenSCAD not on PATH. Existing repository unions
were 2D operations, not a reusable 3D fusion engine. Added only the headless
`manifold3d==3.5.4` Web dependency. Its [published wheels](https://pypi.org/project/manifold3d/3.5.4/)
include CPython 3.12 Windows and manylinux x86_64. Both wheels were actually
installed/downloaded respectively. Existing Python 3.12 Debian Bookworm Docker
image already installs libstdc++6. No GUI or new CAD framework is needed.
Linux/Render runtime is **not verified** here: Docker is unavailable and WSL
has no installed Linux runtime. Wheel compatibility is not a cloud deployment PASS.

Use direct Manifold Mesh64 input/output to preserve double-precision world mm.
The installed trimesh wrapper uses float32, so it was not chosen. Native batch
Boolean gave one zero-area triangle for a valid 20-cone Pattern Points fixture
touching the base boundary. A deterministic balanced tree on the identical
Mesh64 operands passed with minimum face area 0.0170371 mm². Therefore the
official strategy is balanced reduction, stable candidate order, no growing
global sequential accumulator, no retry repair or triangle removal.

The initial Fin prototype had inward face winding and negative signed volume.
Corrected its static factory face indices to outward winding. Vertices, shape,
dimensions and transform semantics did not change; this is not runtime repair.
Testing a tiny overlap did not fix the inward solid and that experiment was
removed. All five 100-cell fixtures now fuse at exact coplanar contact.
`interface_overlap_mm=0`, bottom extension=0, final top Z unchanged. No overlap
strategy is shipped, and genuinely separated MARGINAL cells fail connectivity.

## Pipeline and safeguards

`Existing full design plan → F5-A candidate → preflight gate → Mesh64 solids →
balanced true Boolean union → actual connected components → existing
MeshValidator → bounds/positive volume gate → readonly final result/report`.

FabricFusionService consumes only FabricManufacturingCandidate. It does not
evaluate Fields or create another plan. The API resolves current DTO assets and
constructs the existing full plan/candidate once, then invokes the service.
Only enabled instances enter the candidate; no invalid or detached cells are
deleted to make a result pass. INVALID/DETACHED block before Boolean. MARGINAL
must prove real final connectivity; a 5e-6 mm gap fails with two components.
Negative-volume or invalid solid inputs fail with the source instance ID.

Manifold performs solid Boolean geometry operations. Application code does not
call merge_vertices, repair, remesh, face deletion or tolerance welding.
Final MeshValidator remains unchanged: area epsilon 1e-12 mm². Both Manifold
solid decomposition and actual final triangle connectivity must be one component;
finite coordinates, watertight topology, positive signed volume and zero errors
are mandatory. Bounds must equal candidate bounds within existing 1e-6 mm
distance tolerance, with no relative tolerance.

POST `/api/v1/fabric/fusion` returns metadata only, with current document ID and
revision, backend/version, strategy, bounds, measured volume, connectivity and
formal validation report. CPU work remains in the existing threadpool with
staging concurrency protection. Failure stages distinguish candidate, preflight,
backend, boolean_input, boolean_union, connectivity, mesh_validation and bounds.
Failures have failure_id and measurements/component or source IDs when known.
Degenerate output reports minimum triangle area and affected final face indices;
Boolean output face-to-source provenance is not invented.

Existing opt-in failure snapshots preserve DTO/config for replay, stage/backend,
fusion settings, validation/pre/post component counts and a bounded sample of
50 instance diagnostics. No mesh arrays or unbounded per-cell meshes are stored.
The returned failure_id matches the snapshot filename. Snapshot output remains
off by default; no static directory exposure is introduced.

## Cache, UI and export boundary

Per-app service cache: at most four results, 30-minute TTL, 128 MiB mesh-buffer
budget. Key covers document identity/revision, actual candidate geometry buffers
and shapes, backend version and fusion configuration. Identical valid candidates
do not run Boolean again. Immutable mesh buffers and copied report metadata
prevent caller report mutation. One service lock provides single-flight fusion.
Candidate reconstruction still occurs on repeated API requests; no claim of
skipping evaluate/candidate work is made. Cache and candidate budgets do not
bound transient native Boolean peak memory; 5000 is measured below.

Fabric manufacturing page shows the existing preflight and a new final mesh
button/status/report. Revision changes immediately invalidate the result;
AbortController plus request sequence discards late responses. UI neither changes
PatternDocument nor creates history entries. A strict success-contract guard
rejects stale identities, weak validation or export-enabled responses.

Final meshes are not inserted into the ordinary manufacturing artifact store.
The existing Fabric STL disabled button remains. Ordinary 2D manufacturing,
GLB and STL services remain separate and unchanged. No F5-C or print claim.

## Fixture acceptance

- Solid 60×60×0.6 +100 Pyramid (2×2×3): one component, watertight,
  zero degenerate faces, volume 2560 mm³, XYZ 60×60×3.6 mm.
- Pyramid/Cone/Fin/DoubleTower/Cylinder: 100 cells each, one final component,
  zero validator errors, zero overlap. Fin winding regression included.
- Grid valid: 100 cells on actual material, true union and one component.
  Grid hole: 100 detached cells rejected before Boolean, IDs retained.
- Cell-cell overlap reduces volume relative to the unfused sum and remains one
  component. No touching-only or concatenation claim is used as proof of fusion.
- Distance→Height + Gradient Tangent/offset: 400 Area Fill and 100 Pattern Points,
  combined with 2D Size/Rotation/Position, fuse and preserve candidate bounds
  without changing the source DTO. Existing F5-A preview/candidate parity passes.
- Determinism, cache reuse/isolation/TTL/revision and API no-STL boundary pass.
  Failure snapshot replay information is tested through the actual API.

## Performance

Single local Windows CPython 3.12 run, 60×60×0.6 Solid, Pyramid 0.3×0.3×3 mm.
All requested enabled instances are real; no preview sampling. Milliseconds.
Candidate column includes plan creation. Fusion total excludes candidate.
Peak is observed **process-lifetime cumulative peak working set**, not per-case
incremental allocation and not Render memory. Other cell shapes cost more.

|Enabled|Candidate|Prepare|Boolean|Connectivity|Validator|Fusion total|Combined total|Peak MiB|Result|
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
|100|36.93|3.60|4.77|0.15|35.09|43.62|80.55|56.82|PASS|
|400|127.26|9.39|14.15|0.19|109.25|132.98|260.23|85.18|PASS|
|1000|325.22|19.34|45.34|0.34|301.49|366.51|691.73|85.18|PASS|
|5000|1832.93|98.39|398.25|1.42|1713.27|2211.34|4044.27|170.18|FAIL validation|

5000 genuinely ran to completion, one closed connected component and positive
volume, but produced **38 degenerate faces, minimum area 0**. Official Validator
rejects it, final-ready=false; no face deletion, repair, precision reduction or
threshold relaxation. Native batch also failed this fixture (56 degenerate
faces). This is a genuine current backend/triangulation limitation, not a PASS
or timeout. Increasing scale/count is not silently altered. The core 100/400
gates and actual 1000 benchmark pass; user explicitly allowed a failed 5000 try.

For 100-cell variants fusion totals: Cone 202.17 ms, Fin 50.19 ms,
DoubleTower 692.64 ms, Cylinder 340.45 ms. MeshValidator dominates these cases.
Repeat: `python -m tools.profile_fabric_fusion_f5b` from repository root.

## Regression and production browser

- Python affected suite: 118 passed +43 subtests, exit code 0. Includes F1–F4,
  F5-A/F5-B, 169 Shared Field matrix, ordinary manufacturing/API/STL and snapshots.
- Web: 181/181, 43 files; TypeScript/Vite production build PASS.
- Headless Edge actual production UI: builtin example→Solid→64 Pyramid final
  mesh ready, one component, watertight, zero degenerate; repeated request cache
  hit same ID; Grid switch stale, hole case 422 preflight with failure_id;
  Fabric STL disabled. Fatal page errors zero. Local production build only,
  not Render/public or manual physical-print acceptance.
- Existing bundle-size/TestClient warnings retained. No unrelated Tk full suite
  was run, and its known infrastructure issue is not relabeled PASS.

## Changed files and rollback

Modified: GATE_STATUS.md; xiaomang_pattern_lab/fabric_cells.py,
requirements-web.txt, web/app.py, web/failure_snapshot.py;
web/src/manufacturing/ManufacturingPanel.tsx.
Added: this doc; xiaomang_pattern_lab/fabric_fusion.py;
tests/test_fabric_fusion_f5b.py; tools/profile_fabric_fusion_f5b.py,
tools/smoke_fabric_fusion_f5b.cjs; web/src/api/fabricFusion.ts;
web/src/manufacturing/FabricFusionPanel.tsx and FabricFusionPanel.test.tsx.
Deleted: none. The normal manufacturing algorithms and MeshValidator unchanged.

Non-destructive rollback in a new, nonexistent destination:
`git worktree add --detach ../f5b-baseline-review backup/f5a-manufacturing-candidate-final`.
Completed F5-B only; do not enter F5-C.

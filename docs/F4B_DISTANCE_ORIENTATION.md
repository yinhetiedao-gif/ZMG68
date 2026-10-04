# F4-B Distance Field & Gradient Orientation

Status: PASS — local targeted tests and actual production-browser smoke, 2026-10-04.

Baseline: `7d0afef3bd0802d8c9087f54d7106b315f3d7cc7`,
`backup/f4a-image-driven-fabric-final`. Branch: `feature/f4-image-driven-fabric`.
Pre-change rollback reference: `backup/pre-f4b-distance-orientation`.
Final stable reference: `backup/f4b-distance-orientation-final`.

## Contract and implementation

- Shared Fields still return scalar 0..1. Distance extends the existing ImageField
  loader, pinned pixels, asset boundary and UV mapping; no new dependency.
- Black foreground is selected using threshold. Inside distances are measured to
  foreground boundary samples; boundary/outside are zero. Inversion is performed
  after bilinear interpolation, only inside the mask. Automatic normalization uses
  the mask's maximum internal distance. Otherwise `max_distance_mm` is the cap.
- A separable Euclidean transform weights each axis by world-mm raster pitch.
  Standard evaluation uses the document unit factor; Fabric uses its existing mm
  context. Canvas zoom/pan are not inputs.
- Distance rasters are read-only, cached by pinned source pixels, bounds,
  threshold, invert and normalization configuration. Cache is bounded by eight
  entries and a 64 MiB retained-data budget. Transform is not run per instance.
- Orientation retains Value mode. Gradient consumes the scalar field through
  central differences using raster/world-mm deltas. Normal uses atan2; Tangent
  adds 90 degrees. Finite angle offset is applied once. Flat gradients retain the
  inherited/base rotation, without offset or jitter.
- Pattern Points continue using Final Geometry position, relative scale and
  rotation. Fabric scale multiplies inherited scale once; Fabric orientation adds
  inherited rotation once. No instance-derived state is persisted in the document.
- Distance parameters and orientation selects use the existing Python parameter
  definitions and Generic ParameterPanel. Image binding, IndexedDB Blob restore,
  transport-only re-upload and one retry after unresolved assets reuse F4-A.
- No manufacturing geometry, MeshValidator, Boolean, final Fabric STL or F5 work.

## Acceptance

- Circle center height, inverted edge height, ring Fin Tangent, ring Fin Normal,
  and combined Height/Scale/Gradient: PASS in actual browser and scalar tests.
- Pattern Points with 2D Size/Rotation/Position plus Distance Height/Scale and
  Gradient: PASS, no source document mutation or duplicate scaling.
- Refresh restores the source Blob and identical transforms. API expiry/new-store
  tests reject dead bindings; Web tests verify re-upload without revision change.
- Production UI (no project JSON loader): add Distance, upload PNG, configure
  Height/Scale/Gradient through generic controls, preview 64 Fin instances: PASS.
- Browser slider movement produces zero evaluate requests; release one. No fatal
  page error. Existing normal manufacturing/API/STL regressions pass.

## Measurements

Local 101×101 mask, 40×40 mm, single-run browser measurements (not device guarantees).

| Instances | Python cold total ms | Python warm median ms | Browser first ready ms | Browser warm ready ms | Three.js creation ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| 400 | 231.487 | 12.752 | 142 | 94 | 25.3 |
| 1000 | 37.608 | 30.343 | 271 | 88 | 20.9 |
| 5000 | 176.223 | 147.145 | 284 | 126 | 21.9 |

The first Python row also includes cold prototype initialization. Each Python cold
run explicitly clears the distance cache; browser first requests do not assert an
empty server cache. Browser warm values are single observations. Python warm
values are medians of five runs.

| Instances | Cold mask ms | Cold distance ms | Warm gradient preparation ms | Warm scalar sampling ms | Warm gradient/orientation ms | Warm plan/prototype ms | Warm serialization ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 400 | 0.453 | 7.014 | 0.003 | 3.976 | 6.044 | 10.799 | 1.160 |
| 1000 | 0.296 | 6.593 | 0.003 | 9.784 | 15.167 | 26.277 | 2.725 |
| 5000 | 0.259 | 6.448 | 0.004 | 47.563 | 76.289 | 126.330 | 14.065 |

These stages overlap: sampling/gradient are inside modifier application and the
plan. They must not be summed. Warm mask/transform time is zero (cache hit).

## Tests and reproduction

- Python broad affected suite: 116 passed, 67 subtests passed, exit 0.
- Additional contracts/API/manufacturing/snapshot/STL suite: 43 passed, exit 0;
  includes 12 overlapping F4-B tests. Total unique tests: 147, not 159.
- Web: 173/173, 41 files. TypeScript/Vite production build PASS.
- `python -m tools.profile_distance_fabric_f4b` generates ignored fixtures and
  `work/f4b/python-performance.json` using the existing document/preview factory.
- `tools/smoke_distance_fabric_f4b.cjs`: existing test-mode fixture loader, real HTTP
  and real Three.js, controlled via F4B_SMOKE_URL (default localhost:8767).
- `tools/smoke_distance_fabric_public_f4b.cjs`: production UI via the built-in
  example and file input, default localhost:8768. Both use PLAYWRIGHT_MODULE when
  Playwright is supplied by the local bundled runtime. Evidence is in ignored
  `work/f4b/`; the two isolated servers use the existing formal FastAPI entry.

## Known limitations

- Boundary is the raster boundary sample, not an analytic contour. Thin masks and
  direction at the mask discontinuity are resolution-dependent.
- Large source images have not been performance-certified by these small-mask
  measurements; preprocessing is linear in pixel count and happens on cold input.
- Existing large frontend-bundle warning and TestClient deprecation notices remain.
- No Render deployment, physical print validation or final Fabric STL was claimed.
- Unrelated full Tk regression was not run in this targeted scope. Existing Tk
  infrastructure issues are not described as resolved by F4-B.

STOP: no F5.

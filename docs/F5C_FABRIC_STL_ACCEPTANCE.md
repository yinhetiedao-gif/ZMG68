# F5-C Fabric STL acceptance — INCOMPLETE

Baseline: `709579af59398fe620d7945ffad39ae85b7461e6`, branch
`feature/f5-fabric-manufacturing`. No Software PASS, physical certification,
or final physical backup is declared.

## Export contract

The cached `fabric-final-*` result has its own namespace. Export verifies the
document identity, revision and canonical DTO fingerprint against that cached
result. Fusion settings and candidate content remain in the fusion fingerprint.
No evaluation or Boolean is repeated at download. The existing `STLExporter`
validates and serializes the exact cached final mesh. Binary STL is then reopened
and validated before returning bytes. One component, watertight topology,
positive volume, unchanged bounds and triangle count, and zero degenerate faces
are required. Float32 STL bounds tolerance is explicit; MeshValidator tolerances
are unchanged. Artifact bytes share the existing bounded in-memory cache.

`XIAOMANG_FABRIC_STL_TEST_EXPORT=1` enables the testing download only in
development/staging. Production and all environments by default remain closed.
The UI says testing, not physical certification. Revision changes invalidate
the download and late responses are discarded. Standard STL is unchanged.

## Local evidence (2026-10-05)

Basic, rotated Fin, Distance Height/Tangent Orientation, Pattern Points with
2D Size/Rotation/Position, and 1000-instance export/reload pass. Each reopened
STL has one component, watertight topology, positive volume and zero degenerate
faces. The real 5000-instance fixture still fails with 38 degenerate faces;
fusion API returns an error and no successful STL artifact is available.

Production-build browser smoke downloaded a binary STL through the actual
testing button. Revision changes and failed fusion disable it; page errors: 0.
Ordinary manufacturing/STL, 169-field matrix, snapshots and F1–F4 affected
regressions passed (122 tests plus 43 subtests). Final export/fusion/ordinary
STL/performance subset: 24 passed.

Measured local Pyramid fixtures (milliseconds; not cloud measurements):

| Instances | Boolean | Final validation | STL serialization | Reload | Candidate-to-STL total | Bytes | Triangles |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 100 | 5.87 | 33.30 | 0.38 | 4.41 | 152.93 | 50684 | 1012 |
| 400 | 13.71 | 117.14 | 0.82 | 10.66 | 534.64 | 200684 | 4012 |
| 1000 | 42.57 | 322.42 | 1.31 | 26.22 | 1337.62 | 500684 | 10012 |

Total includes candidate generation, fusion, exporter validation, serialization,
reload and round-trip validation. Timings vary and do not include cloud transfer.
The profile tool reproduces these fixtures without a 1000-instance hard limit.

Representative physical test file generated under ignored runtime storage:
`work/f5c/20261005T073603859173Z/distance-area_fill-60mm.stl`.
It has 144 Fin instances, base thickness 0.6 mm, bounds
60 × 60 × 6.984666824 mm, 1740 triangles, 87084 bytes.
No printing or slicing success is inferred from this mesh validation.

## Outstanding gates

- Actual slicer import, dimensions, repair warnings, slice and layer preview:
  NOT VERIFIED. Bambu Studio is installed; computer-use initialization failed
  twice (`failed to write kernel assets`, missing path), including after reset.
- Linux/Render native runtime, 100-instance and 400-instance Distance export:
  NOT VERIFIED. No local Docker/usable WSL; Render browser access failed.
- Physical print: WAITING FOR USER, only after Software PASS.

One full Web rerun observed a pending-draft beforeunload assertion failure in
`App.p2c.test.tsx`; its isolated rerun passed without changes. Do not label this
as a proven pre-existing issue without baseline evidence. Bundle-size and
TestClient deprecation warnings remain. No unrelated Tk suite was run.
The final full Web rerun passed 182/182; production build passed.

No F5-C official PASS commit or physical backup until the required gates pass.

## Final-mesh / test-export linkage fix (2026-10-05)

Branch and HEAD unchanged; all earlier uncommitted F5-C files were copied before
this change into `work/f5c-linkage-20261005T0816118413088Z/`.
The supplied screenshot itself was not attached and the existing tabs were blank;
the actual current Vite click path was therefore replayed without replacing the
user's draft or requesting a project export.

Observed first request: `POST http://127.0.0.1:8765/api/v1/fabric/fusion`,
revision 2, HTTP 404, body `{"detail":"Not Found"}`. No result/failure ID or
mesh validation report existed because no fusion route was reached. OpenAPI
confirmed that 8765 and 8766 lacked both fusion and Fabric STL routes; the
independent 8773 process had them. Frontend response handling had generalized
this route error, while its status line still represented any missing report as
not generated. A separate preflight panel's untouched state was not evidence
that the fusion endpoint skipped its internal preflight.

Only the verified current-project 8765 service (old PID 25012) was restarted
with the project virtual environment and current working tree. New PID 35900,
same module `xiaomang_pattern_lab.web.app:create_app`. Local development:
`XIAOMANG_FABRIC_STL_TEST_EXPORT=1`, `XIAOMANG_ENV=development`.
The existing contract now reports the effective boolean capability using the
same flag as the fusion/download endpoint, not a second feature switch.
Production remains disabled even if this flag is set. The older 8766 service
was not restarted; the accepted development URL is `http://127.0.0.1:5173/`.

Frontend now distinguishes idle, building, failure, stale/expired, validated
with export disabled, and validated with test export enabled. Public failure
text preserves stage (translated), HTTP status/reason and failure ID; raw
diagnostics remain in details. Document content as well as identity/revision
invalidates old state; late requests remain aborted/discarded. An expired server
result disables downloads until regenerated. A disabled-export response updates
capability feedback rather than falsely reporting a mesh failure. Preview and
independent preflight copy no longer override final mesh capabilities with fixed
old-stage language. Test-export-disabled API errors return 403, not 500.

Final real Vite browser test: existing circle example, Solid Base, Pyramid,
4-mm placement spacing, 100 instances. Fusion and STL responses both HTTP 200,
revision 4, identical current request DTO. Result:
`fabric-final-13f56a7e1e725781fadb712ed1df0c335058c5a8dd329b95c0585bfe657ce1b2`;
document fingerprint `5f957359e1710542b6f37cca5d101d9ab5045deb0a4f09fd8d3315aade658927`.
Binary file 50684 bytes, 1012 triangles, readback bounds 40 × 40 × 3.599999905
mm, positive volume 1360.000022252 mm³, watertight, one component, zero
degenerate faces and validator errors. No second fusion was called for export.
Evidence: `work/f5c-linkage-browser-1791188789599/` (request/response JSON,
STL, ready/failed screenshots). Browser fatal errors: 0.

After design modification the old download was disabled. Actual Grid-hole
failure: HTTP 422, code `fabric_fusion_failed`, stage `preflight`, failure ID
`de41180b1fd04932b8c0709bf16def54`; the opt-in local failure snapshot exists.
It contains the document/settings/validation summary, not STL/base64. Separate
local production-build browser with flag 0 validated 100 instances successfully
and correctly disabled export without displaying generation failure; its
temporary server was stopped, not any user/development server.

Affected Web tests: 52/52. Fabric export/API plus Standard STL regression:
Python 20/20. TypeScript/Vite build: PASS. No manufacturing algorithm,
MeshValidator tolerance, source document or fusion geometry changes in this
linkage repair. C1 remains incomplete pending slicer and Linux/Render runtime.

Files changed in the linkage repair (earlier F5-C implementation retained):
`web/src/App.tsx`, `web/src/api/client.ts`, `web/src/api/fabricFusion.ts`,
`web/src/manufacturing/FabricFusionPanel.tsx`, `FabricPreflightPanel.tsx`,
`ManufacturingPanel.tsx`, `PreviewPanel.tsx`, `fabricCopy.ts`,
`web/src/App.f1.test.tsx`, `web/src/manufacturing/FabricFusionPanel.test.tsx`,
`xiaomang_pattern_lab/web/app.py`, `xiaomang_pattern_lab/web/http_errors.py`,
`tests/test_fabric_stl_f5c.py`, `tools/smoke_fabric_stl_f5c.cjs`,
`GATE_STATUS.md` and this acceptance record. No files deleted.

## Public release alignment checkpoint (2026-10-05)

Read-only evidence: local F5-B HEAD `709579af59398fe620d7945ffad39ae85b7461e6`
had the F5-C implementation uncommitted. GitHub's actual Render-bound branch
`feature/staging-render-deployment` and Render's **Live** deployment both pointed
to `2c9caa76f2973852d99175b4c106ac5b55b8a63b`. Service `ZMG68-1` is Docker/Free;
public URL is `https://zmg68-1.onrender.com/`. Its old health response only had
status/contract 1.0; frontend and backend build identities were UNKNOWN. Contract
1.0 is not a deployment identity. No actual 405 has been captured in this check.

Staging is an ancestor of the current F4/F5-A/B chain, so a fast-forward can keep
existing Docker/Render configuration without a merge conflict. Preview/preflight/
fusion UI is not gated by export configuration. The existing sole flag is
`XIAOMANG_FABRIC_STL_TEST_EXPORT=1`, effective only in development/staging.
It was saved in the authorized Render staging service, not enabled in production.

Minimal release diagnostics retain a separate frontend build SHA (compiled in
Vite from Docker's Render build argument or a clean local Git tree) and backend
runtime SHA (`RENDER_GIT_COMMIT`). Missing/unreliable identity is UNKNOWN.
Health publishes only environment and three explicit capabilities, not paths,
secrets or arbitrary environment data. Existing diagnostics displays both
identities and capabilities independently. Health performs no geometry work.

Related release/API/STL/ordinary manufacturing tests: Python 25 PASS, two 5000
stress cases deselected for this release check (prior strict rejection retained).
Affected frontend tests: 24 PASS. Production build PASS; existing bundle-size
warning remains non-blocking. Docker dependency-cache layout is preserved.

This is a **pending deployment / slicer / physical acceptance checkpoint**.
Public 9-cell A/B/C/D requests, download/readback and Linux representative 100/400
checks must be reported separately after the target commit is Live. No Physical
backup, physical PASS, or Software PASS is created by this checkpoint.

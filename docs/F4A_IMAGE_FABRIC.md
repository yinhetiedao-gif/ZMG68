# F4-A — Image Driven Fabric

Scope: shared raster scalar fields → existing Fabric Height/Scale/Density →
read-only instanced preview. No final Fabric mesh, STL, distance or image orientation.

## One field definition

The existing `shared_fields.ImageField` remains authoritative. Web Parameter
Schema exposes polarity, invert, grayscale/mask, threshold, contrast,
black/white points and outside behavior through the same Generic Renderer.
Source selection only registers a Blob-backed asset; React performs no sampling.

New Web default: black=1, white=0; outside=0 (also when inverted). Grayscale
uses the existing bilinear scalar; mask applies `value >= threshold` after
polarity/invert. Legacy fields keep old defaults (white=1, clamp). SVG remains
geometry input only. The backend checks the registered raster, not the client
MIME claim or a supplied filesystem path.

`sample_bounds=[x0,y0,x1,y1]` stores image registration in document world units.
Web initializes it from the document canvas extent at field creation. Fabric
converts this extent using `mm_per_unit`, then samples instance world-mm XY.
Changing placement or browser zoom/pan does not resize this registration.
Custom image cropping/registration UI is not part of F4-A.

## Existing consumers and inheritance

- Height interpolates minimum/maximum mm without changing XY.
- Scale multiplies inherited Pattern Scale once by Fabric Scale.
- Density uses the existing deterministic threshold, not random per-refresh state.
- Composite can reuse an image scalar. Image-derived Orientation is deferred
  and rejected, including through Composite references.
- Pattern Points keeps Final Geometry position and reliable Z rotation;
  Area Fill keeps existing regular sampling.

One request-level field registry pins decoded pixels. Multiple modifiers bound
to the same field share one scalar per point. The existing prototype cache and
Three.js InstancedMesh remain in use. No per-cell GLB or manufacturing build.

## Asset and draft lifecycle

`PatternDocumentDTO.assets` uses the existing `field:<id>` role. IndexedDB's
existing draft record gains an optional `image_sources` map of stable browser
token → Blob/name/MIME. Uploaded server asset IDs are transient transport
bindings, not permanent design identity.

`imageAssetFetcher` uploads once per token/session and maps a copy of the
outgoing DTO to current server IDs. Refresh creates a new upload session. A
missing/expired server asset triggers one re-upload/retry. Missing local Blobs
give an explicit failure; revision and undo history are not rewritten.
Draft switching/pre-example restore carries the same image_sources map.
Old source Blobs remain available during a session so undo can restore bindings.

The preview cache checks referenced assets before returning a cached plan.
Ordinary manufacturing still uses its existing API, consistency checks,
validator and STL exporter.

## Verification and reproduction

Use the existing project Python environment (pytest restored in that environment).
Bundled Tk tests need the runtime's Tcl/Tk library directories configured.
Do not change tests or product algorithms to hide an environment failure.

- `tests/test_image_fabric_f4a.py`: fixed 101×101 white raster/central black
  circle (v1), PNG/JPEG sampling, world registration, invert/mask, Height/Scale/
  Density, combined/Composite, Pattern Points transforms, mm conversion,
  expired preview assets, spoofed SVG, standard manufacturing/STL.
- `web/src/api/imageAssets.test.ts`: transport deduplication, abort, expiry,
  IndexedDB Blob/rebinding and unchanged canonical document.
- `python -m tools.profile_image_fabric_f4a`: real 400/1000/5000 sample timings
  and reproducible internal loader artifacts under ignored `work/f4a/`.
- `tools/smoke_image_fabric_f4a.cjs`: use `npm run build -- --mode test` for the
  existing internal file loader, serve the current FastAPI/dist on an isolated
  port, then set `PLAYWRIGHT_MODULE` to the already installed Playwright runtime.
- `tools/smoke_image_fabric_public_f4a.cjs`: use normal `npm run build`; verifies
  the actual public UI without a fixture loader or mocked API/renderer.

Both browser scripts accept `F4A_SMOKE_URL` (default isolated localhost:8766).
Restore the normal production build after internal-loader benchmarking. No
existing development server needs to be stopped. Timing artifacts are local
evidence, not a performance guarantee. See GATE_STATUS for measured results.

Modified areas: Shared ImageField/Parameter Schema, Fabric scalar consumers,
server asset resolution, Web image transport, existing Inspector/draft/hooks,
tests and these opt-in probes. No files deleted. Baseline rollback should use a
new detached worktree at `2c9caa76f2973852d99175b4c106ac5b55b8a63b` and retain
the active workspace. F4-A does not publish changes to Render.

# F4-C — Gradient Orientation Stability

Validated locally on 2026-10-05, from `ff42cf47244e1122e824650f6d2a05d440fbc7ab`.
Protection: `backup/pre-f4c-orientation-stability`. Final reference:
`backup/f4c-orientation-stability-final`. No F5 or final Fabric manufacturing.

## Actual cause

Raw central differences are unreliable at nearest-boundary ownership changes
and medial ridges. Fin axes were previously consumed as directional angles,
without neighborhood coherence or a relative gradient-magnitude check.

The original 401×401 failed mask is preserved verbatim in
`tests/fixtures/f4c-spine-401.png`. It contains narrow white fissures in the
black ribbon: it is not a perfectly solid smooth S. Do not attribute every
failed pair to a zero gradient. At its worst pair:

| Position mm | Distance | dF/dx | dF/dy | Magnitude | Raw normal |
| --- | --- | --- | --- | --- | --- |
| 27.5, 31.5 | .543003 | .124030 | -.235650 | .266298 | -62.2407° |
| 28.5, 31.5 | .536656 | -.238381 | -.118993 | .266430 | -153.4730° |

Closest foreground-boundary pixels change from (26.55,33.30) to
(30.30,32.40) mm. Both gradients are substantial; magnitude alone cannot
reject the 88.7677° axial jump. A separate disk-swept solid S control avoids
those fissures without rewriting the failed input.

## Minimal consumer-only change

`orientation_raster.py` prepares gradient-magnitude-weighted cos(2θ)/sin(2θ)
statistics. Spatial Gaussian weighting uses image/world registration, not
screen coordinates or instance spacing/order. Radius is estimated from the
scalar peak / median interior slope, with pixel-pitch and extent limits.

Raw orientation is retained only when coherence ≥ .9 and magnitude > .75
of the median nonzero interior slope. Otherwise the local weighted axis is
used. Coherence < .05 tries a 1.5× neighborhood; still unreliable samples
return None, preserving inherited/base rotation in both Normal and Tangent.
There is no previous-instance propagation, angle-delta clamp, or random state.

Normal/Tangent consume exactly the same stable normal; reliable Tangent adds
90°, followed by the existing inherited rotation/offset composition once.
Only direct Distance gradient consumption changes. Image/analytic/Composite
gradient behavior, scalar Distance raster/sampling, Height/Scale/Density,
PatternDocument and manufacturing geometry/validation remain unchanged.

Cache dependencies include source pixel content, registration bounds, world
unit conversion, threshold/invert/distance configuration and algorithm policy.
Cached immutable statistics are bounded to four entries / 64 MiB of derived
planes. Neighborhood preparation is never repeated per instance. No dependency
was added; NumPy performs the separable zero-padded convolution.

## Results

High neighbors: both enabled, heights >3 mm, adjacent XY grid spacing 1 mm.
Axis differences are normalized to 0–90°, with θ ≡ θ+180°.

| Fixture / mode | >45° pairs | >75° pairs | Maximum |
| --- | ---: | ---: | ---: |
| Original S, raw F4-B | 35 | 6 | 88.7677° |
| Original S, stable Tangent | 4 | 0 | 56.0534° |
| Original S, stable Normal | 5 | 0 | 59.1425° |
| Solid S control, Tangent | 0 | 0 | 21.2457° |

Ring cardinal axes retain zero error modulo 180° at five-decimal tolerance.
All high ring samples vs the ideal analytic circle: mean error 2.3292°, max
7.8936° (pixelated contours are not exact analytic circles). Normal/Tangent
remain 90° apart except deterministic inherited-rotation fallback. The real
right-angle L branch retains >75° axis difference; real corners are not
forced continuous. A straight ribbon's exact zero-gradient ridge recovers
its normal from coherent neighbors; an empty/flat field falls back safely.

Production browser Pattern Points: XY error 0; inherited scales
.5/.833333/1.166667/1.5; rotation-composition error 7.1e-15°. Before/after
original S positions, heights, scales and visibility match exactly. Repeated
and reversed-order samples are deterministic and document state is unchanged.

## Performance

Opt-in profiler: 101×101 circle, same sizes as F4-B reference, one cold run
and five warm runs (median). Milliseconds; preparation is included in
orientation total, which is included in plan total; do not add nested times.

| Instances | Prep cold / warm | Sampling cold / warm | Plan cold / warm |
| --- | --- | --- | --- |
| 400 | 19.81 / .104 | 9.08 / 9.46 | 313.30 / 18.77 |
| 1000 | 19.40 / .094 | 19.84 / 22.55 | 67.07 / 42.15 |
| 5000 | 23.03 / .097 | 113.67 / 108.11 | 254.28 / 200.23 |

The first plan also includes cold existing base/prototype initialization.
Production-browser 401×401 circle, real UI and HTTP, single warm request:
400/1000/5000 ready **166/135/290 ms**, reported instance creation
**15.3/16.2/20.8 ms**. Density leaves 360/892/4460 visible instances; plan
counts stay 400/1000/5000. Cold browser requests are more expensive (about
1.15 s for the first 400 request in this run); these are local measurements,
not cross-device guarantees. No repeated final manufacturing/GLB/STL is used.

Reproduce using `python -m tools.profile_orientation_f4c`, then the existing
production FastAPI entry point serving `web/dist`, and
`tools/smoke_orientation_stability_f4c.cjs` with `PLAYWRIGHT_MODULE` and
`F4C_SMOKE_URL` pointing to the isolated test service.
The profiler reproduces the original visual-gate circle/ring/low-resolution
sources in `work/f4c` and copies the tracked original S without alteration.
`python -m tools.diagnose_orientation_f4c` reads the actual browser payloads.

## Verification and scope

- Python targeted: **71 PASS + 38 subtests**, exit 0. Includes F4-C/F4-B/F4-A,
  Image/asset lifecycle, F1/F2/F2.5/F3/F3.5, 169 Shared Field manufacturing
  matrix, ordinary manufacturing service and API performance regressions.
- Web: **173/173 PASS**. TypeScript + Vite production build PASS.
- Production UI: built-in examples → real raster upload → circle/ring/S,
  Normal/Tangent/offset, threshold/invert/max-distance, Height/Scale/Density,
  400/1000/5000 and Pattern Points combination. No mock API or project-loader
  bypass, no fatal Console errors. Actual screenshots were inspected using the
  built-in image viewer because optional vision-skills commands are unavailable.
- Evidence in ignored `work/f4c`: requests/responses, screenshots, diagnostics,
  timing reports and isolated-server logs. User's running services were not stopped.

Known limitations: low-resolution scalar Distance stair-stepping is unchanged;
the original mask fissures remain; unavoidable direction ambiguity can fall
back to inherited rotation. Existing large frontend bundle/TestClient warnings
remain. No unrelated full Tk regression, Render deployment or physical print
validation was claimed. Final Fabric mesh/STL remain disabled.

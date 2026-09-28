# WM6 — Web Parametric Controls MVP

WM6 extends the existing WM5 web workspace. The browser edits the official
`PatternDocumentDTO` through `web/src/document/editor.ts`; it does not evaluate
fields, modifiers or geometry. Each committed edit increments
`document_revision` once and calls the existing WM3 `POST /api/v1/evaluate`.

## Available controls

- Transform: X/Y, width/height and rotation for an unambiguous free source
  element. Derived or effect-driven elements remain read-only.
- Parametric: existing grid rows, columns, spacing, cell size, rotation and
  origin. Existing explicit basis vectors are preserved and adjusted when
  spacing or rotation changes.
- Field: numeric parameters on existing constant, linear, ring, wave,
  stripe, checker, spiral and noise fields. Existing image and composite
  fields are displayed read-only, with composite references retained.
- Modifier: enable/disable and existing numeric settings for graph size,
  rotation and density layers; enable/disable on existing ordered layers,
  plus numeric settings on ordered position layers. Order is never changed.
- Shape: an existing placement assignment can switch a selected element to
  an existing prototype or restore its original prototype.

There is no creation of new field/modifier types, and the browser never
computes final geometry. Some legacy parametric families and modifier details
remain read-only until their DTO schema can be safely edited.

## Interaction and history

A slider's movement changes only its local draft value. Releasing it commits
one document revision, one Evaluate request and one session Undo entry. Number
inputs commit on Enter/blur. Direct Canvas drag follows the same history path.
Undo and Redo restore committed document snapshots and each re-evaluate once;
revisions remain monotonic. Pan, zoom, selection and draft values are browser
state only and do not change the document. A failed Evaluate preserves the
previous valid geometry, rolls back the attempted document/history change and
shows an error. The right inspector remains reachable below the Canvas on
narrow screens rather than being hidden.

## Verification and limitations

`npm test` (38/38), `npm run build` (TypeScript 0 error), Python full regression
(335/335), fixed-pattern self-test (6/6), Tk smoke (2/2) all passed on
2026-09-28. Web tests exercise the actual 144-dot project file and the actual
physically printed three-star project through the import flow; mocked Evaluate
responses are used for frontend transaction assertions. A local browser with
the real Python backend imported the printed project, displayed all three
filled black stars, changed the first star's path scale from `10` to `14.4`
after a modifier edit, and restored `10` with Undo. Backend Online, contract
v1.0 and narrow-screen inspector accessibility were also checked. The 144-dot
fixture was exercised in Vitest but not in the live browser. The browser's
captured error-level console log was empty; frame-rate measurements were not
collected.

No web project save, image upload, manufacturing UI, Three.js, STL download or
asset upload is provided by WM6. Image-field assets still require the future
asset pipeline. Session Undo/Redo is lost when the browser page closes.

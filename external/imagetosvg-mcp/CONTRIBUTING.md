# Contributing to imagetosvg-mcp

Thanks for your interest in improving this project.

## Development setup

```bash
git clone https://github.com/ujo78/imagetosvg-mcp.git
cd imagetosvg-mcp
npm install      # builds automatically via the prepare hook
```

Requires Node.js >= 20. All native dependencies (`sharp`, `@resvg/resvg-js`,
`@neplex/vectorizer`, `mupdf`) ship prebuilt binaries — no system toolchain
needed. EPS import additionally requires [Ghostscript](https://ghostscript.com/releases/)
on `PATH`; everything else works without it.

## Workflow

- Create a feature branch off `master`.
- This project is test-driven. Add or update a test for any behavior change,
  and keep the suite green.
- Run the checks below before opening a PR.

```bash
npm run typecheck   # tsc --noEmit, must be clean
npm test            # vitest, all tests must pass
npm run build       # tsc -> dist/, must succeed
```

- Match the existing code style: small focused modules, one responsibility per
  file, explicit error handling, no drive-by reformatting.
- Tests use real fixtures (generated at runtime with `sharp` / `pdf-lib`) rather
  than mocking the conversion engines — please keep it that way.

## Project layout

| Path | Responsibility |
|------|----------------|
| `src/convert.ts` | raster -> SVG (complexity heuristic + vtracer) |
| `src/importVector.ts` | PDF/AI (mupdf) and EPS (Ghostscript) -> SVG |
| `src/svgModel.ts` | parse SVG, assign stable layer ids, list layers, bbox |
| `src/inspect.ts` / `edit.ts` / `render.ts` / `optimize.ts` | the per-tool logic |
| `src/server.ts` / `index.ts` | MCP server wiring + entrypoint |
| `skill/SKILL.md` | the Claude skill that teaches the workflow |
| `test/` | one suite per module, real fixtures in `test/helpers.ts` |

## Commit messages

Use clear, conventional-style prefixes (`feat:`, `fix:`, `docs:`, `chore:`,
`refactor:`, `test:`). Keep the subject imperative and scoped to the change.

## Reporting issues

Open an issue with a minimal repro: the input file type, the tool call and
arguments, what you expected, and what happened. Include OS and Node version.

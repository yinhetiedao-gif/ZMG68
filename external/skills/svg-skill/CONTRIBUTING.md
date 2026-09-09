# Contributing

Thanks for your interest in svg-skill (Agent Skill for AI coding tools)!

## What to contribute

- **New scenarios**: add guides to `scenarios.md` and samples to `examples.md`
- **Skill improvements**: workflow and quality checks in `SKILL.md`
- **Test cases**: add fixtures under `test-output/` and update `TEST.md`
- **Bug fixes**: validation script, docs, sample SVG issues
- **README translations**: keep the 中文 section in README.md up to date

## Development workflow

1. Fork the repository
2. Create a branch: `git checkout -b feat/your-feature`
3. Run tests after changes:

   ```bash
   bash test-output/run-tests.sh
   bash scripts/validate.sh test-output/
   ```

4. Open a PR describing what changed and why

## Guidelines

### SVG files

- Must include `xmlns` and `viewBox`
- Non-ASCII text requires `<?xml version="1.0" encoding="UTF-8"?>`
- No placeholder paths or editor metadata
- Decorative icons: `aria-hidden`; informative graphics: `title`/`desc`

### Skill docs

- Keep `SKILL.md` concise; details go in `scenarios.md` / `reference.md`
- `description` in frontmatter: English, third person, with trigger keywords
- Example code must render or run as-is

### Tests

When adding an SVG scenario:

1. Place it under the matching `test-output/` directory
2. Register it in `test-output/TEST.md`
3. Add the path to `EXPECTED` in `test-output/run-tests.sh`
4. Add a preview card in `test-output/preview.html` (recommended)

## PR checklist

- [ ] `bash test-output/run-tests.sh` passes
- [ ] New SVGs pass `scripts/validate.sh`
- [ ] Related docs updated
- [ ] No unrelated files committed (`.DS_Store`, etc.)

## Issues

Please include:

- Agent / tool name and version (e.g. Cursor, Claude Code, Codex)
- Expected SVG scenario or output
- Actual agent behavior (paste conversation if helpful)
- Broken SVG or screenshot when applicable

## Code of conduct

Be respectful and constructive. Focus on technical discussion.

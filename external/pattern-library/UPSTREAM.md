# 小芒图案库 — upstream provenance

Source: https://github.com/catchspider2002/svelte-svg-patterns
Pinned commit: 803e30bfde106cf094581aabfc80ced2062c5ab7
License: MIT, Copyright (c) 2020-2023 pattern.monster.
The original full license remains in LICENSE.md.

Reused unchanged: the 330 pattern definitions, Svelte/Sapper gallery,
search/filter/sort, parameter editor, color picker, live SVG background
preview, random/reset controls, CSS/SVG copy and save-svg-as-png export.

Local changes: Chinese primary controls and name; removed advertising,
analytics, newsletter/personal-service/Pro links; return link; static
Sapper export under /patterns/; one minifier worker for small build hosts.
SVG file download uses the existing live SVG with the chosen export size,
so rotation/position and scale match the preview and PNG.
No manufacturing algorithm or PatternDocument format is introduced here.

Installation: npm ci --ignore-scripts
Native sharp / Puppeteer installation scripts belong to the upstream
offline authoring utilities, not the site/export build; no dependency
versions or lock file were upgraded.
Production static build: node build-static.cjs
Integration: serve __sapper__/export/patterns at /patterns/ using FastAPI.
Verified integrated local URL: http://127.0.0.1:8777/patterns/
Use the main repository's docs/PATTERN_LIBRARY_REUSE.md for the tested startup.

The reference parametric-form-studio repository was also downloaded and
inspected; it contains bundled assets, no reusable source modules or
verified source license. No reference bundle was copied or decompiled.

# SVG Reference

## Encoding & text

Standalone files with non-ASCII characters: save as UTF-8 + `<?xml version="1.0" encoding="UTF-8"?>`; run `xmllint --noout` before delivery.

Pure icons may omit the XML declaration. Formal logos: use paths, not `<text>`, to avoid font dependency.

## Coordinate system

- Origin top-left; x right, y down
- `viewBox="min-x min-y width height"`
- `preserveAspectRatio`: `xMidYMid meet` (default, proportional) | `none` (stretch to fill)

## Path commands

| Command | Meaning |
|---------|---------|
| M/m L/l H/h V/v | move, line |
| C/c S/s Q/q T/t | Bézier curves |
| A/a | elliptical arc `A rx ry rot large-arc sweep x y` |
| Z/z | close |

Pie arcs: center (cx,cy), start at 12 o'clock, large-arc flag 0/1.

## `<defs>` resources

| Element | Purpose |
|---------|---------|
| `linearGradient` / `radialGradient` | gradient fill |
| `pattern` | tiled texture |
| `clipPath` | clipping |
| `mask` | alpha mask |
| `filter` | shadow, blur |
| `symbol` | sprite icon |
| `marker` | line arrows |

Reference: `fill="url(#id)"` `clip-path="url(#id)"` `filter="url(#id)"` `href="#id"` (use)

**id rules**: unique per file; prefix when multiple files share a page.

## Chart coordinate math

```
plotWidth  = viewWidth  - marginLeft - marginRight
plotHeight = viewHeight - marginTop  - marginBottom

barX(i)   = marginLeft + (i + 0.2) * (plotWidth / n)
barH(v)   = (v / maxValue) * plotHeight
barY(v)   = marginTop + plotHeight - barH(v)

linePoint = values.map((v,i) => `${i===0?'M':'L'} ${x(i)} ${y(v)}`).join(' ')
```

## Progress ring formula

Circumference `C = 2 * π * r`; progress p (0–1):
- `stroke-dasharray="C"`
- `stroke-dashoffset="C * (1 - p)"`
- `transform="rotate(-90 cx cy)"` to start from top

## Outline vs filled icons

| Style | Attributes |
|-------|------------|
| Outline | `fill="none" stroke="currentColor" stroke-width="2"` |
| Filled | `fill="currentColor"` |
| Dual-stroke | thick background path + normal foreground (rare) |

## Optimization

1. Merge paths with same attributes
2. Reduce transform nesting
3. Round coords to 1–2 decimals
4. Icons: presentation attributes; use `<style>` only for animation/hover
5. Remove metadata, comments, unused groups

## Accessibility

| Case | Handling |
|------|----------|
| Decorative icon | `aria-hidden="true"` |
| Meaningful graphic | `role="img"` + `<title>` |
| Chart | `<title>` + `<desc>` with data summary |
| Icon in button | `aria-label` on button |

## Framework attribute map

| HTML | React |
|------|-------|
| `class` | `className` |
| `stroke-width` | `strokeWidth` |
| `stroke-linecap` | `strokeLinecap` |
| `fill-opacity` | `fillOpacity` |
| `clip-path` | `clipPath` |

```css
.icon { width: 1.25rem; height: 1.25rem; color: var(--text); }
.icon--em { width: 1em; height: 1em; vertical-align: -0.125em; }
```

## Recommended viewBox sizes

| Type | viewBox |
|------|---------|
| UI icon | 24×24 |
| Compact icon | 20×20 |
| Favicon | 32×32 |
| Chart | data-dependent, often 400×300 |
| Full-width wave | 1200×120 |
| Illustration | 100×100 – 200×200 |

## Compatibility notes

| Environment | Notes |
|-------------|-------|
| Modern browsers | full support |
| Safari mask | needs `-webkit-mask` |
| Email clients | avoid defs/animation; inline attributes |
| IE11 | deprecated; state unsupported if asked |

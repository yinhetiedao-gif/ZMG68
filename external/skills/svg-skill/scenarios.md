# SVG Scenario Guide

Step-by-step per scenario. Indexed from SKILL.md.

---

## 1. UI icons

**Outline**: `fill="none" stroke="currentColor" stroke-width="2"`; inset ~1px for visual centering.

**Filled**: `fill="currentColor"`, one or few paths.

**Multi-color** (brand icons): each region `fill="#..."`, not currentColor.

Check: 24×24 grid alignment; visual weight matches sibling icons.

---

## 2. Logo / Favicon

**Logo**: 10% safe margin; prefer path outlines over `<text>` font dependency.

**Favicon 32×32**: 1–2 shapes max; avoid thin strokes (<2px); high contrast.

Export both: larger logo viewBox + simplified favicon variant.

---

## 3. Illustration / empty state

- Flat color blocks + simple shapes, minimal detail
- Characters: round head + body rect/ellipse + limb lines
- Empty box/folder: trapezoid rect or path for perspective
- viewBox 100×100 or 200×200

---

## 4. Flowchart / architecture

1. Set canvas width and node spacing (e.g. 100px horizontal step)
2. Define arrow marker in `<defs>`; lines use `marker-end="url(#arrow)"`
3. Nodes: `<rect rx="6">` + `<text text-anchor="middle">`
4. Non-ASCII labels → XML declaration + UTF-8
5. Complex diagrams: layer with `<g id="layer-nodes">`

Architecture extras: dashed border = external service; cylinder = database (two ellipses + rect).

---

## 5. Charts

**General**: margins left 40 / bottom 30 / top 20 / right 20; compute plot area inside viewBox.

**Bar chart**: `barWidth = plotWidth / n * 0.6`; `x = margin + i * step`; `height = value / max * plotHeight`.

**Line chart**: data → `M x y L x y ...`; optional `<circle>` data points.

**Pie/donut**: `A` arc commands; start at 12 o'clock; donut = outer arc + inner arc closed.

Required: `role="img"` + `<title>` summarizing data; repeat key values in `<desc>`.

---

## 6. Progress ring / bar

**Ring**: background circle `stroke="#e5e7eb"`; progress circle same radius, `stroke-dasharray="C 2*pi*r"`, `stroke-dashoffset` for percent; `transform="rotate(-90 cx cy)"` from top.

**Bar**: background rect + foreground rect width at `percent%`.

Animate: CSS transition on `stroke-dashoffset` or `width`.

---

## 7. Avatar placeholder

- Circle base: `circle` or `clipPath` circle
- Letter: `<text dominant-baseline="central" text-anchor="middle">` single char
- Generic person: head circle + shoulder arc path

`fill="currentColor"` or `opacity="0.2"` background + darker symbol.

---

## 8. Wave divider / decor strip

```svg
<svg viewBox="0 0 1200 120" preserveAspectRatio="none" xmlns="...">
  <path d="M0,60 C300,120 900,0 1200,60 L1200,120 L0,120 Z" fill="currentColor"/>
</svg>
```

CSS: `width:100%; height:80px; display:block;`. Use `preserveAspectRatio="none"` to span full width.

---

## 9. Map pin

Teardrop path or triangle + base circle; small center dot. Common 24×24, point facing down.

---

## 10. Sprite icon sheet

```svg
<svg xmlns="http://www.w3.org/2000/svg" style="display:none">
  <symbol id="icon-home" viewBox="0 0 24 24">...</symbol>
  <symbol id="icon-user" viewBox="0 0 24 24">...</symbol>
</svg>
```

Usage: `<svg><use href="#icon-home" width="24" height="24"/></svg>` (same page) or external sprite + `<use href="sprite.svg#icon-home">`.

Each symbol uses currentColor internally; ids globally unique. **Never preview sprite files via `<img>`** — root is `display:none`.

---

## 11. CSS background & mask

**Background**:
```css
.icon-home {
  width: 24px; height: 24px;
  background: url('/assets/icons/home.svg') center/contain no-repeat;
}
```

**Mask** (recolor single shape):
```css
.icon {
  width: 24px; height: 24px;
  background: var(--accent);
  -webkit-mask: url('/assets/icons/home.svg') center/contain no-repeat;
  mask: url('/assets/icons/home.svg') center/contain no-repeat;
}
```

Mask source needs visible fill area. Use explicit fill colors in mask SVG, not currentColor.

---

## 12. Animation

| Type | Approach |
|------|----------|
| Spin loader | CSS `@keyframes spin` on `<g>` |
| Stroke draw | `stroke-dasharray` = path length; animate or CSS offset |
| Pulse | CSS `opacity` / `scale` alternate |
| Hover | CSS `svg:hover .part { fill: ... }` |

Avoid animation in email.

---

## 13. Clip / mask / filter

**Rounded avatar clip**:
```svg
<defs>
  <clipPath id="round"><circle cx="20" cy="20" r="20"/></clipPath>
</defs>
<g clip-path="url(#round)"><!-- content --></g>
```

**Drop shadow**: `<filter id="s"><feDropShadow dx="0" dy="2" stdDeviation="3" flood-opacity=".2"/></filter>`

**Pattern**: `<pattern id="p" width="8" height="8" patternUnits="userSpaceOnUse">...</pattern>`

---

## 14. React / Vue

**React**: `strokeWidth` `strokeLinecap` camelCase; `{...props}` last; `aria-hidden` for decorative icons.

**Vue 3**: same attribute rules as React; dynamic color via `:fill="color"`.

**Svelte**: standard HTML attributes; `class` not `className`.

---

## 15. Email inline

- Inline presentation attributes only; avoid `<style>` and animation
- Set `width` and `height`
- Simplify paths; avoid defs references for Outlook compatibility

---

## 16. Responsive

| Need | Setting |
|------|---------|
| Scale proportionally, centered | default `preserveAspectRatio="xMidYMid meet"` |
| Fill container | `preserveAspectRatio="none"` |
| Max width | CSS `max-width:100%; height:auto` |
| Icon follows font size | `width:1em; height:1em` |

---

## 17. Inline SVG vs `<img>`

| Need | Use |
|------|-----|
| currentColor / CSS theme | **inline SVG** in HTML |
| Static asset, no theming | `<img src="icon.svg">` or CSS background |
| Sprite symbols | inline `<use href="#id">` |
| Wave with currentColor | inline SVG, not `<img>` |

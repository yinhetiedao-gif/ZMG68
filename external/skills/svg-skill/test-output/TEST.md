# svg-skill full-scenario tests

| # | Scenario | File | Checks |
|---|----------|------|--------|
| 01 | Outline icon | `01-icons/bell-outline.svg` | currentColor, uniform stroke |
| 02 | Filled icon | `01-icons/check-filled.svg` | fill currentColor |
| 03 | Multi-color icon | `01-icons/layers-multicolor.svg` | fixed fill per region |
| 04 | Logo | `02-brand/logo.svg` | title, safe margin |
| 05 | Favicon | `02-brand/favicon.svg` | 32×32 minimal |
| 06 | Empty state | `03-illustration/empty-box.svg` | shape composition |
| 07 | Flowchart (CJK) | `04-diagrams/flow-zh.svg` | UTF-8 + marker |
| 08 | Architecture | `04-diagrams/architecture.svg` | layers + dashed box |
| 09 | Bar chart | `05-charts/bar.svg` | title + scale |
| 10 | Line chart | `05-charts/line.svg` | path + data points |
| 11 | Pie chart | `05-charts/pie.svg` | arc commands |
| 12 | Progress ring | `06-progress/ring-75.svg` | dashoffset |
| 13 | Progress bar | `06-progress/bar-60.svg` | rect width ratio |
| 14 | Avatar placeholder | `07-ui/avatar.svg` | generic person |
| 15 | Badge | `07-ui/badge.svg` | rounded rect |
| 16 | Wave divider | `08-decor/wave.svg` | preserveAspectRatio none |
| 17 | Map pin | `01-icons/map-pin.svg` | teardrop shape |
| 18 | Sprite sheet | `09-sprite/icons.svg` | symbol + use |
| 19 | Loading animation | `10-motion/spinner.svg` | CSS keyframes |
| 20 | Hover interaction | `10-motion/heart-hover.svg` | :hover style |
| 21 | Clip | `11-effects/clip-card.svg` | clipPath |
| 22 | Drop shadow | `11-effects/shadow.svg` | feDropShadow |
| 23 | Dot pattern | `11-effects/dots-pattern.svg` | pattern |
| 24 | CSS mask | `12-integration/demo.css` | mask property |
| 25 | React | `12-integration/BellIcon.tsx` | spread props |
| 26 | Vue | `12-integration/MailIcon.vue` | template svg |
| 27 | Email inline | `12-integration/email-icon.svg` | no style/animation |

Run: `bash run-tests.sh`

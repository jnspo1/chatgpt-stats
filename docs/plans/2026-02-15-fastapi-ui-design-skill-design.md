# Design: FastAPI UI Design Skill

## Problem

The ChatGPT Stats dashboard has a distinctive warm-dark visual design that the user loves. Currently, this design exists only in that project's templates. Future FastAPI projects would need to manually copy and adapt the styles, leading to inconsistency and forgotten details.

## Solution

Create a Claude skill at `~/.claude/skills/fastapi-ui-design.md` that captures the complete design system — colours, fonts, component styles, Chart.js theming, JS interaction patterns, form elements, and base template structure — so any future FastAPI web app built by Claude inherits the same aesthetic automatically.

## Decisions

- **Scope**: Full design + code patterns (not just CSS reference)
- **Form elements**: Included (inputs, buttons, selects, toggles) — designed to match the aesthetic even though the reference app doesn't have them yet
- **Invocation**: Auto-trigger when building FastAPI web UIs
- **Structure**: Single monolithic skill file (no separate CSS or template files)
- **Header mark**: Excluded — the user doesn't want the amber icon square reproduced

## Skill Structure

1. **Metadata & trigger** — YAML frontmatter with auto-invoke description
2. **Colour palette** — All CSS custom properties with usage context
3. **Typography** — Font stack, Google Fonts import, complete type scale
4. **Component library** — Cards, chart boxes, tables, pills, nav, comparison cards, heatmap, stat cards, progress bars, fade-in animation, form elements
5. **Chart.js configuration** — Global defaults, tooltip theme, legend, bar/line chart recipes
6. **JS patterns** — DOM helpers, pill switching, tooltip wiring
7. **Base template** — Complete Jinja2 base.html skeleton
8. **Do's and Don'ts** — Design rules to maintain consistency

## File Location

`~/.claude/skills/fastapi-ui-design.md`

## Integration

Add to global CLAUDE.md skills table:

| Skill | File | Use For |
|-------|------|---------|
| **FastAPI UI Design** | `fastapi-ui-design.md` | Visual design system, CSS, component patterns, Chart.js theming, Jinja2 templates |

## Reference App

ChatGPT Stats dashboard (`~/python/chatgpt_stats/`) — the canonical implementation of this design system.

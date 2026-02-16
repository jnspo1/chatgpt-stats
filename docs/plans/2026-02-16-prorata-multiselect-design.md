# Design: Pro-rata Comparisons, Icon Removal, Multi-select Year Pills

**Date**: 2026-02-16

## Changes

### 1. Pro-rata Period Comparison (Overview)

**Problem**: Current month/year comparison is unfair — compares partial current period to full previous period.

**Solution**: Project current period forward to full-period rate.

**Backend** (`analytics.py` — `compute_period_comparison()`):
- Calculate `elapsed_days` (days from start of period to reference date) and `total_days` (total days in the period)
- For this_month: elapsed = ref.day, total = calendar.monthrange(ref.year, ref.month)[1]
- For this_year: elapsed = (ref - Jan 1).days + 1, total = 365 or 366 (leap year)
- Add projection fields: `projected_chats`, `projected_messages`, `projected_avg_messages`
- Formula: `actual * (total_days / elapsed_days)` — avg_messages not projected (already a rate)
- Include `elapsed_days` and `total_days` in the returned dict for frontend display

**Frontend** (`overview.html`):
- Use projected values for percentage-change arrows
- Display format: actual value shown, with "(proj: X)" next to it
- Subtitle under card title: "16 of 28 days" to indicate partial period

### 2. Remove G Icon (base.html)

- Delete `<div class="header-mark">G</div>` element (line 268)
- Delete `.header-mark` CSS rule (lines 63-69)

### 3. Multi-select Year Pills (Trends + Patterns)

**UX**:
- Click year pill to toggle on/off (multi-select, doesn't deselect others)
- "All" is special: click to select all years (reset). Auto-activates when no years selected
- Minimum 1 selection enforced via auto-activating "All"

**Trends** (`trends.html`):
- Refactor `createPills()` to multi-select mode
- `filterByYear()` accepts array of years
- Charts and top-days tables filter to include any selected year

**Patterns** (`patterns.html`):
- Same multi-select behavior for gap analysis pills
- `filterGapsByYear()` accepts array of years

## Files Changed

| File | Change |
|------|--------|
| `analytics.py` | Add pro-rata fields to `compute_period_comparison()` |
| `templates/base.html` | Remove G icon + CSS |
| `templates/overview.html` | Use projected values in comparison cards |
| `templates/trends.html` | Multi-select pill logic |
| `templates/patterns.html` | Multi-select pill logic for gaps |

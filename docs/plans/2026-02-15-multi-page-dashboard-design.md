# Multi-Page Dashboard Redesign

**Date**: 2026-02-15
**Problem**: Current dashboard has 3 charts each rendering 948 daily data points — unreadable on mobile and barely useful on desktop.
**Solution**: Split into 3 focused pages with better aggregations and new visualizations.

## Architecture

### Routing

| Route | Page | Purpose |
|-------|------|---------|
| `GET /` | Overview | At-a-glance health check |
| `GET /trends` | Trends | Deep dive into usage over time |
| `GET /patterns` | Patterns | Habit analysis (when/how) |

Each page gets its own HTML template. All pages share the same cached data payload (extended with new computed fields). Navigation via a shared top nav component.

### API Changes

| Route | Change |
|-------|--------|
| `GET /api/data` | Extended payload with new fields (hourly data, monthly aggregates, distributions) |
| `GET /api/refresh` | No change |
| `GET /healthz` | No change |

## Page 1: Overview (`/`)

**Components**:

1. **Summary cards** — Existing 6 cards (total chats, total messages, date range, time span, days active, longest gap). No change.

2. **Month-over-month comparison cards** — Two side-by-side cards:
   - This month vs last month: chats, messages, avg msgs/chat with directional arrows and % change
   - This year vs last year: same metrics at year level

3. **Monthly usage chart** — Single grouped bar chart at monthly granularity (~36 bars). Chats per month as bars, 3-month rolling average as line. Readable on iPhone.

4. **Conversation length histogram** — Horizontal bar chart with buckets: 1-2, 3-5, 6-10, 11-20, 21-50, 50+ messages. Shows distribution of conversation depth.

## Page 2: Trends (`/trends`)

**Components**:

1. **Granularity switcher** — Pills: `Daily | Weekly | Monthly`. Default: Weekly.

2. **Year scope pills** — `All | 2023 | 2024 | 2025 | 2026`. Controls chart date range AND table filtering.

3. **Three trend charts** (from current, improved):
   - Chat frequency: bars + 4-period/12-period moving averages
   - Messages per chat: same structure
   - Total messages: same structure
   - No lifetime average (adds noise over long periods)

4. **Top days tables** — Existing tables with year pills. Moved from overview.

**Key data point reductions**:
- Weekly + All years: ~156 bars (vs 948 currently)
- Weekly + single year: ~52 bars
- Monthly + All years: ~36 bars

## Page 3: Patterns (`/patterns`)

**Components**:

1. **Day-of-week × hour-of-day heatmap** — 7×24 grid colored by activity intensity (like GitHub contribution graph but for hours). Year pills to scope.

2. **Busiest hours bar chart** — Horizontal bars showing conversations per hour (0-23).

3. **Weekday vs weekend comparison** — Stat cards: avg daily chats on weekdays vs weekends.

4. **Gap analysis table** — Moved from current page. Already has year pills.

## Data Model Changes

### New fields in `analytics.py`

```python
# Monthly aggregation (for Overview chart)
compute_monthly_data(daily_records) -> {months: [...], chats: [...], messages: [...]}

# Hourly distribution (for Patterns heatmap)
compute_hourly_data(timestamps) -> {
    heatmap: [[count for hour in 24] for day in 7],  # 7×24 grid
    hourly_totals: [count for hour in 24],
}

# Conversation length distribution (for Overview histogram)
compute_length_distribution(summaries) -> {
    buckets: ["1-2", "3-5", "6-10", "11-20", "21-50", "50+"],
    counts: [n, n, n, n, n, n],
}

# Month-over-month comparison (for Overview cards)
compute_period_comparison(daily_records) -> {
    this_month: {chats, messages, avg_msgs},
    last_month: {chats, messages, avg_msgs},
    this_year: {chats, messages, avg_msgs},
    last_year: {chats, messages, avg_msgs},
}

# Weekly aggregation (for Trends switchable granularity)
compute_weekly_data(daily_records) -> {weeks: [...], chats: [...], ...}
```

### Granularity switching

The daily, weekly, and monthly data series are all sent in the payload. Granularity switching is client-side only — JS swaps which dataset Chart.js renders. No server round-trips.

## Navigation

Shared top nav bar across all pages. Simple links, highlight active page. Same dark theme as current header.

## Template Strategy

Three HTML templates:
- `templates/overview.html`
- `templates/trends.html`
- `templates/patterns.html`

Shared styles extracted to a `<style>` block that's consistent across all three (or a shared CSS include). Each template gets the full data payload injected server-side (same pattern as current `DASHBOARD_DATA`).

## Mobile Considerations

- Overview monthly chart: ~36 bars, fits comfortably on iPhone
- Trends at weekly: ~52 bars per year, readable
- Heatmap: 7×24 grid fits with proper cell sizing
- Histogram: horizontal bars stack naturally on narrow screens
- Nav: top pills, wraps on narrow screens

# Changelog

All notable changes to the ChatGPT Statistics project will be documented in this file.

## Current State

The ChatGPT Stats analytics system provides both CLI and web dashboard modes:
- **CLI**: `chat_gpt_summary.py` processes `conversations.json` and generates CSV/JSON files to `chat_analytics/`
- **Web Dashboard**: Multi-page FastAPI service (port 8203, systemd unit `chatgpt-stats`) with 3 pages:
  - **Overview**: Summary cards, monthly usage chart, month-over-month comparison, conversation length histogram
  - **Trends**: Daily/weekly/monthly time-series charts with year scope filter pills and top days tables
  - **Patterns**: 7x24 activity heatmap, hourly distribution, weekday vs weekend comparison, message gap analysis
- **Analytics Engine**: 13 core computation functions covering summaries, trends, distributions, gaps, and comparative analysis
- **Test Coverage**: 53 unit tests validating data processing edge cases, template rendering, and API endpoints
- **Infrastructure**: Nginx reverse proxy, 1-hour dashboard cache (thread-safe), ~100KB API payload with per-year bucketed rankings

## Unreleased

#### 2026-02-15: Multi-Page Dashboard with Advanced Analytics
- **Added**: Split single-page dashboard into 3 focused pages — Overview (summary cards + monthly trends), Trends (daily/weekly/monthly granularity switcher + year filter pills), Patterns (activity heatmap + hourly distribution + weekday comparison)
- **Added**: 5 new analytics functions: `compute_monthly_data()`, `compute_weekly_data()`, `compute_hourly_data()`, `compute_length_distribution()`, `compute_period_comparison()` for enhanced time-series, distribution, and comparative analysis
- **Added**: Template inheritance system with `base.html` + 3 page templates (`overview.html`, `trends.html`, `patterns.html`) for maintainable multi-page layout
- **Changed**: Dashboard routes now serve `/`, `/trends/`, `/patterns/` with shared cache and navigation UI
- **Added**: 17 new tests bringing test suite from 36 to 53 tests, covering all new analytics functions and edge cases
- **Updated**: `CLAUDE.md` with expanded architecture docs reflecting new page structure and analytics functions

#### 2026-02-15: Year Filter Pills for Dashboard Tables
- **Added**: Year filter UI with pill buttons (2023–2026 + All) to all three bottom tables on the web dashboard for quick year-based filtering
- **Added**: `_top_records_per_year()` and `_top_gaps_per_year()` helper functions in `analytics.py` to compute per-year bucketed top-N data instead of global rankings
- **Changed**: Backend now sends top-10-per-year for daily records and top-25-per-year for message gaps, reducing payload from 2MB+ to ~99KB for optimal frontend filtering
- **Changed**: Frontend filtering logic now applies `.slice(0, N)` after year selection to ensure each year shows its true top records rather than pre-filtered globals
- **Added**: CSS pill styling and `createPillBar()` JavaScript function with safe DOM clearing via `clearChildren()` utility

#### 2026-02-15: Code Review Fixes
- **Fixed**: Cache race condition in `app.py` — rebuild now happens inside the lock to prevent concurrent 15s parses
- **Fixed**: Missing error handling for `conversations.json` not found or invalid JSON in both `app.py` (HTTPException) and `chat_gpt_summary.py` (stderr + sys.exit)
- **Fixed**: Template placeholder validation before string replacement in `app.py`
- **Fixed**: Per-message timestamp errors in `analytics.py` now caught instead of crashing the entire parse
- **Fixed**: Temp file leak in tests — switched from `tempfile.NamedTemporaryFile(delete=False)` to pytest `tmp_path`
- **Changed**: Test suite expanded from 24 to 36 tests covering `save_analytics_files`, `print_summary_report`, invalid timestamps, and edge cases
- **Changed**: Docstrings updated for accuracy across `analytics.py` and `app.py`

#### 2026-02-15: Web Dashboard & Architecture Refactor
- **Added**: `analytics.py` — extracted all data processing into importable functions from module-level scripts
- **Added**: `app.py` — FastAPI web dashboard on port 8203 with Chart.js visualizations, 1-hour cache TTL
- **Added**: `dashboard_template.html` — dark-themed Chart.js dashboard with 3 mixed bar+line charts, gap analysis table, and top days tables
- **Added**: `requirements.txt` — fastapi, uvicorn, jinja2 (no pandas/matplotlib — pure Python rolling averages)
- **Added**: `tests/test_analytics.py` — unit tests with synthetic data, `pytest.ini`
- **Added**: `.github/workflows/ci.yml` — GitHub Actions CI with Python 3.11/3.12
- **Added**: `chatgpt-stats.service` — systemd unit, nginx proxy at `/chatgpt_stats/`
- **Changed**: `chat_gpt_summary.py` refactored from 243-line module-level script to 29-line thin CLI wrapper around `analytics.py`
- **Removed**: `chat_gpt_viz.py` — matplotlib PNG generation replaced by interactive Chart.js dashboard

#### 2026-02-15: CLAUDE.md Quality Audit
- **Added**: Data flow summary, JSON structure hint, interactive mode warning for `chat_gpt_export.py`, and gotchas section to CLAUDE.md

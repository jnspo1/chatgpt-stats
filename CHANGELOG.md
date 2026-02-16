# Changelog

All notable changes to the ChatGPT Statistics project will be documented in this file.

## Current State

The ChatGPT Stats analytics system provides both CLI and web dashboard modes:
- **CLI**: `chat_gpt_summary.py` processes `conversations.json` and generates CSV/JSON files to `chat_analytics/`
- **Web Dashboard**: Multi-page FastAPI service (port 8203, systemd unit `chatgpt-stats`) with 3 pages:
  - **Overview**: Summary cards (now including Avg Your Message, Avg ChatGPT Reply, Response Ratio, Code in Conversations), monthly usage chart, month-over-month comparison with pro-rata projections, conversation length histogram
  - **Trends**: Daily/weekly/monthly time-series charts plus 3 new content charts (Message Length Over Time, Response Ratio Over Time, Code Block Usage Over Time) with multi-select year pills, top days tables
  - **Patterns**: 7x24 activity heatmap, hourly distribution, weekday vs weekend comparison, per-year activity overview table, Code Analysis section with top 10 languages and code percentage, gap analysis with multi-select year pills
- **Content Analytics**: New message analysis tracks word counts, character counts, code block detection, and detected programming languages for both user and assistant messages
- **Pro-Rata Analytics**: Comparison cards compute elapsed/total days and project chat/message counts to full months/years for in-progress periods
- **Analytics Engine**: 18 core computation functions covering summaries, trends, distributions, gaps, per-year breakdowns, content metrics, and code statistics with pro-rata projections
- **Test Coverage**: 58+ unit tests validating data processing edge cases, template rendering, and API endpoints
- **Infrastructure**: Nginx reverse proxy, 1-hour dashboard cache (thread-safe), ~100KB API payload with per-year bucketed rankings and content metrics

## Unreleased

#### 2026-02-16: Message Content Analytics & Code Detection
- **Added**: Content metrics tracking in `process_conversations()` — extracts word count, character count, code block presence, and detected programming languages from user and assistant messages for richer conversational analysis
- **Added**: New daily analytics fields — user_words, user_chars, user_msgs, user_code_msgs, asst_words, asst_chars, asst_msgs, asst_code_msgs to enable content-based trends
- **Added**: New conversation summary fields — user_words, asst_words, response_ratio (asst_words / user_words), and code_languages list for per-chat insights
- **Added**: 4 new analytics functions in `analytics.py` — `compute_content_chart_data()`, `compute_content_weekly_data()`, `compute_content_monthly_data()`, `compute_code_stats()` — enabling rolling averages for message length and response balance
- **Added**: Helper functions `_safe_div()`, `_content_metrics_from_records()`, `_wrap_with_rolling()` for DRY rolling average computation and safe division
- **Added**: 4 new summary cards on Overview page — Avg Your Message (words), Avg ChatGPT Reply (words), Response Ratio (numeric), Code in Conversations (%)
- **Added**: 3 new line charts on Trends page — Message Length Over Time (user vs assistant), Response Ratio Over Time, Code Block Usage Over Time — integrated with granularity and year pill system
- **Added**: Code Analysis section on Patterns page with horizontal bar chart showing top 10 programming languages detected and percentage of conversations containing code blocks
- **Updated**: `build_dashboard_payload()` with new keys — content_charts, content_weekly, content_monthly, code_stats, content_summary
- **Updated**: Integration test to validate new payload structure

#### 2026-02-16: Pro-Rata Projections & Multi-Select Year Filters
- **Added**: Pro-rata projection logic to `compute_period_comparison()` — calculates elapsed_days, total_days, projected_chats, and projected_messages for incomplete periods (this_month, this_year) to estimate full-month/full-year activity
- **Added**: Comparison cards on Overview page now display "X of Y days" subtitles and projected values (≈N suffix) for in-progress periods, with percentage change calculated using projected figures for meaningful trends
- **Changed**: Removed G icon from header (`base.html`) — deleted `.header-mark` CSS class and icon element for cleaner UI
- **Added**: Multi-select year pills on Trends page — year buttons now toggle individually instead of exclusive selection, "All" auto-syncs when toggling all years or none
- **Added**: Multi-select year pills on Patterns page (gap analysis section) — consistent toggle behavior across dashboard, enabling simultaneous view of multiple years' data

#### 2026-02-16: PWA Home Screen Support
- **Added**: Apple touch icon link and app title meta tags to `base.html` for iOS home screen installation with "ChatGPT Stats" display name
- **Added**: `/app_icon.jpg` endpoint in `app.py` serving cached icon file for iPhone home screen display
- **Added**: Standalone mode meta tags to enable full-screen app mode without Safari chrome on iOS and Android
- **Changed**: Updated `base.html` with proper meta tags for `apple-mobile-web-app-title`, `application-name`, and `mobile-web-app-capable`

#### 2026-02-15: Per-Year Activity Overview Table
- **Added**: `compute_activity_by_year()` function in `analytics.py` that groups timestamps by calendar year and computes total_days, days_active, days_inactive, pct_active, pct_inactive per year with smart date boundaries (partial first/last years, full middle years) plus an Overall aggregate row
- **Added**: Activity Overview section on Patterns page with table rendering calendar-year breakdowns and usage percentages for quick year-over-year comparison
- **Changed**: Gap Analysis section simplified by removing static summary row; per-year stats now exposed via dedicated Activity Overview table
- **Added**: 5 new unit tests in `TestComputeActivityByYear` class covering empty data, single timestamp, single year, multi-year scenarios, and percentage validation
- **Updated**: `CLAUDE.md` with `compute_activity_by_year()` in analytics functions list
- **Test Coverage**: 58 passing tests (up from 53)

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

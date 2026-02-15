# Changelog

All notable changes to the ChatGPT Statistics project will be documented in this file.

## Unreleased

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

# Changelog

All notable changes to the ChatGPT Statistics project will be documented in this file.

## Unreleased

#### 2026-02-15: Web Dashboard & Architecture Refactor
- **Added**: `analytics.py` — extracted all data processing into importable functions from module-level scripts
- **Added**: `app.py` — FastAPI web dashboard on port 8203 with Chart.js visualizations, 1-hour cache TTL
- **Added**: `dashboard_template.html` — dark-themed Chart.js dashboard with 3 mixed bar+line charts, gap analysis table, and top days tables
- **Added**: `requirements.txt` — fastapi, uvicorn, jinja2 (no pandas/matplotlib — pure Python rolling averages)
- **Added**: `tests/test_analytics.py` — 24 unit tests with synthetic data, `pytest.ini`
- **Added**: `.github/workflows/ci.yml` — GitHub Actions CI with Python 3.11/3.12
- **Added**: `chatgpt-stats.service` — systemd unit, nginx proxy at `/chatgpt_stats/`
- **Changed**: `chat_gpt_summary.py` refactored from 243-line module-level script to 29-line thin CLI wrapper around `analytics.py`
- **Removed**: `chat_gpt_viz.py` — matplotlib PNG generation replaced by interactive Chart.js dashboard

#### 2026-02-15: CLAUDE.md Quality Audit
- **Added**: Data flow summary, JSON structure hint, interactive mode warning for `chat_gpt_export.py`, and gotchas section to CLAUDE.md

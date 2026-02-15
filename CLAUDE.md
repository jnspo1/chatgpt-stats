# CLAUDE.md

## Project Overview

Python analytics for ChatGPT conversation history exported from OpenAI. Provides both a CLI tool and a live FastAPI web dashboard with Chart.js visualizations.

**Data flow**: `conversations.json` (OpenAI export) → `analytics.py` (processing) → CLI output or web dashboard

## Live Service

The dashboard runs as a FastAPI service: `chatgpt-stats` on port **8203**.

- Systemd unit: `chatgpt-stats.service`
- Nginx proxy: `/chatgpt_stats/` on Tailscale IP
- After code changes: `sudo systemctl restart chatgpt-stats`
- App entry point: `app.py`

### Pages & API Endpoints

| Route | Description |
|---|---|
| `GET /` | Overview page — summary cards, monthly chart, comparison cards, length histogram |
| `GET /trends` | Trends page — 3 time-series charts with daily/weekly/monthly granularity switcher |
| `GET /patterns` | Patterns page — activity heatmap, hourly distribution, gap analysis |
| `GET /api/data` | Raw dashboard JSON payload |
| `GET /api/refresh` | Force cache rebuild (1hr TTL) |
| `GET /healthz` | Health check |

## Commands

```bash
# Development server (with auto-reload)
source venv/bin/activate
uvicorn app:app --host 127.0.0.1 --port 8203 --reload

# Restart production service
sudo systemctl restart chatgpt-stats

# Run tests
./venv/bin/pytest tests/ -v

# CLI analytics (generates CSV/JSON to chat_analytics/)
python chat_gpt_summary.py
```

## Architecture

- **analytics.py** — Core data processing module. Functions: `load_conversations`, `process_conversations`, `compute_gap_analysis`, `compute_summary_stats`, `compute_chart_data`, `compute_monthly_data`, `compute_weekly_data`, `compute_hourly_data`, `compute_length_distribution`, `compute_period_comparison`, `build_dashboard_payload`, `save_analytics_files`, `print_summary_report`
- **app.py** — FastAPI service with Jinja2 templates (port 8203). Thread-safe in-memory cache with 1-hour TTL
- **templates/base.html** — Shared Jinja2 base with nav, styles, Chart.js includes
- **templates/overview.html** — Overview page (summary cards, monthly chart, comparison cards, length histogram)
- **templates/trends.html** — Trends page (3 charts with daily/weekly/monthly granularity, year pills, top days tables)
- **templates/patterns.html** — Patterns page (7x24 heatmap, hourly bar chart, weekday comparison, gap analysis)
- **chat_gpt_summary.py** — Thin CLI wrapper around analytics.py
- **chat_gpt_history.py** — Extracts user prompts from conversation JSON
- **chat_gpt_export.py** — Interactive conversation exporter (requires terminal input)

## Dependencies

fastapi, uvicorn, jinja2 (install via `venv/bin/pip install -r requirements.txt`)

No pandas or matplotlib — rolling averages computed in pure Python.

## Input

`conversations.json` — Downloaded from OpenAI (Settings > Data Controls > Export). JSON array of conversation objects with `mapping` dicts.

## Output

- **Web**: Dashboard at `/chatgpt_stats/` with interactive charts
- **CLI**: `chat_analytics/` directory with `chat_summaries.json/csv`, `daily_stats.json/csv`, `message_gaps.json/csv`

## Gotchas

- `conversations.json` can be 100MB+; first dashboard load takes ~15s to parse (then cached for 1hr)
- `chat_gpt_export.py` uses interactive menus — must be run in a terminal
- Export date range depends on when the user requested it from OpenAI

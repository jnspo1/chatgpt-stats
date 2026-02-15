# CLAUDE.md

## Project Overview

Python scripts for analyzing ChatGPT conversation history exported from OpenAI.

**Data flow**: `conversations.json` (OpenAI export) → parser scripts → `chat_analytics/` (CSV, JSON, PNG)

## Key Scripts

- **chat_gpt_history.py** - Extracts user prompts from conversation JSON
- **chat_gpt_summary.py** - Generates conversation summaries and statistics (CSV/JSON)
- **chat_gpt_viz.py** - Creates visualizations (frequency charts, length distributions)
- **chat_gpt_export.py** - Exports conversations to human-readable text format (interactive menu — cannot be scripted non-interactively)

## Dependencies

pandas, matplotlib, seaborn (install via `venv/bin/pip install -r requirements.txt`)

## Input

`conversations.json` - Downloaded from OpenAI (Settings > Data Controls > Export). This is a JSON array of conversation objects, each containing a `mapping` dict of message nodes with `author.role` and `content.parts`.

## Output

`chat_analytics/` directory containing:
- `chat_summaries.json`, `chat_summaries.csv` - Per-conversation statistics
- `daily_stats.csv` - Daily usage aggregates
- `chat_frequency.png`, `chat_length.png` - Visualizations

## Usage

```bash
source venv/bin/activate
python chat_gpt_summary.py      # Generate stats
python chat_gpt_viz.py          # Create charts
python chat_gpt_export.py       # Interactive export (requires terminal input)
```

## Gotchas

- `conversations.json` can be 100MB+; all scripts load it fully into memory
- `chat_gpt_export.py` uses interactive menus — it must be run in a terminal, not piped
- Export date range depends on when the user requested it from OpenAI, not a fixed window

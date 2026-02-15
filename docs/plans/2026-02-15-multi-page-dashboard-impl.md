# Multi-Page Dashboard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Split the single-page ChatGPT stats dashboard into 3 focused pages (Overview, Trends, Patterns) with better data aggregations and new visualizations.

**Architecture:** Add 5 new analytics functions to `analytics.py` (monthly/weekly/hourly aggregation, length distribution, period comparison). Update `build_dashboard_payload` to include them. Move from single template string replacement to Jinja2 template directory with 3 page templates + shared base. Add FastAPI routes for `/trends` and `/patterns`.

**Tech Stack:** Python 3, FastAPI, Jinja2 templates, Chart.js 4.x, pure-Python aggregations (no pandas)

---

### Task 1: Add `compute_monthly_data` to analytics.py

**Files:**
- Modify: `analytics.py` (add function after `compute_chart_data`)
- Test: `tests/test_analytics.py`

**Step 1: Write the failing test**

Add to `tests/test_analytics.py`:

```python
from analytics import (
    # ... existing imports ...
    compute_monthly_data,
)

class TestComputeMonthlyData:
    def test_basic_aggregation(self):
        records = [
            {"date": "2024-01-15", "total_messages": 10, "total_chats": 2, "avg_messages_per_chat": 5.0, "max_messages_in_chat": 6},
            {"date": "2024-01-20", "total_messages": 8, "total_chats": 1, "avg_messages_per_chat": 8.0, "max_messages_in_chat": 8},
            {"date": "2024-02-05", "total_messages": 5, "total_chats": 3, "avg_messages_per_chat": 1.67, "max_messages_in_chat": 2},
        ]
        result = compute_monthly_data(records)
        assert result["months"] == ["2024-01", "2024-02"]
        assert result["chats"] == [3, 3]
        assert result["messages"] == [18, 5]

    def test_avg_messages_per_chat(self):
        records = [
            {"date": "2024-01-10", "total_messages": 10, "total_chats": 2, "avg_messages_per_chat": 5.0, "max_messages_in_chat": 6},
            {"date": "2024-01-20", "total_messages": 6, "total_chats": 3, "avg_messages_per_chat": 2.0, "max_messages_in_chat": 3},
        ]
        result = compute_monthly_data(records)
        # Weighted avg: (10+6) / (2+3) = 3.2
        assert result["avg_messages"] == [pytest.approx(3.2)]

    def test_empty_records(self):
        result = compute_monthly_data([])
        assert result["months"] == []
        assert result["chats"] == []

    def test_rolling_avg_3m(self):
        records = [
            {"date": "2024-01-15", "total_messages": 10, "total_chats": 1, "avg_messages_per_chat": 10.0, "max_messages_in_chat": 10},
            {"date": "2024-02-15", "total_messages": 20, "total_chats": 2, "avg_messages_per_chat": 10.0, "max_messages_in_chat": 12},
            {"date": "2024-03-15", "total_messages": 30, "total_chats": 3, "avg_messages_per_chat": 10.0, "max_messages_in_chat": 15},
        ]
        result = compute_monthly_data(records)
        # 3-month rolling avg of chats: [1, 1.5, 2.0]
        assert result["chats_avg_3m"] == [1.0, 1.5, 2.0]
```

**Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_analytics.py::TestComputeMonthlyData -v`
Expected: ImportError — `compute_monthly_data` does not exist

**Step 3: Write minimal implementation**

Add to `analytics.py` after `compute_chart_data`:

```python
def compute_monthly_data(daily_records: list[dict]) -> dict[str, Any]:
    """Aggregate daily records into monthly buckets for the overview chart."""
    sorted_records = sorted(daily_records, key=lambda r: r["date"])

    monthly: dict[str, dict] = {}
    for r in sorted_records:
        month = r["date"][:7]  # "YYYY-MM"
        if month not in monthly:
            monthly[month] = {"chats": 0, "messages": 0, "total_msgs_raw": 0, "total_chats_raw": 0}
        monthly[month]["chats"] += r["total_chats"]
        monthly[month]["messages"] += r["total_messages"]
        monthly[month]["total_msgs_raw"] += r["total_messages"]
        monthly[month]["total_chats_raw"] += r["total_chats"]

    months = sorted(monthly.keys())
    chats = [monthly[m]["chats"] for m in months]
    messages = [monthly[m]["messages"] for m in months]
    avg_messages = [
        round(monthly[m]["total_msgs_raw"] / monthly[m]["total_chats_raw"], 2)
        if monthly[m]["total_chats_raw"] > 0 else 0
        for m in months
    ]

    return {
        "months": months,
        "chats": chats,
        "messages": messages,
        "avg_messages": avg_messages,
        "chats_avg_3m": [round(v, 2) for v in _rolling_avg([float(c) for c in chats], 3)],
        "messages_avg_3m": [round(v, 2) for v in _rolling_avg([float(m) for m in messages], 3)],
    }
```

**Step 4: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_analytics.py::TestComputeMonthlyData -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add analytics.py tests/test_analytics.py
git commit -m "feat(analytics): add compute_monthly_data for overview chart"
```

---

### Task 2: Add `compute_weekly_data` to analytics.py

**Files:**
- Modify: `analytics.py`
- Test: `tests/test_analytics.py`

**Step 1: Write the failing test**

```python
from analytics import compute_weekly_data

class TestComputeWeeklyData:
    def test_basic_aggregation(self):
        # Mon Jan 15 and Tue Jan 16 are same ISO week (2024-W03)
        # Mon Jan 22 is next week (2024-W04)
        records = [
            {"date": "2024-01-15", "total_messages": 10, "total_chats": 2, "avg_messages_per_chat": 5.0, "max_messages_in_chat": 6},
            {"date": "2024-01-16", "total_messages": 8, "total_chats": 1, "avg_messages_per_chat": 8.0, "max_messages_in_chat": 8},
            {"date": "2024-01-22", "total_messages": 5, "total_chats": 3, "avg_messages_per_chat": 1.67, "max_messages_in_chat": 2},
        ]
        result = compute_weekly_data(records)
        assert len(result["weeks"]) == 2
        assert result["chats"] == [3, 3]
        assert result["messages"] == [18, 5]

    def test_empty_records(self):
        result = compute_weekly_data([])
        assert result["weeks"] == []

    def test_has_rolling_averages(self):
        records = [
            {"date": f"2024-01-{d:02d}", "total_messages": d, "total_chats": 1, "avg_messages_per_chat": float(d), "max_messages_in_chat": d}
            for d in range(1, 29)  # 4 weeks of data
        ]
        result = compute_weekly_data(records)
        assert len(result["chats_avg_4w"]) == len(result["weeks"])
        assert len(result["chats_avg_12w"]) == len(result["weeks"])
```

**Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_analytics.py::TestComputeWeeklyData -v`
Expected: ImportError

**Step 3: Write minimal implementation**

```python
def compute_weekly_data(daily_records: list[dict]) -> dict[str, Any]:
    """Aggregate daily records into ISO-week buckets for the trends page."""
    from datetime import date as date_type

    sorted_records = sorted(daily_records, key=lambda r: r["date"])

    weekly: dict[str, dict] = {}
    for r in sorted_records:
        d = date_type.fromisoformat(r["date"])
        iso = d.isocalendar()
        week_key = f"{iso[0]}-W{iso[1]:02d}"
        # Use the Monday of that ISO week as the label date
        monday = d - timedelta(days=d.weekday())
        if week_key not in weekly:
            weekly[week_key] = {"monday": monday.isoformat(), "chats": 0, "messages": 0, "total_msgs": 0, "total_chats": 0}
        weekly[week_key]["chats"] += r["total_chats"]
        weekly[week_key]["messages"] += r["total_messages"]
        weekly[week_key]["total_msgs"] += r["total_messages"]
        weekly[week_key]["total_chats"] += r["total_chats"]

    sorted_keys = sorted(weekly.keys())
    weeks = [weekly[k]["monday"] for k in sorted_keys]
    chats = [weekly[k]["chats"] for k in sorted_keys]
    messages = [weekly[k]["messages"] for k in sorted_keys]
    avg_messages = [
        round(weekly[k]["total_msgs"] / weekly[k]["total_chats"], 2)
        if weekly[k]["total_chats"] > 0 else 0
        for k in sorted_keys
    ]

    return {
        "weeks": weeks,
        "chats": chats,
        "messages": messages,
        "avg_messages": avg_messages,
        "chats_avg_4w": [round(v, 2) for v in _rolling_avg([float(c) for c in chats], 4)],
        "chats_avg_12w": [round(v, 2) for v in _rolling_avg([float(c) for c in chats], 12)],
        "messages_avg_4w": [round(v, 2) for v in _rolling_avg([float(m) for m in messages], 4)],
        "messages_avg_12w": [round(v, 2) for v in _rolling_avg([float(m) for m in messages], 12)],
        "avg_messages_avg_4w": [round(v, 2) for v in _rolling_avg([float(a) for a in avg_messages], 4)],
        "avg_messages_avg_12w": [round(v, 2) for v in _rolling_avg([float(a) for a in avg_messages], 12)],
    }
```

**Step 4: Run tests**

Run: `./venv/bin/pytest tests/test_analytics.py::TestComputeWeeklyData -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add analytics.py tests/test_analytics.py
git commit -m "feat(analytics): add compute_weekly_data for trends granularity"
```

---

### Task 3: Add `compute_hourly_data` to analytics.py

**Files:**
- Modify: `analytics.py`
- Test: `tests/test_analytics.py`

**Step 1: Write the failing test**

```python
from analytics import compute_hourly_data

class TestComputeHourlyData:
    def test_heatmap_dimensions(self):
        ts = [
            datetime(2024, 1, 15, 10, 30),  # Monday, hour 10
            datetime(2024, 1, 15, 10, 45),  # Monday, hour 10
            datetime(2024, 1, 16, 14, 0),   # Tuesday, hour 14
        ]
        result = compute_hourly_data(ts)
        assert len(result["heatmap"]) == 7      # 7 days
        assert len(result["heatmap"][0]) == 24   # 24 hours per day
        # Monday=0, hour 10 should have 2
        assert result["heatmap"][0][10] == 2
        # Tuesday=1, hour 14 should have 1
        assert result["heatmap"][1][14] == 1

    def test_hourly_totals(self):
        ts = [
            datetime(2024, 1, 15, 10, 30),  # hour 10
            datetime(2024, 1, 16, 10, 0),   # hour 10
            datetime(2024, 1, 17, 14, 0),   # hour 14
        ]
        result = compute_hourly_data(ts)
        assert result["hourly_totals"][10] == 2
        assert result["hourly_totals"][14] == 1
        assert len(result["hourly_totals"]) == 24

    def test_empty_timestamps(self):
        result = compute_hourly_data([])
        assert len(result["heatmap"]) == 7
        assert all(all(v == 0 for v in row) for row in result["heatmap"])
        assert all(v == 0 for v in result["hourly_totals"])

    def test_weekday_totals(self):
        ts = [
            datetime(2024, 1, 15, 10, 0),  # Monday
            datetime(2024, 1, 15, 11, 0),  # Monday
            datetime(2024, 1, 20, 10, 0),  # Saturday
        ]
        result = compute_hourly_data(ts)
        assert result["weekday_totals"][0] == 2  # Monday
        assert result["weekday_totals"][5] == 1  # Saturday
```

**Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_analytics.py::TestComputeHourlyData -v`
Expected: ImportError

**Step 3: Write minimal implementation**

```python
def compute_hourly_data(timestamps: list[datetime]) -> dict[str, Any]:
    """Compute hour-of-day × day-of-week activity grid from timestamps."""
    heatmap = [[0] * 24 for _ in range(7)]  # [weekday][hour]
    hourly_totals = [0] * 24
    weekday_totals = [0] * 7

    for ts in timestamps:
        weekday = ts.weekday()  # 0=Monday
        hour = ts.hour
        heatmap[weekday][hour] += 1
        hourly_totals[hour] += 1
        weekday_totals[weekday] += 1

    return {
        "heatmap": heatmap,
        "hourly_totals": hourly_totals,
        "weekday_totals": weekday_totals,
    }
```

**Step 4: Run tests**

Run: `./venv/bin/pytest tests/test_analytics.py::TestComputeHourlyData -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add analytics.py tests/test_analytics.py
git commit -m "feat(analytics): add compute_hourly_data for patterns heatmap"
```

---

### Task 4: Add `compute_length_distribution` to analytics.py

**Files:**
- Modify: `analytics.py`
- Test: `tests/test_analytics.py`

**Step 1: Write the failing test**

```python
from analytics import compute_length_distribution

class TestComputeLengthDistribution:
    def test_basic_buckets(self):
        summaries = [
            {"message_count": 1},
            {"message_count": 2},
            {"message_count": 5},
            {"message_count": 10},
            {"message_count": 15},
            {"message_count": 30},
            {"message_count": 75},
        ]
        result = compute_length_distribution(summaries)
        assert result["buckets"] == ["1-2", "3-5", "6-10", "11-20", "21-50", "50+"]
        assert result["counts"] == [2, 1, 1, 1, 1, 1]

    def test_empty(self):
        result = compute_length_distribution([])
        assert result["counts"] == [0, 0, 0, 0, 0, 0]

    def test_all_in_one_bucket(self):
        summaries = [{"message_count": 1}, {"message_count": 2}, {"message_count": 1}]
        result = compute_length_distribution(summaries)
        assert result["counts"][0] == 3
        assert sum(result["counts"]) == 3
```

**Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_analytics.py::TestComputeLengthDistribution -v`
Expected: ImportError

**Step 3: Write minimal implementation**

```python
_LENGTH_BUCKETS = [
    ("1-2", 1, 2),
    ("3-5", 3, 5),
    ("6-10", 6, 10),
    ("11-20", 11, 20),
    ("21-50", 21, 50),
    ("50+", 51, float("inf")),
]


def compute_length_distribution(summaries: list[dict]) -> dict[str, Any]:
    """Bucket conversation lengths into a histogram distribution."""
    counts = [0] * len(_LENGTH_BUCKETS)
    for s in summaries:
        mc = s["message_count"]
        for i, (_, lo, hi) in enumerate(_LENGTH_BUCKETS):
            if lo <= mc <= hi:
                counts[i] += 1
                break
    return {
        "buckets": [b[0] for b in _LENGTH_BUCKETS],
        "counts": counts,
    }
```

**Step 4: Run tests**

Run: `./venv/bin/pytest tests/test_analytics.py::TestComputeLengthDistribution -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add analytics.py tests/test_analytics.py
git commit -m "feat(analytics): add compute_length_distribution for histogram"
```

---

### Task 5: Add `compute_period_comparison` to analytics.py

**Files:**
- Modify: `analytics.py`
- Test: `tests/test_analytics.py`

**Step 1: Write the failing test**

```python
from analytics import compute_period_comparison

class TestComputePeriodComparison:
    def test_month_comparison(self):
        records = [
            {"date": "2024-01-15", "total_messages": 10, "total_chats": 2, "avg_messages_per_chat": 5.0, "max_messages_in_chat": 6},
            {"date": "2024-01-20", "total_messages": 8, "total_chats": 1, "avg_messages_per_chat": 8.0, "max_messages_in_chat": 8},
            {"date": "2024-02-05", "total_messages": 20, "total_chats": 5, "avg_messages_per_chat": 4.0, "max_messages_in_chat": 6},
        ]
        # reference_date as Feb 15, 2024 — "this month" is Feb, "last month" is Jan
        result = compute_period_comparison(records, reference_date="2024-02-15")
        assert result["this_month"]["chats"] == 5
        assert result["this_month"]["messages"] == 20
        assert result["last_month"]["chats"] == 3
        assert result["last_month"]["messages"] == 18

    def test_year_comparison(self):
        records = [
            {"date": "2023-06-15", "total_messages": 100, "total_chats": 10, "avg_messages_per_chat": 10.0, "max_messages_in_chat": 15},
            {"date": "2024-03-15", "total_messages": 50, "total_chats": 5, "avg_messages_per_chat": 10.0, "max_messages_in_chat": 12},
        ]
        result = compute_period_comparison(records, reference_date="2024-06-15")
        assert result["this_year"]["chats"] == 5
        assert result["last_year"]["chats"] == 10

    def test_empty_periods(self):
        result = compute_period_comparison([], reference_date="2024-02-15")
        assert result["this_month"]["chats"] == 0
        assert result["last_month"]["chats"] == 0
        assert result["this_year"]["chats"] == 0
        assert result["last_year"]["chats"] == 0
```

**Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_analytics.py::TestComputePeriodComparison -v`
Expected: ImportError

**Step 3: Write minimal implementation**

```python
def compute_period_comparison(
    daily_records: list[dict],
    reference_date: str | None = None,
) -> dict[str, Any]:
    """Compute month-over-month and year-over-year comparison stats."""
    from datetime import date as date_type

    if reference_date:
        ref = date_type.fromisoformat(reference_date)
    else:
        ref = date_type.today()

    this_month = f"{ref.year}-{ref.month:02d}"
    # Previous month
    if ref.month == 1:
        last_month = f"{ref.year - 1}-12"
    else:
        last_month = f"{ref.year}-{ref.month - 1:02d}"
    this_year = str(ref.year)
    last_year = str(ref.year - 1)

    def _zero():
        return {"chats": 0, "messages": 0, "total_msgs": 0, "total_chats": 0}

    buckets = {
        "this_month": _zero(),
        "last_month": _zero(),
        "this_year": _zero(),
        "last_year": _zero(),
    }

    for r in daily_records:
        d = r["date"]
        m = d[:7]
        y = d[:4]
        for key, match_val, match_field in [
            ("this_month", this_month, m),
            ("last_month", last_month, m),
            ("this_year", this_year, y),
            ("last_year", last_year, y),
        ]:
            if match_field == match_val:
                buckets[key]["chats"] += r["total_chats"]
                buckets[key]["messages"] += r["total_messages"]
                buckets[key]["total_msgs"] += r["total_messages"]
                buckets[key]["total_chats"] += r["total_chats"]

    result = {}
    for key in ["this_month", "last_month", "this_year", "last_year"]:
        b = buckets[key]
        avg = round(b["total_msgs"] / b["total_chats"], 2) if b["total_chats"] > 0 else 0
        result[key] = {
            "chats": b["chats"],
            "messages": b["messages"],
            "avg_messages": avg,
        }

    return result
```

**Step 4: Run tests**

Run: `./venv/bin/pytest tests/test_analytics.py::TestComputePeriodComparison -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add analytics.py tests/test_analytics.py
git commit -m "feat(analytics): add compute_period_comparison for overview cards"
```

---

### Task 6: Update `build_dashboard_payload` and add new API data

**Files:**
- Modify: `analytics.py:311-335` (the `build_dashboard_payload` function)
- Test: `tests/test_analytics.py`

**Step 1: Update existing integration test**

In `tests/test_analytics.py`, update `TestBuildDashboardPayload.test_integration`:

```python
class TestBuildDashboardPayload:
    def test_integration(self, tmp_path):
        convos = _make_conversations_with_days([
            ("2024-01-15", 2, 3),
            ("2024-01-16", 1, 5),
        ])
        json_file = tmp_path / "conversations.json"
        json_file.write_text(json.dumps(convos))

        payload = build_dashboard_payload(str(json_file))

        # Existing assertions
        assert "summary" in payload
        assert "charts" in payload
        assert "gaps" in payload
        assert "gap_stats" in payload
        assert "generated_at" in payload
        assert payload["summary"]["total_chats"] == 3
        assert payload["summary"]["total_messages"] == 11
        assert len(payload["charts"]["dates"]) == 2
        assert "avg_7d" in payload["charts"]["chats"]
        assert "avg_lifetime" in payload["charts"]["total_messages"]

        # New assertions for multi-page data
        assert "monthly" in payload
        assert "weekly" in payload
        assert "hourly" in payload
        assert "length_distribution" in payload
        assert "comparison" in payload

        assert len(payload["monthly"]["months"]) >= 1
        assert len(payload["hourly"]["heatmap"]) == 7
        assert len(payload["length_distribution"]["buckets"]) == 6
```

**Step 2: Run test to see it fail**

Run: `./venv/bin/pytest tests/test_analytics.py::TestBuildDashboardPayload -v`
Expected: FAIL — missing keys

**Step 3: Update `build_dashboard_payload`**

In `analytics.py`, modify the function:

```python
def build_dashboard_payload(path: str = "conversations.json") -> dict[str, Any]:
    """One-call entry point: load, process, compute all stats for the dashboard."""
    convos = load_conversations(path)
    summaries, records, timestamps = process_conversations(convos)
    gap_data = compute_gap_analysis(timestamps)
    stats = compute_summary_stats(summaries, records)
    charts = compute_chart_data(records)

    return {
        "generated_at": datetime.now().isoformat(),
        "summary": stats,
        "charts": charts,
        "gaps": _top_gaps_per_year(gap_data["gaps"], per_year=25),
        "gap_stats": {
            "total_days": gap_data["total_days"],
            "days_active": gap_data["days_active"],
            "days_inactive": gap_data["days_inactive"],
            "proportion_inactive": gap_data["proportion_inactive"],
            "longest_gap": gap_data["longest_gap"],
        },
        "monthly": compute_monthly_data(records),
        "weekly": compute_weekly_data(records),
        "hourly": compute_hourly_data(timestamps),
        "length_distribution": compute_length_distribution(summaries),
        "comparison": compute_period_comparison(records),
    }
```

**Step 4: Run all tests**

Run: `./venv/bin/pytest tests/test_analytics.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add analytics.py tests/test_analytics.py
git commit -m "feat(analytics): extend dashboard payload with multi-page data"
```

---

### Task 7: Set up Jinja2 templates directory and shared base

**Files:**
- Create: `templates/base.html`
- Modify: `app.py` (set up Jinja2Templates)

**Step 1: Create templates directory**

```bash
mkdir -p templates
```

**Step 2: Create `templates/base.html`**

This is the shared base template with navigation, styles, and the data injection pattern. Extract the existing CSS from `dashboard_template.html` plus add navigation styles.

Key elements:
- All existing CSS variables and styles from current template
- New nav bar with Overview / Trends / Patterns links
- `{% block content %}` for page-specific content
- `{% block scripts %}` for page-specific JS
- Data injection: `const DASHBOARD_DATA = {{ data_json | safe }};`

**Step 3: Update `app.py` to use Jinja2Templates**

```python
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
```

Add `starlette` to the route handlers (FastAPI uses Starlette's Request internally — no new dependency needed).

**Step 4: Verify app starts without errors**

Run: `cd /home/pi/python/chatgpt_stats && source venv/bin/activate && python -c "from app import app; print('OK')"`
Expected: "OK"

**Step 5: Commit**

```bash
git add templates/base.html app.py
git commit -m "feat: add Jinja2 template base with shared nav"
```

---

### Task 8: Create Overview page template

**Files:**
- Create: `templates/overview.html`
- Modify: `app.py` (update `GET /` route)

**Step 1: Create `templates/overview.html`**

Extends `base.html`. Contains:
- Summary cards (ported from existing template)
- Month-over-month comparison cards (new)
- Monthly usage chart (Chart.js, ~36 bars)
- Conversation length histogram (Chart.js horizontal bar)

All JS for chart rendering is in a `{% block scripts %}` section.

**Step 2: Update the `/` route in `app.py`**

```python
@app.get("/", response_class=HTMLResponse)
def overview(request: Request):
    data = _get_cached_data()
    data_json = json.dumps(data, ensure_ascii=False).replace("</", r"<\/")
    return templates.TemplateResponse(
        "overview.html",
        {"request": request, "data_json": data_json},
    )
```

**Step 3: Test manually**

Run: `curl -s http://127.0.0.1:8203/ | head -20`
Expected: HTML with nav bar and overview content

**Step 4: Commit**

```bash
git add templates/overview.html app.py
git commit -m "feat: add overview page with monthly chart and histogram"
```

---

### Task 9: Create Trends page template

**Files:**
- Create: `templates/trends.html`
- Modify: `app.py` (add `GET /trends` route)

**Step 1: Create `templates/trends.html`**

Extends `base.html`. Contains:
- Granularity switcher pills (Daily | Weekly | Monthly)
- Year scope pills (All | 2023 | 2024 | 2025 | 2026)
- Three trend charts (chats, avg messages, total messages)
- Top days tables (ported from existing)

**JS logic for granularity switching:**
```javascript
// The payload contains charts (daily), weekly, and monthly data
// When user clicks a granularity pill:
// - "Daily" → use D.charts.dates, D.charts.chats.values, etc.
// - "Weekly" → use D.weekly.weeks, D.weekly.chats, etc.
// - "Monthly" → use D.monthly.months, D.monthly.chats, etc.
// Destroy old charts, build new ones with the selected dataset
```

**JS logic for year scoping:**
Filter the selected dataset's arrays to only include entries where the date starts with the selected year prefix. Then rebuild charts.

**Step 2: Add the route**

```python
@app.get("/trends", response_class=HTMLResponse)
def trends(request: Request):
    data = _get_cached_data()
    data_json = json.dumps(data, ensure_ascii=False).replace("</", r"<\/")
    return templates.TemplateResponse(
        "trends.html",
        {"request": request, "data_json": data_json},
    )
```

**Step 3: Test manually**

Run: `curl -s http://127.0.0.1:8203/trends | head -20`
Expected: HTML with granularity pills and chart canvases

**Step 4: Commit**

```bash
git add templates/trends.html app.py
git commit -m "feat: add trends page with switchable granularity"
```

---

### Task 10: Create Patterns page template

**Files:**
- Create: `templates/patterns.html`
- Modify: `app.py` (add `GET /patterns` route)

**Step 1: Create `templates/patterns.html`**

Extends `base.html`. Contains:
- Day×hour heatmap (Canvas-based or Chart.js matrix, see note below)
- Busiest hours horizontal bar chart
- Weekday vs weekend comparison cards
- Gap analysis table (ported from existing, with year pills)

**Heatmap implementation note:** Chart.js doesn't have a built-in heatmap. Two options:
1. Use `chartjs-chart-matrix` plugin — adds a dependency but clean integration
2. Render as an HTML table/grid with CSS background colors — zero dependencies, simpler

Recommend option 2 (CSS grid heatmap) — it's simpler, more mobile-friendly, and avoids another Chart.js plugin. Each cell is a `<div>` with `background-color` set via inline style based on the count value, using the amber color scale from the design system.

**Step 2: Add the route**

```python
@app.get("/patterns", response_class=HTMLResponse)
def patterns(request: Request):
    data = _get_cached_data()
    data_json = json.dumps(data, ensure_ascii=False).replace("</", r"<\/")
    return templates.TemplateResponse(
        "patterns.html",
        {"request": request, "data_json": data_json},
    )
```

**Step 3: Test manually**

Run: `curl -s http://127.0.0.1:8203/patterns | head -20`
Expected: HTML with heatmap grid and chart canvases

**Step 4: Commit**

```bash
git add templates/patterns.html app.py
git commit -m "feat: add patterns page with heatmap and gap analysis"
```

---

### Task 11: Remove old template, update tests, final polish

**Files:**
- Delete: `dashboard_template.html` (replaced by templates/)
- Modify: `app.py` (remove old template references)
- Modify: `CLAUDE.md` (update architecture docs)

**Step 1: Remove references to old template**

In `app.py`, remove:
- `TEMPLATE_PATH` constant
- `DATA_PLACEHOLDER` constant
- The old string-replacement logic in `dashboard_html()`

These are now replaced by the Jinja2 template rendering.

**Step 2: Delete old template file**

```bash
git rm dashboard_template.html
```

**Step 3: Update CLAUDE.md**

Update the Architecture section to reflect the new multi-page structure:
- `templates/base.html` — Shared nav, styles, Jinja2 base
- `templates/overview.html` — Overview page (summary cards, monthly chart, histogram, comparison)
- `templates/trends.html` — Trends page (granularity switcher, 3 trend charts, top days)
- `templates/patterns.html` — Patterns page (heatmap, hourly chart, gap analysis)

Update the API Endpoints table to include `/trends` and `/patterns`.

**Step 4: Run all tests**

Run: `./venv/bin/pytest tests/ -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add -A
git commit -m "refactor: remove old single-page template, update docs"
```

---

### Task 12: Restart service and verify on device

**Step 1: Restart production service**

```bash
sudo systemctl restart chatgpt-stats
```

**Step 2: Verify all pages load**

```bash
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8203/
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8203/trends
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8203/patterns
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8203/healthz
```

Expected: All return 200

**Step 3: Test on iPhone**

Open on your phone via Tailscale:
- `http://100.99.217.84/chatgpt_stats/` — Overview
- `http://100.99.217.84/chatgpt_stats/trends` — Trends (try switching granularity)
- `http://100.99.217.84/chatgpt_stats/patterns` — Patterns (check heatmap readability)

**Step 4: Final commit and push**

```bash
git push
```

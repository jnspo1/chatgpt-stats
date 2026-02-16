# Pro-rata Comparisons, Icon Removal, Multi-select Year Pills — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make period comparisons fair by projecting partial current periods forward, remove the G icon, and enable multi-year selection on trends/patterns pages.

**Architecture:** Backend change to `compute_period_comparison()` adds projection metadata. Frontend changes update comparison card rendering and convert year pill bars from single-select to multi-select toggle behavior.

**Tech Stack:** Python (analytics.py), Jinja2 HTML templates, vanilla JS, Chart.js

---

### Task 1: Add pro-rata projection fields to `compute_period_comparison()`

**Files:**
- Modify: `analytics.py:464-520` — `compute_period_comparison()`
- Test: `tests/test_analytics.py`

**Step 1: Write failing tests for pro-rata fields**

Add to `tests/test_analytics.py` in the `TestComputePeriodComparison` class:

```python
def test_prorata_month_projection(self):
    """Mid-month: projected values scale up to full month."""
    records = [
        {"date": "2024-02-05", "total_messages": 20, "total_chats": 5,
         "avg_messages_per_chat": 4.0, "max_messages_in_chat": 6},
        {"date": "2024-02-10", "total_messages": 10, "total_chats": 3,
         "avg_messages_per_chat": 3.33, "max_messages_in_chat": 5},
    ]
    # Reference date is Feb 15 → 15 days elapsed of 29 (2024 is leap year)
    result = compute_period_comparison(records, reference_date="2024-02-15")
    tm = result["this_month"]
    assert tm["chats"] == 8
    assert tm["messages"] == 30
    assert tm["elapsed_days"] == 15
    assert tm["total_days"] == 29  # Feb 2024 is 29 days (leap year)
    # projected_chats = 8 * (29 / 15) ≈ 15.47 → rounded to 2dp
    assert tm["projected_chats"] == pytest.approx(8 * 29 / 15, abs=0.01)
    assert tm["projected_messages"] == pytest.approx(30 * 29 / 15, abs=0.01)

def test_prorata_year_projection(self):
    """Partial year: projected values scale up to full year."""
    records = [
        {"date": "2024-01-15", "total_messages": 50, "total_chats": 10,
         "avg_messages_per_chat": 5.0, "max_messages_in_chat": 8},
    ]
    # Reference date is Feb 15, 2024 → 46 days elapsed of 366 (leap year)
    result = compute_period_comparison(records, reference_date="2024-02-15")
    ty = result["this_year"]
    assert ty["chats"] == 10
    assert ty["messages"] == 50
    assert ty["elapsed_days"] == 46
    assert ty["total_days"] == 366  # 2024 is leap year
    assert ty["projected_chats"] == pytest.approx(10 * 366 / 46, abs=0.01)

def test_prorata_last_periods_have_no_projection(self):
    """Last month/year are complete periods — no projection fields."""
    records = [
        {"date": "2024-01-15", "total_messages": 10, "total_chats": 2,
         "avg_messages_per_chat": 5.0, "max_messages_in_chat": 6},
    ]
    result = compute_period_comparison(records, reference_date="2024-02-15")
    lm = result["last_month"]
    ly = result["last_year"]
    assert "projected_chats" not in lm
    assert "projected_chats" not in ly
    assert "elapsed_days" not in lm
    assert "elapsed_days" not in ly

def test_prorata_day_one_of_month(self):
    """Day 1: elapsed=1, projection multiplier is large but correct."""
    records = [
        {"date": "2024-03-01", "total_messages": 5, "total_chats": 1,
         "avg_messages_per_chat": 5.0, "max_messages_in_chat": 5},
    ]
    result = compute_period_comparison(records, reference_date="2024-03-01")
    tm = result["this_month"]
    assert tm["elapsed_days"] == 1
    assert tm["total_days"] == 31  # March
    assert tm["projected_chats"] == pytest.approx(1 * 31 / 1, abs=0.01)
```

**Step 2: Run tests to verify they fail**

Run: `./venv/bin/pytest tests/test_analytics.py::TestComputePeriodComparison -v`
Expected: 4 new tests FAIL with KeyError on `elapsed_days` / `projected_chats`

**Step 3: Implement pro-rata in `compute_period_comparison()`**

In `analytics.py`, modify `compute_period_comparison()`. After the existing loop that builds `result`, add projection fields for `this_month` and `this_year` only:

```python
import calendar

# At the end of compute_period_comparison(), replace the result-building loop:

    result = {}
    for key in ["this_month", "last_month", "this_year", "last_year"]:
        b = buckets[key]
        avg = round(b["total_msgs"] / b["total_chats"], 2) if b["total_chats"] > 0 else 0
        result[key] = {
            "chats": b["chats"],
            "messages": b["messages"],
            "avg_messages": avg,
        }

    # Pro-rata projection for current (partial) periods
    month_total_days = calendar.monthrange(ref.year, ref.month)[1]
    month_elapsed = ref.day
    year_total_days = 366 if calendar.isleap(ref.year) else 365
    year_elapsed = (ref - date_type(ref.year, 1, 1)).days + 1

    for key, elapsed, total in [
        ("this_month", month_elapsed, month_total_days),
        ("this_year", year_elapsed, year_total_days),
    ]:
        r = result[key]
        r["elapsed_days"] = elapsed
        r["total_days"] = total
        factor = total / elapsed if elapsed > 0 else 1
        r["projected_chats"] = round(r["chats"] * factor, 2)
        r["projected_messages"] = round(r["messages"] * factor, 2)

    return result
```

Also add `import calendar` at the top of the file (alongside existing imports).

**Step 4: Run tests to verify they pass**

Run: `./venv/bin/pytest tests/test_analytics.py::TestComputePeriodComparison -v`
Expected: All tests PASS (including existing ones)

**Step 5: Commit**

```bash
git add analytics.py tests/test_analytics.py
git commit -m "feat(analytics): add pro-rata projection to period comparison"
```

---

### Task 2: Remove G icon from header

**Files:**
- Modify: `templates/base.html:63-69` (CSS) and `templates/base.html:268` (HTML)

**Step 1: Remove the `.header-mark` CSS rule**

In `templates/base.html`, delete these lines (63-69):

```css
  .header-mark {
    width: 32px; height: 32px; border-radius: 8px;
    background: linear-gradient(135deg, var(--amber) 0%, var(--amber-dim) 100%);
    display: flex; align-items: center; justify-content: center;
    font-size: 16px; font-weight: 700; color: var(--bg);
    letter-spacing: -0.5px;
  }
```

**Step 2: Remove the G icon HTML element**

In `templates/base.html`, remove line 268:

```html
    <div class="header-mark">G</div>
```

**Step 3: Commit**

```bash
git add templates/base.html
git commit -m "fix(ui): remove G icon from header"
```

---

### Task 3: Update overview comparison cards to use projected values

**Files:**
- Modify: `templates/overview.html:90-135` — comparison card rendering

**Step 1: Update `buildComparisonCard()` to show projection info**

In `templates/overview.html`, replace the comparison card section (lines 90-135) with:

```javascript
  // ── Comparison Cards ─────────────────────
  var comp = D.comparison;
  if (comp) {
    var grid = document.getElementById('comparison-grid');

    function pctChange(newVal, oldVal) {
      if (oldVal === 0) return newVal > 0 ? { text: 'New', cls: 'up' } : { text: '\u2014', cls: 'neutral' };
      var pct = ((newVal - oldVal) / oldVal * 100).toFixed(0);
      if (pct > 0) return { text: '+' + pct + '%', cls: 'up' };
      if (pct < 0) return { text: pct + '%', cls: 'down' };
      return { text: '0%', cls: 'neutral' };
    }

    function buildComparisonCard(title, current, previous, subtitle) {
      var card = el('div', { className: 'comparison-card' });
      card.appendChild(txt('h3', title));
      if (subtitle) card.appendChild(txt('div', subtitle, 'comparison-subtitle'));

      var metrics = [
        { label: 'Chats', cur: current.chats, prev: previous.chats, proj: current.projected_chats },
        { label: 'Messages', cur: current.messages, prev: previous.messages, proj: current.projected_messages },
        { label: 'Avg msgs/chat', cur: current.avg_messages, prev: previous.avg_messages },
      ];

      metrics.forEach(function(m) {
        var compareVal = m.proj != null ? m.proj : m.cur;
        var change = pctChange(compareVal, m.prev);
        var row = el('div', { className: 'comparison-row' });
        row.appendChild(txt('span', m.label, 'comparison-label'));
        var vals = el('div', { className: 'comparison-values' });
        vals.appendChild(txt('span', m.prev.toLocaleString(), 'comparison-old'));
        vals.appendChild(txt('span', '\u2192'));
        vals.appendChild(txt('span', m.cur.toLocaleString(), 'comparison-new'));
        if (m.proj != null) {
          vals.appendChild(txt('span', '(\u2248' + Math.round(m.proj).toLocaleString() + ')', 'comparison-proj'));
        }
        vals.appendChild(txt('span', change.text, 'comparison-change ' + change.cls));
        row.appendChild(vals);
        card.appendChild(row);
      });

      return card;
    }

    var tmSub = comp.this_month.elapsed_days + ' of ' + comp.this_month.total_days + ' days';
    var tySub = comp.this_year.elapsed_days + ' of ' + comp.this_year.total_days + ' days';

    grid.appendChild(buildComparisonCard(
      'This Month vs Last Month', comp.this_month, comp.last_month, tmSub
    ));
    grid.appendChild(buildComparisonCard(
      'This Year vs Last Year', comp.this_year, comp.last_year, tySub
    ));
  }
```

**Step 2: Add CSS for the new elements**

In `templates/base.html`, add these rules after the existing `.comparison-change.neutral` rule (around line 233):

```css
  .comparison-subtitle {
    font-size: 11px; color: var(--text-muted); margin-bottom: 10px;
    font-family: 'JetBrains Mono', monospace;
  }
  .comparison-proj {
    font-size: 10px; color: var(--text-muted); font-style: italic;
  }
```

**Step 3: Verify visually**

Run: `sudo systemctl restart chatgpt-stats` then check the overview page.

**Step 4: Commit**

```bash
git add templates/overview.html templates/base.html
git commit -m "feat(ui): show pro-rata projections in comparison cards"
```

---

### Task 4: Multi-select year pills on trends page

**Files:**
- Modify: `templates/trends.html:139-151` — `filterByYear()` function
- Modify: `templates/trends.html:235-265` — `createPills()` function and year pill setup

**Step 1: Replace `createPills()` to support multi-select for year pills**

In `templates/trends.html`, replace the `createPills` function and year pill setup (lines 235-265) with:

```javascript
  // ── Single-select pills (granularity) ──
  function createSinglePills(containerId, options, defaultVal, onChange) {
    var bar = document.getElementById(containerId);
    options.forEach(function(opt) {
      var pill = txt('span', opt, 'pill' + (opt === defaultVal ? ' active' : ''));
      pill.addEventListener('click', function() {
        bar.querySelectorAll('.pill').forEach(function(p) { p.classList.remove('active'); });
        pill.classList.add('active');
        onChange(opt);
      });
      bar.appendChild(pill);
    });
  }

  // ── Multi-select pills (years) ──
  function createMultiPills(containerId, options, onChange) {
    var bar = document.getElementById(containerId);
    var allPill = null;

    function getSelected() {
      var selected = [];
      bar.querySelectorAll('.pill').forEach(function(p) {
        if (p.classList.contains('active') && p.textContent !== 'All') {
          selected.push(p.textContent);
        }
      });
      return selected;
    }

    function syncAllPill() {
      var yearPills = bar.querySelectorAll('.pill:not([data-all])');
      var allActive = true;
      yearPills.forEach(function(p) { if (!p.classList.contains('active')) allActive = false; });
      if (allActive || getSelected().length === 0) {
        allPill.classList.add('active');
        yearPills.forEach(function(p) { p.classList.add('active'); });
      } else {
        allPill.classList.remove('active');
      }
    }

    options.forEach(function(opt) {
      var pill = txt('span', opt, 'pill active');
      if (opt === 'All') {
        pill.setAttribute('data-all', 'true');
        allPill = pill;
        pill.addEventListener('click', function() {
          bar.querySelectorAll('.pill').forEach(function(p) { p.classList.add('active'); });
          onChange(['All']);
        });
      } else {
        pill.addEventListener('click', function() {
          pill.classList.toggle('active');
          var selected = getSelected();
          if (selected.length === 0) {
            allPill.classList.add('active');
            bar.querySelectorAll('.pill:not([data-all])').forEach(function(p) { p.classList.add('active'); });
            onChange(['All']);
          } else {
            syncAllPill();
            onChange(selected);
          }
        });
      }
      bar.appendChild(pill);
    });
  }

  createSinglePills('granularity-pills', ['Daily', 'Weekly', 'Monthly'], 'Weekly', function(val) {
    currentGranularity = val.toLowerCase();
    renderCharts();
  });

  var years = ['All'];
  if (D.charts && D.charts.dates) {
    var yearSet = {};
    D.charts.dates.forEach(function(d) { yearSet[d.substring(0, 4)] = true; });
    Object.keys(yearSet).sort().forEach(function(y) { years.push(y); });
  }

  createMultiPills('year-pills', years, function(selected) {
    selectedYears = selected;
    renderCharts();
    renderTopTables();
  });
```

**Step 2: Update state variable and `filterByYear()`**

Replace the state variable `currentYear` (line 81) with:

```javascript
  var selectedYears = ['All'];
```

Replace `filterByYear()` (lines 139-151) with:

```javascript
  function filterByYear(dates, arrays, years) {
    if (years.indexOf('All') >= 0 || years.length === 0) return { dates: dates, arrays: arrays };
    var filtered = { dates: [], arrays: arrays.map(function() { return []; }) };
    for (var i = 0; i < dates.length; i++) {
      var yr = dates[i].substring(0, 4);
      if (years.indexOf(yr) >= 0) {
        filtered.dates.push(dates[i]);
        for (var j = 0; j < arrays.length; j++) {
          filtered.arrays[j].push(arrays[j][i]);
        }
      }
    }
    return filtered;
  }
```

Update `renderCharts()` call (line 218) from `filterByYear(ds.dates, allArrays, currentYear)` to:

```javascript
    var f = filterByYear(ds.dates, allArrays, selectedYears);
```

Update `filterTableByYear()` (line 273) from single year to multi:

```javascript
  function filterTableByYear(rows, years, dateKey) {
    if (years.indexOf('All') >= 0 || years.length === 0) return rows;
    return rows.filter(function(r) { return years.indexOf(r[dateKey].substring(0, 4)) >= 0; });
  }
```

Update call at line 293 from `currentYear` to `selectedYears`:

```javascript
    var filtered = filterTableByYear(rows, selectedYears, 'date').slice(0, TOP_DAYS_LIMIT);
```

**Step 3: Commit**

```bash
git add templates/trends.html
git commit -m "feat(ui): multi-select year pills on trends page"
```

---

### Task 5: Multi-select year pills on patterns page (gap analysis)

**Files:**
- Modify: `templates/patterns.html:427-496` — gap analysis pill bar and filter

**Step 1: Update gap analysis pills to multi-select**

In `templates/patterns.html`, replace the single-select gap pill bar (lines 447-458) and the filter function (lines 475-479) with multi-select logic:

Replace the state variable `currentGapYear` (line 427) with:

```javascript
  var selectedGapYears = ['All'];
```

Replace the pill bar creation (lines 448-458) with:

```javascript
    var allGapPill = null;

    function getSelectedGapYears() {
      var selected = [];
      pillBar.querySelectorAll('.pill').forEach(function(p) {
        if (p.classList.contains('active') && p.textContent !== 'All') {
          selected.push(p.textContent);
        }
      });
      return selected;
    }

    function syncGapAllPill() {
      var yearPills = pillBar.querySelectorAll('.pill:not([data-all])');
      var allActive = true;
      yearPills.forEach(function(p) { if (!p.classList.contains('active')) allActive = false; });
      if (allActive || getSelectedGapYears().length === 0) {
        allGapPill.classList.add('active');
        yearPills.forEach(function(p) { p.classList.add('active'); });
      } else {
        allGapPill.classList.remove('active');
      }
    }

    gapYears.forEach(function(yr) {
      var pill = txt('span', yr, 'pill active');
      if (yr === 'All') {
        pill.setAttribute('data-all', 'true');
        allGapPill = pill;
        pill.addEventListener('click', function() {
          pillBar.querySelectorAll('.pill').forEach(function(p) { p.classList.add('active'); });
          selectedGapYears = ['All'];
          renderGapRows();
        });
      } else {
        pill.addEventListener('click', function() {
          pill.classList.toggle('active');
          var selected = getSelectedGapYears();
          if (selected.length === 0) {
            allGapPill.classList.add('active');
            pillBar.querySelectorAll('.pill:not([data-all])').forEach(function(p) { p.classList.add('active'); });
            selectedGapYears = ['All'];
          } else {
            syncGapAllPill();
            selectedGapYears = selected;
          }
          renderGapRows();
        });
      }
      pillBar.appendChild(pill);
    });
```

Replace `filterGapsByYear()` (lines 475-479) with:

```javascript
    function filterGapsByYear(gaps, years) {
      if (years.indexOf('All') >= 0 || years.length === 0) return gaps;
      return gaps.filter(function(g) {
        return years.indexOf(g.start_timestamp.substring(0, 4)) >= 0;
      });
    }
```

Update the call in `renderGapRows()` (line 484) from `currentGapYear` to `selectedGapYears`:

```javascript
      var filtered = filterGapsByYear(D.gaps, selectedGapYears).slice(0, TOP_GAPS_LIMIT);
```

**Step 2: Commit**

```bash
git add templates/patterns.html
git commit -m "feat(ui): multi-select year pills on patterns page"
```

---

### Task 6: Run full test suite, restart service, verify

**Step 1: Run all tests**

Run: `./venv/bin/pytest tests/ -v`
Expected: All tests PASS

**Step 2: Restart the service**

Run: `sudo systemctl restart chatgpt-stats`

**Step 3: Verify each change visually**

1. Overview page: Comparison cards show "(≈projected)" values and "X of Y days" subtitles
2. Overview page: No G icon in header — just the h1 text
3. Trends page: Year pills are multi-select — click toggles individual years, "All" resets
4. Patterns page: Gap analysis year pills are multi-select with same behavior

**Step 4: Final commit (if any fixups needed)**

```bash
git add -A
git commit -m "fix: address visual polish from verification"
```

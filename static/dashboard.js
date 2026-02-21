/**
 * Shared dashboard helpers for ChatGPT Statistics.
 *
 * Provides DOM utilities, date formatting, and Chart.js default
 * configuration used across all dashboard pages.
 *
 * @namespace DashboardHelpers
 */

/**
 * Create a DOM element with optional attributes and children.
 * @param {string} tag - HTML tag name.
 * @param {Object<string, string>} [attrs] - Attribute map. Use 'className' for class, 'textContent' for text.
 * @param {HTMLElement[]} [children] - Child elements to append.
 * @returns {HTMLElement} The created element.
 */
function el(tag, attrs, children) {
  const e = document.createElement(tag);
  if (attrs) {
    Object.keys(attrs).forEach(function(k) {
      if (k === 'className') e.className = attrs[k];
      else if (k === 'textContent') e.textContent = attrs[k];
      else e.setAttribute(k, attrs[k]);
    });
  }
  if (children) children.forEach(function(c) { if (c) e.appendChild(c); });
  return e;
}

/**
 * Create a text-only DOM element with optional class.
 * @param {string} tag - HTML tag name.
 * @param {string} text - Text content.
 * @param {string} [cls] - CSS class name.
 * @returns {HTMLElement} The created element.
 */
function txt(tag, text, cls) {
  const e = document.createElement(tag);
  e.textContent = text;
  if (cls) e.className = cls;
  return e;
}

/**
 * Remove all child nodes from a DOM element.
 * @param {HTMLElement} node - The parent element to clear.
 */
function clearChildren(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

/**
 * Format an ISO date string as a locale-friendly short date.
 * @param {string} isoStr - ISO 8601 date string (e.g. '2024-01-15').
 * @returns {string} Formatted date like 'Jan 15, 2024'.
 */
function formatDate(isoStr) {
  const d = new Date(isoStr);
  return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
}

/**
 * Apply shared Chart.js default styles used across all pages.
 * Call once at the start of each page's chart initialization.
 */
function applyChartDefaults() {
  Chart.defaults.color = cssVar('--text-dim');
  Chart.defaults.borderColor = cssVar('--border');
  Chart.defaults.font.family = "'DM Sans', sans-serif";
  Chart.defaults.font.size = 11;
}

/**
 * Read a CSS custom property value from the document root.
 * @param {string} name - Variable name including '--' prefix (e.g. '--amber').
 * @returns {string} The trimmed property value.
 */
function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/**
 * Read a CSS custom property (hex colour) and return it as rgba with the given alpha.
 * @param {string} name - Variable name including '--' prefix (e.g. '--skyblue').
 * @param {number} alpha - Opacity value between 0 and 1.
 * @returns {string} CSS rgba colour string.
 */
function cssAlpha(name, alpha) {
  const hex = cssVar(name);
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
}

/**
 * Build the full dataset descriptor (dates, bar values, rolling-average lines)
 * for the three usage charts at the requested granularity.
 * @param {Object} D - The DASHBOARD_DATA object
 * @param {string} granularity - 'daily' | 'weekly' | 'monthly'
 * @returns {Object} Dataset descriptor with dates, chats, avg_messages, total_messages, timeUnit, dateFormat
 */
function getDatasets(D, granularity) {
  if (granularity === 'daily') {
    return {
      dates: D.charts.dates,
      chats: { values: D.charts.chats.values, lines: [
        { label: '7-day avg', data: D.charts.chats.avg_7d, color: cssVar('--red') },
        { label: '28-day avg', data: D.charts.chats.avg_28d, color: cssVar('--green') },
      ]},
      avg_messages: { values: D.charts.avg_messages.values, lines: [
        { label: '7-day avg', data: D.charts.avg_messages.avg_7d, color: cssVar('--red') },
        { label: '28-day avg', data: D.charts.avg_messages.avg_28d, color: cssVar('--green') },
      ]},
      total_messages: { values: D.charts.total_messages.values, lines: [
        { label: '7-day avg', data: D.charts.total_messages.avg_7d, color: cssVar('--red') },
        { label: '28-day avg', data: D.charts.total_messages.avg_28d, color: cssVar('--green') },
      ]},
      timeUnit: 'month',
      dateFormat: 'MMM yyyy',
    };
  } else if (granularity === 'weekly') {
    return {
      dates: D.weekly.weeks,
      chats: { values: D.weekly.chats, lines: [
        { label: '4-week avg', data: D.weekly.chats_avg_4w, color: cssVar('--red') },
        { label: '12-week avg', data: D.weekly.chats_avg_12w, color: cssVar('--green') },
      ]},
      avg_messages: { values: D.weekly.avg_messages, lines: [
        { label: '4-week avg', data: D.weekly.avg_messages_avg_4w, color: cssVar('--red') },
        { label: '12-week avg', data: D.weekly.avg_messages_avg_12w, color: cssVar('--green') },
      ]},
      total_messages: { values: D.weekly.messages, lines: [
        { label: '4-week avg', data: D.weekly.messages_avg_4w, color: cssVar('--red') },
        { label: '12-week avg', data: D.weekly.messages_avg_12w, color: cssVar('--green') },
      ]},
      timeUnit: 'month',
      dateFormat: 'MMM yyyy',
    };
  } else { // monthly
    return {
      dates: D.monthly.months.map(function(m) { return `${m}-01`; }),
      chats: { values: D.monthly.chats, lines: [
        { label: '3-month avg', data: D.monthly.chats_avg_3m, color: cssVar('--red') },
      ]},
      avg_messages: { values: D.monthly.avg_messages, lines: []},
      total_messages: { values: D.monthly.messages, lines: [
        { label: '3-month avg', data: D.monthly.messages_avg_3m, color: cssVar('--red') },
      ]},
      timeUnit: 'quarter',
      dateFormat: 'MMM yyyy',
    };
  }
}

/**
 * Filter parallel arrays by selected years. Returns only entries whose date
 * string starts with one of the selected year values.
 * @param {string[]} dates - Array of date strings (YYYY-MM-DD or similar)
 * @param {Array[]} arrays - Parallel data arrays to filter in sync with dates
 * @param {string[]} years - Selected year strings, or ['All'] for no filtering
 * @returns {Object} Object with dates (string[]) and arrays (Array[]) filtered by year
 */
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

/**
 * Create a row of single-select pill buttons. Clicking one deactivates all
 * others and fires the onChange callback with the selected value.
 * @param {string} containerId - DOM id of the pill bar container
 * @param {string[]} options - Labels for each pill
 * @param {string} defaultVal - Initially active pill label
 * @param {function(string): void} onChange - Callback fired with the selected label
 */
function createSinglePills(containerId, options, defaultVal, onChange) {
  var bar = document.getElementById(containerId);
  options.forEach(function(opt) {
    var pill = txt('button', opt, 'pill' + (opt === defaultVal ? ' active' : ''));
    pill.setAttribute('type', 'button');
    pill.addEventListener('click', function() {
      bar.querySelectorAll('.pill').forEach(function(p) { p.classList.remove('active'); });
      pill.classList.add('active');
      onChange(opt);
    });
    bar.appendChild(pill);
  });
}

/**
 * Create a row of multi-select pill buttons with an 'All' toggle.
 * Clicking individual pills toggles them; if none remain active, 'All'
 * re-activates automatically. The onChange callback receives the selected labels.
 * @param {string} containerId - DOM id of the pill bar container
 * @param {string[]} options - Labels for each pill (first should be 'All')
 * @param {function(string[]): void} onChange - Callback fired with array of selected labels
 */
function createMultiPills(containerId, options, onChange) {
  var bar = document.getElementById(containerId);
  var allPill = null;

  /**
   * Collect currently active year pill labels (excluding 'All').
   * @returns {string[]} Array of active year strings
   */
  function getSelected() {
    var selected = [];
    bar.querySelectorAll('.pill').forEach(function(p) {
      if (p.classList.contains('active') && p.textContent !== 'All') {
        selected.push(p.textContent);
      }
    });
    return selected;
  }

  /**
   * Synchronise the 'All' pill state: activate it when every year pill
   * is active (or none are), deactivate it otherwise.
   */
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
    var pill = txt('button', opt, 'pill active');
    pill.setAttribute('type', 'button');
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

/**
 * Convert an array of line-series descriptors into Chart.js dataset objects.
 * Handles dashed lines and filled areas based on descriptor properties.
 * @param {Array<{label: string, data: number[], color: string, dashed?: boolean, fill?: boolean, fillColor?: string}>} seriesList - Line series descriptors
 * @returns {Object[]} Array of Chart.js dataset configuration objects
 */
function buildLineDatasets(seriesList) {
  var datasets = [];
  seriesList.forEach(function(s) {
    var ds = {
      type: 'line', label: s.label, data: s.data,
      borderColor: s.color, borderWidth: s.dashed ? 1.5 : 2,
      pointRadius: 0, pointHoverRadius: 3, tension: 0.3,
      borderDash: s.dashed ? [4, 3] : [],
    };
    if (s.fill) {
      ds.fill = true;
      ds.backgroundColor = s.fillColor || (s.color.replace(')', ', 0.15)').replace('rgb(', 'rgba('));
    }
    datasets.push(ds);
  });
  return datasets;
}

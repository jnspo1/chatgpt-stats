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
  Chart.defaults.color = '#8a877e';
  Chart.defaults.borderColor = '#2a2d3a';
  Chart.defaults.font.family = "'DM Sans', sans-serif";
  Chart.defaults.font.size = 11;
}

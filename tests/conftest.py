"""Shared fixtures for chatgpt_stats tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


# ── Minimal dashboard payload for app.py tests ──


def _empty_content_metric() -> dict:
    """Return an empty content metric series (values + rolling averages)."""
    return {"values": [], "avg_7d": [], "avg_28d": []}


def _empty_chart_series() -> dict:
    """Return an empty chart series (values + rolling + lifetime averages)."""
    return {"values": [], "avg_7d": [], "avg_28d": [], "avg_lifetime": []}


def _minimal_dashboard_payload() -> dict:
    """Return a minimal payload matching build_dashboard_payload() shape.

    Keys and structure must exactly match the dict returned by
    ``analytics.build_dashboard_payload``.
    """
    return {
        "generated_at": "2024-01-15T12:00:00",
        "summary": {
            "total_messages": 50,
            "total_chats": 10,
            "first_date": "2024-01-01",
            "last_date": "2024-01-15",
            "years_span": 0.04,
            "top_days_by_chats": [],
            "top_days_by_messages": [],
        },
        "charts": {
            "dates": [],
            "chats": _empty_chart_series(),
            "avg_messages": _empty_chart_series(),
            "total_messages": _empty_chart_series(),
        },
        "gaps": [],
        "gap_stats": {
            "total_days": 0,
            "days_active": 0,
            "days_inactive": 0,
            "proportion_inactive": 0.0,
            "longest_gap": None,
        },
        "monthly": {
            "months": [], "chats": [], "messages": [],
            "avg_messages": [], "chats_avg_3m": [], "messages_avg_3m": [],
        },
        "weekly": {
            "weeks": [], "chats": [], "messages": [], "avg_messages": [],
            "chats_avg_4w": [], "chats_avg_12w": [],
            "messages_avg_4w": [], "messages_avg_12w": [],
            "avg_messages_avg_4w": [], "avg_messages_avg_12w": [],
        },
        "hourly": {
            "heatmap": [[0] * 24 for _ in range(7)],
            "hourly_totals": [0] * 24,
            "weekday_totals": [0] * 7,
        },
        "length_distribution": {"buckets": [], "counts": []},
        "comparison": {
            "this_month": {"chats": 0, "messages": 0, "avg_messages": 0},
            "last_month": {"chats": 0, "messages": 0, "avg_messages": 0},
            "this_year": {"chats": 0, "messages": 0, "avg_messages": 0},
            "last_year": {"chats": 0, "messages": 0, "avg_messages": 0},
        },
        "activity_by_year": [],
        "content_charts": {
            "dates": [],
            "avg_user_words": _empty_content_metric(),
            "avg_asst_words": _empty_content_metric(),
            "response_ratio": _empty_content_metric(),
            "code_pct_user": _empty_content_metric(),
            "code_pct_asst": _empty_content_metric(),
        },
        "content_weekly": {
            "weeks": [],
            "avg_user_words": _empty_content_metric(),
            "avg_asst_words": _empty_content_metric(),
            "response_ratio": _empty_content_metric(),
            "code_pct_user": _empty_content_metric(),
            "code_pct_asst": _empty_content_metric(),
        },
        "content_monthly": {
            "months": [],
            "avg_user_words": _empty_content_metric(),
            "avg_asst_words": _empty_content_metric(),
            "response_ratio": _empty_content_metric(),
            "code_pct_user": _empty_content_metric(),
            "code_pct_asst": _empty_content_metric(),
        },
        "code_stats": {
            "total_conversations_with_code": 0,
            "pct_with_code": 0.0,
            "language_counts": [],
        },
        "content_summary": {
            "avg_user_words": 0,
            "avg_asst_words": 0,
            "avg_response_ratio": 0,
            "pct_conversations_with_code": 0.0,
        },
    }


@pytest.fixture()
def mock_payload():
    """Return the minimal dashboard payload dict."""
    return _minimal_dashboard_payload()


@pytest.fixture()
def client(mock_payload):
    """TestClient for app.py with mocked analytics data.

    Patches build_dashboard_payload so no conversations.json is needed.
    Resets the module-level cache between tests.
    """
    import app as app_module

    with patch.object(
        app_module, "_cache", {"data": None, "built_at": 0.0}
    ):
        with patch(
            "app.build_dashboard_payload", return_value=mock_payload
        ):
            with TestClient(app_module.app) as tc:
                yield tc

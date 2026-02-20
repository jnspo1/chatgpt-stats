"""Shared fixtures for chatgpt_stats tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


# ── Minimal dashboard payload for app.py tests ──


def _minimal_dashboard_payload() -> dict:
    """Return a minimal payload matching build_dashboard_payload() shape."""
    return {
        "generated_at": "2024-01-15T12:00:00",
        "summary": {
            "total_conversations": 10,
            "total_messages": 50,
            "date_range": {"first": "2024-01-01", "last": "2024-01-15"},
            "daily_avg_conversations": 0.7,
            "daily_avg_messages": 3.3,
            "avg_messages_per_conversation": 5.0,
            "total_words": 1000,
            "total_code_blocks": 5,
            "avg_words_per_message": 20.0,
            "code_block_percentage": 10.0,
        },
        "chart": {"labels": [], "conversations": [], "messages": []},
        "monthly": {"labels": [], "conversations": [], "messages": []},
        "weekly": {"labels": [], "conversations": [], "messages": []},
        "hourly": {"labels": list(range(24)), "counts": [0] * 24},
        "content_chart": {"labels": [], "words": [], "code_blocks": []},
        "content_monthly": {"labels": [], "words": [], "code_blocks": []},
        "content_weekly": {"labels": [], "words": [], "code_blocks": []},
        "code_stats": {"total_code_blocks": 0, "languages": {}},
        "length_distribution": {"buckets": [], "counts": []},
        "period_comparison": {"current": {}, "previous": {}},
        "gap_analysis": [],
        "activity_by_year": {},
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

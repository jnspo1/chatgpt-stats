"""Tests for analytics.py using synthetic conversation data."""

import json
import tempfile
from datetime import datetime

import pytest

from analytics import (
    _expanding_avg,
    _rolling_avg,
    build_dashboard_payload,
    compute_chart_data,
    compute_gap_analysis,
    compute_summary_stats,
    process_conversations,
)


def _make_conversation(user_messages):
    """Build a minimal conversation dict from a list of (timestamp, text) tuples."""
    mapping = {}
    for i, (ts, text) in enumerate(user_messages):
        mapping[f"msg-{i}"] = {
            "message": {
                "author": {"role": "user"},
                "create_time": ts,
                "content": {"parts": [text]},
            }
        }
    # Add a system node with no message (common in real data)
    mapping["system-node"] = {"message": None}
    return {"mapping": mapping}


def _make_conversations_with_days(day_configs):
    """Build conversations spanning multiple days.

    day_configs: list of (date_str, num_chats, msgs_per_chat) tuples.
    """
    convos = []
    for date_str, num_chats, msgs_per_chat in day_configs:
        base = datetime.fromisoformat(date_str + "T10:00:00")
        for c in range(num_chats):
            msgs = []
            for m in range(msgs_per_chat):
                ts = base.timestamp() + c * 3600 + m * 60
                msgs.append((ts, f"msg-{c}-{m}"))
            convos.append(_make_conversation(msgs))
    return convos


# ── TestProcessConversations ────────────────


class TestProcessConversations:
    def test_basic_counts(self):
        convos = _make_conversations_with_days([("2024-01-15", 2, 3)])
        summaries, records, timestamps = process_conversations(convos)
        assert len(summaries) == 2
        assert len(timestamps) == 6  # 2 chats * 3 msgs each

    def test_message_counts_in_daily_records(self):
        convos = _make_conversations_with_days([("2024-01-15", 1, 5)])
        _, records, _ = process_conversations(convos)
        assert len(records) == 1
        assert records[0]["total_messages"] == 5
        assert records[0]["total_chats"] == 1

    def test_multiple_days(self):
        convos = _make_conversations_with_days([
            ("2024-01-15", 2, 3),
            ("2024-01-16", 1, 4),
        ])
        summaries, records, timestamps = process_conversations(convos)
        assert len(summaries) == 3
        assert len(records) == 2
        assert len(timestamps) == 10

    def test_empty_mapping(self):
        convos = [{"mapping": {}}]
        summaries, records, timestamps = process_conversations(convos)
        assert summaries == []
        assert records == []
        assert timestamps == []

    def test_null_message_in_mapping(self):
        convos = [{"mapping": {"node1": {"message": None}}}]
        summaries, records, timestamps = process_conversations(convos)
        assert summaries == []

    def test_non_dict_mapping(self):
        convos = [{"mapping": "not a dict"}]
        summaries, records, timestamps = process_conversations(convos)
        assert summaries == []

    def test_missing_mapping(self):
        convos = [{}]
        summaries, records, timestamps = process_conversations(convos)
        assert summaries == []

    def test_assistant_messages_ignored(self):
        mapping = {
            "user-msg": {
                "message": {
                    "author": {"role": "user"},
                    "create_time": 1705300000,
                    "content": {"parts": ["hello"]},
                }
            },
            "assistant-msg": {
                "message": {
                    "author": {"role": "assistant"},
                    "create_time": 1705300060,
                    "content": {"parts": ["hi there"]},
                }
            },
        }
        convos = [{"mapping": mapping}]
        summaries, records, timestamps = process_conversations(convos)
        assert len(timestamps) == 1  # only the user message


# ── TestComputeGapAnalysis ──────────────────


class TestComputeGapAnalysis:
    def test_gap_detection(self):
        ts = [
            datetime(2024, 1, 1, 10, 0),
            datetime(2024, 1, 1, 11, 0),
            datetime(2024, 1, 5, 10, 0),  # 4-day gap
        ]
        result = compute_gap_analysis(ts)
        assert len(result["gaps"]) == 2
        # Longest gap should be first
        assert result["gaps"][0]["length_days"] > 3

    def test_empty_timestamps(self):
        result = compute_gap_analysis([])
        assert result["total_days"] == 0
        assert result["gaps"] == []
        assert result["longest_gap"] is None

    def test_single_timestamp(self):
        result = compute_gap_analysis([datetime(2024, 1, 1)])
        assert result["total_days"] == 1
        assert result["days_active"] == 1
        assert result["days_inactive"] == 0
        assert result["gaps"] == []

    def test_inactive_days_counted(self):
        ts = [
            datetime(2024, 1, 1, 10, 0),
            datetime(2024, 1, 3, 10, 0),
        ]
        result = compute_gap_analysis(ts)
        assert result["total_days"] == 3
        assert result["days_active"] == 2
        assert result["days_inactive"] == 1

    def test_longest_gap_is_first(self):
        ts = [
            datetime(2024, 1, 1, 10, 0),
            datetime(2024, 1, 2, 10, 0),  # 1 day gap
            datetime(2024, 1, 10, 10, 0),  # 8 day gap
            datetime(2024, 1, 12, 10, 0),  # 2 day gap
        ]
        result = compute_gap_analysis(ts)
        assert result["longest_gap"]["length_days"] == pytest.approx(8.0, abs=0.01)


# ── TestComputeSummaryStats ─────────────────


class TestComputeSummaryStats:
    def test_totals(self):
        summaries = [
            {"date": "2024-01-15", "start_time": "2024-01-15T10:00:00", "end_time": "2024-01-15T11:00:00", "message_count": 5, "duration_minutes": 60},
            {"date": "2024-01-16", "start_time": "2024-01-16T10:00:00", "end_time": "2024-01-16T11:00:00", "message_count": 3, "duration_minutes": 60},
        ]
        records = [
            {"date": "2024-01-15", "total_messages": 5, "total_chats": 1, "avg_messages_per_chat": 5.0, "max_messages_in_chat": 5},
            {"date": "2024-01-16", "total_messages": 3, "total_chats": 1, "avg_messages_per_chat": 3.0, "max_messages_in_chat": 3},
        ]
        stats = compute_summary_stats(summaries, records)
        assert stats["total_messages"] == 8
        assert stats["total_chats"] == 2
        assert stats["first_date"] == "2024-01-15"
        assert stats["last_date"] == "2024-01-16"

    def test_empty(self):
        stats = compute_summary_stats([], [])
        assert stats["total_messages"] == 0
        assert stats["total_chats"] == 0
        assert stats["first_date"] is None

    def test_top_days(self):
        records = [
            {"date": "2024-01-15", "total_messages": 10, "total_chats": 5, "avg_messages_per_chat": 2.0, "max_messages_in_chat": 3},
            {"date": "2024-01-16", "total_messages": 20, "total_chats": 2, "avg_messages_per_chat": 10.0, "max_messages_in_chat": 12},
        ]
        summaries = [
            {"date": "2024-01-15", "start_time": "2024-01-15T10:00:00", "end_time": "2024-01-15T11:00:00", "message_count": 5, "duration_minutes": 60},
        ]
        stats = compute_summary_stats(summaries, records)
        assert stats["top_days_by_chats"][0]["date"] == "2024-01-15"
        assert stats["top_days_by_messages"][0]["date"] == "2024-01-16"


# ── TestComputeChartData ────────────────────


class TestComputeChartData:
    def test_sorted_dates(self):
        records = [
            {"date": "2024-01-16", "total_messages": 3, "total_chats": 1, "avg_messages_per_chat": 3.0, "max_messages_in_chat": 3},
            {"date": "2024-01-15", "total_messages": 5, "total_chats": 2, "avg_messages_per_chat": 2.5, "max_messages_in_chat": 3},
        ]
        chart = compute_chart_data(records)
        assert chart["dates"] == ["2024-01-15", "2024-01-16"]

    def test_series_lengths_match(self):
        records = [
            {"date": f"2024-01-{d:02d}", "total_messages": d, "total_chats": 1, "avg_messages_per_chat": float(d), "max_messages_in_chat": d}
            for d in range(1, 11)
        ]
        chart = compute_chart_data(records)
        n = len(chart["dates"])
        assert len(chart["chats"]["values"]) == n
        assert len(chart["chats"]["avg_7d"]) == n
        assert len(chart["chats"]["avg_28d"]) == n
        assert len(chart["chats"]["avg_lifetime"]) == n
        assert len(chart["total_messages"]["values"]) == n

    def test_empty_records(self):
        chart = compute_chart_data([])
        assert chart["dates"] == []
        assert chart["chats"]["values"] == []


# ── TestRollingAvg ──────────────────────────


class TestRollingAvg:
    def test_window_3(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = _rolling_avg(values, 3)
        assert result[0] == pytest.approx(1.0)
        assert result[1] == pytest.approx(1.5)
        assert result[2] == pytest.approx(2.0)
        assert result[3] == pytest.approx(3.0)
        assert result[4] == pytest.approx(4.0)

    def test_window_larger_than_data(self):
        values = [2.0, 4.0]
        result = _rolling_avg(values, 10)
        assert result[0] == pytest.approx(2.0)
        assert result[1] == pytest.approx(3.0)

    def test_empty(self):
        assert _rolling_avg([], 7) == []


class TestExpandingAvg:
    def test_expanding(self):
        values = [2.0, 4.0, 6.0]
        result = _expanding_avg(values)
        assert result[0] == pytest.approx(2.0)
        assert result[1] == pytest.approx(3.0)
        assert result[2] == pytest.approx(4.0)


# ── TestBuildDashboardPayload ───────────────


class TestBuildDashboardPayload:
    def test_integration(self):
        convos = _make_conversations_with_days([
            ("2024-01-15", 2, 3),
            ("2024-01-16", 1, 5),
        ])
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(convos, f)
            tmp_path = f.name

        payload = build_dashboard_payload(tmp_path)

        assert "summary" in payload
        assert "charts" in payload
        assert "gaps" in payload
        assert "gap_stats" in payload
        assert "generated_at" in payload
        assert payload["summary"]["total_chats"] == 3
        assert payload["summary"]["total_messages"] == 11
        assert len(payload["charts"]["dates"]) == 2

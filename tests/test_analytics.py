"""Tests for analytics.py using synthetic conversation data."""

import json
from datetime import datetime
from io import StringIO

import pytest

from analytics import (
    _expanding_avg,
    _rolling_avg,
    build_dashboard_payload,
    compute_chart_data,
    compute_gap_analysis,
    compute_monthly_data,
    compute_summary_stats,
    compute_weekly_data,
    print_summary_report,
    process_conversations,
    save_analytics_files,
)


def _make_conversation(user_messages):
    """Build a minimal conversation dict from a list of (unix_epoch, text) tuples."""
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

    def test_single_message_chat_has_zero_duration(self):
        ts = datetime(2024, 1, 15, 10, 0).timestamp()
        convos = [_make_conversation([(ts, "hello")])]
        summaries, _, _ = process_conversations(convos)
        assert len(summaries) == 1
        assert summaries[0]["message_count"] == 1
        assert summaries[0]["duration_minutes"] == 0.0

    def test_non_dict_message_data_in_mapping(self):
        convos = [{"mapping": {
            "node1": "not a dict",
            "node2": ["also", "not", "a", "dict"],
            "node3": {"message": {"author": {"role": "user"}, "create_time": 1705300000}},
        }}]
        summaries, _, timestamps = process_conversations(convos)
        assert len(timestamps) == 1  # only node3 is valid

    def test_invalid_timestamp_skipped(self):
        mapping = {
            "bad": {"message": {"author": {"role": "user"}, "create_time": "not-a-number"}},
            "good": {"message": {"author": {"role": "user"}, "create_time": 1705300000}},
        }
        convos = [{"mapping": mapping}]
        summaries, _, timestamps = process_conversations(convos)
        assert len(timestamps) == 1

    def test_overflow_timestamp_skipped(self):
        mapping = {
            "bad": {"message": {"author": {"role": "user"}, "create_time": 1e20}},
            "good": {"message": {"author": {"role": "user"}, "create_time": 1705300000}},
        }
        convos = [{"mapping": mapping}]
        summaries, _, timestamps = process_conversations(convos)
        assert len(timestamps) == 1


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
        assert result["proportion_inactive"] == pytest.approx(33.33, abs=0.01)

    def test_longest_gap_is_first(self):
        ts = [
            datetime(2024, 1, 1, 10, 0),
            datetime(2024, 1, 2, 10, 0),  # 1 day gap
            datetime(2024, 1, 10, 10, 0),  # 8 day gap
            datetime(2024, 1, 12, 10, 0),  # 2 day gap
        ]
        result = compute_gap_analysis(ts)
        assert result["longest_gap"]["length_days"] == pytest.approx(8.0, abs=0.01)

    def test_unsorted_input_produces_correct_gaps(self):
        ts = [
            datetime(2024, 1, 5, 10, 0),
            datetime(2024, 1, 1, 10, 0),
            datetime(2024, 1, 3, 10, 0),
        ]
        result = compute_gap_analysis(ts)
        assert result["total_days"] == 5
        assert result["days_active"] == 3
        assert result["days_inactive"] == 2


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
        assert stats["years_span"] >= 0

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

    def test_rolling_avg_values(self):
        records = [
            {"date": "2024-01-01", "total_messages": 10, "total_chats": 1, "avg_messages_per_chat": 10.0, "max_messages_in_chat": 10},
            {"date": "2024-01-02", "total_messages": 20, "total_chats": 1, "avg_messages_per_chat": 20.0, "max_messages_in_chat": 20},
        ]
        chart = compute_chart_data(records)
        assert chart["total_messages"]["avg_7d"] == [10.0, 15.0]
        assert chart["total_messages"]["avg_lifetime"] == [10.0, 15.0]


# ── TestComputeMonthlyData ──────────────────


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
        assert result["chats_avg_3m"] == [1.0, 1.5, 2.0]


# ── TestComputeWeeklyData ─────────────────


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

    def test_window_1(self):
        values = [1.0, 3.0, 5.0]
        assert _rolling_avg(values, 1) == [1.0, 3.0, 5.0]


class TestExpandingAvg:
    def test_expanding(self):
        values = [2.0, 4.0, 6.0]
        result = _expanding_avg(values)
        assert result[0] == pytest.approx(2.0)
        assert result[1] == pytest.approx(3.0)
        assert result[2] == pytest.approx(4.0)

    def test_empty(self):
        assert _expanding_avg([]) == []


# ── TestSaveAnalyticsFiles ──────────────────


class TestSaveAnalyticsFiles:
    def test_creates_expected_files(self, tmp_path):
        summaries = [{"date": "2024-01-15", "start_time": "2024-01-15T10:00:00",
                       "end_time": "2024-01-15T11:00:00", "message_count": 5,
                       "duration_minutes": 60}]
        records = [{"date": "2024-01-15", "total_messages": 5, "total_chats": 1,
                     "avg_messages_per_chat": 5.0, "max_messages_in_chat": 5}]
        gaps = [{"start_timestamp": "2024-01-15T10:00:00",
                 "end_timestamp": "2024-01-17T10:00:00", "length_days": 2.0}]

        save_analytics_files(summaries, records, gaps, str(tmp_path))

        assert (tmp_path / "chat_summaries.json").exists()
        assert (tmp_path / "chat_summaries.csv").exists()
        assert (tmp_path / "daily_stats.json").exists()
        assert (tmp_path / "daily_stats.csv").exists()
        assert (tmp_path / "message_gaps.json").exists()
        assert (tmp_path / "message_gaps.csv").exists()

        # Verify JSON round-trips
        loaded = json.loads((tmp_path / "chat_summaries.json").read_text())
        assert loaded[0]["message_count"] == 5

    def test_no_gap_files_when_gaps_empty(self, tmp_path):
        save_analytics_files([], [], [], str(tmp_path))
        assert (tmp_path / "chat_summaries.json").exists()
        assert not (tmp_path / "message_gaps.json").exists()
        assert not (tmp_path / "message_gaps.csv").exists()


# ── TestPrintSummaryReport ──────────────────


class TestPrintSummaryReport:
    def test_smoke_with_data(self, capsys):
        stats = {
            "total_messages": 100, "total_chats": 10,
            "first_date": "2024-01-01", "last_date": "2024-01-31",
            "years_span": 0.08,
            "top_days_by_chats": [{"date": "2024-01-15", "total_chats": 5}],
            "top_days_by_messages": [{"date": "2024-01-15", "total_messages": 20}],
        }
        gap_data = {
            "total_days": 31, "days_active": 20, "days_inactive": 11,
            "proportion_inactive": 35.48,
            "longest_gap": {"length_days": 3.5, "start_timestamp": "2024-01-10T10:00:00",
                            "end_timestamp": "2024-01-13T22:00:00"},
            "gaps": [{"length_days": 3.5, "start_timestamp": "2024-01-10T10:00:00",
                       "end_timestamp": "2024-01-13T22:00:00"}],
        }
        print_summary_report(stats, gap_data)
        output = capsys.readouterr().out
        assert "Total Messages: 100" in output
        assert "Total Chats: 10" in output
        assert "Inactivity Analysis" in output

    def test_smoke_with_empty_data(self, capsys):
        stats = {
            "total_messages": 0, "total_chats": 0,
            "first_date": None, "last_date": None,
            "years_span": 0, "top_days_by_chats": [], "top_days_by_messages": [],
        }
        gap_data = {"total_days": 0, "days_active": 0, "days_inactive": 0,
                     "proportion_inactive": 0, "longest_gap": None, "gaps": []}
        print_summary_report(stats, gap_data)
        output = capsys.readouterr().out
        assert "Total Messages: 0" in output


# ── TestBuildDashboardPayload ───────────────


class TestBuildDashboardPayload:
    def test_integration(self, tmp_path):
        convos = _make_conversations_with_days([
            ("2024-01-15", 2, 3),
            ("2024-01-16", 1, 5),
        ])
        json_file = tmp_path / "conversations.json"
        json_file.write_text(json.dumps(convos))

        payload = build_dashboard_payload(str(json_file))

        assert "summary" in payload
        assert "charts" in payload
        assert "gaps" in payload
        assert "gap_stats" in payload
        assert "generated_at" in payload
        assert payload["summary"]["total_chats"] == 3
        assert payload["summary"]["total_messages"] == 11
        assert len(payload["charts"]["dates"]) == 2
        # Verify chart sub-keys exist
        assert "avg_7d" in payload["charts"]["chats"]
        assert "avg_lifetime" in payload["charts"]["total_messages"]

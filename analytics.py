"""Core data processing for ChatGPT conversation analytics.

Extracts and computes statistics from OpenAI conversation export JSON.
Used by both the CLI (chat_gpt_summary.py) and the web dashboard (app.py).
"""

from __future__ import annotations

import csv
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


def load_conversations(path: str = "conversations.json") -> list[dict]:
    """Load conversations from an OpenAI export JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def process_conversations(
    conversations: list[dict],
) -> tuple[list[dict], list[dict], list[datetime]]:
    """Parse raw conversations into chat summaries, daily records, and timestamps.

    Returns:
        (chat_summaries, daily_records, all_message_timestamps)
    """
    chat_summaries: list[dict] = []
    daily_stats: dict = {}
    all_message_timestamps: list[datetime] = []

    for chat in conversations:
        chat_message_count = 0
        chat_start_time = None
        chat_end_time = None

        mapping = chat.get("mapping", {})
        if not isinstance(mapping, dict):
            continue

        for message_data in mapping.values():
            message = message_data.get("message") if isinstance(message_data, dict) else None
            if message is None:
                continue

            author = message.get("author")
            if author is None or not isinstance(author, dict):
                continue

            author_role = author.get("role")
            create_time = message.get("create_time")

            if author_role == "user" and create_time is not None:
                try:
                    message_datetime = datetime.fromtimestamp(float(create_time))
                except (TypeError, ValueError, OSError, OverflowError):
                    continue
                chat_message_count += 1
                message_date = message_datetime.date()

                all_message_timestamps.append(message_datetime)

                if chat_start_time is None or message_datetime < chat_start_time:
                    chat_start_time = message_datetime
                if chat_end_time is None or message_datetime > chat_end_time:
                    chat_end_time = message_datetime

                if message_date not in daily_stats:
                    daily_stats[message_date] = {
                        "total_messages": 0,
                        "total_chats": 0,
                        "messages_per_chat": [],
                    }
                daily_stats[message_date]["total_messages"] += 1

        if chat_message_count > 0:
            chat_date = chat_start_time.date()
            chat_duration = (chat_end_time - chat_start_time).total_seconds() / 60

            chat_summaries.append(
                {
                    "date": chat_date.isoformat(),
                    "start_time": chat_start_time.isoformat(),
                    "end_time": chat_end_time.isoformat(),
                    "message_count": chat_message_count,
                    "duration_minutes": round(chat_duration, 2),
                }
            )

            daily_stats[chat_date]["total_chats"] += 1
            daily_stats[chat_date]["messages_per_chat"].append(chat_message_count)

    if conversations and not chat_summaries:
        logger.warning(
            "Loaded %d conversations but none produced valid summaries. "
            "The OpenAI export format may have changed.",
            len(conversations),
        )

    daily_records = []
    for date, stats in daily_stats.items():
        mpc = stats["messages_per_chat"]
        avg_mpc = sum(mpc) / len(mpc) if mpc else 0
        daily_records.append(
            {
                "date": date.isoformat(),
                "total_messages": stats["total_messages"],
                "total_chats": stats["total_chats"],
                "avg_messages_per_chat": round(avg_mpc, 2),
                "max_messages_in_chat": max(mpc) if mpc else 0,
            }
        )

    return chat_summaries, daily_records, all_message_timestamps


def compute_gap_analysis(
    timestamps: list[datetime],
) -> dict[str, Any]:
    """Compute gap analysis from message timestamps (sorted internally).

    Returns dict with keys: gaps, total_days, days_active, days_inactive,
    proportion_inactive, longest_gap.
    """
    if not timestamps:
        return {
            "gaps": [],
            "total_days": 0,
            "days_active": 0,
            "days_inactive": 0,
            "proportion_inactive": 0.0,
            "longest_gap": None,
        }

    sorted_ts = sorted(timestamps)

    gaps = []
    for i in range(1, len(sorted_ts)):
        diff = sorted_ts[i] - sorted_ts[i - 1]
        gap_days = diff.total_seconds() / 86400
        if gap_days > 0:
            gaps.append(
                {
                    "start_timestamp": sorted_ts[i - 1].isoformat(),
                    "end_timestamp": sorted_ts[i].isoformat(),
                    "length_days": gap_days,
                }
            )

    gaps.sort(key=lambda g: g["length_days"], reverse=True)

    dates_with_messages = set(ts.date() for ts in sorted_ts)
    start_date = sorted_ts[0].date()
    end_date = sorted_ts[-1].date()
    total_days = (end_date - start_date).days + 1

    days_inactive = 0
    current = start_date
    while current <= end_date:
        if current not in dates_with_messages:
            days_inactive += 1
        current += timedelta(days=1)

    proportion_inactive = (days_inactive / total_days * 100) if total_days > 0 else 0.0

    return {
        "gaps": gaps,
        "total_days": total_days,
        "days_active": len(dates_with_messages),
        "days_inactive": days_inactive,
        "proportion_inactive": round(proportion_inactive, 2),
        "longest_gap": gaps[0] if gaps else None,
    }


def compute_summary_stats(
    summaries: list[dict], records: list[dict]
) -> dict[str, Any]:
    """Compute high-level summary statistics.

    Returns dict with keys: total_messages, total_chats, first_date, last_date,
    years_span, top_days_by_chats, top_days_by_messages.
    """
    total_messages = sum(r["total_messages"] for r in records)
    total_chats = len(summaries)

    first_date = None
    last_date = None
    years_span = 0.0

    if summaries:
        dates = [datetime.fromisoformat(s["start_time"]) for s in summaries]
        first_date = min(dates).strftime("%Y-%m-%d")
        last_date = max(dates).strftime("%Y-%m-%d")
        years_span = round((max(dates) - min(dates)).days / 365.25, 2)

    sorted_by_chats = sorted(records, key=lambda r: r["total_chats"], reverse=True)
    sorted_by_messages = sorted(records, key=lambda r: r["total_messages"], reverse=True)

    return {
        "total_messages": total_messages,
        "total_chats": total_chats,
        "first_date": first_date,
        "last_date": last_date,
        "years_span": years_span,
        "top_days_by_chats": sorted_by_chats[:5],
        "top_days_by_messages": sorted_by_messages[:5],
    }


# ---------------------------------------------------------------------------
# Rolling average helpers (pure Python, no pandas)
# ---------------------------------------------------------------------------

def _rolling_avg(values: list[float], window: int) -> list[float]:
    """Compute rolling average, using available values when the window is not yet full."""
    result = []
    for i in range(len(values)):
        start = max(0, i - window + 1)
        w = values[start : i + 1]
        result.append(sum(w) / len(w))
    return result


def _expanding_avg(values: list[float]) -> list[float]:
    """Compute expanding (lifetime) average."""
    result: list[float] = []
    s = 0.0
    for i, v in enumerate(values, 1):
        s += v
        result.append(s / i)
    return result


def compute_chart_data(daily_records: list[dict]) -> dict[str, Any]:
    """Compute chart series from daily records for Chart.js rendering.

    Returns dict with keys: dates, and for each metric (chats, avg_messages,
    total_messages): values, avg_7d, avg_28d, avg_lifetime.
    """
    sorted_records = sorted(daily_records, key=lambda r: r["date"])

    dates = [r["date"] for r in sorted_records]
    chats = [r["total_chats"] for r in sorted_records]
    avg_msgs = [r["avg_messages_per_chat"] for r in sorted_records]
    total_msgs = [r["total_messages"] for r in sorted_records]

    return {
        "dates": dates,
        "chats": {
            "values": chats,
            "avg_7d": [round(v, 2) for v in _rolling_avg(chats, 7)],
            "avg_28d": [round(v, 2) for v in _rolling_avg(chats, 28)],
            "avg_lifetime": [round(v, 2) for v in _expanding_avg(chats)],
        },
        "avg_messages": {
            "values": avg_msgs,
            "avg_7d": [round(v, 2) for v in _rolling_avg(avg_msgs, 7)],
            "avg_28d": [round(v, 2) for v in _rolling_avg(avg_msgs, 28)],
            "avg_lifetime": [round(v, 2) for v in _expanding_avg(avg_msgs)],
        },
        "total_messages": {
            "values": total_msgs,
            "avg_7d": [round(v, 2) for v in _rolling_avg(total_msgs, 7)],
            "avg_28d": [round(v, 2) for v in _rolling_avg(total_msgs, 28)],
            "avg_lifetime": [round(v, 2) for v in _expanding_avg(total_msgs)],
        },
    }


def build_dashboard_payload(path: str = "conversations.json") -> dict[str, Any]:
    """One-call entry point: load, process, compute all stats for the dashboard.

    Returns dict with keys: generated_at, summary, charts, gaps (top 20),
    gap_stats.
    """
    convos = load_conversations(path)
    summaries, records, timestamps = process_conversations(convos)
    gap_data = compute_gap_analysis(timestamps)
    stats = compute_summary_stats(summaries, records)
    charts = compute_chart_data(records)

    return {
        "generated_at": datetime.now().isoformat(),
        "summary": stats,
        "charts": charts,
        "gaps": gap_data["gaps"][:20],
        "gap_stats": {
            "total_days": gap_data["total_days"],
            "days_active": gap_data["days_active"],
            "days_inactive": gap_data["days_inactive"],
            "proportion_inactive": gap_data["proportion_inactive"],
            "longest_gap": gap_data["longest_gap"],
        },
    }


# ---------------------------------------------------------------------------
# CLI helpers (backward compat for chat_gpt_summary.py)
# ---------------------------------------------------------------------------

def save_analytics_files(
    summaries: list[dict],
    records: list[dict],
    gaps: list[dict],
    output_dir: str = "chat_analytics",
) -> None:
    """Write CSV/JSON analytics files to output_dir."""
    os.makedirs(output_dir, exist_ok=True)

    with open(f"{output_dir}/chat_summaries.json", "w") as f:
        json.dump(summaries, f, indent=2)

    with open(f"{output_dir}/daily_stats.json", "w") as f:
        json.dump(records, f, indent=2)

    with open(f"{output_dir}/chat_summaries.csv", "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["date", "start_time", "end_time", "message_count", "duration_minutes"],
        )
        writer.writeheader()
        writer.writerows(summaries)

    with open(f"{output_dir}/daily_stats.csv", "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "date",
                "total_messages",
                "total_chats",
                "avg_messages_per_chat",
                "max_messages_in_chat",
            ],
        )
        writer.writeheader()
        writer.writerows(records)

    if gaps:
        with open(f"{output_dir}/message_gaps.json", "w") as f:
            json.dump(gaps, f, indent=2)

        with open(f"{output_dir}/message_gaps.csv", "w", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["start_timestamp", "end_timestamp", "length_days"]
            )
            writer.writeheader()
            writer.writerows(gaps)


def print_summary_report(
    stats: dict[str, Any], gap_data: dict[str, Any]
) -> None:
    """Print the CLI summary report to stdout."""
    print(f"\n{'=' * 60}")
    print("ChatGPT Usage Summary")
    print(f"{'=' * 60}")
    print(f"Total Messages: {stats['total_messages']:,}")
    print(f"Total Chats: {stats['total_chats']:,}")

    if stats["first_date"] and stats["last_date"]:
        print(f"First Chat: {stats['first_date']}")
        print(f"Last Chat: {stats['last_date']}")
        print(f"Time Span: {stats['years_span']:.2f} years")

    if stats["top_days_by_chats"]:
        top_chat = stats["top_days_by_chats"][0]
        top_msg = stats["top_days_by_messages"][0]
        print(f"Max Chats in a Day: {top_chat['total_chats']:,} on {top_chat['date']}")
        print(f"Max Messages in a Day: {top_msg['total_messages']:,} on {top_msg['date']}")

        print("\nTop 5 Days by Chats:")
        for rec in stats["top_days_by_chats"]:
            print(f"  {rec['date']}: {rec['total_chats']:,} chats")

        print("\nTop 5 Days by Messages:")
        for rec in stats["top_days_by_messages"]:
            print(f"  {rec['date']}: {rec['total_messages']:,} messages")

    if gap_data.get("total_days"):
        print(f"\n{'=' * 60}")
        print("Inactivity Analysis")
        print(f"{'=' * 60}")
        print(f"Total Days in Range: {gap_data['total_days']:,}")
        print(f"Days with Messages: {gap_data['days_active']:,}")
        print(f"Days without Messages: {gap_data['days_inactive']:,}")
        print(f"Proportion Inactive: {gap_data['proportion_inactive']:.2f}%")

        longest = gap_data.get("longest_gap")
        if longest:
            print(f"\nLongest Gap: {longest['length_days']:.2f} days")
            print(f"  From: {longest['start_timestamp']}")
            print(f"  To:   {longest['end_timestamp']}")

        gaps = gap_data.get("gaps", [])
        if gaps:
            print(f"\nTop 20 Longest Gaps (No Messages):")
            print(f"{'Rank':<6} {'Days':<10} {'Start Time':<21} {'End Time':<21}")
            print(f"{'-' * 80}")
            for i, gap in enumerate(gaps[:20], 1):
                print(
                    f"{i:<6} {gap['length_days']:<10.2f} "
                    f"{gap['start_timestamp']:<21} {gap['end_timestamp']:<21}"
                )

    print(f"{'=' * 60}")
    print(f"\nAnalytics data has been saved to the 'chat_analytics' directory:")
    print("1. chat_summaries.json/csv - Per-conversation statistics")
    print("2. daily_stats.json/csv - Daily usage aggregates")
    print("3. message_gaps.json/csv - Message gaps sorted by length")

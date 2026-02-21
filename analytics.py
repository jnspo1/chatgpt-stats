"""Core data processing for ChatGPT conversation analytics.

Extracts and computes statistics from OpenAI conversation export JSON.
Used by both the CLI (chat_gpt_summary.py) and the web dashboard (app.py).
"""

from __future__ import annotations

import calendar
import csv
import json
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


def load_conversations(path: str = "conversations.json") -> list[dict]:
    """Load conversations from an OpenAI export JSON file.

    Args:
        path: Filesystem path to the OpenAI conversations.json export.
            Defaults to "conversations.json" in the current directory.

    Returns:
        List of raw conversation dicts as exported by OpenAI.  Each dict
        contains a "mapping" key with the message tree.

    Raises:
        FileNotFoundError: If the file at *path* does not exist.
        json.JSONDecodeError: If the file contains invalid JSON.
    """
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _extract_message_content(message: dict) -> tuple[str, int, int, bool, list[str]]:
    """Extract text content and metrics from a single message.

    Args:
        message: A message dict containing a 'content' key with 'parts'.

    Returns:
        A tuple of (text, word_count, char_count, has_code, code_languages).
    """
    text = ""
    content = message.get("content")
    if isinstance(content, dict):
        parts = content.get("parts", [])
        if isinstance(parts, list):
            text = " ".join(p for p in parts if isinstance(p, str))

    word_count = len(text.split()) if text.strip() else 0
    char_count = len(text)
    has_code = bool(re.search(r"```", text))
    code_languages = re.findall(r"```(\w+)", text) if has_code else []
    return text, word_count, char_count, has_code, code_languages


def _init_daily_bucket() -> dict:
    """Create a fresh daily stats accumulator dict.

    Returns:
        Dict with zeroed counters for messages, words, chars, and code.
    """
    return {
        "total_messages": 0,
        "total_chats": 0,
        "messages_per_chat": [],
        "user_words": 0,
        "user_chars": 0,
        "user_msgs": 0,
        "user_code_msgs": 0,
        "asst_words": 0,
        "asst_chars": 0,
        "asst_msgs": 0,
        "asst_code_msgs": 0,
    }


def _build_daily_records(daily_stats: dict) -> list[dict]:
    """Convert accumulated daily stats into final daily record dicts.

    Args:
        daily_stats: Dict mapping date objects to accumulator dicts.

    Returns:
        List of per-day record dicts with computed averages and maximums.
    """
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
                "user_words": stats["user_words"],
                "user_chars": stats["user_chars"],
                "user_msgs": stats["user_msgs"],
                "user_code_msgs": stats["user_code_msgs"],
                "asst_words": stats["asst_words"],
                "asst_chars": stats["asst_chars"],
                "asst_msgs": stats["asst_msgs"],
                "asst_code_msgs": stats["asst_code_msgs"],
            }
        )
    return daily_records


def _extract_conversation_messages(
    chat: dict,
) -> list[tuple[str, float | None, int, int, bool, list[str]]]:
    """Walk a conversation mapping and extract valid user/assistant messages.

    Validates each node in the mapping tree, filters to "user" and
    "assistant" roles, and extracts content metrics via
    ``_extract_message_content``.

    Args:
        chat: A single conversation dict from the OpenAI export.  Must
            contain a "mapping" key whose values are message-node dicts.

    Returns:
        List of tuples (role, create_time, word_count, char_count,
        has_code, code_languages) for each valid user or assistant
        message.  Returns an empty list if the mapping is missing or
        not a dict.
    """
    mapping = chat.get("mapping", {})
    if not isinstance(mapping, dict):
        return []

    results: list[tuple[str, float | None, int, int, bool, list[str]]] = []
    for message_data in mapping.values():
        message = message_data.get("message") if isinstance(message_data, dict) else None
        if message is None:
            continue

        author = message.get("author")
        if author is None or not isinstance(author, dict):
            continue

        role = author.get("role")
        if role not in ("user", "assistant"):
            continue

        create_time = message.get("create_time")
        _, word_count, char_count, has_code, code_langs = _extract_message_content(message)
        results.append((role, create_time, word_count, char_count, has_code, code_langs))

    return results


def _update_time_range(
    start: datetime | None,
    end: datetime | None,
    new_time: datetime,
) -> tuple[datetime, datetime]:
    """Update a start/end time range with a new timestamp.

    Expands the range so that *start* is the earliest and *end* is
    the latest time seen so far.

    Args:
        start: Current earliest datetime, or None if no times seen yet.
        end: Current latest datetime, or None if no times seen yet.
        new_time: The new datetime to incorporate into the range.

    Returns:
        A (start, end) tuple with the updated range.
    """
    if start is None or new_time < start:
        start = new_time
    if end is None or new_time > end:
        end = new_time
    return start, end


def _accumulate_user_daily_stats(
    daily_stats: dict,
    message_date: object,
    word_count: int,
    char_count: int,
    has_code: bool,
) -> None:
    """Accumulate a user message's metrics into the daily stats bucket.

    Creates a new daily bucket if one does not exist for *message_date*.
    Increments total_messages, user_words, user_chars, user_msgs, and
    (conditionally) user_code_msgs.

    Args:
        daily_stats: Dict mapping date objects to accumulator dicts.
        message_date: The date of the user message.
        word_count: Number of words in the message.
        char_count: Number of characters in the message.
        has_code: Whether the message contains a code block.
    """
    if message_date not in daily_stats:
        daily_stats[message_date] = _init_daily_bucket()
    daily_stats[message_date]["total_messages"] += 1
    daily_stats[message_date]["user_words"] += word_count
    daily_stats[message_date]["user_chars"] += char_count
    daily_stats[message_date]["user_msgs"] += 1
    if has_code:
        daily_stats[message_date]["user_code_msgs"] += 1


def _accumulate_asst_daily_stats(
    daily_stats: dict,
    asst_date: object,
    word_count: int,
    char_count: int,
    has_code: bool,
) -> None:
    """Accumulate an assistant message's metrics into the daily stats bucket.

    Only updates an existing bucket — does nothing if *asst_date* is
    not already present in *daily_stats*.

    Args:
        daily_stats: Dict mapping date objects to accumulator dicts.
        asst_date: The date to attribute the assistant message to.
        word_count: Number of words in the message.
        char_count: Number of characters in the message.
        has_code: Whether the message contains a code block.
    """
    if asst_date not in daily_stats:
        return
    daily_stats[asst_date]["asst_words"] += word_count
    daily_stats[asst_date]["asst_chars"] += char_count
    daily_stats[asst_date]["asst_msgs"] += 1
    if has_code:
        daily_stats[asst_date]["asst_code_msgs"] += 1


def _process_chat_messages(
    messages: list[tuple[str, float | None, int, int, bool, list[str]]],
    daily_stats: dict,
    all_timestamps: list[datetime],
) -> dict | None:
    """Process extracted messages for a single conversation.

    Loops over messages, accumulates daily stats for user and assistant
    messages, tracks timestamps, and builds a chat summary dict.

    Args:
        messages: List of (role, create_time, word_count, char_count,
            has_code, code_languages) tuples from
            ``_extract_conversation_messages``.
        daily_stats: Shared dict mapping date objects to accumulator
            dicts.  Modified in place.
        all_timestamps: Shared list of user message datetimes.  Appended
            to in place.

    Returns:
        A chat summary dict if the conversation had at least one valid
        user message, or None otherwise.
    """
    chat_message_count = 0
    chat_start_time: datetime | None = None
    chat_end_time: datetime | None = None
    chat_user_words = 0
    chat_asst_words = 0
    chat_code_langs: set[str] = set()

    for role, create_time, word_count, char_count, has_code, code_langs in messages:
        chat_code_langs.update(code_langs)

        if role == "user" and create_time is not None:
            try:
                message_datetime = datetime.fromtimestamp(float(create_time))
            except (TypeError, ValueError, OSError, OverflowError):
                continue
            chat_message_count += 1
            chat_user_words += word_count
            all_timestamps.append(message_datetime)
            chat_start_time, chat_end_time = _update_time_range(
                chat_start_time, chat_end_time, message_datetime,
            )
            _accumulate_user_daily_stats(
                daily_stats, message_datetime.date(), word_count, char_count, has_code,
            )
        elif role == "assistant":
            chat_asst_words += word_count
            if chat_start_time is not None:
                _accumulate_asst_daily_stats(
                    daily_stats, chat_start_time.date(), word_count, char_count, has_code,
                )

    if chat_message_count == 0:
        return None

    chat_date = chat_start_time.date()
    chat_duration = (chat_end_time - chat_start_time).total_seconds() / 60
    response_ratio = (
        round(chat_asst_words / chat_user_words, 2)
        if chat_user_words > 0
        else 0.0
    )

    daily_stats[chat_date]["total_chats"] += 1
    daily_stats[chat_date]["messages_per_chat"].append(chat_message_count)

    return {
        "date": chat_date.isoformat(),
        "start_time": chat_start_time.isoformat(),
        "end_time": chat_end_time.isoformat(),
        "message_count": chat_message_count,
        "duration_minutes": round(chat_duration, 2),
        "user_words": chat_user_words,
        "asst_words": chat_asst_words,
        "response_ratio": response_ratio,
        "code_languages": sorted(chat_code_langs),
    }


def process_conversations(
    conversations: list[dict],
) -> tuple[list[dict], list[dict], list[datetime]]:
    """Parse raw conversations into chat summaries, daily records, and timestamps.

    Iterates through every conversation's message mapping, extracting user
    messages and assistant replies.  Produces per-chat summaries (date, message
    count, duration, word counts, code languages) and per-day aggregates
    (total messages, chats, content metrics).

    Args:
        conversations: List of raw conversation dicts from ``load_conversations``.
            Each dict must contain a "mapping" key whose values hold messages.

    Returns:
        A 3-tuple of (chat_summaries, daily_records, all_message_timestamps):
            - chat_summaries: list of per-conversation summary dicts with keys
              date, start_time, end_time, message_count, duration_minutes,
              user_words, asst_words, response_ratio, code_languages.
            - daily_records: list of per-day aggregate dicts with keys date,
              total_messages, total_chats, avg_messages_per_chat,
              max_messages_in_chat, plus content metric fields.
            - all_message_timestamps: flat list of datetime objects for every
              user message, useful for downstream gap and hourly analysis.
    """
    chat_summaries: list[dict] = []
    daily_stats: dict = {}
    all_message_timestamps: list[datetime] = []

    for chat in conversations:
        messages = _extract_conversation_messages(chat)
        if not messages:
            continue
        summary = _process_chat_messages(messages, daily_stats, all_message_timestamps)
        if summary is not None:
            chat_summaries.append(summary)

    if conversations and not chat_summaries:
        logger.warning(
            "Loaded %d conversations but none produced valid summaries. "
            "The OpenAI export format may have changed.",
            len(conversations),
        )

    return chat_summaries, _build_daily_records(daily_stats), all_message_timestamps


def compute_gap_analysis(
    timestamps: list[datetime],
) -> dict[str, Any]:
    """Compute gap analysis from message timestamps (sorted internally).

    Sorts timestamps, calculates every consecutive gap between messages,
    and derives activity/inactivity metrics across the full date range.

    Args:
        timestamps: List of datetime objects representing user message times.
            Need not be pre-sorted; the function sorts a copy internally.

    Returns:
        Dict with keys:
            - gaps: list of gap dicts (start_timestamp, end_timestamp,
              length_days), sorted longest-first.
            - total_days: int, calendar days from first to last message
              (inclusive).
            - days_active: int, distinct calendar dates with at least one
              message.
            - days_inactive: int, calendar dates with no messages.
            - proportion_inactive: float, percentage of inactive days (0-100).
            - longest_gap: the single longest gap dict, or None if no gaps.
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


def _compute_year_stats(
    yr: int,
    active_by_year: dict[int, set],
    first_date: object,
    last_date: object,
) -> dict:
    """Compute activity statistics for a single calendar year.

    Determines the date range for the year: the first/last years use
    actual message date boundaries, while middle years span the full
    calendar year (Jan 1 to Dec 31).

    Args:
        yr: The calendar year to compute stats for.
        active_by_year: Dict mapping year ints to sets of active dates.
        first_date: The earliest message date across all years.
        last_date: The latest message date across all years.

    Returns:
        Dict with keys year (str), total_days, days_active,
        days_inactive, pct_active, pct_inactive.
    """
    from datetime import date as date_type

    start = first_date if yr == first_date.year else date_type(yr, 1, 1)
    end = last_date if yr == last_date.year else date_type(yr, 12, 31)

    total = (end - start).days + 1
    active = len(active_by_year.get(yr, set()))
    inactive = total - active
    pct_active = round(active / total * 100, 1) if total > 0 else 0.0
    pct_inactive = round(inactive / total * 100, 1) if total > 0 else 0.0

    return {
        "year": str(yr),
        "total_days": total,
        "days_active": active,
        "days_inactive": inactive,
        "pct_active": pct_active,
        "pct_inactive": pct_inactive,
    }


def _compute_overall_stats(
    active_dates: set,
    first_date: object,
    last_date: object,
) -> dict:
    """Compute overall activity statistics across the full date range.

    Args:
        active_dates: Set of all dates that had at least one message.
        first_date: The earliest message date.
        last_date: The latest message date.

    Returns:
        Dict with keys year ("Overall"), total_days, days_active,
        days_inactive, pct_active, pct_inactive.
    """
    total = (last_date - first_date).days + 1
    active = len(active_dates)
    inactive = total - active
    return {
        "year": "Overall",
        "total_days": total,
        "days_active": active,
        "days_inactive": inactive,
        "pct_active": round(active / total * 100, 1) if total > 0 else 0.0,
        "pct_inactive": round(inactive / total * 100, 1) if total > 0 else 0.0,
    }


def compute_activity_by_year(timestamps: list[datetime]) -> list[dict]:
    """Compute per-year activity breakdown from message timestamps.

    Splits timestamps by calendar year and computes active/inactive day
    counts for each year.  First/last years use actual message date
    boundaries; middle years use full calendar year (Jan 1 -- Dec 31).

    Args:
        timestamps: List of datetime objects representing user message times.
            Need not be pre-sorted.

    Returns:
        List of dicts with the Overall row first, then ascending years.
        Each dict has keys: year (str), total_days, days_active,
        days_inactive, pct_active, pct_inactive.  Returns an empty list
        when *timestamps* is empty.
    """
    if not timestamps:
        return []

    sorted_ts = sorted(timestamps)
    active_dates = set(ts.date() for ts in sorted_ts)
    first_date = sorted_ts[0].date()
    last_date = sorted_ts[-1].date()

    active_by_year: dict[int, set] = {}
    for d in active_dates:
        active_by_year.setdefault(d.year, set()).add(d)

    years = sorted(active_by_year.keys())
    rows = [_compute_year_stats(yr, active_by_year, first_date, last_date) for yr in years]
    overall = _compute_overall_stats(active_dates, first_date, last_date)

    return [overall] + rows


def compute_summary_stats(
    summaries: list[dict], records: list[dict]
) -> dict[str, Any]:
    """Compute high-level summary statistics.

    Derives totals, date range, and top-day rankings from the per-chat
    summaries and per-day records produced by ``process_conversations``.

    Args:
        summaries: List of per-conversation summary dicts (from
            ``process_conversations``).  Each must contain "start_time".
        records: List of per-day aggregate dicts (from
            ``process_conversations``).  Each must contain "total_messages"
            and "total_chats".

    Returns:
        Dict with keys: total_messages, total_chats, first_date (str or
        None), last_date (str or None), years_span (float), top_days_by_chats
        (list of record dicts), top_days_by_messages (list of record dicts).
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
        "top_days_by_chats": _top_records_per_year(sorted_by_chats),
        "top_days_by_messages": _top_records_per_year(sorted_by_messages),
    }


# ---------------------------------------------------------------------------
# Rolling average helpers (pure Python, no pandas)
# ---------------------------------------------------------------------------

def _rolling_avg(values: list[float], window: int) -> list[float]:
    """Compute rolling average, using available values when the window is not yet full.

    Args:
        values: Numeric series to smooth.
        window: Maximum number of trailing values to average.  At the
            start of the series, fewer values are used (expanding window
            until *window* values are available).

    Returns:
        List of floats the same length as *values*, where each element
        is the mean of the trailing *window* (or fewer) values.
    """
    result = []
    for i in range(len(values)):
        start = max(0, i - window + 1)
        w = values[start : i + 1]
        result.append(sum(w) / len(w))
    return result


def _expanding_avg(values: list[float]) -> list[float]:
    """Compute expanding (lifetime) average.

    Args:
        values: Numeric series to compute a running average over.

    Returns:
        List of floats the same length as *values*, where element *i* is
        the mean of values[0] through values[i] (inclusive).
    """
    result: list[float] = []
    s = 0.0
    for i, v in enumerate(values, 1):
        s += v
        result.append(s / i)
    return result


def _format_rolling(values: list[float], window: int) -> list[float]:
    """Compute a rolling average and round each element to 2 decimal places.

    Args:
        values: Numeric series to smooth.
        window: Rolling window size passed to ``_rolling_avg``.

    Returns:
        List of floats, same length as *values*, each rounded to 2dp.
    """
    return [round(v, 2) for v in _rolling_avg(values, window)]


def _format_expanding(values: list[float]) -> list[float]:
    """Compute an expanding average and round each element to 2 decimal places.

    Args:
        values: Numeric series to compute running average over.

    Returns:
        List of floats, same length as *values*, each rounded to 2dp.
    """
    return [round(v, 2) for v in _expanding_avg(values)]


def _build_chart_series(values: list[float]) -> dict[str, list[float]]:
    """Build a chart series dict with raw values and rolling averages.

    Produces the standard structure used by Chart.js rendering: raw
    values plus 7-day, 28-day, and lifetime rolling averages.

    Args:
        values: Raw numeric series for one metric.

    Returns:
        Dict with keys: values, avg_7d, avg_28d, avg_lifetime.
    """
    return {
        "values": values,
        "avg_7d": _format_rolling(values, 7),
        "avg_28d": _format_rolling(values, 28),
        "avg_lifetime": _format_expanding(values),
    }


def compute_chart_data(daily_records: list[dict]) -> dict[str, Any]:
    """Compute chart series from daily records for Chart.js rendering.

    Sorts records by date and produces raw values plus 7-day, 28-day, and
    lifetime rolling averages for each metric.

    Args:
        daily_records: List of per-day aggregate dicts (from
            ``process_conversations``).  Each must contain "date",
            "total_chats", "avg_messages_per_chat", and "total_messages".

    Returns:
        Dict with keys: dates (list of ISO date strings), and for each
        metric (chats, avg_messages, total_messages) a sub-dict with
        keys: values, avg_7d, avg_28d, avg_lifetime.
    """
    sorted_records = sorted(daily_records, key=lambda r: r["date"])
    dates = [r["date"] for r in sorted_records]
    chats = [r["total_chats"] for r in sorted_records]
    avg_msgs = [r["avg_messages_per_chat"] for r in sorted_records]
    total_msgs = [r["total_messages"] for r in sorted_records]
    return {
        "dates": dates,
        "chats": _build_chart_series(chats),
        "avg_messages": _build_chart_series(avg_msgs),
        "total_messages": _build_chart_series(total_msgs),
    }


def _build_monthly_buckets(sorted_records: list[dict]) -> dict[str, dict]:
    """Aggregate sorted daily records into monthly buckets.

    Groups records by their "YYYY-MM" month key and sums chats,
    messages, and raw totals for avg-message computation.

    Args:
        sorted_records: List of daily record dicts, already sorted by
            date.  Each must contain "date", "total_chats", and
            "total_messages".

    Returns:
        Dict mapping "YYYY-MM" month keys to bucket dicts with keys
        chats, messages, total_msgs_raw, total_chats_raw.
    """
    monthly: dict[str, dict] = {}
    for r in sorted_records:
        month = r["date"][:7]
        if month not in monthly:
            monthly[month] = {"chats": 0, "messages": 0, "total_msgs_raw": 0, "total_chats_raw": 0}
        monthly[month]["chats"] += r["total_chats"]
        monthly[month]["messages"] += r["total_messages"]
        monthly[month]["total_msgs_raw"] += r["total_messages"]
        monthly[month]["total_chats_raw"] += r["total_chats"]
    return monthly


def compute_monthly_data(daily_records: list[dict]) -> dict[str, Any]:
    """Aggregate daily records into monthly buckets for the overview chart.

    Args:
        daily_records: List of per-day aggregate dicts.  Each must contain
            "date" (ISO string), "total_chats", and "total_messages".

    Returns:
        Dict with keys: months (list of "YYYY-MM" strings), chats (list of
        int), messages (list of int), avg_messages (list of float),
        chats_avg_3m (3-month rolling average of chats), messages_avg_3m
        (3-month rolling average of messages).
    """
    sorted_records = sorted(daily_records, key=lambda r: r["date"])
    monthly = _build_monthly_buckets(sorted_records)

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
        "chats_avg_3m": _format_rolling(chats, 3),
        "messages_avg_3m": _format_rolling(messages, 3),
    }


def _build_weekly_buckets(sorted_records: list[dict]) -> dict[str, dict]:
    """Aggregate sorted daily records into ISO-week buckets.

    Groups records by ISO week key and sums chats, messages, and raw
    totals for avg-message computation.

    Args:
        sorted_records: List of daily record dicts, already sorted by
            date.  Each must contain "date", "total_chats", and
            "total_messages".

    Returns:
        Dict mapping ISO week keys ("YYYY-Www") to bucket dicts with
        keys monday (isoformat string), chats, messages, total_msgs,
        total_chats.
    """
    from datetime import date as date_type

    weekly: dict[str, dict] = {}
    for r in sorted_records:
        d = date_type.fromisoformat(r["date"])
        iso = d.isocalendar()
        week_key = f"{iso[0]}-W{iso[1]:02d}"
        monday = d - timedelta(days=d.weekday())
        if week_key not in weekly:
            weekly[week_key] = {
                "monday": monday.isoformat(),
                "chats": 0,
                "messages": 0,
                "total_msgs": 0,
                "total_chats": 0,
            }
        weekly[week_key]["chats"] += r["total_chats"]
        weekly[week_key]["messages"] += r["total_messages"]
        weekly[week_key]["total_msgs"] += r["total_messages"]
        weekly[week_key]["total_chats"] += r["total_chats"]
    return weekly


def _weekly_series_from_buckets(
    weekly: dict[str, dict],
) -> tuple[list[str], list[int], list[int], list[float]]:
    """Extract parallel series lists from weekly buckets.

    Sorts bucket keys and builds aligned lists of Monday dates, chat
    counts, message counts, and average messages per chat.

    Args:
        weekly: Dict mapping ISO week keys to bucket dicts (from
            ``_build_weekly_buckets``).

    Returns:
        A 4-tuple of (weeks, chats, messages, avg_messages) where
        weeks is a list of Monday ISO date strings and the rest are
        parallel numeric lists.
    """
    sorted_keys = sorted(weekly.keys())
    weeks = [weekly[k]["monday"] for k in sorted_keys]
    chats = [weekly[k]["chats"] for k in sorted_keys]
    messages = [weekly[k]["messages"] for k in sorted_keys]
    avg_messages = [
        round(weekly[k]["total_msgs"] / weekly[k]["total_chats"], 2)
        if weekly[k]["total_chats"] > 0 else 0
        for k in sorted_keys
    ]
    return weeks, chats, messages, avg_messages


def compute_weekly_data(daily_records: list[dict]) -> dict[str, Any]:
    """Aggregate daily records into ISO-week buckets for the trends page.

    Args:
        daily_records: List of per-day aggregate dicts.  Each must contain
            "date" (ISO string), "total_chats", and "total_messages".

    Returns:
        Dict with keys: weeks (list of Monday ISO date strings), chats,
        messages, avg_messages (per-week values), plus rolling averages
        chats_avg_4w, chats_avg_12w, messages_avg_4w, messages_avg_12w,
        avg_messages_avg_4w, avg_messages_avg_12w.
    """
    sorted_records = sorted(daily_records, key=lambda r: r["date"])
    weekly = _build_weekly_buckets(sorted_records)
    weeks, chats, messages, avg_messages = _weekly_series_from_buckets(weekly)

    return {
        "weeks": weeks,
        "chats": chats,
        "messages": messages,
        "avg_messages": avg_messages,
        "chats_avg_4w": _format_rolling(chats, 4),
        "chats_avg_12w": _format_rolling(chats, 12),
        "messages_avg_4w": _format_rolling(messages, 4),
        "messages_avg_12w": _format_rolling(messages, 12),
        "avg_messages_avg_4w": _format_rolling(avg_messages, 4),
        "avg_messages_avg_12w": _format_rolling(avg_messages, 12),
    }


def compute_hourly_data(timestamps: list[datetime]) -> dict[str, Any]:
    """Compute hour-of-day x day-of-week activity grid from timestamps.

    Args:
        timestamps: List of datetime objects for user messages.

    Returns:
        Dict with keys:
            - heatmap: 7x24 nested list (heatmap[weekday][hour]) of message
              counts, where weekday 0 is Monday.
            - hourly_totals: list of 24 ints, total messages per hour.
            - weekday_totals: list of 7 ints, total messages per weekday.
    """
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


def _safe_div(num: float, den: float, default: float = 0.0) -> float:
    """Safe division returning *default* when denominator is zero.

    Args:
        num: Numerator.
        den: Denominator.
        default: Value to return when *den* is zero or falsy.

    Returns:
        ``round(num / den, 2)`` when *den* is truthy, otherwise *default*.
    """
    return round(num / den, 2) if den else default


def _content_metrics_from_records(
    sorted_records: list[dict],
) -> dict[str, list[float]]:
    """Extract per-period content metric lists from sorted daily/aggregated records.

    Computes averages and percentages from the raw word/message/code counts
    present in each record.

    Args:
        sorted_records: List of aggregate record dicts (daily, weekly, or
            monthly), already sorted by date.  Each must contain
            user_words, user_msgs, user_code_msgs, asst_words, asst_msgs,
            and asst_code_msgs.

    Returns:
        Dict mapping metric names to parallel float lists:
            - avg_user_words: average words per user message.
            - avg_asst_words: average words per assistant message.
            - response_ratio: assistant words / user words.
            - code_pct_user: percentage of user messages containing code.
            - code_pct_asst: percentage of assistant messages containing code.
    """
    avg_user_words = [_safe_div(r["user_words"], r["user_msgs"]) for r in sorted_records]
    avg_asst_words = [_safe_div(r["asst_words"], r["asst_msgs"]) for r in sorted_records]
    response_ratio = [_safe_div(r["asst_words"], r["user_words"]) for r in sorted_records]
    code_pct_user = [_safe_div(r["user_code_msgs"] * 100, r["user_msgs"]) for r in sorted_records]
    code_pct_asst = [_safe_div(r["asst_code_msgs"] * 100, r["asst_msgs"]) for r in sorted_records]
    return {
        "avg_user_words": avg_user_words,
        "avg_asst_words": avg_asst_words,
        "response_ratio": response_ratio,
        "code_pct_user": code_pct_user,
        "code_pct_asst": code_pct_asst,
    }


def _wrap_with_rolling(values: list[float]) -> dict[str, list[float]]:
    """Wrap a metric series with 7-day and 28-day rolling averages.

    Args:
        values: Raw metric series to augment with rolling averages.

    Returns:
        Dict with keys: values (the original series), avg_7d (7-period
        rolling average), avg_28d (28-period rolling average).
    """
    return {
        "values": values,
        "avg_7d": [round(v, 2) for v in _rolling_avg(values, 7)],
        "avg_28d": [round(v, 2) for v in _rolling_avg(values, 28)],
    }


def compute_content_chart_data(daily_records: list[dict]) -> dict[str, Any]:
    """Compute daily content metrics (word counts, response ratio, code %) with rolling averages.

    Args:
        daily_records: List of per-day aggregate dicts with content metric
            fields (user_words, user_msgs, asst_words, asst_msgs, etc.).

    Returns:
        Dict with keys: dates (list of ISO date strings), and for each
        content metric (avg_user_words, avg_asst_words, response_ratio,
        code_pct_user, code_pct_asst) a sub-dict with values, avg_7d,
        and avg_28d.
    """
    sorted_records = sorted(daily_records, key=lambda r: r["date"])
    dates = [r["date"] for r in sorted_records]
    m = _content_metrics_from_records(sorted_records)
    return {
        "dates": dates,
        "avg_user_words": _wrap_with_rolling(m["avg_user_words"]),
        "avg_asst_words": _wrap_with_rolling(m["avg_asst_words"]),
        "response_ratio": _wrap_with_rolling(m["response_ratio"]),
        "code_pct_user": _wrap_with_rolling(m["code_pct_user"]),
        "code_pct_asst": _wrap_with_rolling(m["code_pct_asst"]),
    }


def compute_content_weekly_data(daily_records: list[dict]) -> dict[str, Any]:
    """Aggregate content metrics by ISO week.

    Args:
        daily_records: List of per-day aggregate dicts with content metric
            fields (user_words, user_msgs, asst_words, asst_msgs, etc.).

    Returns:
        Dict with keys: weeks (list of Monday ISO date strings), and for
        each content metric (avg_user_words, avg_asst_words,
        response_ratio, code_pct_user, code_pct_asst) a sub-dict with
        values, avg_7d, and avg_28d.
    """
    from datetime import date as date_type

    sorted_records = sorted(daily_records, key=lambda r: r["date"])
    weekly: dict[str, dict] = {}
    for r in sorted_records:
        d = date_type.fromisoformat(r["date"])
        iso = d.isocalendar()
        week_key = f"{iso[0]}-W{iso[1]:02d}"
        monday = d - timedelta(days=d.weekday())
        if week_key not in weekly:
            weekly[week_key] = {
                "monday": monday.isoformat(),
                "user_words": 0, "user_chars": 0, "user_msgs": 0, "user_code_msgs": 0,
                "asst_words": 0, "asst_chars": 0, "asst_msgs": 0, "asst_code_msgs": 0,
            }
        for field in ("user_words", "user_chars", "user_msgs", "user_code_msgs",
                       "asst_words", "asst_chars", "asst_msgs", "asst_code_msgs"):
            weekly[week_key][field] += r[field]

    sorted_keys = sorted(weekly.keys())
    weeks = [weekly[k]["monday"] for k in sorted_keys]
    agg_records = [weekly[k] for k in sorted_keys]
    m = _content_metrics_from_records(agg_records)

    return {
        "weeks": weeks,
        "avg_user_words": _wrap_with_rolling(m["avg_user_words"]),
        "avg_asst_words": _wrap_with_rolling(m["avg_asst_words"]),
        "response_ratio": _wrap_with_rolling(m["response_ratio"]),
        "code_pct_user": _wrap_with_rolling(m["code_pct_user"]),
        "code_pct_asst": _wrap_with_rolling(m["code_pct_asst"]),
    }


def compute_content_monthly_data(daily_records: list[dict]) -> dict[str, Any]:
    """Aggregate content metrics by calendar month.

    Args:
        daily_records: List of per-day aggregate dicts with content metric
            fields (user_words, user_msgs, asst_words, asst_msgs, etc.).

    Returns:
        Dict with keys: months (list of "YYYY-MM" strings), and for each
        content metric (avg_user_words, avg_asst_words, response_ratio,
        code_pct_user, code_pct_asst) a sub-dict with values, avg_7d,
        and avg_28d.
    """
    sorted_records = sorted(daily_records, key=lambda r: r["date"])
    monthly: dict[str, dict] = {}
    for r in sorted_records:
        month = r["date"][:7]
        if month not in monthly:
            monthly[month] = {
                "user_words": 0, "user_chars": 0, "user_msgs": 0, "user_code_msgs": 0,
                "asst_words": 0, "asst_chars": 0, "asst_msgs": 0, "asst_code_msgs": 0,
            }
        for field in ("user_words", "user_chars", "user_msgs", "user_code_msgs",
                       "asst_words", "asst_chars", "asst_msgs", "asst_code_msgs"):
            monthly[month][field] += r[field]

    months = sorted(monthly.keys())
    agg_records = [monthly[m] for m in months]
    m = _content_metrics_from_records(agg_records)

    return {
        "months": months,
        "avg_user_words": _wrap_with_rolling(m["avg_user_words"]),
        "avg_asst_words": _wrap_with_rolling(m["avg_asst_words"]),
        "response_ratio": _wrap_with_rolling(m["response_ratio"]),
        "code_pct_user": _wrap_with_rolling(m["code_pct_user"]),
        "code_pct_asst": _wrap_with_rolling(m["code_pct_asst"]),
    }


def compute_code_stats(chat_summaries: list[dict]) -> dict[str, Any]:
    """Compute code language breakdown from chat summaries.

    Counts how many conversations contain code fences and tallies the
    programming languages detected across all conversations.

    Args:
        chat_summaries: List of per-conversation summary dicts (from
            ``process_conversations``).  Each must contain a
            "code_languages" key (list of language strings).

    Returns:
        Dict with keys:
            - total_conversations_with_code: int, number of conversations
              containing at least one code block.
            - pct_with_code: float, percentage of conversations with code.
            - language_counts: list of dicts (language, count), sorted
              descending by count.
    """
    lang_counter: dict[str, int] = {}
    convos_with_code = 0
    for s in chat_summaries:
        langs = s.get("code_languages", [])
        if langs:
            convos_with_code += 1
            for lang in langs:
                lang_counter[lang] = lang_counter.get(lang, 0) + 1

    total = len(chat_summaries)
    pct_with_code = round(convos_with_code / total * 100, 1) if total else 0.0
    language_counts = sorted(
        [{"language": lang, "count": cnt} for lang, cnt in lang_counter.items()],
        key=lambda x: x["count"],
        reverse=True,
    )

    return {
        "total_conversations_with_code": convos_with_code,
        "pct_with_code": pct_with_code,
        "language_counts": language_counts,
    }


_LENGTH_BUCKETS = [
    ("1-2", 1, 2),
    ("3-5", 3, 5),
    ("6-10", 6, 10),
    ("11-20", 11, 20),
    ("21-50", 21, 50),
    ("50+", 51, float("inf")),
]


def compute_length_distribution(summaries: list[dict]) -> dict[str, Any]:
    """Bucket conversation lengths into a histogram distribution.

    Groups conversations by their message_count into predefined buckets
    (1-2, 3-5, 6-10, 11-20, 21-50, 50+) for bar-chart rendering.

    Args:
        summaries: List of per-conversation summary dicts.  Each must
            contain a "message_count" key (int).

    Returns:
        Dict with keys:
            - buckets: list of bucket label strings (e.g., "1-2", "50+").
            - counts: list of ints, number of conversations in each bucket.
    """
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


def _compute_period_bucket(
    daily_records: list[dict],
    match_fn: object,
) -> dict[str, int | float]:
    """Aggregate daily records matching a predicate into a period bucket.

    Loops through all daily records and accumulates chats and messages
    for those where *match_fn* returns True.

    Args:
        daily_records: List of per-day aggregate dicts.  Each must
            contain "date", "total_chats", and "total_messages".
        match_fn: A callable taking a single record dict and returning
            True if the record belongs to this period.

    Returns:
        Dict with keys chats (int), messages (int), avg_messages (float).
    """
    chats = 0
    messages = 0
    total_chats = 0
    for r in daily_records:
        if match_fn(r):
            chats += r["total_chats"]
            messages += r["total_messages"]
            total_chats += r["total_chats"]
    avg = round(messages / total_chats, 2) if total_chats > 0 else 0
    return {"chats": chats, "messages": messages, "avg_messages": avg}


def _add_period_projections(
    stats: dict,
    elapsed: int,
    total: int,
) -> None:
    """Add pro-rata projections to a current-period stats dict.

    Computes projected_chats and projected_messages by scaling the
    actual values by the ratio of total to elapsed days.

    Args:
        stats: Period stats dict (modified in place).  Must contain
            "chats" and "messages" keys.
        elapsed: Number of days elapsed in the current period.
        total: Total number of days in the full period.
    """
    stats["elapsed_days"] = elapsed
    stats["total_days"] = total
    factor = total / elapsed if elapsed > 0 else 1
    stats["projected_chats"] = round(stats["chats"] * factor, 2)
    stats["projected_messages"] = round(stats["messages"] * factor, 2)


def compute_period_comparison(
    daily_records: list[dict],
    reference_date: str | None = None,
) -> dict[str, Any]:
    """Compute month-over-month and year-over-year comparison stats.

    Buckets daily records into this-month, last-month, this-year, and
    last-year periods relative to *reference_date*.  For current
    (partial) periods, includes pro-rata projections.

    Args:
        daily_records: List of per-day aggregate dicts.  Each must contain
            "date" (ISO string), "total_chats", and "total_messages".
        reference_date: ISO date string ("YYYY-MM-DD") to use as "today"
            for period boundaries.  Defaults to the actual current date.

    Returns:
        Dict with keys this_month, last_month, this_year, last_year.
        Each value is a dict with: chats, messages, avg_messages.
        Current-period entries (this_month, this_year) additionally
        include elapsed_days, total_days, projected_chats, and
        projected_messages.
    """
    from datetime import date as date_type

    if reference_date:
        ref = date_type.fromisoformat(reference_date)
    else:
        ref = date_type.today()

    this_month_key = f"{ref.year}-{ref.month:02d}"
    last_month_key = f"{ref.year - 1}-12" if ref.month == 1 else f"{ref.year}-{ref.month - 1:02d}"
    this_year_key = str(ref.year)
    last_year_key = str(ref.year - 1)

    result = {
        "this_month": _compute_period_bucket(daily_records, lambda r: r["date"][:7] == this_month_key),
        "last_month": _compute_period_bucket(daily_records, lambda r: r["date"][:7] == last_month_key),
        "this_year": _compute_period_bucket(daily_records, lambda r: r["date"][:4] == this_year_key),
        "last_year": _compute_period_bucket(daily_records, lambda r: r["date"][:4] == last_year_key),
    }

    month_total_days = calendar.monthrange(ref.year, ref.month)[1]
    year_total_days = 366 if calendar.isleap(ref.year) else 365
    year_elapsed = (ref - date_type(ref.year, 1, 1)).days + 1

    _add_period_projections(result["this_month"], ref.day, month_total_days)
    _add_period_projections(result["this_year"], year_elapsed, year_total_days)

    return result


def _top_records_per_year(records: list[dict], per_year: int = 10) -> list[dict]:
    """Return top *per_year* records for each calendar year, preserving sort order.

    Records are already sorted by the desired ranking field (descending).
    Collects up to *per_year* per year, then returns the merged list
    in the original sort order.

    Args:
        records: Pre-sorted (descending by ranking metric) list of daily
            record dicts.  Each must contain a "date" key starting with
            a 4-digit year.
        per_year: Maximum number of records to keep per calendar year.

    Returns:
        Filtered list of record dicts, containing at most *per_year*
        entries per year, in the same order as the input.
    """
    buckets: dict[str, int] = {}
    result = []
    for r in records:
        yr = r["date"][:4]
        count = buckets.get(yr, 0)
        if count < per_year:
            result.append(r)
            buckets[yr] = count + 1
    return result


def _top_gaps_per_year(gaps: list[dict], per_year: int = 25) -> list[dict]:
    """Return top *per_year* gaps for each calendar year, merged and sorted.

    Gaps are already sorted longest-first.  Collects up to *per_year*
    for each year (based on start_timestamp), merges, and re-sorts
    descending by length_days.

    Args:
        gaps: Pre-sorted (descending by length_days) list of gap dicts.
            Each must contain "start_timestamp" (ISO string) and
            "length_days".
        per_year: Maximum number of gaps to keep per calendar year.

    Returns:
        Merged list of gap dicts, at most *per_year* per year, sorted
        descending by length_days.
    """
    buckets: dict[str, list[dict]] = {}
    for g in gaps:
        yr = g["start_timestamp"][:4]
        bucket = buckets.setdefault(yr, [])
        if len(bucket) < per_year:
            bucket.append(g)
    merged = [g for bucket in buckets.values() for g in bucket]
    merged.sort(key=lambda g: g["length_days"], reverse=True)
    return merged


def build_dashboard_payload(path: str = "conversations.json") -> dict[str, Any]:
    """One-call entry point: load, process, compute all stats for the dashboard.

    Loads the conversation file, processes it, and runs every analytics
    computation needed by the web dashboard.  This is the only function
    the FastAPI app needs to call.

    Args:
        path: Filesystem path to the OpenAI conversations.json export.
            Defaults to "conversations.json" in the current directory.

    Returns:
        Dict with keys: generated_at (ISO timestamp), summary, charts,
        gaps (top 25/year), gap_stats, monthly, weekly, hourly,
        length_distribution, comparison, activity_by_year,
        content_charts, content_weekly, content_monthly, code_stats,
        content_summary.

    Raises:
        FileNotFoundError: If the conversations file does not exist.
        json.JSONDecodeError: If the file contains invalid JSON.
    """
    convos = load_conversations(path)
    summaries, records, timestamps = process_conversations(convos)
    gap_data = compute_gap_analysis(timestamps)
    stats = compute_summary_stats(summaries, records)
    charts = compute_chart_data(records)
    code_stats = compute_code_stats(summaries)

    # Compute content summary from summaries
    total_user_words = sum(s.get("user_words", 0) for s in summaries)
    total_asst_words = sum(s.get("asst_words", 0) for s in summaries)
    total_summaries = len(summaries)
    content_summary = {
        "avg_user_words": round(total_user_words / total_summaries, 1) if total_summaries else 0,
        "avg_asst_words": round(total_asst_words / total_summaries, 1) if total_summaries else 0,
        "avg_response_ratio": round(total_asst_words / total_user_words, 2) if total_user_words else 0,
        "pct_conversations_with_code": code_stats["pct_with_code"],
    }

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
        "activity_by_year": compute_activity_by_year(timestamps),
        "content_charts": compute_content_chart_data(records),
        "content_weekly": compute_content_weekly_data(records),
        "content_monthly": compute_content_monthly_data(records),
        "code_stats": code_stats,
        "content_summary": content_summary,
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
    """Write CSV/JSON analytics files to output_dir.

    Creates the output directory if it doesn't exist and writes:
    chat_summaries.json/csv, daily_stats.json/csv, and (if gaps is
    non-empty) message_gaps.json/csv.

    Args:
        summaries: List of per-conversation summary dicts.
        records: List of per-day aggregate dicts.
        gaps: List of gap dicts (start_timestamp, end_timestamp,
            length_days).  If empty, gap files are not written.
        output_dir: Directory path for output files.  Created if it
            doesn't exist.  Defaults to "chat_analytics".
    """
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
    """Print the CLI summary report to stdout.

    Formats and prints a human-readable summary including totals, date
    range, top days, and inactivity analysis.

    Args:
        stats: Summary statistics dict (from ``compute_summary_stats``).
            Must contain total_messages, total_chats, first_date,
            last_date, years_span, top_days_by_chats, top_days_by_messages.
        gap_data: Gap analysis dict (from ``compute_gap_analysis``).
            Must contain total_days, days_active, days_inactive,
            proportion_inactive, longest_gap, and gaps.
    """
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

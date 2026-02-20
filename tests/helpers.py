"""Shared test helpers for chatgpt_stats tests.

Regular functions (not fixtures) that can be imported by any test module.
"""

from __future__ import annotations

from datetime import datetime


def make_conversation(user_messages: list[tuple[float, str]]) -> dict:
    """Build a minimal conversation dict from (unix_epoch, text) tuples.

    Args:
        user_messages: List of (timestamp, text) pairs for user messages.

    Returns:
        A dict matching the ChatGPT export conversation structure.
    """
    mapping: dict[str, dict] = {}
    for i, (ts, text) in enumerate(user_messages):
        mapping[f"msg-{i}"] = {
            "message": {
                "author": {"role": "user"},
                "create_time": ts,
                "content": {"parts": [text]},
            }
        }
    mapping["system-node"] = {"message": None}
    return {"mapping": mapping}


def make_conversations_with_days(
    day_configs: list[tuple[str, int, int]],
) -> list[dict]:
    """Build conversations spanning multiple days.

    Args:
        day_configs: List of (date_str, num_chats, msgs_per_chat) tuples.

    Returns:
        A list of conversation dicts.
    """
    convos = []
    for date_str, num_chats, msgs_per_chat in day_configs:
        base = datetime.fromisoformat(date_str + "T10:00:00")
        for c in range(num_chats):
            msgs = []
            for m in range(msgs_per_chat):
                ts = base.timestamp() + c * 3600 + m * 60
                msgs.append((ts, f"msg-{c}-{m}"))
            convos.append(make_conversation(msgs))
    return convos

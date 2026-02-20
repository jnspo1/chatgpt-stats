"""Tests for chat_gpt_history.py (extract_user_prompts, find_earliest_conversation)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chat_gpt_history import extract_user_prompts, find_earliest_conversation


# ── Helpers ──────────────────────────────────────────────────────


def _write_json(path: Path, data: object) -> str:
    """Write *data* as JSON and return the string path."""
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def _make_conversation(user_texts: list[str], base_ts: float = 1_700_000_000) -> dict:
    """Build a minimal conversation dict with user messages.

    Each message gets a sequential timestamp starting at *base_ts*.
    """
    mapping: dict[str, dict] = {}
    for i, text in enumerate(user_texts):
        mapping[f"msg-{i}"] = {
            "message": {
                "author": {"role": "user"},
                "create_time": base_ts + i * 60,
                "content": {"parts": [text]},
            }
        }
    # Include a system node (no message) to exercise null-guard paths
    mapping["system-node"] = {"message": None}
    return {"title": "Test Chat", "mapping": mapping}


# ── extract_user_prompts ─────────────────────────────────────────


class TestExtractUserPrompts:

    def test_extract_basic(self, tmp_path: Path):
        """User messages are extracted from a single conversation."""
        conv = _make_conversation(["Hello world", "Follow-up question"])
        path = _write_json(tmp_path / "conv.json", [conv])

        result = extract_user_prompts(path)

        assert len(result) == 2
        assert "Hello world" in result
        assert "Follow-up question" in result

    def test_extract_empty_file(self, tmp_path: Path):
        """An empty JSON array produces an empty prompt list."""
        path = _write_json(tmp_path / "empty.json", [])

        result = extract_user_prompts(path)

        assert result == []

    def test_extract_first_prompt_flag(self, tmp_path: Path):
        """only_first_prompt=True truncates messages at the first semicolon.

        Messages without a semicolon are excluded entirely (the function
        only appends when a semicolon is found in this mode).
        """
        conv = _make_conversation([
            "Start of prompt; rest is ignored",
            "No semicolon here",
        ])
        path = _write_json(tmp_path / "conv.json", [conv])

        result = extract_user_prompts(path, only_first_prompt=True)

        # Only the message with a semicolon is included
        assert len(result) == 1
        assert result[0] == "Start of prompt;"


# ── find_earliest_conversation ───────────────────────────────────


class TestFindEarliestConversation:

    def test_find_earliest_missing_file(self, tmp_path: Path):
        """A non-existent file returns (None, None)."""
        missing = str(tmp_path / "does_not_exist.json")

        conv, ts = find_earliest_conversation(missing)

        assert conv is None
        assert ts is None

    def test_find_earliest_basic(self, tmp_path: Path):
        """The conversation containing the oldest timestamp is returned."""
        newer = _make_conversation(["newer msg"], base_ts=1_700_100_000)
        older = _make_conversation(["older msg"], base_ts=1_700_000_000)
        older["title"] = "Oldest Chat"
        path = _write_json(tmp_path / "conv.json", [newer, older])

        conv, ts = find_earliest_conversation(path)

        assert conv is not None
        assert ts == 1_700_000_000
        assert conv["title"] == "Oldest Chat"

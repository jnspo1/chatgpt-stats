"""Tests for chat_gpt_export.py parsing and formatting functions."""

from __future__ import annotations

import json

import pytest

from chat_gpt_export import (
    _extract_export_message,
    _load_and_parse_conversations,
    _parse_mapping_messages,
    _parse_single_conversation,
    clean_text,
    format_timestamp,
    get_first_user_message,
    preview_conversation,
)


# -- Helpers -----------------------------------------------------------------

def _make_message_data(
    role: str = "user",
    content_parts: list | None = None,
    create_time: float | None = 1700000000.0,
) -> dict:
    """Build a minimal mapping entry for _extract_export_message."""
    if content_parts is None:
        content_parts = ["Hello world"]
    return {
        "message": {
            "author": {"role": role},
            "create_time": create_time,
            "content": {"parts": content_parts},
        }
    }


def _make_chat(
    title: str = "Test Chat",
    mapping: dict | None = None,
) -> dict:
    """Build a minimal conversation dict with a valid mapping."""
    if mapping is None:
        mapping = {
            "msg-0": _make_message_data("user", ["Hi there"], 1700000000.0),
            "msg-1": _make_message_data("assistant", ["Hello!"], 1700000060.0),
        }
    return {"title": title, "mapping": mapping}


# -- clean_text --------------------------------------------------------------

class TestCleanText:
    def test_basic_text_unchanged(self):
        assert clean_text("Hello world") == "Hello world"

    def test_multiple_newlines_reduced(self):
        assert clean_text("a\n\n\n\nb") == "a\n\nb"

    def test_strips_leading_trailing_whitespace(self):
        assert clean_text("  hello  ") == "hello"

    def test_empty_string(self):
        assert clean_text("") == ""


# -- format_timestamp --------------------------------------------------------

class TestFormatTimestamp:
    def test_valid_int_timestamp(self):
        result = format_timestamp(1700000000)
        # 2023-11-14 in UTC — exact string depends on local TZ, just check format
        assert len(result) == 19
        assert result[4] == "-" and result[10] == " " and result[13] == ":"

    def test_valid_float_timestamp(self):
        result = format_timestamp(1700000000.5)
        assert len(result) == 19
        assert result[4] == "-"

    def test_none_returns_unknown_time(self):
        assert format_timestamp(None) == "Unknown time"

    def test_invalid_value_returns_invalid(self):
        assert format_timestamp("not-a-number") == "Invalid timestamp"


# -- get_first_user_message --------------------------------------------------

class TestGetFirstUserMessage:
    def test_returns_first_user_content(self):
        messages = [
            {"role": "assistant", "content": "Hi"},
            {"role": "user", "content": "My question"},
        ]
        assert get_first_user_message(messages) == "My question"

    def test_long_message_truncated(self):
        long_text = "x" * 300
        messages = [{"role": "user", "content": long_text}]
        result = get_first_user_message(messages)
        assert len(result) == 203  # 200 + "..."
        assert result.endswith("...")

    def test_no_user_messages(self):
        messages = [{"role": "assistant", "content": "Hi"}]
        assert get_first_user_message(messages) == "[No user message found]"

    def test_empty_list(self):
        assert get_first_user_message([]) == "[No user message found]"


# -- preview_conversation ----------------------------------------------------

class TestPreviewConversation:
    def test_returns_formatted_preview(self):
        convo = {
            "title": "My Chat",
            "create_time": 1700000000,
            "messages": [{"role": "user", "content": "Hello"}],
        }
        result = preview_conversation(convo, 3)
        assert "[3] My Chat" in result
        assert "First message: Hello" in result


# -- _extract_export_message -------------------------------------------------

class TestExtractExportMessage:
    def test_valid_message(self):
        data = _make_message_data("user", ["Hello world"], 1700000000.0)
        result = _extract_export_message(data)
        assert result is not None
        assert result["role"] == "user"
        assert result["content"] == "Hello world"
        assert result["timestamp"] == 1700000000.0

    def test_non_dict_returns_none(self):
        assert _extract_export_message("not a dict") is None

    def test_missing_message_key(self):
        assert _extract_export_message({"other": "data"}) is None

    def test_system_role_returns_none(self):
        data = _make_message_data("system", ["System prompt"])
        assert _extract_export_message(data) is None

    def test_empty_content_parts_returns_none(self):
        data = _make_message_data("user", [])
        assert _extract_export_message(data) is None


# -- _parse_mapping_messages -------------------------------------------------

class TestParseMappingMessages:
    def test_valid_items(self):
        items = [
            ("msg-0", _make_message_data("user", ["Hi"], 100.0)),
            ("msg-1", _make_message_data("assistant", ["Hey"], 200.0)),
        ]
        create_time, messages = _parse_mapping_messages(items)
        assert create_time == 100.0
        assert len(messages) == 2
        assert messages[0]["role"] == "user"

    def test_all_invalid_items(self):
        items = [
            ("msg-0", {"message": None}),
            ("msg-1", "not a dict"),
        ]
        create_time, messages = _parse_mapping_messages(items)
        assert create_time is None
        assert messages == []


# -- _parse_single_conversation ----------------------------------------------

class TestParseSingleConversation:
    def test_valid_chat(self):
        chat = _make_chat("My Title")
        result = _parse_single_conversation(chat)
        assert result is not None
        assert result["title"] == "My Title"
        assert len(result["messages"]) == 2

    def test_missing_mapping_returns_none(self):
        assert _parse_single_conversation({"title": "No Mapping"}) is None

    def test_non_dict_mapping_returns_none(self):
        assert _parse_single_conversation({"mapping": "bad"}) is None

    def test_empty_messages_returns_none(self):
        # Mapping with only a system message -> no valid messages
        mapping = {"sys": _make_message_data("system", ["sys prompt"])}
        assert _parse_single_conversation({"mapping": mapping}) is None


# -- _load_and_parse_conversations -------------------------------------------

class TestLoadAndParseConversations:
    def test_valid_json(self, tmp_path):
        chats = [_make_chat("Chat A"), _make_chat("Chat B")]
        path = tmp_path / "convos.json"
        path.write_text(json.dumps(chats))

        result = _load_and_parse_conversations(str(path))
        assert len(result) == 2
        # Newest first — both have same timestamp so order is stable but both present
        titles = {c["title"] for c in result}
        assert titles == {"Chat A", "Chat B"}

    def test_file_not_found(self, tmp_path, capsys):
        result = _load_and_parse_conversations(str(tmp_path / "missing.json"))
        assert result == []
        assert "not found" in capsys.readouterr().out

    def test_invalid_json(self, tmp_path, capsys):
        path = tmp_path / "bad.json"
        path.write_text("{bad json!!")

        result = _load_and_parse_conversations(str(path))
        assert result == []
        assert "not a valid JSON" in capsys.readouterr().out

    def test_empty_conversations_list(self, tmp_path):
        path = tmp_path / "empty.json"
        path.write_text("[]")

        result = _load_and_parse_conversations(str(path))
        assert result == []

    def test_invalid_entries_skipped(self, tmp_path):
        chats = [_make_chat("Good Chat"), {"mapping": "invalid"}]
        path = tmp_path / "mixed.json"
        path.write_text(json.dumps(chats))

        result = _load_and_parse_conversations(str(path))
        assert len(result) == 1
        assert result[0]["title"] == "Good Chat"

"""Tests for chat_gpt_summary.py::main()."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest


MODULE = "chat_gpt_summary"


class TestMainErrorHandling:
    """Verify main() exits with code 1 on file-related errors."""

    def test_missing_file_exits_1(self):
        with patch(
            f"{MODULE}.load_conversations",
            side_effect=FileNotFoundError("not found"),
        ):
            with pytest.raises(SystemExit) as exc_info:
                from chat_gpt_summary import main

                main("nonexistent.json")
            assert exc_info.value.code == 1

    def test_invalid_json_exits_1(self):
        err = json.JSONDecodeError("bad value", "", 0)
        with patch(
            f"{MODULE}.load_conversations",
            side_effect=err,
        ):
            with pytest.raises(SystemExit) as exc_info:
                from chat_gpt_summary import main

                main("corrupt.json")
            assert exc_info.value.code == 1


class TestMainSuccessfulRun:
    """Verify main() completes without error when all analytics succeed."""

    def test_successful_run(self):
        with (
            patch(f"{MODULE}.load_conversations", return_value=[]),
            patch(
                f"{MODULE}.process_conversations",
                return_value=([], [], []),
            ),
            patch(
                f"{MODULE}.compute_gap_analysis",
                return_value={"gaps": []},
            ),
            patch(f"{MODULE}.compute_summary_stats", return_value={}),
            patch(f"{MODULE}.save_analytics_files"),
            patch(f"{MODULE}.print_summary_report"),
        ):
            from chat_gpt_summary import main

            # Should complete without raising SystemExit or any exception
            main("conversations.json")

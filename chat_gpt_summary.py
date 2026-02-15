"""CLI tool for ChatGPT conversation analytics.

Generates summary statistics, CSV/JSON files, and gap analysis from
an OpenAI conversation export (conversations.json).
"""

import json
import sys

from analytics import (
    load_conversations,
    process_conversations,
    compute_gap_analysis,
    compute_summary_stats,
    save_analytics_files,
    print_summary_report,
)


def main(json_path: str = "conversations.json") -> None:
    try:
        convos = load_conversations(json_path)
    except FileNotFoundError:
        print(
            f"Error: '{json_path}' not found.\n"
            f"Download your data from OpenAI (Settings > Data Controls > Export)\n"
            f"and place conversations.json in the current directory.",
            file=sys.stderr,
        )
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(
            f"Error: '{json_path}' is not valid JSON (line {e.lineno}): {e.msg}\n"
            f"The file may be corrupted. Try re-downloading from OpenAI.",
            file=sys.stderr,
        )
        sys.exit(1)

    summaries, records, timestamps = process_conversations(convos)
    gap_data = compute_gap_analysis(timestamps)
    stats = compute_summary_stats(summaries, records)
    save_analytics_files(summaries, records, gap_data["gaps"])
    print_summary_report(stats, gap_data)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "conversations.json")

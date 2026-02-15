"""CLI tool for ChatGPT conversation analytics.

Generates summary statistics, CSV/JSON files, and gap analysis from
an OpenAI conversation export (conversations.json).
"""

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
    convos = load_conversations(json_path)
    summaries, records, timestamps = process_conversations(convos)
    gap_data = compute_gap_analysis(timestamps)
    stats = compute_summary_stats(summaries, records)
    save_analytics_files(summaries, records, gap_data["gaps"])
    print_summary_report(stats, gap_data)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "conversations.json")

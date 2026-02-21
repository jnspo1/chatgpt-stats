"""chat_gpt_history.py

Extract user prompts from a ChatGPT conversation history JSON file.

By default the script runs quietly (no stdout) to avoid printing large sample
messages. Use `--print` to print found prompts, or `--output FILE` to write the
prompts to a file.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime


def extract_user_prompts(json_file: str, only_first_prompt: bool = False) -> list[str]:
    """Extract user prompts from a ChatGPT conversation JSON file.

    Args:
        json_file: Path to the JSON file.
        only_first_prompt: If True, include only up to the first semicolon for
            each user message.

    Returns:
        A list of extracted prompt strings.

    Raises:
        FileNotFoundError: If the JSON file does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    with open(json_file, 'r', encoding='utf-8') as file:
        data = json.load(file)

    user_prompts: list[str] = []

    def search_messages(item):
        if isinstance(item, dict):
            if item.get('author', {}).get('role') == 'user':
                content_parts = item.get('content', {}).get('parts', [])
                if all(isinstance(part, str) for part in content_parts):
                    content = ' '.join(content_parts)
                    semicolon_index = content.find(';')
                    if semicolon_index != -1 and only_first_prompt:
                        user_prompts.append(content[:semicolon_index + 1])
                    elif not only_first_prompt:
                        user_prompts.append(content[:semicolon_index + 1] if semicolon_index != -1 else content)
            for value in item.values():
                search_messages(value)
        elif isinstance(item, list):
            for sub_item in item:
                search_messages(sub_item)

    search_messages(data)
    return user_prompts


def _extract_conversation_timestamp(chat: dict) -> int | None:
    """Extract the earliest message timestamp from a conversation mapping.

    Iterates over all messages in the conversation's mapping and returns
    the minimum valid Unix timestamp found.

    Args:
        chat: A conversation dict containing a 'mapping' key with message data.

    Returns:
        The earliest Unix timestamp as an integer, or None if no valid
        timestamps are found or the input is not a valid conversation dict.
    """
    if not isinstance(chat, dict):
        return None
    mapping = chat.get('mapping', {})
    if not isinstance(mapping, dict):
        return None

    timestamps: list[int] = []
    for message_data in mapping.values():
        if not isinstance(message_data, dict):
            continue
        msg = message_data.get('message')
        if not isinstance(msg, dict):
            continue
        ts = msg.get('create_time')
        if ts is None:
            continue
        try:
            timestamps.append(int(float(ts)))
        except (TypeError, ValueError, OverflowError):
            continue

    return min(timestamps) if timestamps else None


def find_earliest_conversation(json_file: str) -> tuple[dict | None, int | None]:
    """Return the conversation with the earliest message timestamp and that timestamp.

    Args:
        json_file: Path to the conversations JSON file.

    Returns:
        A tuple of (conversation_dict, earliest_unix_timestamp), or
        (None, None) if no valid conversations are found or the file
        cannot be read.
    """
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return None, None

    earliest_conv = None
    earliest_time = None

    for chat in data:
        ts = _extract_conversation_timestamp(chat)
        if ts is not None and (earliest_time is None or ts < earliest_time):
            earliest_time = ts
            earliest_conv = chat

    return earliest_conv, earliest_time


def _extract_printable_message(message_data: dict) -> dict | None:
    """Validate a mapping entry and return a printable message dict.

    Extracts timestamp, role, and content from a conversation mapping
    entry, performing validation at each step.

    Args:
        message_data: A single entry from a conversation's mapping dict,
            expected to contain a 'message' key with author and content info.

    Returns:
        A dict with keys 'ts' (int), 'role' (str), and 'content' (str),
        or None if the entry is invalid or missing required fields.
    """
    if not isinstance(message_data, dict):
        return None
    msg = message_data.get('message')
    if not isinstance(msg, dict):
        return None

    ts = msg.get('create_time')
    try:
        t = int(float(ts)) if ts is not None else 0
    except (TypeError, ValueError, OverflowError):
        t = 0

    role = msg.get('author', {}).get('role', 'unknown')
    parts = msg.get('content', {}).get('parts', [])
    content = ' '.join(str(p) for p in parts) if parts else ''

    return {'ts': t, 'role': role, 'content': content}


def _format_timestamp_str(ts: int | float | None) -> str:
    """Format a Unix timestamp for display.

    Args:
        ts: A Unix timestamp as an integer or float, or None.

    Returns:
        A formatted datetime string ('YYYY-MM-DD HH:MM:SS'), 'Unknown'
        if the timestamp is falsy, or 'Invalid' if formatting fails.
    """
    if not ts:
        return 'Unknown'
    try:
        return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return 'Invalid'


def format_and_print_conversation(conv: dict, title: str | None = None) -> None:
    """Pretty-print a conversation mapping to stdout.

    Args:
        conv: A conversation dict with a 'mapping' key containing messages.
        title: Optional title override. Defaults to the conversation's own title.
    """
    if not conv or not isinstance(conv, dict):
        return

    if title is None:
        title = conv.get('title', 'Untitled Conversation')

    print('\n' + '=' * 60)
    print(f"First Conversation (earliest): {title}")
    print('=' * 60)

    mapping = conv.get('mapping', {})
    messages = []
    for message_data in mapping.values():
        msg = _extract_printable_message(message_data)
        if msg is not None:
            messages.append(msg)

    messages.sort(key=lambda m: m.get('ts', 0))

    for m in messages:
        ts_str = _format_timestamp_str(m.get('ts'))
        role = (m.get('role') or 'unknown').upper()
        print(f"[{ts_str}] {role}: {m.get('content', '')}")
    print('\n' + '-' * 60 + '\n')


def main() -> None:
    """CLI entry point for extracting user prompts from ChatGPT history."""
    parser = argparse.ArgumentParser(description='Extract user prompts from ChatGPT history JSON')
    parser.add_argument('json_file', nargs='?', default='conversations.json',
                        help='Path to the conversations JSON file (default: conversations.json)')
    parser.add_argument('--only-first-prompt', '-f', action='store_true',
                        help='Include only up to the first semicolon of each message')
    parser.add_argument('--print', '-p', dest='do_print', action='store_true',
                        help='Print extracted prompts to stdout')
    parser.add_argument('--quiet', '-q', dest='do_print', action='store_false',
                        help='Suppress printing')
    parser.add_argument('--output', '-o', help='Write extracted prompts to a file')

    # Default to printing the earliest conversation unless --quiet is given
    parser.set_defaults(do_print=True)

    args = parser.parse_args()

    try:
        prompts = extract_user_prompts(args.json_file, only_first_prompt=args.only_first_prompt)
    except FileNotFoundError:
        parser.error(f"File not found: {args.json_file}")

    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as out:
                for p in prompts:
                    out.write(p + "\n" + ("-" * 36) + "\n")
        except Exception as e:
            parser.error(f"Failed to write output file: {e}")

    # If printing is requested, pretty-print only the earliest full
    # conversation chain (no extracted prompts are printed).
    if args.do_print:
        conv, ts = find_earliest_conversation(args.json_file)
        if conv:
            format_and_print_conversation(conv, title=conv.get('title'))
        else:
            print("No conversation found to display.")

    # Final guidance for next steps
    print("\nRun 'python chat_gpt_summary.py' to generate summaries and 'python chat_gpt_viz.py' to create visualizations.")


if __name__ == '__main__':
    main()

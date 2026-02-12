"""chat_gpt_history.py

Extract user prompts from a ChatGPT conversation history JSON file.

By default the script runs quietly (no stdout) to avoid printing large sample
messages. Use `--print` to print found prompts, or `--output FILE` to write the
prompts to a file.
"""

import argparse
import json
from datetime import datetime
from typing import List, Optional, Tuple


def extract_user_prompts(json_file: str, only_first_prompt: bool = False) -> List[str]:
    """Extract user prompts from a ChatGPT conversation JSON file.

    Args:
        json_file: Path to the JSON file.
        only_first_prompt: If True, include only up to the first semicolon for
            each user message.

    Returns:
        A list of extracted prompt strings.
    """
    with open(json_file, 'r', encoding='utf-8') as file:
        data = json.load(file)

    user_prompts: List[str] = []

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


def find_earliest_conversation(json_file: str) -> Tuple[Optional[dict], Optional[int]]:
    """Return the conversation with the earliest message timestamp and that timestamp.

    Returns (conversation_dict, earliest_timestamp) or (None, None) if not found.
    """
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return None, None

    earliest_conv = None
    earliest_time = None

    for chat in data:
        mapping = chat.get('mapping', {}) if isinstance(chat, dict) else {}
        for _, message_data in mapping.items():
            if not message_data or not isinstance(message_data, dict):
                continue
            msg = message_data.get('message')
            if not msg or not isinstance(msg, dict):
                continue
            ts = msg.get('create_time')
            if ts is None:
                continue
            try:
                t = int(float(ts))
            except Exception:
                continue
            if earliest_time is None or t < earliest_time:
                earliest_time = t
                earliest_conv = chat

    return earliest_conv, earliest_time


def format_and_print_conversation(conv: dict, title: Optional[str] = None) -> None:
    """Pretty-print a conversation mapping (title optional)."""
    if not conv or not isinstance(conv, dict):
        return

    if title is None:
        title = conv.get('title', 'Untitled Conversation')

    print('\n' + '=' * 60)
    print(f"First Conversation (earliest): {title}")
    print('=' * 60)

    mapping = conv.get('mapping', {})
    messages = []
    for message_id, message_data in mapping.items():
        if not message_data or not isinstance(message_data, dict):
            continue
        msg = message_data.get('message')
        if not msg or not isinstance(msg, dict):
            continue
        ts = msg.get('create_time')
        try:
            t = int(float(ts)) if ts is not None else 0
        except Exception:
            t = 0
        role = msg.get('author', {}).get('role', 'unknown')
        parts = msg.get('content', {}).get('parts', [])
        content = ' '.join(str(p) for p in parts) if parts else ''
        messages.append({'ts': t, 'role': role, 'content': content})

    # Sort messages by timestamp
    messages.sort(key=lambda m: m.get('ts', 0))

    for m in messages:
        ts = m.get('ts')
        try:
            ts_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S') if ts else 'Unknown'
        except Exception:
            ts_str = 'Invalid'
        role = (m.get('role') or 'unknown').upper()
        print(f"[{ts_str}] {role}: {m.get('content', '')}")
    print('\n' + '-' * 60 + '\n')


def main():
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

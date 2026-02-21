"""
This script exports ChatGPT conversations from a conversation history JSON file
into a human-readable text format. It includes the chat title, timestamps, and all messages
from both the user and ChatGPT. The script runs in interactive mode by default,
allowing users to select which conversations to include.
"""

from __future__ import annotations

import json
from datetime import datetime
import os
import re
import sys

def clean_text(text: str) -> str:
    """Remove markdown and excessive whitespace from text.

    Args:
        text: Raw text content potentially containing markdown formatting
            and excessive whitespace.

    Returns:
        Cleaned text with multiple consecutive newlines reduced to double
        newlines and leading/trailing whitespace stripped.
    """
    # Simple cleanup - more sophisticated markdown parsing could be added
    text = re.sub(r'\n{3,}', '\n\n', text)  # Reduce multiple newlines
    return text.strip()

def format_timestamp(timestamp: float | int | None) -> str:
    """Convert Unix timestamp to readable date/time format.

    Args:
        timestamp: Unix timestamp (integer or float), or None if unavailable.

    Returns:
        Formatted date/time string in 'YYYY-MM-DD HH:MM:SS' format,
        'Unknown time' if timestamp is None, or 'Invalid timestamp' if
        conversion fails.
    """
    if timestamp is None:
        return "Unknown time"
    
    try:
        return datetime.fromtimestamp(int(timestamp)).strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError, OSError):
        return "Invalid timestamp"

def get_message_timestamp(message_item: tuple) -> int:
    """Safely extract timestamp from a message item.

    Designed as a sort key function for ordering conversation mapping items
    by creation time. Returns 0 for any items where the timestamp cannot be
    extracted, ensuring sorting still works without raising exceptions.

    Args:
        message_item: A tuple of (message_id, message_data) from a
            conversation's mapping dictionary. message_data is expected
            to be a dict containing a nested 'message' dict with a
            'create_time' field.

    Returns:
        The integer creation timestamp extracted from the message item,
        or 0 if the timestamp cannot be found or parsed.
    """
    try:
        # Check if message_item is valid
        if not message_item or not isinstance(message_item, tuple) or len(message_item) < 2:
            return 0
            
        # Check if message_data exists and is a dict
        message_data = message_item[1]
        if not message_data or not isinstance(message_data, dict):
            return 0
        
        # Try to get the message object
        message = message_data.get('message')
        if not message or not isinstance(message, dict):
            return 0
        
        # Try to get the create_time
        create_time = message.get('create_time')
        if create_time is None:
            return 0
        
        # Ensure it's a number
        return int(float(create_time)) if create_time else 0
    except Exception:
        # If anything goes wrong, return 0 to allow sorting to continue
        return 0

def get_first_user_message(messages: list[dict]) -> str:
    """Find the first user message in a conversation.

    Args:
        messages: List of message dictionaries, each containing at least
            'role' and 'content' keys.

    Returns:
        The content of the first message with role 'user', truncated to
        200 characters with an ellipsis if longer, or '[No user message
        found]' if no user messages exist.
    """
    for msg in messages:
        if msg.get('role', '').lower() == 'user':
            content = msg.get('content', '')
            # Truncate long messages for preview
            if len(content) > 200:
                return content[:200] + "..."
            return content
    
    return "[No user message found]"

def preview_conversation(convo: dict, index: int) -> str:
    """Create a preview of a conversation for selection.

    Args:
        convo: Conversation dictionary containing 'title', 'create_time',
            and 'messages' keys.
        index: Numeric index of the conversation for display labeling.

    Returns:
        A formatted multi-line preview string showing the conversation
        index, title, creation date, and first user message.
    """
    title = convo.get('title', 'Untitled Conversation')
    date = format_timestamp(convo.get('create_time'))
    first_message = get_first_user_message(convo.get('messages', []))
    
    preview = f"[{index}] {title} ({date})\n"
    preview += f"First message: {first_message}\n"
    
    return preview

def get_valid_number_input(
    prompt: str,
    default_value: int,
    min_value: int = 1,
    max_value: int | None = None,
) -> int:
    """Get a valid number input from the user.

    Repeatedly prompts until a valid integer within the specified range
    is entered, or the user accepts the default by pressing Enter.

    Args:
        prompt: The prompt string to display to the user.
        default_value: The default value returned if the user enters
            an empty string.
        min_value: The minimum allowed value (inclusive).
        max_value: The maximum allowed value (inclusive), or None for
            no upper bound.

    Returns:
        The validated integer input from the user, or the default value
        if no input was provided.
    """
    while True:
        try:
            user_input = input(prompt).strip()
            
            # Use default if empty
            if not user_input:
                return default_value
                
            # Convert to integer
            value = int(user_input)
            
            # Validate range
            if value < min_value:
                print(f"Please enter a number greater than or equal to {min_value}.")
                continue
                
            if max_value is not None and value > max_value:
                print(f"Please enter a number less than or equal to {max_value}.")
                continue
                
            return value
            
        except ValueError:
            print("Please enter a valid number.")

def _extract_export_message(message_data: dict) -> dict | None:
    """Validate a single mapping entry and return a parsed message dict.

    Extracts role, timestamp, and content from a conversation mapping entry,
    applying validation at each level. System messages are excluded.

    Args:
        message_data: A single value from a conversation's mapping dictionary,
            expected to contain a nested 'message' dict with 'author',
            'content', and 'create_time' fields.

    Returns:
        A dict with 'role', 'timestamp', and 'content' keys if the entry
        is valid and contains content, or None if the entry should be skipped
        (invalid structure, system message, or empty content).
    """
    if not isinstance(message_data, dict):
        return None
    message = message_data.get('message')
    if not isinstance(message, dict):
        return None
    author = message.get('author')
    if not isinstance(author, dict):
        return None
    role = author.get('role')
    if role and role.lower() == 'system':
        return None
    content_parts = message.get('content', {}).get('parts', [])
    if not content_parts:
        return None
    content = ' '.join(str(part) for part in content_parts)
    return {
        'role': role or 'unknown',
        'timestamp': message.get('create_time'),
        'content': clean_text(content),
    }


def _parse_mapping_messages(
    sorted_items: list[tuple],
) -> tuple[float | int | None, list[dict]]:
    """Parse all messages from sorted mapping items.

    Iterates over pre-sorted conversation mapping entries, extracts valid
    messages, and tracks the earliest non-None timestamp as the conversation
    creation time.

    Args:
        sorted_items: List of (message_id, message_data) tuples from a
            conversation's mapping dictionary, pre-sorted by timestamp.

    Returns:
        A tuple of (create_time, messages) where create_time is the first
        non-None timestamp encountered (or None if all timestamps are None),
        and messages is a list of parsed message dicts.
    """
    create_time: float | int | None = None
    messages: list[dict] = []
    for _message_id, message_data in sorted_items:
        msg = _extract_export_message(message_data)
        if msg is None:
            continue
        if create_time is None and msg['timestamp']:
            create_time = msg['timestamp']
        messages.append(msg)
    return create_time, messages


def _parse_single_conversation(chat: dict) -> dict | None:
    """Parse one conversation dict into structured form.

    Extracts the title and mapping from a raw conversation object, sorts
    the mapping entries by timestamp, and parses all valid messages.

    Args:
        chat: A single conversation dict from the ChatGPT export JSON,
            expected to contain 'title' and 'mapping' keys.

    Returns:
        A dict with 'title', 'create_time', and 'messages' keys if the
        conversation contains at least one valid message, or None if the
        conversation has no mapping or no valid messages.
    """
    title = chat.get('title', 'Untitled Conversation')
    if 'mapping' not in chat or not isinstance(chat['mapping'], dict):
        return None

    mapping_items = list(chat['mapping'].items())
    try:
        sorted_items = sorted(mapping_items, key=get_message_timestamp)
    except (TypeError, ValueError):
        sorted_items = mapping_items

    create_time, messages = _parse_mapping_messages(sorted_items)
    if not messages:
        return None
    return {
        'title': title,
        'create_time': create_time or 0,
        'messages': messages,
    }


def _load_and_parse_conversations(json_file: str) -> list[dict]:
    """Load a ChatGPT export JSON and parse into structured conversation dicts.

    Args:
        json_file: Path to the ChatGPT conversation history JSON file.

    Returns:
        List of parsed conversation dicts sorted newest-first, each containing
        'title', 'create_time', and 'messages' keys. Empty list on error.
    """
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            chat_history = json.load(f)
    except FileNotFoundError:
        print(f"Error: File '{json_file}' not found.")
        return []
    except json.JSONDecodeError:
        print(f"Error: '{json_file}' is not a valid JSON file.")
        return []

    conversations = []
    for chat in chat_history:
        try:
            result = _parse_single_conversation(chat)
            if result is not None:
                conversations.append(result)
        except Exception as e:
            print(f"Error processing a conversation: {str(e)}")
            continue

    def safe_sort_key(convo: dict) -> int:
        try:
            return int(convo.get('create_time', 0) or 0)
        except (TypeError, ValueError):
            return 0

    conversations.sort(key=safe_sort_key, reverse=True)
    return conversations


def _select_conversations_interactively(
    conversations: list[dict],
    preview_limit: int,
) -> list[dict]:
    """Present conversations to the user for interactive selection.

    Args:
        conversations: Pre-sorted list of conversation dicts.
        preview_limit: Maximum number of conversations to show.

    Returns:
        List of user-selected conversation dicts.
    """
    conversations_to_preview = conversations[:preview_limit]
    selected: list[dict] = []

    print(f"\nSelecting conversations to export (showing {len(conversations_to_preview)} most recent):")
    print("-" * 60)

    for i, convo in enumerate(conversations_to_preview, 1):
        print(preview_conversation(convo, i))
        while True:
            choice = input("Include this conversation? (y/n): ").strip().lower()
            if choice in ('y', 'yes'):
                selected.append(convo)
                print("Added to export.")
                break
            elif choice in ('n', 'no'):
                print("Skipped.")
                break
            else:
                print("Please enter 'y' or 'n'.")
        print("-" * 60)

    return selected


def _write_export_file(conversations: list[dict], output_file: str) -> None:
    """Write selected conversations to a formatted text file.

    Args:
        conversations: List of conversation dicts to export.
        output_file: Destination file path. Parent dirs created automatically.
    """
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("CHATGPT CONVERSATION EXPORT\n")
        f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Contains {len(conversations)} selected conversations\n")
        f.write("=" * 100 + "\n\n")

        for i, convo in enumerate(conversations, 1):
            f.write("\n")
            f.write("+" + "=" * 98 + "+\n")
            f.write(f"|{' CONVERSATION #'+str(i)+': '+convo['title'] :<98}|\n")
            f.write(f"|{' Date: '+format_timestamp(convo['create_time']) :<98}|\n")
            f.write("+" + "=" * 98 + "+\n\n")

            for msg in convo['messages']:
                role_str = msg['role'].upper() if msg['role'] else 'UNKNOWN'
                timestamp_str = format_timestamp(msg['timestamp'])

                if role_str == 'USER':
                    f.write(f">>> USER [{timestamp_str}]:\n")
                    for line in msg['content'].split('\n'):
                        f.write(f"    {line}\n")
                elif role_str == 'ASSISTANT':
                    f.write(f"    CHATGPT [{timestamp_str}]:\n")
                    for line in msg['content'].split('\n'):
                        f.write(f"        {line}\n")
                else:
                    continue
                f.write("\n")

            f.write("\n" + "*" * 100 + "\n\n")


def export_conversations(json_file: str, output_file: str) -> int:
    """Export selected conversations from ChatGPT history.

    Coordinates loading, interactive selection, and writing of conversations.

    Args:
        json_file: Path to the ChatGPT conversation history JSON file.
        output_file: Path to save the formatted text output.

    Returns:
        The number of conversations successfully exported, or 0 on failure.
    """
    print(f"Loading conversation history from {json_file}...")

    conversations = _load_and_parse_conversations(json_file)
    if not conversations:
        print("No conversations found or could be processed.")
        return 0

    total = len(conversations)
    print(f"\nFound {total} conversations in total.")

    preview_limit = get_valid_number_input(
        f"How many recent conversations would you like to preview? (1-{total}) [default: 10]: ",
        10, 1, total,
    )

    selected = _select_conversations_interactively(conversations, preview_limit)
    if not selected:
        print("No conversations were selected for export.")
        return 0

    print(f"\nSelected {len(selected)} out of {min(preview_limit, total)} conversations.")
    print(f"Writing {len(selected)} conversations to {output_file}...")

    _write_export_file(selected, output_file)

    print(f"Export complete! File saved to {output_file}")
    return len(selected)

def print_help() -> None:
    """Print help information about how to use the script.

    Displays usage instructions, argument descriptions, and example
    commands to stdout. Called when the user passes ``-h``, ``--help``,
    or ``help`` as a command-line argument.
    """
    print("ChatGPT Conversation Exporter")
    print("-----------------------------")
    print("Usage: python chat_gpt_export.py [input_file] [output_file]")
    print("")
    print("Arguments:")
    print("  input_file         - Path to the ChatGPT conversation history JSON file")
    print("                       Default: conversations.json")
    print("  output_file        - Path to save the formatted output")
    print("                       Default: chat_exports/recent_conversations.txt")
    print("")
    print("Examples:")
    print("  python chat_gpt_export.py")
    print("  python chat_gpt_export.py ~/Downloads/conversations.json")
    print("  python chat_gpt_export.py conversations.json my_chats.txt")
    print("")

if __name__ == "__main__":
    # Default parameters
    input_file = 'conversations.json'
    output_file = 'chat_exports/recent_conversations.txt'
    
    # Check for help flag first
    if any(arg in ['-h', '--help', 'help'] for arg in sys.argv[1:]):
        print_help()
        sys.exit(0)
    
    # Process the remaining positional arguments
    args = [arg for arg in sys.argv[1:] if not arg.startswith('-')]
    
    if len(args) > 0:
        input_file = args[0]
    
    if len(args) > 1:
        output_file = args[1]
    
    # Export the conversations (always in interactive mode now)
    num_exported = export_conversations(input_file, output_file)
    
    if num_exported > 0:
        print(f"Successfully exported {num_exported} conversations!")
    else:
        print("No conversations were exported. Please check the input file.") 
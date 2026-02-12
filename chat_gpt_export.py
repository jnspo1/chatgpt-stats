"""
This script exports ChatGPT conversations from a conversation history JSON file
into a human-readable text format. It includes the chat title, timestamps, and all messages
from both the user and ChatGPT. The script runs in interactive mode by default,
allowing users to select which conversations to include.
"""

import json
from datetime import datetime
import os
import re
import sys

def clean_text(text):
    """Remove markdown and excessive whitespace from text."""
    # Simple cleanup - more sophisticated markdown parsing could be added
    text = re.sub(r'\n{3,}', '\n\n', text)  # Reduce multiple newlines
    return text.strip()

def format_timestamp(timestamp):
    """
    Convert Unix timestamp to readable date/time format.
    
    Args:
        timestamp: Unix timestamp (integer or float)
        
    Returns:
        str: Formatted date/time string or 'Unknown time' if timestamp is None
    """
    if timestamp is None:
        return "Unknown time"
    
    try:
        return datetime.fromtimestamp(int(timestamp)).strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError, OSError):
        return "Invalid timestamp"

def get_message_timestamp(message_item):
    """
    Safely extract timestamp from a message item.
    Returns 0 if the timestamp can't be found to ensure sorting still works.
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

def get_first_user_message(messages):
    """
    Find the first user message in a conversation.
    
    Args:
        messages: List of message dictionaries
        
    Returns:
        str: The first user message or a default message if none found
    """
    for msg in messages:
        if msg.get('role', '').lower() == 'user':
            content = msg.get('content', '')
            # Truncate long messages for preview
            if len(content) > 200:
                return content[:200] + "..."
            return content
    
    return "[No user message found]"

def preview_conversation(convo, index):
    """
    Create a preview of a conversation for selection.
    
    Args:
        convo: Conversation dictionary
        index: Numeric index of the conversation
        
    Returns:
        str: A formatted preview string
    """
    title = convo.get('title', 'Untitled Conversation')
    date = format_timestamp(convo.get('create_time'))
    first_message = get_first_user_message(convo.get('messages', []))
    
    preview = f"[{index}] {title} ({date})\n"
    preview += f"First message: {first_message}\n"
    
    return preview

def get_valid_number_input(prompt, default_value, min_value=1, max_value=None):
    """
    Get a valid number input from the user.
    
    Args:
        prompt: The prompt to show to the user
        default_value: The default value to use if input is empty
        min_value: The minimum allowed value
        max_value: The maximum allowed value (optional)
        
    Returns:
        int: The validated number input
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

def export_conversations(json_file, output_file):
    """
    Export selected conversations from ChatGPT history.
    
    Args:
        json_file (str): Path to the ChatGPT conversation history JSON file
        output_file (str): Path to save the formatted output
    """
    print(f"Loading conversation history from {json_file}...")
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            chat_history = json.load(f)
    except FileNotFoundError:
        print(f"Error: File '{json_file}' not found.")
        return 0
    except json.JSONDecodeError:
        print(f"Error: '{json_file}' is not a valid JSON file.")
        return 0
    
    # Extract conversations with their timestamps
    conversations = []
    
    for chat in chat_history:
        try:
            # Get chat title
            title = chat.get('title', 'Untitled Conversation')
            
            # Find the create time of the first message to sort by recency
            create_time = None
            messages = []
            
            # Check if mapping exists and is a dictionary
            if 'mapping' not in chat or not isinstance(chat['mapping'], dict):
                continue
            
            # Get all mapping items first, then try to sort them
            mapping_items = list(chat['mapping'].items())
            
            # Sort manually to avoid comparison errors
            try:
                # Try to sort the mapping items
                sorted_items = sorted(mapping_items, key=get_message_timestamp)
            except (TypeError, ValueError):
                # If sorting fails, just use them in the original order
                sorted_items = mapping_items
            
            for message_id, message_data in sorted_items:
                if not message_data:
                    continue
                    
                message = message_data.get('message')
                
                if message:
                    author = message.get('author', {})
                    if author:
                        role = author.get('role')
                        # Skip system messages
                        if role and role.lower() == 'system':
                            continue
                            
                        timestamp = message.get('create_time')
                        
                        # Track the earliest timestamp for sorting
                        if create_time is None and timestamp:
                            create_time = timestamp
                        
                        # Get message content
                        content_parts = message.get('content', {}).get('parts', [])
                        if content_parts:
                            # Ensure all parts are strings
                            content = ' '.join(str(part) for part in content_parts)
                            
                            # Add to messages list
                            messages.append({
                                'role': role or 'unknown',
                                'timestamp': timestamp,  # Keep None if it's None
                                'content': clean_text(content)
                            })
            
            # Only add conversations with messages
            if messages:
                conversations.append({
                    'title': title,
                    'create_time': create_time or 0,  # Use 0 if None for sorting
                    'messages': messages
                })
        except Exception as e:
            print(f"Error processing a conversation: {str(e)}")
            continue
    
    if not conversations:
        print("No conversations found or could be processed.")
        return 0
    
    # Sort conversations by create_time (newest first)
    # Use a custom key function that safely handles None values
    def safe_sort_key(convo):
        try:
            return int(convo.get('create_time', 0) or 0)
        except (TypeError, ValueError):
            return 0
    
    conversations.sort(key=safe_sort_key, reverse=True)
    
    # Ask user how many recent conversations to preview
    total_conversations = len(conversations)
    print(f"\nFound {total_conversations} conversations in total.")
    
    preview_limit = get_valid_number_input(
        f"How many recent conversations would you like to preview? (1-{total_conversations}) [default: 10]: ",
        10,
        1,
        total_conversations
    )
    
    # Interactive selection mode
    conversations_to_preview = conversations[:preview_limit]
    selected_conversations = []
    
    print(f"\nSelecting conversations to export (showing {len(conversations_to_preview)} most recent):")
    print("-" * 60)
    
    for i, convo in enumerate(conversations_to_preview, 1):
        print(preview_conversation(convo, i))
        
        while True:
            choice = input(f"Include this conversation? (y/n): ").strip().lower()
            if choice in ('y', 'yes'):
                selected_conversations.append(convo)
                print("Added to export.")
                break
            elif choice in ('n', 'no'):
                print("Skipped.")
                break
            else:
                print("Please enter 'y' or 'n'.")
        
        print("-" * 60)
    
    if not selected_conversations:
        print("No conversations were selected for export.")
        return 0
    
    print(f"\nSelected {len(selected_conversations)} out of {len(conversations_to_preview)} conversations.")
    
    print(f"Writing {len(selected_conversations)} conversations to {output_file}...")
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # Write formatted conversations to file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"CHATGPT CONVERSATION EXPORT\n")
        f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Contains {len(selected_conversations)} selected conversations\n")
        f.write("=" * 100 + "\n\n")
        
        for i, convo in enumerate(selected_conversations, 1):
            # Write conversation header with more prominent formatting
            f.write("\n")  # Extra line before conversation
            f.write("+" + "=" * 98 + "+\n")
            f.write(f"|{' CONVERSATION #'+str(i)+': '+convo['title'] :<98}|\n")
            f.write(f"|{' Date: '+format_timestamp(convo['create_time']) :<98}|\n")
            f.write("+" + "=" * 98 + "+\n\n")
            
            # Write messages with improved formatting
            for msg in convo['messages']:
                role_str = msg['role'].upper() if msg['role'] else 'UNKNOWN'
                timestamp_str = format_timestamp(msg['timestamp'])
                
                # Different formatting based on role
                if role_str == 'USER':
                    # User messages - less indentation, bold header
                    f.write(f">>> USER [{timestamp_str}]:\n")
                    # Indent user messages 4 spaces
                    content_lines = msg['content'].split('\n')
                    for line in content_lines:
                        f.write(f"    {line}\n")
                elif role_str == 'ASSISTANT':
                    # ChatGPT messages - more indentation
                    f.write(f"    CHATGPT [{timestamp_str}]:\n")
                    # Indent ChatGPT responses 8 spaces for better distinction
                    content_lines = msg['content'].split('\n')
                    for line in content_lines:
                        f.write(f"        {line}\n")
                else:
                    # Skip if system or unknown
                    continue
                
                f.write("\n")  # Add space between messages
            
            # Add more prominent separator between conversations
            f.write("\n" + "*" * 100 + "\n\n")
    
    print(f"Export complete! File saved to {output_file}")
    return len(selected_conversations)

def print_help():
    """Print help information about how to use the script."""
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
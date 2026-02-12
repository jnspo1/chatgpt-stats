import json
import csv
from datetime import datetime
from collections import Counter
import os

# Step 1: Load the JSON File
with open('conversations.json', 'r') as f:
    chat_history = json.load(f)

# Step 2: Create data structures to store information
chat_summaries = []
daily_stats = {}

for chat in chat_history:
    chat_messages = []
    chat_message_count = 0
    chat_start_time = None
    chat_end_time = None
    
    for message_id, message_data in chat['mapping'].items():
        message = message_data.get('message', {})
        
        if message is not None:
            author = message.get('author', {})
            
            if author is not None:
                author_role = author.get('role', None)
                create_time = message.get('create_time', None)

                if author_role == 'user' and create_time is not None:
                    chat_message_count += 1
                    message_datetime = datetime.fromtimestamp(create_time)
                    message_date = message_datetime.date()
                    
                    # Track chat start and end times
                    if chat_start_time is None or message_datetime < chat_start_time:
                        chat_start_time = message_datetime
                    if chat_end_time is None or message_datetime > chat_end_time:
                        chat_end_time = message_datetime
                    
                    # Update daily stats
                    if message_date not in daily_stats:
                        daily_stats[message_date] = {
                            'total_messages': 0,
                            'total_chats': 0,
                            'messages_per_chat': []
                        }
                    daily_stats[message_date]['total_messages'] += 1

    # Only process chats with messages
    if chat_message_count > 0:
        chat_date = chat_start_time.date()
        chat_duration = (chat_end_time - chat_start_time).total_seconds() / 60  # in minutes
        
        # Store chat summary
        chat_summary = {
            'date': chat_date.isoformat(),
            'start_time': chat_start_time.isoformat(),
            'end_time': chat_end_time.isoformat(),
            'message_count': chat_message_count,
            'duration_minutes': round(chat_duration, 2)
        }
        chat_summaries.append(chat_summary)
        
        # Update daily stats
        daily_stats[chat_date]['total_chats'] += 1
        daily_stats[chat_date]['messages_per_chat'].append(chat_message_count)

# Convert daily_stats to a list of records
daily_records = []
for date, stats in daily_stats.items():
    # Check if there are any chats for this day
    if stats['messages_per_chat']:
        avg_messages_per_chat = sum(stats['messages_per_chat']) / len(stats['messages_per_chat'])
    else:
        avg_messages_per_chat = 0  # or you could use None if you prefer
        
    daily_records.append({
        'date': date.isoformat(),
        'total_messages': stats['total_messages'],
        'total_chats': stats['total_chats'],
        'avg_messages_per_chat': round(avg_messages_per_chat, 2),
        'max_messages_in_chat': max(stats['messages_per_chat']) if stats['messages_per_chat'] else 0
    })

# Create output directory if it doesn't exist
output_dir = 'chat_analytics'
os.makedirs(output_dir, exist_ok=True)

# Save chat summaries to JSON
with open(f'{output_dir}/chat_summaries.json', 'w') as f:
    json.dump(chat_summaries, f, indent=2)

# Save daily statistics to JSON
with open(f'{output_dir}/daily_stats.json', 'w') as f:
    json.dump(daily_records, f, indent=2)

# Save chat summaries to CSV
with open(f'{output_dir}/chat_summaries.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['date', 'start_time', 'end_time', 'message_count', 'duration_minutes'])
    writer.writeheader()
    writer.writerows(chat_summaries)

# Save daily statistics to CSV
with open(f'{output_dir}/daily_stats.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['date', 'total_messages', 'total_chats', 'avg_messages_per_chat', 'max_messages_in_chat'])
    writer.writeheader()
    writer.writerows(daily_records)

# Calculate and print summary statistics
total_messages = sum(record['total_messages'] for record in daily_records)
total_chats = len(chat_summaries)

# Find first and last dates
if chat_summaries:
    dates = [datetime.fromisoformat(chat['start_time']) for chat in chat_summaries]
    first_date = min(dates)
    last_date = max(dates)
    years_span = (last_date - first_date).days / 365.25
else:
    first_date = None
    last_date = None
    years_span = 0

# Print summary
print(f"\n{'='*60}")
print(f"ChatGPT Usage Summary")
print(f"{'='*60}")
print(f"Total Messages: {total_messages:,}")
print(f"Total Chats: {total_chats:,}")
if first_date and last_date:
    print(f"First Chat: {first_date.strftime('%Y-%m-%d')}")
    print(f"Last Chat: {last_date.strftime('%Y-%m-%d')}")
    print(f"Time Span: {years_span:.2f} years")
    
# Compute and print the maximum chats/messages in a single day
if daily_records:
    try:
        max_chats_record = max(daily_records, key=lambda r: r.get('total_chats', 0))
        max_messages_record = max(daily_records, key=lambda r: r.get('total_messages', 0))

        print(f"Max Chats in a Day: {max_chats_record.get('total_chats', 0):,} on {max_chats_record.get('date')}")
        print(f"Max Messages in a Day: {max_messages_record.get('total_messages', 0):,} on {max_messages_record.get('date')}")
    except Exception:
        # If something unexpected occurs, don't crash the summary printout
        pass
    
    # Print top 5 days by chats and messages
    try:
        sorted_by_chats = sorted(daily_records, key=lambda r: r.get('total_chats', 0), reverse=True)[:5]
        sorted_by_messages = sorted(daily_records, key=lambda r: r.get('total_messages', 0), reverse=True)[:5]

        print('\nTop 5 Days by Chats:')
        for rec in sorted_by_chats:
            print(f"  {rec.get('date')}: {rec.get('total_chats', 0):,} chats")

        print('\nTop 5 Days by Messages:')
        for rec in sorted_by_messages:
            print(f"  {rec.get('date')}: {rec.get('total_messages', 0):,} messages")
    except Exception:
        pass
print(f"{'='*60}")
print(f"\nAnalytics data has been saved to the '{output_dir}' directory:")
print("1. chat_summaries.json/csv - Contains detailed information about each chat session")
print("2. daily_stats.json/csv - Contains aggregated daily statistics")
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime

# Read the daily stats CSV
df = pd.read_csv('chat_analytics/daily_stats.csv')

# Convert date string to datetime
df['date'] = pd.to_datetime(df['date'])

# Sort by date
df = df.sort_values('date')

# Calculate lifetime averages
lifetime_avg_chats = df['total_chats'].mean()
lifetime_avg_messages_per_chat = df['avg_messages_per_chat'].mean()
lifetime_avg_total_messages = df['total_messages'].mean()

# Calculate cumulative averages
df['cumulative_avg_chats'] = df['total_chats'].expanding().mean()
df['cumulative_avg_messages_per_chat'] = df['avg_messages_per_chat'].expanding().mean()
df['cumulative_avg_total_messages'] = df['total_messages'].expanding().mean()

# Calculate rolling averages for chats
df['chats_7_day_avg'] = df['total_chats'].rolling(window=7, min_periods=1).mean()
df['chats_28_day_avg'] = df['total_chats'].rolling(window=28, min_periods=1).mean()

# Calculate rolling averages for messages
df['messages_7_day_avg'] = df['avg_messages_per_chat'].rolling(window=7, min_periods=1).mean()
df['messages_28_day_avg'] = df['avg_messages_per_chat'].rolling(window=28, min_periods=1).mean()

# Calculate rolling averages for total messages
df['total_messages_7_day_avg'] = df['total_messages'].rolling(window=7, min_periods=1).mean()
df['total_messages_28_day_avg'] = df['total_messages'].rolling(window=28, min_periods=1).mean()

# Create visualization for daily chat frequency
plt.figure(figsize=(15, 8))
plt.bar(df['date'], df['total_chats'], alpha=0.5, color='skyblue', label='Daily Chats')
plt.plot(df['date'], df['chats_7_day_avg'], color='red', linewidth=2, label='7-day Average')
plt.plot(df['date'], df['chats_28_day_avg'], color='green', linewidth=2, label='28-day Average')
plt.plot(df['date'], df['cumulative_avg_chats'], color='purple', linewidth=2, label='Lifetime Average to Date')
plt.title('Daily Chat Frequency with Rolling Averages', fontsize=14, pad=20)
plt.xlabel('Date', fontsize=12)
plt.ylabel('Number of Chats', fontsize=12)
plt.grid(True, alpha=0.3)
plt.legend()
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig('chat_analytics/chat_frequency.png', dpi=300, bbox_inches='tight')
plt.close()

# Create visualization for average conversation length
plt.figure(figsize=(15, 8))
plt.bar(df['date'], df['avg_messages_per_chat'], alpha=0.5, color='lightgreen', label='Daily Average Messages')
plt.plot(df['date'], df['messages_7_day_avg'], color='red', linewidth=2, label='7-day Average')
plt.plot(df['date'], df['messages_28_day_avg'], color='blue', linewidth=2, label='28-day Average')
plt.plot(df['date'], df['cumulative_avg_messages_per_chat'], color='purple', linewidth=2, label='Lifetime Average to Date')
plt.title('Average Messages per Chat with Rolling Averages', fontsize=14, pad=20)
plt.xlabel('Date', fontsize=12)
plt.ylabel('Average Messages per Chat', fontsize=12)
plt.grid(True, alpha=0.3)
plt.legend()
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig('chat_analytics/chat_length.png', dpi=300, bbox_inches='tight')
plt.close()

# Create visualization for total daily messages
plt.figure(figsize=(15, 8))
plt.bar(df['date'], df['total_messages'], alpha=0.5, color='lightcoral', label='Daily Total Messages')
plt.plot(df['date'], df['total_messages_7_day_avg'], color='red', linewidth=2, label='7-day Average')
plt.plot(df['date'], df['total_messages_28_day_avg'], color='blue', linewidth=2, label='28-day Average')
plt.plot(df['date'], df['cumulative_avg_total_messages'], color='purple', linewidth=2, label='Lifetime Average to Date')
plt.title('Total Daily Messages with Rolling Averages', fontsize=14, pad=20)
plt.xlabel('Date', fontsize=12)
plt.ylabel('Number of Messages', fontsize=12)
plt.grid(True, alpha=0.3)
plt.legend()
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig('chat_analytics/total_messages.png', dpi=300, bbox_inches='tight')
plt.close()

print("Visualizations have been saved as 'chat_frequency.png', 'chat_length.png', and 'total_messages.png' in the chat_analytics directory") 
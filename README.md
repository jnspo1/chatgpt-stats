# ChatGPT Statistics & Export Tools

This project contains a collection of Python scripts for analyzing and exporting your ChatGPT conversation history.

## Prerequisites

- Python 3.6+ 
- Required packages:
  - pandas
  - matplotlib
  - seaborn
  - json

## Setup

1. Download your ChatGPT conversation history from [https://chat.openai.com/](https://chat.openai.com/) 
   - Go to Settings > Data Controls > Export Data
   - Wait for the email with your data and download the `.json` file

2. Place the `conversations.json` file in the root directory of this project, or provide the full path when running the scripts.

## Scripts

### 1. `chat_gpt_history.py`

Extracts individual user prompts from your conversation history.

**Features:**
- Can extract entire prompts or just the part before the first semicolon
- Prints each prompt to the console

**Usage:**
```bash
python chat_gpt_history.py [path_to_json]
```

### 2. `chat_gpt_summary.py`

Generates statistical summaries of your ChatGPT usage.

**Features:**
- Analyzes conversation frequency and length
- Calculates daily usage statistics
- Outputs both JSON and CSV files

**Usage:**
```bash
python chat_gpt_summary.py
```

**Outputs:**
- `chat_analytics/chat_summaries.json` - Detailed info about each chat session
- `chat_analytics/chat_summaries.csv` - CSV version of the chat summaries
- `chat_analytics/daily_stats.json` - Aggregated daily statistics
- `chat_analytics/daily_stats.csv` - CSV version of daily statistics

### 3. `chat_gpt_viz.py`

Creates visualizations from the analytics data.

**Features:**
- Generates three visualization charts:
  - Daily chat frequency with rolling averages
  - Average messages per chat over time
  - Total daily messages with trend lines

**Usage:**
```bash
python chat_gpt_viz.py
```

**Outputs:**
- `chat_analytics/chat_frequency.png`
- `chat_analytics/chat_length.png`
- `chat_analytics/total_messages.png`

### 4. `chat_gpt_export.py`

Exports selected ChatGPT conversations in a human-readable format.

**Features:**
- Includes chat titles and timestamps
- Contains both user and ChatGPT messages
- Formats content for easy reading
- Interactive selection process
- Preview of the first user message for each conversation

**Formatting Features:**
- Clear visual separation between conversations using box-style headers
- USER messages preceded by ">>>" for easy identification
- Different indentation levels for USER vs CHATGPT messages
- SYSTEM messages are excluded for cleaner output
- Enhanced visual separators between conversations

**Usage:**
```bash
python chat_gpt_export.py [input_file] [output_file]
```

**Arguments:**
- `input_file` - Path to the ChatGPT conversation history JSON file (default: conversations.json)
- `output_file` - Path to save the formatted output (default: chat_exports/recent_conversations.txt)

**Examples:**
```bash
# Show help information
python chat_gpt_export.py help

# Use default parameters
python chat_gpt_export.py

# Specify input file only
python chat_gpt_export.py ~/Downloads/conversations.json

# Specify both input and output files
python chat_gpt_export.py conversations.json my_chats.txt
```

**Interactive Process:**
The script will:
1. Ask you how many recent conversations you want to preview
2. Display each conversation with:
   - Conversation title and date
   - First user message (truncated if very long)
3. For each conversation, ask you if you want to include it (y/n)
4. Export only the conversations you selected

**Output Format:**
```
+===============================+
| CONVERSATION #1: Title Here   |
| Date: 2023-11-01 12:34:56     |
+===============================+

>>> USER [2023-11-01 12:34:56]:
    User message goes here
    Additional line from user

    CHATGPT [2023-11-01 12:35:20]:
        ChatGPT response with more indentation
        to easily distinguish from user messages
        
        Code or formatted content is preserved
        with consistent indentation

>>> USER [2023-11-01 12:36:45]:
    Next user message

************************************
```

## Example Workflow

1. Place your `conversations.json` file in the project directory
2. Run `python chat_gpt_summary.py` to generate analytics
3. Run `python chat_gpt_viz.py` to create visualizations
4. Run `python chat_gpt_export.py` to interactively export selected conversations

## Customization

Each script can be modified to adjust:
- The number of conversations to export
- Date ranges for analysis
- Visualization styles
- Output formats

Look for the main parameters at the top of each script for easy customization. 
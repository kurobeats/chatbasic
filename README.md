# Discord Chat Bot

A Python-based Discord chat bot with memory management using SQLite and OpenRouter AI for LLM responses.

## Features

- **Memory Management**: Retains the last 5 messages in short-term memory
- **Long-term Memory**: Automatically summarizes conversations every 5 messages
- **Configurable**: All settings in `config.json`
- **DM Support**: Responds to direct messages
- **Mention Support**: Responds when mentioned in servers

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure the bot:**
   Edit `config.json` with your settings:
   - `discord_token`: Your Discord bot token from [Discord Developer Portal](https://discord.com/developers/applications)
   - `openrouter_api_key`: Your API key from [OpenRouter](https://openrouter.ai/)
   - `llm_model`: The model to use (e.g., `openai/gpt-3.5-turbo`, `anthropic/claude-3-opus`, etc.)
   - `system_prompt`: The bot's personality/instructions
   - `database_path`: Where to store the SQLite database

3. **Run the bot:**
   ```bash
   python bot.py
   ```

## Commands

- `!help` - Show help information
- `!clear` - Clear your conversation memory
- `!memory` - Show your memory status

## Memory System

The bot uses a two-tier memory system:

1. **Short-term Memory**: Stores the last 5 message exchanges
2. **Long-term Memory**: Every 5 messages, the conversation is summarized and stored

When responding, the bot combines:
- The system prompt
- All long-term memory summaries
- Current short-term messages

This allows the bot to maintain context across longer conversations while keeping token usage manageable.

## Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `bot_name` | Name of your bot | `ChatBot` |
| `discord_token` | Discord bot token | Required |
| `openrouter_api_key` | OpenRouter API key | Required |
| `llm_model` | LLM model identifier | `openai/gpt-3.5-turbo` |
| `system_prompt` | Bot's system prompt | See config.json |
| `database_path` | SQLite database location | `./memory.db` |
| `short_term_memory_limit` | Messages to keep in short-term | `5` |
| `summarize_interval` | Messages before summarizing | `5` |

## Available Models

You can use any model available on OpenRouter. Popular options:
- `openai/gpt-3.5-turbo`
- `openai/gpt-4`
- `anthropic/claude-3-opus`
- `anthropic/claude-3-sonnet`
- `google/gemini-pro`

See [OpenRouter Models](https://openrouter.ai/models) for the full list.

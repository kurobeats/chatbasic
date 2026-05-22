import discord
import json
import aiohttp
import asyncio
from discord.ext import commands
from memory import MemoryManager


class ChatBot(commands.Bot):
    def __init__(self, config: dict):
        # Set up intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )

        self.config = config
        self.bot_name = config.get("bot_name", "ChatBot")
        self.openrouter_key = config["openrouter_api_key"]
        self.llm_model = config.get("llm_model", "openai/gpt-3.5-turbo")
        self.system_prompt = config.get("system_prompt", "You are a helpful assistant.")

        # Initialize memory manager
        self.memory = MemoryManager(
            db_path=config.get("database_path", "./memory.db"),
            short_term_limit=config.get("short_term_memory_limit", 5),
            summarize_interval=config.get("summarize_interval", 5)
        )

        self.session: aiohttp.ClientSession = None

    async def setup_hook(self):
        """Called when the bot is starting up."""
        self.session = aiohttp.ClientSession()
        print(f"{self.bot_name} is starting up...")

    async def close(self):
        """Clean up when bot shuts down."""
        if self.session:
            await self.session.close()
        await super().close()

    async def call_llm(self, messages: list) -> str:
        """Call the OpenRouter API to get a response from the LLM."""
        url = "https://openrouter.ai/api/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.openrouter_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/your-bot",  # Optional, for rankings
            "X-Title": self.bot_name  # Optional, for rankings
        }

        payload = {
            "model": self.llm_model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1000
        }

        try:
            async with self.session.post(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    error_text = await response.text()
                    print(f"API Error: {response.status} - {error_text}")
                    return f"Sorry, I encountered an error: {response.status}"
        except Exception as e:
            print(f"Error calling LLM: {e}")
            return "Sorry, I'm having trouble connecting to my brain right now."

    async def generate_summary(self, conversation: str) -> str:
        """Generate a summary of the conversation using the LLM."""
        summary_prompt = [
            {
                "role": "system",
                "content": "You are a helpful assistant that summarizes conversations concisely. "
                           "Create a brief summary of the key points and context from the conversation."
            },
            {
                "role": "user",
                "content": f"Please summarize this conversation:\n\n{conversation}"
            }
        ]

        return await self.call_llm(summary_prompt)

    async def get_response(self, user_id: str, user_message: str) -> str:
        """Get a response from the LLM with memory context."""
        # Add user message to memory and get current memory state
        short_term, conversation_to_summarize = self.memory.add_message(
            user_id, "user", user_message
        )

        # If we have a conversation to summarize, generate summary and store it
        if conversation_to_summarize:
            summary = await self.generate_summary(conversation_to_summarize)
            # Store the summary in long-term memory
            conn = __import__('sqlite3').connect(self.config.get("database_path", "./memory.db"))
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO long_term_memory (user_id, summary, message_count) VALUES (?, ?, ?)",
                (user_id, summary, 5)
            )
            conn.commit()
            conn.close()

        # Build messages for LLM
        messages = [{"role": "system", "content": self.system_prompt}]

        # Add memory context
        memory_context = self.memory.get_combined_memory(user_id)
        messages.extend(memory_context)

        # If no memory was retrieved, add the current user message
        if not memory_context:
            messages.append({"role": "user", "content": user_message})

        # Get response from LLM
        response = await self.call_llm(messages)

        # Store bot response in memory
        self.memory.add_message(user_id, "assistant", response)

        return response

    async def on_ready(self):
        """Called when the bot is ready."""
        print(f"{self.bot_name} has connected to Discord!")
        print(f"Bot ID: {self.user.id}")
        print(f"Connected to {len(self.guilds)} guild(s)")
        await self.change_presence(activity=discord.Activity(
            type=discord.ActivityType.listening,
            name="your messages | !help"
        ))

    async def on_message(self, message: discord.Message):
        """Handle incoming messages."""
        # Ignore messages from the bot itself
        if message.author == self.user:
            return

        # Process commands
        await self.process_commands(message)

        # Only respond to DMs or when mentioned
        should_respond = False

        if isinstance(message.channel, discord.DMChannel):
            should_respond = True
        elif self.user in message.mentions:
            should_respond = True
            # Remove bot mention from message content
            message.content = message.content.replace(f"@{self.user.name}", "").replace(f"@{self.user.display_name}", "").strip()
            message.content = message.content.replace(f"{self.user.mention}", "").strip()

        if should_respond and message.content:
            async with message.channel.typing():
                user_id = str(message.author.id)
                response = await self.get_response(user_id, message.content)
                await message.reply(response)


# Commands
@commands.command(name="help")
async def help_command(ctx: commands.Context):
    """Show help information."""
    embed = discord.Embed(
        title="Bot Commands",
        description="Here's how to interact with me!",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="Direct Message",
        value="Send me a DM and I'll respond!",
        inline=False
    )
    embed.add_field(
        name="Mention",
        value=f"Mention me (@{ctx.bot.user.name}) in a server and I'll respond!",
        inline=False
    )
    embed.add_field(
        name="!clear",
        value="Clear your conversation memory with me",
        inline=False
    )
    embed.add_field(
        name="!memory",
        value="Show your current memory status",
        inline=False
    )
    await ctx.send(embed=embed)


@commands.command(name="clear")
async def clear_command(ctx: commands.Context):
    """Clear user's memory."""
    user_id = str(ctx.author.id)
    ctx.bot.memory.clear_user_memory(user_id)
    await ctx.send("🗑️ Your conversation memory has been cleared!")


@commands.command(name="memory")
async def memory_command(ctx: commands.Context):
    """Show memory status for the user."""
    user_id = str(ctx.author.id)

    # Get memory stats
    long_term = ctx.bot.memory.get_long_term_memory(user_id)
    short_term = ctx.bot.memory.get_combined_memory(user_id)

    # Count short-term messages (exclude system messages)
    short_count = len([m for m in short_term if m["role"] != "system"])
    long_count = len(long_term)

    embed = discord.Embed(
        title="Memory Status",
        color=discord.Color.green()
    )
    embed.add_field(
        name="Short-term Memory",
        value=f"{short_count} messages",
        inline=True
    )
    embed.add_field(
        name="Long-term Memory",
        value=f"{long_count} summaries",
        inline=True
    )
    embed.add_field(
        name="Next Summary",
        value=f"After {5 - (short_count % 5)} more messages",
        inline=True
    )

    await ctx.send(embed=embed)


def load_config(path: str = "config.json") -> dict:
    """Load configuration from JSON file."""
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: {path} not found!")
        raise
    except json.JSONDecodeError:
        print(f"Error: {path} is not valid JSON!")
        raise


def main():
    # Load configuration
    config = load_config()

    # Validate required fields
    required = ["discord_token", "openrouter_api_key"]
    for field in required:
        if not config.get(field) or config[field] == f"YOUR_{field.upper()}_HERE":
            print(f"Error: Please set your {field} in config.json")
            return

    # Create and run bot
    bot = ChatBot(config)

    # Add commands
    bot.add_command(help_command)
    bot.add_command(clear_command)
    bot.add_command(memory_command)

    try:
        bot.run(config["discord_token"])
    except discord.LoginFailure:
        print("Error: Invalid Discord token!")
    except Exception as e:
        print(f"Error starting bot: {e}")


if __name__ == "__main__":
    main()

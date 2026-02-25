from __future__ import annotations

import os
import time
import discord
from discord.ext import commands
from discord import app_commands
import config
import providers
import db as database

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Required for on_member_join

bot = commands.Bot(command_prefix=config.BOT_PREFIX, intents=intents)

MAX_HISTORY = 20


async def load_cogs():
    """Load cogs from the cogs directory."""
    cogs_dir = os.path.join(os.path.dirname(__file__), "cogs")
    print(f"Loading cogs from: {cogs_dir}")

    for file in os.listdir(cogs_dir):
        if file.endswith(".py") and not file.startswith("__"):
            cog_name = file[:-3]
            ext_name = f"cogs.{cog_name}"
            if ext_name in bot.extensions:
                print(f"↩ Skipping already-loaded cog: {cog_name}")
                continue
            try:
                await bot.load_extension(ext_name)
                print(f"✔ Loaded cog: {cog_name}")
            except Exception as e:
                import traceback
                print(f"✗ Failed to load cog {cog_name}:")
                traceback.print_exc()


async def setup_hook():
    """Called when the bot is setting up."""
    await load_cogs()


bot.setup_hook = setup_hook


# ── Permission check hook ────────────────────────────────────

async def _permission_check(interaction: discord.Interaction) -> bool:
    """Global permission check applied to all slash commands."""
    if not interaction.guild or not interaction.command:
        return True
    from cogs.permissions import check_command_permission
    allowed = await check_command_permission(interaction, interaction.command.name)
    if not allowed:
        await interaction.response.send_message(
            "❌ You don't have the required role to use this command.", ephemeral=True
        )
    return allowed


bot.tree.interaction_check = _permission_check


# ── Core helpers (used by cogs) ──────────────────────────────

async def get_history(channel_id: int) -> list[dict]:
    """Get conversation history for a channel."""
    messages = await database.get_messages(str(channel_id), limit=MAX_HISTORY)
    return [{"role": m["role"], "content": m["content"]} for m in messages]


async def ask_ai(channel_id: int, user_name: str, message: str) -> tuple[str, str]:
    """Send a message to AI and return (response, provider_name)."""
    await database.add_message(str(channel_id), "user", f"{user_name}: {message}")
    history = await get_history(channel_id)

    # Check for channel-specific system prompt
    channel_prompt = await database.get_channel_prompt(str(channel_id))
    system_prompt = channel_prompt if channel_prompt else config.SYSTEM_PROMPT

    # Check for channel-specific provider override
    from cogs.channel_provider import get_channel_provider
    import providers as _providers
    channel_provider = await get_channel_provider(str(channel_id))

    try:
        start = time.time()
        if channel_provider and channel_provider in _providers._clients:
            # Use channel-specific provider
            prov_info = config.PROVIDERS[channel_provider]
            client = _providers._clients[channel_provider]
            import time as _time
            _start = _time.time()
            resp = client.chat.completions.create(
                model=prov_info["model"],
                max_tokens=config.MAX_TOKENS,
                messages=[{"role": "system", "content": system_prompt}, *history],
            )
            response = resp.choices[0].message.content
            provider_name = channel_provider
        else:
            response, provider_name = providers.chat(history, system_prompt)
        latency_ms = int((time.time() - start) * 1000)
        await database.add_message(str(channel_id), "assistant", response, provider=provider_name)
        return response, provider_name
    except RuntimeError as e:
        return f"Sorry, all AI providers failed:\n{e}", "none"


def get_bot_status() -> dict:
    """Return bot status info for the dashboard API."""
    try:
        if bot.user:
            return {
                "online": True,
                "username": str(bot.user),
                "latency_ms": round(bot.latency * 1000, 1) if bot.latency >= 0 else None,
                "guild_count": len(bot.guilds),
                "guilds": [
                    {"id": str(g.id), "name": g.name, "member_count": g.member_count}
                    for g in bot.guilds
                ],
            }
    except Exception as e:
        print(f"Error getting bot status: {e}")
    return {"online": False, "username": None, "latency_ms": None, "guild_count": 0, "guilds": []}


# ── Events ───────────────────────────────────────────────────

@bot.event
async def on_ready():
    await database.init_db()
    await database.sync_env_to_db()

    available = providers.get_available_providers()
    primary = config.AI_PROVIDER
    provider_info = config.PROVIDERS.get(primary, {})

    print(f"SparkSage is online as {bot.user}")
    print(f"Primary provider: {provider_info.get('name', primary)} ({provider_info.get('model', '?')})")
    print(f"Fallback chain: {' -> '.join(available)}")

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s):")
        for cmd in synced:
            print(f"  - /{cmd.name}")
    except Exception as e:
        print(f"Failed to sync commands: {e}")


@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return

    # Respond when mentioned
    if bot.user in message.mentions:
        clean_content = message.content.replace(f"<@{bot.user.id}>", "").strip()
        if not clean_content:
            clean_content = "Hello!"

        from utils.rate_limiter import check_rate_limits
        allowed, error_msg = check_rate_limits(
            str(message.author.id),
            str(message.guild.id) if message.guild else None
        )
        if not allowed:
            await message.reply(error_msg)
            return

        async with message.channel.typing():
            response, provider_name = await ask_ai(
                message.channel.id, message.author.display_name, clean_content
            )

        for i in range(0, len(response), 2000):
            await message.reply(response[i : i + 2000])

    await bot.process_commands(message)


# ── Run ──────────────────────────────────────────────────────

def main():
    if not config.DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN not set.")
        return

    available = providers.get_available_providers()
    if not available:
        print("Error: No AI providers configured.")
        return

    bot.run(config.DISCORD_TOKEN)


if __name__ == "__main__":
    main()
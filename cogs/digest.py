from __future__ import annotations

import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, time, timezone

import config
import providers
import db as database


async def _get_digest_config() -> dict:
    enabled = await database.get_config("DIGEST_ENABLED", "false")
    channel_id = await database.get_config("DIGEST_CHANNEL_ID", "")
    digest_time = await database.get_config("DIGEST_TIME", "09:00")
    return {
        "enabled": enabled.lower() == "true",
        "channel_id": channel_id,
        "digest_time": digest_time,
    }


async def _collect_and_summarize(bot: commands.Bot) -> str | None:
    """Collect recent messages from all channels and summarize with AI."""
    channels = await database.list_channels()
    if not channels:
        return None

    # Gather recent messages from all channels (last 24h worth)
    all_messages = []
    for ch in channels[:10]:  # Limit to 10 most active channels
        msgs = await database.get_messages(ch["channel_id"], limit=10)
        for m in msgs:
            if m["role"] == "user":
                all_messages.append(m["content"])

    if not all_messages:
        return "No messages to summarize yet."

    combined = "\n".join(all_messages[:50])  # Cap at 50 messages
    prompt = f"""Here are recent conversations from a Discord server. 
Please create a brief daily digest summary with:
- Key topics discussed
- Important questions asked
- Notable highlights

Conversations:
{combined}

Keep the summary concise and friendly."""

    try:
        response, _ = providers.chat(
            [{"role": "user", "content": prompt}],
            "You are a helpful assistant that summarizes Discord server activity.",
        )
        return response
    except RuntimeError as e:
        return f"Error generating summary: {e}"


class Digest(commands.Cog):
    """Daily digest scheduler."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.daily_digest.start()

    def cog_unload(self):
        self.daily_digest.cancel()

    @tasks.loop(minutes=1)
    async def daily_digest(self):
        """Check every minute if it's time to send the digest."""
        cfg = await _get_digest_config()
        if not cfg["enabled"] or not cfg["channel_id"]:
            return

        # Check if current UTC time matches digest time
        now = datetime.now(timezone.utc)
        try:
            h, m = map(int, cfg["digest_time"].split(":"))
        except ValueError:
            return

        if now.hour == h and now.minute == m:
            channel = self.bot.get_channel(int(cfg["channel_id"]))
            if not channel:
                return

            summary = await _collect_and_summarize(self.bot)
            if not summary:
                return

            embed = discord.Embed(
                title=f"📋 Daily Digest — {now.strftime('%B %d, %Y')}",
                description=summary,
                color=discord.Color.blurple(),
            )
            embed.set_footer(text="Powered by SparkSage 🤖 | Daily Digest")
            await channel.send(embed=embed)

    @daily_digest.before_loop
    async def before_digest(self):
        await self.bot.wait_until_ready()

    # ── /digest command group ────────────────────────────────

    digest_group = app_commands.Group(
        name="digest", description="Configure the daily digest"
    )

    @digest_group.command(name="status", description="Show digest configuration")
    @app_commands.default_permissions(manage_guild=True)
    async def digest_status(self, interaction: discord.Interaction):
        cfg = await _get_digest_config()
        channel_str = f"<#{cfg['channel_id']}>" if cfg["channel_id"] else "Not set"

        embed = discord.Embed(title="📋 Daily Digest Configuration", color=discord.Color.blurple())
        embed.add_field(name="Enabled", value="✅ Yes" if cfg["enabled"] else "❌ No", inline=True)
        embed.add_field(name="Channel", value=channel_str, inline=True)
        embed.add_field(name="Time (UTC)", value=cfg["digest_time"], inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @digest_group.command(name="toggle", description="Enable or disable the daily digest")
    @app_commands.default_permissions(manage_guild=True)
    async def digest_toggle(self, interaction: discord.Interaction):
        cfg = await _get_digest_config()
        new_state = not cfg["enabled"]
        await database.set_config("DIGEST_ENABLED", str(new_state).lower())
        state_str = "✅ enabled" if new_state else "❌ disabled"
        await interaction.response.send_message(f"Daily digest is now {state_str}.")

    @digest_group.command(name="channel", description="Set the channel for daily digest posts")
    @app_commands.describe(channel="Channel to post the daily digest in")
    @app_commands.default_permissions(manage_guild=True)
    async def digest_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        await database.set_config("DIGEST_CHANNEL_ID", str(channel.id))
        await interaction.response.send_message(f"✅ Digest channel set to {channel.mention}.")

    @digest_group.command(name="time", description="Set the daily digest time (UTC)")
    @app_commands.describe(time="Time in HH:MM format (UTC), e.g. 09:00")
    @app_commands.default_permissions(manage_guild=True)
    async def digest_time(self, interaction: discord.Interaction, time: str):
        # Validate format
        try:
            h, m = map(int, time.split(":"))
            assert 0 <= h <= 23 and 0 <= m <= 59
        except (ValueError, AssertionError):
            await interaction.response.send_message(
                "❌ Invalid time format. Use HH:MM (e.g. `09:00`).", ephemeral=True
            )
            return
        await database.set_config("DIGEST_TIME", time)
        await interaction.response.send_message(f"✅ Digest time set to **{time} UTC**.")

    @digest_group.command(name="preview", description="Send a test digest right now")
    @app_commands.default_permissions(manage_guild=True)
    async def digest_preview(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        summary = await _collect_and_summarize(self.bot)
        if not summary:
            await interaction.followup.send(
                "❌ No conversation data to summarize yet.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="📋 Daily Digest Preview",
            description=summary,
            color=discord.Color.blurple(),
        )
        embed.set_footer(text="This is a preview — Powered by SparkSage 🤖")
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Digest(bot), override=True)
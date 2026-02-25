from __future__ import annotations

import discord
from discord.ext import commands
from discord import app_commands

import db as database


async def _get_onboarding_config() -> dict:
    enabled = await database.get_config("WELCOME_ENABLED", "true")
    channel_id = await database.get_config("WELCOME_CHANNEL_ID", "")
    message = await database.get_config(
        "WELCOME_MESSAGE",
        "👋 Welcome to **{server}**, {user}! Feel free to ask me anything by mentioning me or using `/ask`.",
    )
    return {
        "enabled": enabled.lower() == "true",
        "channel_id": channel_id,
        "message": message,
    }


class Onboarding(commands.Cog):
    """New member onboarding and welcome flow."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        cfg = await _get_onboarding_config()
        if not cfg["enabled"]:
            return

        welcome_text = cfg["message"].replace("{user}", member.mention).replace(
            "{server}", member.guild.name
        )

        # Try configured welcome channel first
        channel = None
        if cfg["channel_id"]:
            channel = member.guild.get_channel(int(cfg["channel_id"]))

        # Fall back to system channel
        if not channel:
            channel = member.guild.system_channel

        if channel:
            embed = discord.Embed(
                description=welcome_text,
                color=discord.Color.gold(),
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text="Powered by SparkSage 🤖")
            await channel.send(embed=embed)
        else:
            # DM as last resort
            try:
                await member.send(welcome_text)
            except discord.Forbidden:
                pass  # User has DMs disabled

    # ── /onboarding command group ────────────────────────────

    onboarding_group = app_commands.Group(
        name="onboarding", description="Configure the member welcome system"
    )

    @onboarding_group.command(name="status", description="Show current onboarding configuration")
    @app_commands.default_permissions(manage_guild=True)
    async def onboarding_status(self, interaction: discord.Interaction):
        cfg = await _get_onboarding_config()
        channel_id = cfg["channel_id"]
        channel_str = f"<#{channel_id}>" if channel_id else "System channel / DM fallback"

        embed = discord.Embed(title="🎉 Onboarding Configuration", color=discord.Color.gold())
        embed.add_field(name="Enabled", value="✅ Yes" if cfg["enabled"] else "❌ No", inline=True)
        embed.add_field(name="Welcome Channel", value=channel_str, inline=True)
        embed.add_field(name="Message Template", value=f"```{cfg['message']}```", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @onboarding_group.command(name="toggle", description="Enable or disable the welcome message")
    @app_commands.default_permissions(manage_guild=True)
    async def onboarding_toggle(self, interaction: discord.Interaction):
        cfg = await _get_onboarding_config()
        new_state = not cfg["enabled"]
        await database.set_config("WELCOME_ENABLED", str(new_state).lower())
        state_str = "✅ enabled" if new_state else "❌ disabled"
        await interaction.response.send_message(f"Welcome messages are now {state_str}.")

    @onboarding_group.command(name="channel", description="Set the welcome channel")
    @app_commands.describe(channel="The channel to send welcome messages in")
    @app_commands.default_permissions(manage_guild=True)
    async def onboarding_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        await database.set_config("WELCOME_CHANNEL_ID", str(channel.id))
        await interaction.response.send_message(f"✅ Welcome channel set to {channel.mention}.")

    @onboarding_group.command(name="message", description="Set the welcome message template")
    @app_commands.describe(
        message="Template text. Use {user} for the mention and {server} for the server name."
    )
    @app_commands.default_permissions(manage_guild=True)
    async def onboarding_message(self, interaction: discord.Interaction, message: str):
        await database.set_config("WELCOME_MESSAGE", message)
        await interaction.response.send_message(
            f"✅ Welcome message updated:\n> {message}"
        )

    @onboarding_group.command(name="test", description="Send a test welcome message as if you just joined")
    @app_commands.default_permissions(manage_guild=True)
    async def onboarding_test(self, interaction: discord.Interaction):
        cfg = await _get_onboarding_config()
        welcome_text = cfg["message"].replace("{user}", interaction.user.mention).replace(
            "{server}", interaction.guild.name if interaction.guild else "this server"
        )
        embed = discord.Embed(description=f"**[TEST]** {welcome_text}", color=discord.Color.gold())
        embed.set_footer(text="This is a preview — Powered by SparkSage 🤖")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    cog = Onboarding(bot)
    await bot.add_cog(cog, override=True)
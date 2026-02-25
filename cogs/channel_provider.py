from __future__ import annotations

import discord
from discord.ext import commands
from discord import app_commands

import config
import db as database


async def get_channel_provider(channel_id: str) -> str | None:
    """Get the provider override for a channel, if any."""
    return await database.get_config(f"CHANNEL_PROVIDER_{channel_id}")


async def set_channel_provider(channel_id: str, provider_name: str):
    await database.set_config(f"CHANNEL_PROVIDER_{channel_id}", provider_name)


async def delete_channel_provider(channel_id: str):
    db = await database.get_db()
    await db.execute(
        "DELETE FROM config WHERE key = ?",
        (f"CHANNEL_PROVIDER_{channel_id}",),
    )
    await db.commit()


async def list_channel_providers(guild_id: str) -> list[dict]:
    db = await database.get_db()
    cursor = await db.execute(
        "SELECT key, value FROM config WHERE key LIKE 'CHANNEL_PROVIDER_%'"
    )
    rows = await cursor.fetchall()
    return [{"channel_id": r["key"].replace("CHANNEL_PROVIDER_", ""), "provider": r["value"]} for r in rows]


class ChannelProvider(commands.Cog):
    """Per-channel AI provider override."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    provider_group = app_commands.Group(
        name="channel-provider",
        description="Set a specific AI provider for this channel",
    )

    @provider_group.command(name="set", description="Use a specific AI provider in this channel")
    @app_commands.describe(provider="Provider name: gemini, groq, or openrouter")
    @app_commands.choices(provider=[
        app_commands.Choice(name="Google Gemini (free)", value="gemini"),
        app_commands.Choice(name="Groq (free)", value="groq"),
        app_commands.Choice(name="OpenRouter (free)", value="openrouter"),
    ])
    @app_commands.default_permissions(manage_guild=True)
    async def cp_set(self, interaction: discord.Interaction, provider: str):
        if provider not in config.PROVIDERS:
            await interaction.response.send_message(
                f"Unknown provider: `{provider}`", ephemeral=True
            )
            return

        provider_info = config.PROVIDERS[provider]
        if not provider_info.get("api_key"):
            await interaction.response.send_message(
                f"Provider `{provider}` has no API key configured.", ephemeral=True
            )
            return

        await set_channel_provider(str(interaction.channel_id), provider)

        embed = discord.Embed(
            title="Channel Provider Set",
            color=discord.Color.green(),
        )
        embed.add_field(name="Channel", value=interaction.channel.mention, inline=True)
        embed.add_field(name="Provider", value=provider_info.get("name", provider), inline=True)
        embed.add_field(name="Model", value=f"`{provider_info.get('model', '?')}`", inline=True)
        embed.set_footer(text="SparkSage will use this provider for all AI calls in this channel.")
        await interaction.response.send_message(embed=embed)

    @provider_group.command(name="view", description="View the current provider override for this channel")
    async def cp_view(self, interaction: discord.Interaction):
        provider = await get_channel_provider(str(interaction.channel_id))

        if not provider:
            primary = config.AI_PROVIDER
            info = config.PROVIDERS.get(primary, {})
            await interaction.response.send_message(
                f"No override set. Using global provider: **{info.get('name', primary)}**",
                ephemeral=True,
            )
            return

        info = config.PROVIDERS.get(provider, {})
        embed = discord.Embed(title="Channel Provider Override", color=discord.Color.blue())
        embed.add_field(name="Channel", value=interaction.channel.mention, inline=True)
        embed.add_field(name="Provider", value=info.get("name", provider), inline=True)
        embed.add_field(name="Model", value=f"`{info.get('model', '?')}`", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @provider_group.command(name="reset", description="Remove provider override and use the global default")
    @app_commands.default_permissions(manage_guild=True)
    async def cp_reset(self, interaction: discord.Interaction):
        await delete_channel_provider(str(interaction.channel_id))
        primary = config.AI_PROVIDER
        info = config.PROVIDERS.get(primary, {})
        await interaction.response.send_message(
            f"Provider override removed. Back to global: **{info.get('name', primary)}**"
        )

    @provider_group.command(name="list", description="List all channel provider overrides")
    @app_commands.default_permissions(manage_guild=True)
    async def cp_list(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("Must be used in a server.", ephemeral=True)
            return

        overrides = await list_channel_providers(str(interaction.guild_id))
        if not overrides:
            await interaction.response.send_message(
                "No channel provider overrides set.", ephemeral=True
            )
            return

        embed = discord.Embed(title="Channel Provider Overrides", color=discord.Color.blue())
        for o in overrides[:10]:
            info = config.PROVIDERS.get(o["provider"], {})
            embed.add_field(
                name=f"<#{o['channel_id']}>",
                value=f"{info.get('name', o['provider'])} — `{info.get('model', '?')}`",
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ChannelProvider(bot), override=True)
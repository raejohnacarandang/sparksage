from __future__ import annotations

import discord
from discord.ext import commands
from discord import app_commands

import db as database


class ChannelPrompt(commands.Cog):
    """Custom AI personality per channel using system prompts."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    prompt_group = app_commands.Group(
        name="prompt", description="Set a custom AI personality for this channel"
    )

    @prompt_group.command(name="set", description="Set a custom system prompt for this channel")
    @app_commands.describe(
        text="The system prompt - defines how SparkSage behaves in this channel"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def prompt_set(self, interaction: discord.Interaction, text: str):
        await interaction.response.defer()

        if not interaction.guild:
            await interaction.followup.send("Must be used in a server.", ephemeral=True)
            return

        await database.set_channel_prompt(
            str(interaction.channel_id),
            str(interaction.guild_id),
            text,
        )

        embed = discord.Embed(
            title="Channel Prompt Set",
            color=discord.Color.green(),
        )
        embed.add_field(name="Channel", value=interaction.channel.mention, inline=True)
        embed.add_field(name="Prompt", value=f"```{text[:500]}```", inline=False)
        embed.set_footer(text="SparkSage will now use this personality in this channel.")
        await interaction.followup.send(embed=embed)

    @prompt_group.command(name="view", description="View the current system prompt for this channel")
    async def prompt_view(self, interaction: discord.Interaction):
        prompt = await database.get_channel_prompt(str(interaction.channel_id))

        if not prompt:
            import config
            await interaction.response.send_message(
                f"No custom prompt set for this channel.\n"
                f"Using global prompt:\n```{config.SYSTEM_PROMPT[:300]}```",
                ephemeral=True,
            )
            return

        embed = discord.Embed(title="Channel System Prompt", color=discord.Color.blue())
        embed.add_field(name="Channel", value=interaction.channel.mention, inline=True)
        embed.add_field(name="Prompt", value=f"```{prompt[:1000]}```", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @prompt_group.command(name="reset", description="Remove custom prompt and use the global default")
    @app_commands.default_permissions(manage_guild=True)
    async def prompt_reset(self, interaction: discord.Interaction):
        await database.delete_channel_prompt(str(interaction.channel_id))
        await interaction.response.send_message(
            "Channel prompt removed. Using the global system prompt again."
        )

    @prompt_group.command(name="list", description="List all channels with custom prompts")
    @app_commands.default_permissions(manage_guild=True)
    async def prompt_list(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("Must be used in a server.", ephemeral=True)
            return

        prompts = await database.list_channel_prompts(str(interaction.guild_id))

        if not prompts:
            await interaction.response.send_message(
                "No custom channel prompts set.", ephemeral=True
            )
            return

        embed = discord.Embed(title="Custom Channel Prompts", color=discord.Color.blue())
        for p in prompts[:10]:
            embed.add_field(
                name=f"<#{p['channel_id']}>",
                value=f"`{p['system_prompt'][:80]}...`",
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ChannelPrompt(bot), override=True)
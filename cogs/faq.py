from __future__ import annotations

import discord
from discord.ext import commands
from discord import app_commands

import db as database

# Minimum keyword matches required to auto-respond
MIN_KEYWORD_MATCHES = 1


def _score_message(content: str, keywords: list[str]) -> int:
    """Count how many keywords appear in the message content (case-insensitive)."""
    lower = content.lower()
    return sum(1 for kw in keywords if kw.strip().lower() in lower)


class FAQ(commands.Cog):
    """FAQ management and auto-detection."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Cog listener for auto-detection ─────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if not message.guild:
            return
        # Don't trigger on slash commands or bot mentions (handled by bot.py)
        if self.bot.user in message.mentions:
            return

        guild_id = str(message.guild.id)
        faqs = await database.get_faqs(guild_id)
        if not faqs:
            return

        content = message.content
        best_match = None
        best_score = 0

        for faq in faqs:
            keywords = faq["match_keywords"].split(",")
            score = _score_message(content, keywords)
            if score >= MIN_KEYWORD_MATCHES and score > best_score:
                best_score = score
                best_match = faq

        if best_match:
            await database.increment_faq_usage(best_match["id"])
            embed = discord.Embed(
                title="📋 FAQ Match",
                description=best_match["answer"],
                color=discord.Color.blue(),
            )
            embed.set_footer(text=f"Q: {best_match['question']}")
            await message.reply(embed=embed, mention_author=False)

    # ── /faq group ───────────────────────────────────────────

    faq_group = app_commands.Group(name="faq", description="Manage FAQ entries for this server")

    @faq_group.command(name="add", description="Add a new FAQ entry")
    @app_commands.describe(
        question="The question this FAQ answers",
        answer="The answer to show",
        keywords="Comma-separated trigger keywords (e.g. price,cost,fee)",
    )
    @app_commands.default_permissions(manage_guild=True)
    async def faq_add(
        self,
        interaction: discord.Interaction,
        question: str,
        answer: str,
        keywords: str,
    ):
        
        await interaction.response.defer()

        if not interaction.guild:
            await interaction.followup.send("This command must be used in a server.", ephemeral=True)
            return

        try:
            faq_id = await database.add_faq(
                guild_id=str(interaction.guild_id),
                question=question,
                answer=answer,
                keywords=keywords,
                created_by=str(interaction.user.id),
            )
        except Exception as e:
            print(f"FAQ ADD ERROR: {e}")
            await interaction.followup.send(f"Error: {e}", ephemeral=True)
            return

        embed = discord.Embed(title="FAQ Added", color=discord.Color.green())
        embed.add_field(name="ID", value=f"`{faq_id}`", inline=True)
        embed.add_field(name="Question", value=question, inline=False)
        embed.add_field(name="Keywords", value=f"`{keywords}`", inline=False)
        await interaction.followup.send(embed=embed)

    @faq_group.command(name="list", description="List all FAQ entries for this server")
    async def faq_list(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
            return

        faqs = await database.get_faqs(str(interaction.guild_id))
        if not faqs:
            await interaction.response.send_message("No FAQs configured yet. Use `/faq add` to create one.")
            return

        embed = discord.Embed(title="📋 FAQ Entries", color=discord.Color.blue())
        for faq in faqs[:25]:  # Discord embed limit
            embed.add_field(
                name=f"[{faq['id']}] {faq['question'][:50]}",
                value=f"Keywords: `{faq['match_keywords']}` | Used: {faq['times_used']}x",
                inline=False,
            )

        print("SENDING FOLLOWUP...")
        await interaction.followup.send(embed=embed)
        print("DONE!")

    @faq_group.command(name="remove", description="Remove a FAQ entry by ID")
    @app_commands.describe(faq_id="The ID of the FAQ to remove (use /faq list to find it)")
    @app_commands.default_permissions(manage_guild=True)
    async def faq_remove(self, interaction: discord.Interaction, faq_id: int):
        if not interaction.guild:
            await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
            return

        deleted = await database.delete_faq(faq_id, str(interaction.guild_id))
        if deleted:
            await interaction.response.send_message(f"✅ FAQ `{faq_id}` removed.")
        else:
            await interaction.response.send_message(
                f"❌ FAQ `{faq_id}` not found or doesn't belong to this server.", ephemeral=True
            )


async def setup(bot: commands.Bot):
    cog = FAQ(bot)
    await bot.add_cog(cog, override=True)
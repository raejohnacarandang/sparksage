from __future__ import annotations

import random
import discord
from discord.ext import commands
from discord import app_commands
import providers

TRIVIA_PROMPT = """Generate a fun trivia question with 4 multiple choice options (A, B, C, D).
Respond ONLY in this exact format:
QUESTION: <question text>
A: <option>
B: <option>
C: <option>
D: <option>
ANSWER: <A/B/C/D>
EXPLANATION: <brief explanation>"""


class Trivia(commands.Cog):
    """Fun trivia game — community plugin example."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._pending: dict[int, str] = {}  # channel_id -> correct answer

    @app_commands.command(name="trivia", description="Get a random trivia question")
    @app_commands.describe(topic="Optional topic (e.g. science, history, movies)")
    async def trivia(self, interaction: discord.Interaction, topic: str = "general knowledge"):
        await interaction.response.defer()

        prompt = f"Topic: {topic}\n\n{TRIVIA_PROMPT}"
        try:
            response, _ = providers.chat(
                [{"role": "user", "content": prompt}],
                "You are a trivia game host. Always respond in the exact format requested.",
            )
        except RuntimeError as e:
            await interaction.followup.send(f"Failed to generate question: {e}")
            return

        # Parse response
        lines = response.strip().splitlines()
        parsed = {}
        for line in lines:
            if ":" in line:
                key, _, val = line.partition(":")
                parsed[key.strip()] = val.strip()

        question = parsed.get("QUESTION", "Unknown question")
        answer = parsed.get("ANSWER", "A")
        explanation = parsed.get("EXPLANATION", "")

        # Store correct answer for this channel
        self._pending[interaction.channel_id] = answer

        embed = discord.Embed(
            title=f"🎯 Trivia — {topic.title()}",
            description=f"**{question}**",
            color=discord.Color.purple(),
        )
        for opt in ["A", "B", "C", "D"]:
            val = parsed.get(opt, "")
            if val:
                embed.add_field(name=opt, value=val, inline=True)
        embed.set_footer(text="Reply with /trivia-answer A/B/C/D to answer!")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="trivia-answer", description="Answer the current trivia question")
    @app_commands.describe(answer="Your answer: A, B, C, or D")
    @app_commands.choices(answer=[
        app_commands.Choice(name="A", value="A"),
        app_commands.Choice(name="B", value="B"),
        app_commands.Choice(name="C", value="C"),
        app_commands.Choice(name="D", value="D"),
    ])
    async def trivia_answer(self, interaction: discord.Interaction, answer: str):
        correct = self._pending.get(interaction.channel_id)
        if not correct:
            await interaction.response.send_message(
                "No active trivia question! Use `/trivia` first.", ephemeral=True
            )
            return

        if answer.upper() == correct.upper():
            await interaction.response.send_message(
                f"✅ **Correct!** Well done, {interaction.user.mention}! The answer was **{correct}**."
            )
        else:
            await interaction.response.send_message(
                f"❌ **Wrong!** The correct answer was **{correct}**. Better luck next time!"
            )

        # Clear pending
        self._pending.pop(interaction.channel_id, None)


async def setup(bot: commands.Bot):
    await bot.add_cog(Trivia(bot), override=True)
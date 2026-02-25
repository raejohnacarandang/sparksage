from __future__ import annotations

import discord
from discord.ext import commands
from discord import app_commands

import db as database


async def check_command_permission(interaction: discord.Interaction, command_name: str) -> bool:
    """
    Returns True if the user can run the command.
    If the command has no role restrictions, everyone can run it.
    If it has restrictions, the user must have at least one of the required roles.
    """
    if not interaction.guild:
        return True  # DMs are always unrestricted

    allowed_roles = await database.get_allowed_roles(command_name, str(interaction.guild_id))
    if not allowed_roles:
        return True  # No restrictions — open to all

    user_role_ids = {str(r.id) for r in interaction.user.roles}
    return bool(user_role_ids & set(allowed_roles))


class Permissions(commands.Cog):
    """Role-based command access control."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    perms_group = app_commands.Group(
        name="permissions",
        description="Manage which roles can use SparkSage commands",
    )

    @perms_group.command(name="set", description="Restrict a command to a specific role")
    @app_commands.describe(
        command_name="The command to restrict (e.g. review, ask)",
        role="The role that is allowed to use this command",
    )
    @app_commands.default_permissions(administrator=True)
    async def perms_set(
        self,
        interaction: discord.Interaction,
        command_name: str,
        role: discord.Role,
    ):
        if not interaction.guild:
            await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
            return

        await database.add_command_permission(command_name, str(interaction.guild_id), str(role.id))
        await interaction.response.send_message(
            f"✅ `/{command_name}` is now restricted to {role.mention}."
        )

    @perms_group.command(name="remove", description="Remove a role restriction from a command")
    @app_commands.describe(
        command_name="The command to update",
        role="The role to remove from the allowed list",
    )
    @app_commands.default_permissions(administrator=True)
    async def perms_remove(
        self,
        interaction: discord.Interaction,
        command_name: str,
        role: discord.Role,
    ):
        if not interaction.guild:
            await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
            return

        removed = await database.remove_command_permission(
            command_name, str(interaction.guild_id), str(role.id)
        )
        if removed:
            await interaction.response.send_message(
                f"✅ Removed {role.mention} from `/{command_name}` restrictions."
            )
        else:
            await interaction.response.send_message(
                f"❌ That restriction wasn't found.", ephemeral=True
            )

    @perms_group.command(name="list", description="Show all command restrictions for this server")
    @app_commands.default_permissions(manage_guild=True)
    async def perms_list(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
            return

        perms = await database.get_command_permissions(str(interaction.guild_id))
        if not perms:
            await interaction.response.send_message(
                "No command restrictions set. All commands are open to everyone."
            )
            return

        # Group by command
        grouped: dict[str, list[str]] = {}
        for p in perms:
            grouped.setdefault(p["command_name"], []).append(p["role_id"])

        embed = discord.Embed(title="🔒 Command Permissions", color=discord.Color.red())
        for cmd, role_ids in grouped.items():
            roles_str = " ".join(f"<@&{rid}>" for rid in role_ids)
            embed.add_field(name=f"/{cmd}", value=roles_str, inline=False)

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    cog = Permissions(bot)
    await bot.add_cog(cog, override=True)
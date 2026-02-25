from __future__ import annotations

import os
import json
import sys
import discord
from discord.ext import commands
from discord import app_commands

PLUGINS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "plugins")


def _get_all_plugins() -> list[dict]:
    """Scan plugins/ directory and return list of plugin manifests."""
    plugins = []
    if not os.path.isdir(PLUGINS_DIR):
        return plugins

    for folder in os.listdir(PLUGINS_DIR):
        folder_path = os.path.join(PLUGINS_DIR, folder)
        manifest_path = os.path.join(folder_path, "manifest.json")
        if os.path.isdir(folder_path) and os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r") as f:
                    manifest = json.load(f)
                manifest["folder"] = folder
                manifest["ext_name"] = f"plugins.{folder}.{manifest['cog'].replace('.py', '')}"
                plugins.append(manifest)
            except (json.JSONDecodeError, KeyError):
                continue
    return plugins


class PluginManager(commands.Cog):
    """Runtime plugin management system."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Ensure plugins dir exists
        os.makedirs(PLUGINS_DIR, exist_ok=True)

    plugin_group = app_commands.Group(
        name="plugin", description="Manage SparkSage community plugins"
    )

    @plugin_group.command(name="list", description="List all available plugins")
    @app_commands.default_permissions(manage_guild=True)
    async def plugin_list(self, interaction: discord.Interaction):
        plugins = _get_all_plugins()

        if not plugins:
            await interaction.response.send_message(
                "No plugins found in the `plugins/` directory.", ephemeral=True
            )
            return

        embed = discord.Embed(title="🧩 Available Plugins", color=discord.Color.teal())
        for p in plugins:
            loaded = p["ext_name"] in self.bot.extensions
            status = "✅ Enabled" if loaded else "⭕ Disabled"
            embed.add_field(
                name=f"{p['name']} v{p.get('version', '?')} — {status}",
                value=f"{p.get('description', 'No description')}\n*by {p.get('author', 'unknown')}*",
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @plugin_group.command(name="enable", description="Enable a plugin by name")
    @app_commands.describe(name="Plugin name (from /plugin list)")
    @app_commands.default_permissions(administrator=True)
    async def plugin_enable(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(ephemeral=True)

        plugins = _get_all_plugins()
        plugin = next((p for p in plugins if p["name"].lower() == name.lower()), None)

        if not plugin:
            await interaction.followup.send(f"❌ Plugin `{name}` not found.", ephemeral=True)
            return

        ext_name = plugin["ext_name"]
        if ext_name in self.bot.extensions:
            await interaction.followup.send(f"⚠️ Plugin `{name}` is already enabled.", ephemeral=True)
            return

        # Add plugin directory to path
        plugin_dir = os.path.join(PLUGINS_DIR, plugin["folder"])
        if plugin_dir not in sys.path:
            sys.path.insert(0, os.path.dirname(plugin_dir))

        try:
            await self.bot.load_extension(ext_name)
            await self.bot.tree.sync()
            await interaction.followup.send(
                f"✅ Plugin `{name}` enabled! New commands are now available.", ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to enable `{name}`: {e}", ephemeral=True)

    @plugin_group.command(name="disable", description="Disable a plugin by name")
    @app_commands.describe(name="Plugin name (from /plugin list)")
    @app_commands.default_permissions(administrator=True)
    async def plugin_disable(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(ephemeral=True)

        plugins = _get_all_plugins()
        plugin = next((p for p in plugins if p["name"].lower() == name.lower()), None)

        if not plugin:
            await interaction.followup.send(f"❌ Plugin `{name}` not found.", ephemeral=True)
            return

        ext_name = plugin["ext_name"]
        if ext_name not in self.bot.extensions:
            await interaction.followup.send(f"⚠️ Plugin `{name}` is not enabled.", ephemeral=True)
            return

        try:
            await self.bot.unload_extension(ext_name)
            await self.bot.tree.sync()
            await interaction.followup.send(
                f"✅ Plugin `{name}` disabled. Commands removed.", ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to disable `{name}`: {e}", ephemeral=True)

    @plugin_group.command(name="info", description="Show details about a plugin")
    @app_commands.describe(name="Plugin name")
    async def plugin_info(self, interaction: discord.Interaction, name: str):
        plugins = _get_all_plugins()
        plugin = next((p for p in plugins if p["name"].lower() == name.lower()), None)

        if not plugin:
            await interaction.response.send_message(f"❌ Plugin `{name}` not found.", ephemeral=True)
            return

        loaded = plugin["ext_name"] in self.bot.extensions
        embed = discord.Embed(
            title=f"🧩 Plugin: {plugin['name']}",
            description=plugin.get("description", "No description"),
            color=discord.Color.green() if loaded else discord.Color.greyple(),
        )
        embed.add_field(name="Version", value=plugin.get("version", "?"), inline=True)
        embed.add_field(name="Author", value=plugin.get("author", "unknown"), inline=True)
        embed.add_field(name="Status", value="✅ Enabled" if loaded else "⭕ Disabled", inline=True)
        embed.add_field(name="Cog File", value=f"`{plugin.get('cog', '?')}`", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(PluginManager(bot), override=True)
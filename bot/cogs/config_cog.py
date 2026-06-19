"""#config — edit configuration. Structured edits are deterministic; free-form
("add a bucket called X") is routed to the agent by the message handler.
"""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from db.repos import config_repo


class ConfigCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    bucket = app_commands.Group(name="bucket", description="Manage content buckets.")
    project = app_commands.Group(name="project", description="Manage projects.")

    @bucket.command(name="add", description="Add a bucket.")
    async def bucket_add(self, interaction: discord.Interaction, name: str, description: str | None = None):
        config_repo.add_bucket(name, description)
        await interaction.response.send_message(f"Added bucket **{name}**.")

    @bucket.command(name="rename", description="Rename a bucket.")
    async def bucket_rename(self, interaction: discord.Interaction, current: str, new: str):
        row = config_repo.get_bucket_by_name(current)
        if not row:
            await interaction.response.send_message(f"No bucket '{current}'.", ephemeral=True)
            return
        config_repo.rename_bucket(row["id"], new)
        await interaction.response.send_message(f"Renamed **{current}** → **{new}**.")

    @bucket.command(name="archive", description="Archive a bucket.")
    async def bucket_archive(self, interaction: discord.Interaction, name: str):
        row = config_repo.get_bucket_by_name(name)
        if not row:
            await interaction.response.send_message(f"No bucket '{name}'.", ephemeral=True)
            return
        config_repo.archive_bucket(row["id"])
        await interaction.response.send_message(f"Archived **{name}**.")

    @project.command(name="add", description="Add a project.")
    async def project_add(self, interaction: discord.Interaction, name: str, description: str | None = None):
        config_repo.add_project(name, description)
        await interaction.response.send_message(f"Added project **{name}**.")

    @app_commands.command(name="checkins", description="Turn schedule check-ins on or off globally.")
    @app_commands.describe(state="on / off")
    async def checkins(self, interaction: discord.Interaction, state: str):
        on = state.strip().lower() in ("on", "true", "yes", "enable", "enabled")
        config_repo.set_setting("checkins_enabled", "true" if on else "false")
        await interaction.response.send_message(
            f"Check-ins {'enabled ✅' if on else 'disabled ⏸️'}."
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ConfigCog(bot))

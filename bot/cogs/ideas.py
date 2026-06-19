"""#ideas — free-form capture + recall via the agent (handoff 5.1, 5.2).

Capture and loose recall are fuzzy turns, so the message handler routes them to
the agent. A couple of structured slash commands exist for exact queries (which
stay deterministic, no model call).
"""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from core.logging_config import get_logger
from db.repos import config_repo, ideas_repo

log = get_logger("bot.cogs.ideas")


class IdeasCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ideas", description="List idea titles for a bucket or project.")
    @app_commands.describe(bucket="Bucket name", project="Project name")
    async def ideas(
        self,
        interaction: discord.Interaction,
        bucket: str | None = None,
        project: str | None = None,
    ) -> None:
        # Deterministic recall — no model call.
        bucket_row = config_repo.get_bucket_by_name(bucket) if bucket else None
        project_row = config_repo.get_project_by_name(project) if project else None
        titles = ideas_repo.list_titles(
            bucket_id=bucket_row["id"] if bucket_row else None,
            project_id=project_row["id"] if project_row else None,
        )
        if not titles:
            await interaction.response.send_message("No ideas found.", ephemeral=True)
            return
        lines = [f"• {t['title']}  _({t['status'] or 'no status'})_" for t in titles]
        header = "**Ideas**"
        if bucket:
            header += f" in {bucket}"
        if project:
            header += f" / {project}"
        await interaction.response.send_message(header + "\n" + "\n".join(lines[:50]))

    @app_commands.command(name="buckets", description="List active content buckets.")
    async def buckets(self, interaction: discord.Interaction) -> None:
        rows = config_repo.list_buckets()
        names = ", ".join(b["name"] for b in rows) or "(none)"
        await interaction.response.send_message(f"Active buckets: {names}", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(IdeasCog(bot))

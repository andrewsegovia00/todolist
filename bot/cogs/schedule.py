"""#schedule — timecard close-out, dead-time, day-off (handoff 5.3–5.6).

Structured slash commands are deterministic (no model call):
  /close  — close out a block instance (timecard)
  /dead   — best use of an N-minute window (lanes 1 & 2 deterministic; lane 3
            develop-an-idea is a fuzzy turn handled by the message router)
  /task   — add a dead-time task
  /dayoff — set a day-off window
  /recap  — weekly analytics on demand
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

import discord
from discord import app_commands
from discord.ext import commands

from core.logging_config import get_logger
from bot.services import analytics
from db.repos import (
    dayoff_repo,
    deadtime_repo,
    ideas_repo,
    people_repo,
    schedule_repo,
)

log = get_logger("bot.cogs.schedule")


class ScheduleCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # --- timecard close-out --------------------------------------------------

    @app_commands.command(name="close", description="Close out a schedule block (timecard).")
    @app_commands.describe(block="Block label", result="done / no", finish="Finish time HH:MM (optional)")
    async def close(
        self,
        interaction: discord.Interaction,
        block: str,
        result: str,
        finish: str | None = None,
    ) -> None:
        blocks = [b for b in schedule_repo.list_blocks() if b["label"].lower() == block.lower()]
        if not blocks:
            await interaction.response.send_message(f"No block named '{block}'.", ephemeral=True)
            return
        completed = result.strip().lower() in ("done", "yes", "y", "complete", "completed")
        person = people_repo.get_by_discord_id(str(interaction.user.id))

        finish_dt = None
        if finish:
            try:
                hh, mm = finish.split(":")
                finish_dt = datetime.combine(date.today(), time(int(hh), int(mm))).astimezone()
            except ValueError:
                await interaction.response.send_message("Finish time must be HH:MM.", ephemeral=True)
                return

        schedule_repo.close_log(
            block_id=blocks[0]["id"],
            on=date.today(),
            completed=completed,
            closed_by=person["id"] if person else None,
            finish_time=finish_dt,
        )
        await interaction.response.send_message(
            f"Logged **{blocks[0]['label']}** as {'completed ✅' if completed else 'not finished ❌'}."
        )

    # --- dead-time -----------------------------------------------------------

    @app_commands.command(name="dead", description="Best use of an N-minute window.")
    @app_commands.describe(minutes="How many minutes you have")
    async def dead(self, interaction: discord.Interaction, minutes: int) -> None:
        # Lanes 1 & 2 are deterministic.
        tasks = deadtime_repo.list_open(max_minutes=minutes)[:5]
        ideas = ideas_repo.actionable_ideas(limit=5)

        lines = [f"**{minutes} minutes — your options:**", ""]
        if tasks:
            lines.append("__Tasks that fit__")
            for t in tasks:
                est = f" (~{t['duration_est_min']}m)" if t.get("duration_est_min") else ""
                lines.append(f"  • {t['content']}{est}")
        if ideas:
            lines.append("")
            lines.append("__Ideas to act on__")
            for i in ideas:
                lines.append(f"  • {i['title']}")
        lines.append("")
        lines.append(
            "_To develop one of these, just say e.g. \"develop the [title] idea\" here — "
            "I'll brainstorm it with you and save it back._"
        )
        if not tasks and not ideas:
            lines = ["Nothing queued that fits. Add one with `/task`."]
        await interaction.response.send_message("\n".join(lines))

    @app_commands.command(name="task", description="Add a dead-time task.")
    @app_commands.describe(
        content="What needs doing",
        minutes="Estimated minutes (optional)",
        priority="Priority, higher = sooner (optional)",
    )
    async def task(
        self,
        interaction: discord.Interaction,
        content: str,
        minutes: int | None = None,
        priority: int = 0,
    ) -> None:
        deadtime_repo.add_task(content=content, priority=priority, duration_est_min=minutes)
        await interaction.response.send_message(f"Added dead-time task: {content}", ephemeral=True)

    @app_commands.command(name="done", description="Mark a dead-time task done by its text.")
    @app_commands.describe(content="Task text (or part of it)")
    async def done(self, interaction: discord.Interaction, content: str) -> None:
        matches = [
            t for t in deadtime_repo.list_open() if content.lower() in t["content"].lower()
        ]
        if not matches:
            await interaction.response.send_message("No matching open task.", ephemeral=True)
            return
        deadtime_repo.complete_task(matches[0]["id"])
        await interaction.response.send_message(f"Done: {matches[0]['content']}", ephemeral=True)

    # --- day-off -------------------------------------------------------------

    @app_commands.command(name="dayoff", description="Mark a day off (excluded from analytics).")
    @app_commands.describe(day="YYYY-MM-DD (default today)", reason="Optional reason")
    async def dayoff(
        self, interaction: discord.Interaction, day: str | None = None, reason: str | None = None
    ) -> None:
        try:
            target = date.fromisoformat(day) if day else date.today()
        except ValueError:
            await interaction.response.send_message("Date must be YYYY-MM-DD.", ephemeral=True)
            return
        start = datetime.combine(target, time.min).astimezone()
        end = datetime.combine(target, time.max).astimezone()
        dayoff_repo.add_day_off(start, end, reason=reason)
        await interaction.response.send_message(
            f"🌴 {target:%A %b %d} marked off — check-ins paused and excluded from analytics."
        )

    # --- analytics -----------------------------------------------------------

    @app_commands.command(name="recap", description="Weekly schedule recap.")
    async def recap(self, interaction: discord.Interaction) -> None:
        recap = analytics.compute_weekly_recap(date.today() - timedelta(days=7))
        await interaction.response.send_message(analytics.format_recap(recap))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ScheduleCog(bot))

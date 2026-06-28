"""/help — list every command with a breakdown, grouped by channel.

This is a deterministic command (no model call). Keep it in sync with the cogs.
"""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands


def build_help_embed() -> discord.Embed:
    embed = discord.Embed(
        title="Command Hub — commands",
        description=(
            "Type `/` in any channel to see commands inline. Free-form messages in "
            "**#ideas**, **#schedule**, and **#config** are read by the agent; the "
            "slash commands below are exact and never use the model."
        ),
        color=0x2B2D31,
    )

    embed.add_field(
        name="💡 #ideas — capture & recall",
        value=(
            "`/ideas [bucket] [project]` — list idea **titles** (filter optional)\n"
            "`/buckets` — list active content buckets\n"
            "_Free-form:_ drop an idea in plain text → it drafts a title, asks the "
            "bucket + optional project, and files it. Ask “show me Market ideas” or "
            "“tell me about <title>” to recall."
        ),
        inline=False,
    )

    embed.add_field(
        name="🗓️ #schedule — timecard, dead-time, days off",
        value=(
            "`/close <block> <done|no> [HH:MM]` — close out a block (timecard). "
            "`done`/`no` = did you finish; optional finish time if you forgot.\n"
            "`/dead <minutes>` — best use of an N-min window (tasks + ideas to act on)\n"
            "`/task <content> [minutes] [priority]` — add a dead-time task\n"
            "`/done <text>` — mark a dead-time task done\n"
            "`/dayoff [YYYY-MM-DD] [reason]` — mark a day off (default today)\n"
            "`/recap` — weekly schedule analytics\n"
            "_Free-form:_ “develop the <title> idea” → brainstorm + save back to notes."
        ),
        inline=False,
    )

    embed.add_field(
        name="⚙️ #config — edit configuration",
        value=(
            "`/bucket add <name> [description]` · `/bucket rename <current> <new>` · "
            "`/bucket archive <name>`\n"
            "`/project add <name> [description]`\n"
            "`/checkins <on|off>` — global schedule check-in switch\n"
            "_Free-form:_ “add a bucket called X”, “turn check-ins off”, etc."
        ),
        inline=False,
    )

    embed.add_field(
        name="ℹ️ What the toggles actually do",
        value=(
            "**`/checkins off`** — turns off **all** schedule check-ins globally "
            "(no start reminders, no close-out prompts, no nightly nudge) until you "
            "`/checkins on`. Use it for a stretch of off-script days.\n"
            "**`/dayoff`** — marks a single day off: check-ins are suppressed **and** "
            "that day is **excluded from analytics**, so it never counts as dead/"
            "mismanaged time (a holiday won't tank your adherence).\n"
            "**Difference:** `/checkins off` = quiet but undated, stays off till you "
            "flip it back; `/dayoff` = one dated day that's also wiped from the stats."
        ),
        inline=False,
    )

    embed.set_footer(text="Reminders & recaps post automatically — no command needed.")
    return embed


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Show all Command Hub commands and what they do.")
    async def help(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(embed=build_help_embed(), ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HelpCog(bot))

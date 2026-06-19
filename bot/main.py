"""Command Hub bot entrypoint.

Run:  python -m bot.main

Boots in this order:
  1. Guardrails (refuse to start if ANTHROPIC_API_KEY is set).
  2. discord.py client with the Message Content intent.
  3. Load cogs (slash commands), start APScheduler.
  4. on_message: deterministic where possible; route fuzzy turns to the agent
     based on the channel's configured mode.
"""
from __future__ import annotations

import discord
from discord.ext import commands

from core.guardrails import run_all as run_guardrails
from core.logging_config import get_logger
from core.settings import settings
from bot import router
from bot.scheduler import HubScheduler

log = get_logger("bot.main")

INTENTS = discord.Intents.default()
INTENTS.message_content = True  # REQUIRED — enable in the Developer Portal too.
INTENTS.members = True

# Modes whose free-form messages should be sent to the agent.
AGENT_MODES = {"ideas", "schedule", "config", "briefing"}


class CommandHubBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix="!", intents=INTENTS)
        self.scheduler: HubScheduler | None = None

    async def setup_hook(self) -> None:
        for ext in ("bot.cogs.ideas", "bot.cogs.schedule", "bot.cogs.config_cog"):
            await self.load_extension(ext)
        # Sync slash commands — to one guild if configured (instant), else global.
        if settings.discord_guild_id:
            guild = discord.Object(id=int(settings.discord_guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()
        log.info("Cogs loaded and slash commands synced.")

    async def on_ready(self) -> None:
        log.info("Logged in as %s (id=%s).", self.user, self.user.id if self.user else "?")
        if self.scheduler is None:
            self.scheduler = HubScheduler(self)
            self.scheduler.start()

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        # Let prefix commands (if any) process first.
        await self.process_commands(message)

        mode = router.mode_for_channel(str(message.channel.id))
        if mode not in AGENT_MODES:
            return
        content = message.content.strip()
        if not content:
            return

        async with message.channel.typing():
            try:
                reply = await router.handle_fuzzy_turn(
                    channel_id=str(message.channel.id),
                    mode=mode,
                    user_message=content,
                    actor=str(message.author.id),
                )
            except Exception:
                log.exception("Agent turn failed")
                reply = "(agent error — see logs)"
        # Discord hard-limits messages to 2000 chars.
        await _send_chunked(message.channel, reply)


async def _send_chunked(channel: discord.abc.Messageable, text: str, limit: int = 1990) -> None:
    if not text:
        return
    for i in range(0, len(text), limit):
        await channel.send(text[i : i + limit])


def main() -> None:
    run_guardrails()
    settings.require("discord_bot_token")
    bot = CommandHubBot()
    bot.run(settings.discord_bot_token, log_handler=None)


if __name__ == "__main__":
    main()

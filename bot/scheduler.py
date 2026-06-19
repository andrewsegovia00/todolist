"""APScheduler jobs — the deterministic proactive layer (handoff 5.3, 5.6).

All of this is plain Python + Supabase, NO model calls (guardrail #7):
  - start-of-block reminders (templated)
  - end-of-block close-out prompts (the timecard)
  - unclosed-block handling + nightly backfill nudge
  - daily briefing + weekly recap

Reminders are templated. The agent is only invoked for the dead-time "develop"
lane and free-form capture/recall, which live in the cogs, not here.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from core.logging_config import get_logger
from core.settings import settings
from bot.services import analytics
from db.repos import config_repo, dayoff_repo, schedule_repo

log = get_logger("bot.scheduler")


class HubScheduler:
    """Owns the APScheduler instance and the proactive jobs."""

    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.tz = ZoneInfo(settings.timezone)
        self.scheduler = AsyncIOScheduler(timezone=self.tz)
        # Tracks block instances we've already prompted to close, so end-of-block
        # checks don't double-fire: {(block_id, date_iso)}
        self._closeout_due: set[tuple[str, str]] = set()

    # --- lifecycle ----------------------------------------------------------

    def start(self) -> None:
        self._register_jobs()
        self.scheduler.start()
        log.info("Scheduler started (tz=%s).", settings.timezone)

    def _register_jobs(self) -> None:
        # Tick every minute to fire block-boundary events.
        self.scheduler.add_job(self.tick_blocks, "cron", minute="*", id="tick_blocks")

        # Daily briefing.
        self.scheduler.add_job(
            self.post_daily_briefing,
            "cron",
            hour=settings.briefing_time.hour,
            minute=settings.briefing_time.minute,
            id="daily_briefing",
        )
        # Nightly nudge for unclosed/blank blocks.
        self.scheduler.add_job(
            self.nightly_backfill_nudge,
            "cron",
            hour=settings.nightly_nudge_time.hour,
            minute=settings.nightly_nudge_time.minute,
            id="nightly_nudge",
        )
        # Weekly recap.
        self.scheduler.add_job(
            self.post_weekly_recap,
            "cron",
            day_of_week=settings.weekly_recap_dow,
            hour=settings.weekly_recap_time.hour,
            minute=settings.weekly_recap_time.minute,
            id="weekly_recap",
        )

    # --- helpers ------------------------------------------------------------

    def _now(self) -> datetime:
        return datetime.now(self.tz)

    async def _channel(self, mode: str) -> discord.abc.Messageable | None:
        """Resolve the Discord channel for a given mode via channel_config."""
        for cfg in config_repo.list_channel_config():
            if cfg["mode"] == mode:
                chan = self.bot.get_channel(int(cfg["channel_id"]))
                if chan is None:
                    try:
                        chan = await self.bot.fetch_channel(int(cfg["channel_id"]))
                    except discord.DiscordException:
                        chan = None
                return chan
        return None

    async def _post(self, mode: str, content: str) -> None:
        chan = await self._channel(mode)
        if chan is None:
            log.warning("No channel configured for mode=%s; skipping post.", mode)
            return
        await chan.send(content)

    def _instances_today(self) -> list[dict]:
        """Today's block instances with concrete start/end datetimes.

        Handles both one-off blocks (explicit start_at/end_at today) and simple
        recurring weekly blocks (recurring_rule contains today's weekday name).
        """
        today = self._now().date()
        out: list[dict] = []
        for block in schedule_repo.list_blocks():
            start_at, end_at = self._resolve_times(block, today)
            if start_at and end_at:
                out.append({"block": block, "start": start_at, "end": end_at})
        return out

    def _resolve_times(self, block: dict, on: date) -> tuple[datetime | None, datetime | None]:
        rule = (block.get("recurring_rule") or "").strip().lower()
        s_raw, e_raw = block.get("start_at"), block.get("end_at")
        if not s_raw or not e_raw:
            return None, None
        s_dt = _parse_dt(s_raw, self.tz)
        e_dt = _parse_dt(e_raw, self.tz)
        if s_dt is None or e_dt is None:
            return None, None
        if rule:
            # Simple weekly recurrence: project the stored time-of-day onto `on`
            # if the weekday matches the rule (e.g. "mon,wed,fri" or "weekdays").
            weekday = on.strftime("%a").lower()  # mon, tue, ...
            applies = (
                weekday[:3] in rule
                or ("weekday" in rule and on.weekday() < 5)
                or ("daily" in rule)
            )
            if not applies:
                return None, None
            s_dt = datetime.combine(on, s_dt.timetz())
            e_dt = datetime.combine(on, e_dt.timetz())
        else:
            # One-off: only applies on its own date.
            if s_dt.date() != on:
                return None, None
        return s_dt, e_dt

    # --- jobs ---------------------------------------------------------------

    async def tick_blocks(self) -> None:
        """Fire start reminders and end close-out prompts on block boundaries."""
        if not config_repo.checkins_enabled():
            return
        now = self._now()
        today = now.date()

        # Day-off => exclude today's instances from analytics and stay silent.
        if dayoff_repo.is_day_off(today):
            for inst in self._instances_today():
                schedule_repo.exclude_log(inst["block"]["id"], today)
            return

        for inst in self._instances_today():
            block, start, end = inst["block"], inst["start"], inst["end"]
            # Start reminder: within this minute of the start time.
            if _same_minute(now, start):
                schedule_repo.ensure_log(block["id"], today, state="open")
                await self._post(
                    "schedule",
                    f"⏰ Starting now: **{block['label']}**"
                    + (f" — goal: {block['goal']}" if block.get("goal") else ""),
                )
            # End close-out: within this minute of the end time.
            if _same_minute(now, end):
                self._closeout_due.add((block["id"], today.isoformat()))
                await self._post(
                    "schedule",
                    f"✅ Wrapping up **{block['label']}** — did you finish it? "
                    f"Reply `/close {block['label']} done` or `/close {block['label']} no`.",
                )
            # Grace expiry: mark unclosed if still open past the grace window.
            grace_deadline = end + timedelta(minutes=settings.closeout_grace_min)
            if _same_minute(now, grace_deadline):
                logrow = schedule_repo.get_log(block["id"], today)
                if logrow and logrow["state"] == "open":
                    schedule_repo.mark_unclosed(block["id"], today)
                    log.info("Block %s marked unclosed for %s", block["label"], today)

    async def post_daily_briefing(self) -> None:
        now = self._now()
        today = now.date()
        instances = self._instances_today()
        lines = [f"**Daily briefing — {today:%A %b %d}**", ""]
        if dayoff_repo.is_day_off(today):
            lines.append("🌴 Day off — check-ins paused, nothing counts against analytics.")
        elif instances:
            lines.append("Today's blocks:")
            for inst in sorted(instances, key=lambda i: i["start"]):
                b = inst["block"]
                lines.append(
                    f"  • {inst['start']:%H:%M}–{inst['end']:%H:%M}  {b['label']}"
                    + (f" — {b['goal']}" if b.get("goal") else "")
                )
        else:
            lines.append("No scheduled blocks today.")

        from db.repos import deadtime_repo

        tasks = deadtime_repo.list_open()[:3]
        if tasks:
            lines.append("")
            lines.append("Top dead-time priorities:")
            for t in tasks:
                est = f" (~{t['duration_est_min']}m)" if t.get("duration_est_min") else ""
                lines.append(f"  • {t['content']}{est}")

        await self._post("briefing", "\n".join(lines))

    async def nightly_backfill_nudge(self) -> None:
        if not config_repo.checkins_enabled():
            return
        today = self._now().date()
        if dayoff_repo.is_day_off(today):
            return
        pending = [
            row
            for row in schedule_repo.open_logs_before(today)
            if row["state"] in ("open", "unclosed")
        ]
        if not pending:
            return
        labels = ", ".join((p.get("block") or {}).get("label", "?") for p in pending[:6])
        await self._post(
            "schedule",
            f"🌙 You have {len(pending)} unclosed block(s) today ({labels}). "
            "Backfill finish times with `/close`, or open the dashboard. "
            "Anything left blank reads as mismanaged time.",
        )

    async def post_weekly_recap(self) -> None:
        # Recap the week that just ended.
        last_week = self._now().date() - timedelta(days=1)
        recap = analytics.compute_weekly_recap(last_week)
        await self._post("schedule", analytics.format_recap(recap))


# --- module-level datetime helpers ------------------------------------------


def _parse_dt(raw: str, tz: ZoneInfo) -> datetime | None:
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


def _same_minute(a: datetime, b: datetime) -> bool:
    return a.replace(second=0, microsecond=0) == b.replace(second=0, microsecond=0)

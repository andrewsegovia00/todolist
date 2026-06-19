"""Schedule analytics computed from block_logs (handoff 5.6).

Excludes `excluded` instances (day-off). Pure computation over repo data — no
model calls.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from db.repos import schedule_repo


@dataclass
class WeeklyRecap:
    start: date
    end: date
    total: int = 0
    closed: int = 0
    completed: int = 0
    unclosed: int = 0          # mismanaged time
    open_blank: int = 0        # never closed, reads as mismanaged
    excluded: int = 0
    by_category: dict[str, dict] = field(default_factory=dict)

    @property
    def counted(self) -> int:
        """Instances that count toward adherence (everything but excluded)."""
        return self.total - self.excluded

    @property
    def adherence_pct(self) -> float | None:
        if self.counted == 0:
            return None
        return round(100.0 * self.completed / self.counted, 1)

    @property
    def dead_spots(self) -> int:
        """Mismanaged time: unclosed + open/blank, excluding day-off."""
        return self.unclosed + self.open_blank


def week_bounds(reference: date | None = None) -> tuple[date, date]:
    """Monday..Sunday containing the reference date (default: last full week)."""
    ref = reference or date.today()
    monday = ref - timedelta(days=ref.weekday())
    return monday, monday + timedelta(days=6)


def compute_weekly_recap(reference: date | None = None) -> WeeklyRecap:
    start, end = week_bounds(reference)
    logs = schedule_repo.logs_between(start, end)
    recap = WeeklyRecap(start=start, end=end, total=len(logs))

    for log in logs:
        state = log.get("state")
        cat = ((log.get("block") or {}).get("category")) or "Uncategorized"
        bucket = recap.by_category.setdefault(
            cat, {"total": 0, "completed": 0, "dead": 0, "excluded": 0}
        )
        bucket["total"] += 1

        if state == "excluded":
            recap.excluded += 1
            bucket["excluded"] += 1
            continue
        if state == "closed":
            recap.closed += 1
            if log.get("completed"):
                recap.completed += 1
                bucket["completed"] += 1
        elif state == "unclosed":
            recap.unclosed += 1
            bucket["dead"] += 1
        elif state == "open":
            recap.open_blank += 1
            bucket["dead"] += 1

    return recap


def format_recap(recap: WeeklyRecap) -> str:
    """Render a recap as a Discord-friendly message."""
    lines = [
        f"**Weekly recap — {recap.start:%b %d} to {recap.end:%b %d}**",
        "",
        f"Blocks: {recap.total}  ·  counted: {recap.counted}  ·  excluded (day-off): {recap.excluded}",
        f"Completed: {recap.completed}  ·  dead spots (mismanaged): {recap.dead_spots}",
    ]
    adh = recap.adherence_pct
    lines.append(f"Adherence: {adh}%" if adh is not None else "Adherence: n/a (no counted blocks)")
    if recap.by_category:
        lines.append("")
        lines.append("By category:")
        for cat, b in sorted(recap.by_category.items()):
            lines.append(
                f"  • {cat}: {b['completed']}/{b['total']} done, {b['dead']} dead"
            )
    return "\n".join(lines)

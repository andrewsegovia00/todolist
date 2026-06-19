"""The adapter interface every future integration conforms to (architecture 2).

    listen to a source -> normalize the event -> format a notification ->
    post to a target channel

New project = new adapter subclass + one row in the `integrations` table. The
core never needs to know an adapter exists.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator


@dataclass
class IntegrationEvent:
    """A normalized event ready to be formatted and posted."""

    type: str
    summary: str
    payload: dict


class IntegrationAdapter(ABC):
    """Base class for a project integration. Implement in Phase 5 — not now."""

    #: short stable name, matches `integrations.name`
    name: str = "base"

    def __init__(self, config: dict, channel_id: str):
        self.config = config
        self.channel_id = channel_id

    @abstractmethod
    async def listen(self) -> AsyncIterator[IntegrationEvent]:
        """Yield normalized events from the external source (poll or webhook)."""
        raise NotImplementedError

    def format(self, event: IntegrationEvent) -> str:
        """Format an event into a Discord message. Override for custom layout."""
        return f"🔔 {event.summary}"

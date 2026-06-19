"""Minimal, consistent logging setup."""
from __future__ import annotations

import logging

from core.settings import settings

_CONFIGURED = False


def setup_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # discord.py is chatty at INFO; keep it at WARNING unless we're debugging.
    if settings.log_level.upper() != "DEBUG":
        logging.getLogger("discord").setLevel(logging.WARNING)
        logging.getLogger("apscheduler").setLevel(logging.WARNING)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)

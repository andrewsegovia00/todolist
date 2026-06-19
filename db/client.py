"""Supabase client factories.

Two surfaces, two keys (handoff Section 1.3):

- The hub (bot, scheduler, dashboard server-side) holds the ``service_role`` key
  and bypasses RLS. It runs on the trusted device only.
- Any browser/client surface uses the ``anon`` key bound by RLS.

The dashboard here is server-rendered ON the hub, so the browser never receives
a key; the Flask process holds the key server-side. It defaults to service_role
for full admin CRUD, which is appropriate for the trusted hub.
"""
from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client

from core.settings import settings


@lru_cache(maxsize=1)
def get_service_client() -> Client:
    """Service-role client (bypasses RLS). Hub-only."""
    settings.require("supabase_url", "supabase_service_role_key")
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


@lru_cache(maxsize=1)
def get_anon_client() -> Client:
    """Anon client (bound by RLS). For client-style surfaces."""
    settings.require("supabase_url", "supabase_anon_key")
    return create_client(settings.supabase_url, settings.supabase_anon_key)


# The hub's default handle.
def db() -> Client:
    return get_service_client()

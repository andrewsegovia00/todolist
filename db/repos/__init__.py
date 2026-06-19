"""Deterministic data-access repositories.

These are plain Python + Supabase — NO model calls (handoff guardrail #7). The
bot's slash commands, scheduler, dashboard, and the agent's tool layer all read
and write through here so business logic lives in one place.
"""

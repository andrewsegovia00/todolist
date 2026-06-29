"""Registry integrity tests for dashboard.entities (no network).

Importing the module is safe: the Supabase client is created lazily (only when a
list/create function actually runs), so these checks never touch the network.
"""
from __future__ import annotations

from dashboard import entities


def test_registry_nonempty_and_lookup():
    assert entities.all_entities()
    assert entities.get("ideas") is not None
    assert entities.get("does-not-exist") is None


def test_every_entity_has_columns_and_table():
    for e in entities.all_entities():
        assert e.table, f"{e.key} missing table"
        assert e.columns, f"{e.key} has no columns"
        assert e.key and e.label and e.icon


def test_required_fields_subset_of_known():
    for e in entities.all_entities():
        assert set(e.required_fields).issubset(set(e.known_fields)), e.key


def test_importable_entities_have_create_fn():
    for e in entities.all_entities():
        if e.importable and e.import_fields:
            assert e.create_fn is not None, f"{e.key} importable but no create_fn"


def test_coercers_only_for_known_fields():
    for e in entities.all_entities():
        assert set(e.coercers).issubset(set(e.known_fields)), e.key


def test_has_active_matches_columns():
    assert entities.get("projects").has_active is True
    assert entities.get("ideas").has_active is False


def test_events_is_export_only():
    ev = entities.get("events")
    assert ev.deletable is False
    assert ev.importable is False


def test_only_ideas_supports_tags():
    tagged = [e.key for e in entities.all_entities() if e.supports_tags]
    assert tagged == ["ideas"]

-- ============================================================================
-- Command Hub — seed data (handoff Section 0)
-- Idempotent: safe to re-run. People + channel_config are seeded from .env via
-- `python -m db.seed` instead (they need values only known at Phase 0), but
-- placeholders are inserted here so the pipeline is visible.
-- ============================================================================

-- --- Buckets (content accounts) ---------------------------------------------
insert into buckets (name, description) values
  ('The Shop',            'Content account'),
  ('The Market',          'Content account'),
  ('The World of Andrew', 'Content account')
on conflict (name) do nothing;

-- --- Initial projects -------------------------------------------------------
insert into projects (name, description) values
  ('TCG Binders',   'Project'),
  ('Bulk-Card eBay','Project')
on conflict (name) do nothing;

-- --- Content pipeline statuses (ordered) ------------------------------------
insert into statuses (name, sort_order) values
  ('Idea',       1),
  ('Developing', 2),
  ('Scripted',   3),
  ('Producing',  4),
  ('Editing',    5),
  ('Scheduled',  6),
  ('Published',  7)
on conflict (name) do nothing;

-- --- Global settings --------------------------------------------------------
insert into settings (key, value) values
  ('checkins_enabled', 'true')
on conflict (key) do nothing;

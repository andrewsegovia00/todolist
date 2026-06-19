-- ============================================================================
-- Command Hub — Row-Level Security (handoff Section 4, "RLS intent")
--
-- Access scope for v1: everything is SHARED between the two people (both
-- read/write). The hub's service_role key bypasses RLS entirely; these policies
-- govern any client surface using the anon key.
--
-- NOTE: with the anon role and no Supabase Auth wired up yet, "shared between
-- two authenticated people" can't be expressed as a per-user policy. For v1 we
-- enable RLS (so the tables are not open by default) and grant the
-- `authenticated` role full access — i.e. anyone signed in to the project can
-- read/write, which matches "shared between the two people" once both sign in.
-- The anon (signed-out) role gets nothing. When the schedule splits per-person
-- later, scope schedule_blocks/block_logs by person_id here.
-- ============================================================================

do $$
declare
  t text;
  shared_tables text[] := array[
    'people','buckets','projects','statuses','tags','ideas','idea_tags',
    'schedule_blocks','block_logs','dead_time_tasks','settings','day_off',
    'channel_config','integrations','events'
  ];
begin
  foreach t in array shared_tables loop
    execute format('alter table %I enable row level security;', t);

    -- Drop+recreate so this migration is idempotent.
    execute format('drop policy if exists %I on %I;', t || '_authenticated_all', t);
    execute format(
      'create policy %I on %I for all to authenticated using (true) with check (true);',
      t || '_authenticated_all', t
    );
  end loop;
end $$;

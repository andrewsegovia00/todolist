-- ============================================================================
-- Command Hub — initial schema (handoff Section 4)
-- Postgres / Supabase. timestamptz throughout.
-- Run in the Supabase SQL editor, or via `supabase db push` if using the CLI.
-- ============================================================================

-- Helper: keep updated_at fresh on row updates.
create or replace function set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

-- --- People -----------------------------------------------------------------
create table if not exists people (
  id               uuid primary key default gen_random_uuid(),
  discord_user_id  text unique not null,
  name             text not null,
  role             text not null check (role in ('owner', 'partner')),
  created_at       timestamptz not null default now()
);

-- --- Buckets (content accounts) — editable at runtime ----------------------
create table if not exists buckets (
  id           uuid primary key default gen_random_uuid(),
  name         text not null unique,
  description  text,
  active       boolean not null default true,
  created_at   timestamptz not null default now()
);

-- --- Projects — editable ----------------------------------------------------
create table if not exists projects (
  id           uuid primary key default gen_random_uuid(),
  name         text not null unique,
  description  text,
  active       boolean not null default true,
  created_at   timestamptz not null default now()
);

-- --- Statuses (content pipeline) — editable, ordered ------------------------
create table if not exists statuses (
  id          uuid primary key default gen_random_uuid(),
  name        text not null unique,
  sort_order  int not null default 0,
  active      boolean not null default true
);

-- --- Tags -------------------------------------------------------------------
create table if not exists tags (
  id    uuid primary key default gen_random_uuid(),
  name  text not null unique
);

-- --- Ideas ------------------------------------------------------------------
create table if not exists ideas (
  id          uuid primary key default gen_random_uuid(),
  title       text not null,
  notes       text,
  bucket_id   uuid references buckets(id) on delete set null,
  project_id  uuid references projects(id) on delete set null,
  author_id   uuid references people(id) on delete set null,
  status_id   uuid references statuses(id) on delete set null,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create table if not exists idea_tags (
  idea_id  uuid not null references ideas(id) on delete cascade,
  tag_id   uuid not null references tags(id) on delete cascade,
  primary key (idea_id, tag_id)
);

create index if not exists idx_ideas_bucket  on ideas(bucket_id);
create index if not exists idx_ideas_project on ideas(project_id);
create index if not exists idx_ideas_status  on ideas(status_id);

drop trigger if exists trg_ideas_updated_at on ideas;
create trigger trg_ideas_updated_at
  before update on ideas
  for each row execute function set_updated_at();

-- --- Schedule blocks (shared schedule for now) ------------------------------
create table if not exists schedule_blocks (
  id              uuid primary key default gen_random_uuid(),
  label           text not null,
  category        text,
  goal            text,
  start_at        timestamptz,
  end_at          timestamptz,
  recurring_rule  text,            -- iCal RRULE or a simple weekly spec; nullable
  active          boolean not null default true,
  created_at      timestamptz not null default now()
  -- (add person_id later if the schedule splits per-person)
);

-- --- Block logs (the timecard) ----------------------------------------------
-- One row per block-instance per day.
create table if not exists block_logs (
  id           uuid primary key default gen_random_uuid(),
  block_id     uuid not null references schedule_blocks(id) on delete cascade,
  date         date not null,
  state        text not null default 'open'
                 check (state in ('open', 'closed', 'unclosed', 'excluded')),
  finish_time  timestamptz,
  completed    boolean,
  closed_by    uuid references people(id) on delete set null,
  created_at   timestamptz not null default now(),
  unique (block_id, date)
);

create index if not exists idx_block_logs_date on block_logs(date);

-- --- Dead-time tasks --------------------------------------------------------
create table if not exists dead_time_tasks (
  id                uuid primary key default gen_random_uuid(),
  content           text not null,
  priority          int not null default 0,
  category          text,
  duration_est_min  int,
  state             text not null default 'open' check (state in ('open', 'done')),
  created_at        timestamptz not null default now(),
  done_at           timestamptz
);

create index if not exists idx_deadtime_state on dead_time_tasks(state);

-- --- Settings (global toggles) ----------------------------------------------
create table if not exists settings (
  id     uuid primary key default gen_random_uuid(),
  key    text not null unique,
  value  text
);

-- --- Day off (pause windows; exclude blocks from analytics) -----------------
create table if not exists day_off (
  id          uuid primary key default gen_random_uuid(),
  person_id   uuid references people(id) on delete cascade,  -- null = applies to all
  start_at    timestamptz not null,
  end_at      timestamptz not null,
  reason      text,
  created_at  timestamptz not null default now()
);

-- --- Channel routing table --------------------------------------------------
create table if not exists channel_config (
  channel_id        text primary key,           -- discord channel id
  mode              text not null
                      check (mode in ('ideas','schedule','config','briefing','log','project')),
  system_prompt_ref text,
  tools_enabled     text[]                       -- conceptual tool names enabled for the mode
);

-- --- Integrations (future; table + interface only) --------------------------
create table if not exists integrations (
  id          uuid primary key default gen_random_uuid(),
  name        text not null,
  type        text not null,
  config_json jsonb,
  channel_id  text,
  active      boolean not null default false
);

-- --- Events (agent-action audit log -> #agent-log) --------------------------
create table if not exists events (
  id          uuid primary key default gen_random_uuid(),
  type        text not null,
  payload     jsonb,
  actor       text,
  created_at  timestamptz not null default now()
);

create index if not exists idx_events_created on events(created_at desc);

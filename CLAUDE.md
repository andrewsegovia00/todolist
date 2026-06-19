# CLAUDE.md — Command Hub

Working notes for Claude Code across sessions. Read this first. Keep it updated
at each phase boundary (and initialize `claude-mem` for cross-session memory).

## What this is

A personal operating system run through Discord: a **content idea hub**, an
**optimized schedule + timecard**, and a **dead-time task/idea queue**. Discord
is the interface, an always-on hub device is the host, Claude Code (Max
subscription) is the reasoning agent, Supabase is the data store.

Full design lives in `command-hub-handoff.md` (build instructions) and
`command-hub-architecture.md` (rationale). The handoff is the source of truth.

## Hard constraints (do not violate)

1. **$0 extra cost.** Agent runs via Claude Code on the Max subscription, never a
   billed API key. `ANTHROPIC_API_KEY` **must be unset**; `core/guardrails.py`
   fails startup loudly if present. Never add it to `.env`, systemd, launchd, or
   NSSM env.
2. **Secrets in `.env`** (gitignored). `.env.example` has keys, no values.
3. **Supabase free tier + RLS on.** Hub holds `service_role`; client surfaces use
   `anon`.
4. **No imposed visual design** on the dashboard — functional + neutral only.
5. **One feature per Git branch** (per the handoff). NOTE: this remote-session
   workflow pins all work to the assigned `claude/...` branch instead.
6. **Multi-session build** — keep this file + `claude-mem` current.
7. **Keep the model out of deterministic paths.** Reminders, slash commands,
   exact queries = plain Python + Supabase. Agent only for fuzzy turns
   (free-form capture, loose recall, brainstorming).

## Stack (decided — do not re-litigate)

- Bot/router/scheduler: Python `discord.py` + `APScheduler`.
- Agent: Claude Code headless (`claude -p`, `AGENT_MODE=cli`) or Python Agent SDK
  (`AGENT_MODE=sdk`), subscription-authed.
- DB: Supabase Postgres. `supabase-py` for deterministic CRUD; **Supabase MCP**
  gives the agent DB tools.
- Process mgmt: systemd / launchd / NSSM per hub OS (`deploy/`).

## Repo layout

```
core/         settings, guardrails, logging
db/           client, migrations/, seed.py, migrate.py, repos/ (deterministic CRUD)
agent/        runner (claude -p / SDK), prompts per mode, mcp_config.example.json
bot/          main.py (entrypoint), router.py, scheduler.py, cogs/, services/
dashboard/    Flask admin (templates/, static/), delete-confirm modal
integrations/ adapter interface only (Phase 5 — DO NOT build adapters now)
scripts/      check_env, check_supabase, check_claude (Phase-0 health checks)
deploy/       systemd / launchd / windows
tests/        pure-logic unit tests (no network)
```

## How to run

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # fill in real values
python -m scripts.check_env     # guardrail + config presence
# DB: paste db/migrations/*.sql into Supabase SQL editor (in order), OR:
DATABASE_URL=postgresql://... python -m db.migrate
python -m db.seed               # people + channel routes from .env
python -m scripts.check_supabase
python -m scripts.check_claude  # needs Claude Code logged into Max on the hub
python -m bot.main              # start the bot
python -m dashboard.app         # optional admin dashboard
pytest                          # run unit tests
```

## Current state (2026-06-19)

Full code-side scaffold built across all phases in one pass (remote session,
before any hardware provisioning). **Everything compiles as a structure; nothing
has been run against a live Discord/Supabase yet.** Phase-0 real-world
provisioning (Discord app + bot, Supabase project, Claude Code login on the hub,
capturing both Discord user IDs + the hub OS + partner name) is still TODO and
must be done locally.

### Done (code)
- Phase 0: scaffold, `.gitignore`, `.env.example`, guardrails, health-check
  scripts, deploy units.
- Phase 1: full schema (`0001`), RLS (`0002`), seed (`0003`) + `db.seed` for
  people/channels; deterministic repos for every table.
- Phase 2: channel routing (`bot/router.py`), agent runner + per-mode prompts,
  `#ideas` capture/recall (agent free-form + `/ideas` `/buckets` slash commands).
- Phase 3: `APScheduler` block reminders + close-out, timecard states
  (open/closed/unclosed/excluded), nightly nudge, day-off exclusion, `/dead`
  (lanes 1&2 deterministic; lane 3 develop-idea via agent), `/task /done /close
  /dayoff /recap`.
- Phase 4: weekly recap analytics, daily briefing, `#agent-log` via `events`,
  `#config` editing (slash + free-form), Flask dashboard with full idea CRUD +
  project/tag management + delete-confirm modal.
- Phase 5: integration interface + table only (no adapters, by design).

### TODO / next session
- Provision the real Discord + Supabase + hub (Phase 0 manual steps).
- Run migrations + seed against the real project; set `CHANNEL_*` env (or use
  `#config`) so the scheduler/router can resolve channels.
- Verify `claude -p` + Supabase MCP end-to-end on the hub
  (`agent/mcp_config.json` from the example).
- Smoke-test each phase live; tighten agent prompts against real behavior.
- Schedule blocks ingestion: recurring_rule currently supports a simple weekly
  spec (`mon,wed,fri` / `weekdays` / `daily`) — extend to full RRULE if needed.

## Decisions / notes
- Schedule is **shared** (no `person_id` on blocks yet). Split later by adding
  `person_id` to `schedule_blocks`/`block_logs` and scoping RLS.
- RLS v1 grants the `authenticated` role full access (= "shared between the two
  people" once both sign in); `anon` gets nothing. Hub uses `service_role`.
- Dashboard is server-rendered on the hub, so the browser never holds a key; the
  Flask server uses `service_role` for admin CRUD. Documented in `db/client.py`.
- Phoenix is MST year-round → no DST math.
- Parking lot (do NOT build): local LLM fallback, backup DB seeding, voice
  capture, project integrations.
```

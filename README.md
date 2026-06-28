# Command Hub

A personal operating system run through Discord: a **content idea hub**, an
**optimized schedule + timecard**, and a **dead-time task/idea queue**.

- **Discord** is the interface (a dumb terminal — no logic, no data).
- An **always-on hub device** runs the bot, scheduler, and the reasoning agent.
- **Claude Code** (Max subscription, never a billed API key) is the brain,
  invoked only for fuzzy turns.
- **Supabase** (Postgres) is the single source of truth.

See `command-hub-handoff.md` (build spec) and `command-hub-architecture.md`
(design rationale). Working notes for contributors/agents live in `CLAUDE.md`.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # fill in real values — NEVER commit .env
python -m scripts.check_env   # asserts ANTHROPIC_API_KEY is unset + reports config
```

### Database (Supabase)

Apply the migrations in order, then seed:

```bash
# Either paste db/migrations/*.sql into the Supabase SQL editor (in order),
# or apply over a direct connection:
DATABASE_URL='postgresql://...' python -m db.migrate
python -m db.seed             # seeds people + channel routes from .env
python -m scripts.check_supabase
```

### Agent (subscription-authed)

Claude Code must be installed and **logged into the Max account** on the hub.
Copy the MCP config and fill in your Supabase project ref + access token:

```bash
cp agent/mcp_config.example.json agent/mcp_config.json   # gitignored
python -m scripts.check_claude
```

> **Guardrail:** `ANTHROPIC_API_KEY` must be **unset**, or Claude Code silently
> bills the API. The bot refuses to start if it's present.

### Run

```bash
python -m bot.main            # the Discord bot + scheduler
python -m dashboard.app       # optional admin dashboard (http://127.0.0.1:5000)
pytest                        # unit tests (pure logic, no network)
```

### Run as a service

See `deploy/` — `systemd` (Linux), `launchd` (macOS), NSSM/Task Scheduler
(Windows). Keep `ANTHROPIC_API_KEY` out of the service environment.

## Discord layout

```
SYSTEM      #briefing   (daily digest, agent-posted)
            #config     (edit buckets / projects / settings via chat)
            #agent-log  (audit trail from events)
CONTENT HUB #ideas      (capture + recall)
SCHEDULE    #schedule   (blocks, reminders, timecard, /dead, weekly recap)
PROJECTS    (empty now — added per integration later)
```

Map each channel to a mode in `channel_config` (set `CHANNEL_*` env before
`db.seed`, or add rows at runtime via `#config` / the dashboard).

## Slash commands

| Command | Channel | What |
|---|---|---|
| `/help` | any | List every command and what the toggles do |
| `/ideas [bucket] [project]` | #ideas | List idea titles (deterministic recall) |
| `/buckets` | #ideas | List active buckets |
| `/close <block> <done\|no> [HH:MM]` | #schedule | Close out a block (timecard) |
| `/dead <minutes>` | #schedule | Best use of an N-minute window |
| `/task <content> [minutes] [priority]` | #schedule | Add a dead-time task |
| `/done <text>` | #schedule | Mark a dead-time task done |
| `/dayoff [YYYY-MM-DD] [reason]` | #schedule | Mark a day off (excluded from analytics) |
| `/recap` | #schedule | Weekly schedule recap |
| `/bucket add\|rename\|archive`, `/project add`, `/checkins on\|off` | #config | Edit config |

Free-form messages in `#ideas` / `#schedule` / `#config` are routed to the agent.
```

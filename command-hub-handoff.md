# Command Hub — Build Handoff (for Claude Code)

A personal operating system run through Discord: a content idea hub, an optimized schedule with a timecard, and a dead-time task/idea queue. Discord is the interface, an always-on device is the host, Claude Code (on the Max subscription) is the reasoning agent, and Supabase is the data store. Project notifications (eBay, binders) are deferred but designed to plug in later.

> Companion file: `command-hub-architecture.md` holds the full design rationale. Drop both into the repo root. This handoff is the build instruction; read it top to bottom before writing code.

---

## 0. Setup inputs

These are seeded below. Buckets, projects, and statuses are also **editable at runtime** (via `#config` or the dashboard) — these are just the starting set. Three items are captured during Phase-0 provisioning because they can't be known until then: the machine's **OS**, both **Discord user IDs**, and the partner's **display name**.

- **Buckets (content accounts):** `The Shop`, `The Market`, `The World of Andrew`. *(editable)*
- **Initial projects:** `TCG Binders`, `Bulk-Card eBay`. *(editable)*
- **Content pipeline statuses:** `Idea → Developing → Scripted → Producing → Editing → Scheduled → Published`. *(editable)*
- **Schedule model:** **shared** — one schedule both people follow and both get reminders for; either person can close out a block. (Can split per-person later.)
- **Schedule blocks:** provided at Phase 3 — recurring weekly template + each block's goal.
- **Access scope:** everything shared between the two people (Content, Projects, Schedule). No per-person restriction for now.
- **People:** two — `Andrew` (owner) and the partner. Display name (partner) + both Discord user IDs are filled at Phase 0.
- **Hub device:** the home machine, on 24/7. **OS confirmed at Phase 0** (decides process-management: `systemd` on Linux, `launchd` on macOS, NSSM/Task Scheduler on Windows).

**Provisioning checklist (do in Phase 0):**
- Discord application + bot, with the **Message Content intent enabled**; bot token in `.env`.
- Private Discord server; invite both people + the bot. **Copy both members' Discord user IDs** (enable Developer Mode → right-click → Copy User ID) for the `people` seed.
- Supabase project: project URL, `anon` key, `service_role` key.
- Claude Code installed on the hub and **logged into the Max account**. Verify `ANTHROPIC_API_KEY` is **unset** (see guardrails).
- Confirm the hub's **OS** and pick the matching process manager.

---

## 1. Hard constraints & guardrails — read first

1. **$0 extra cost.** The agent runs through Claude Code authenticated to the Max subscription, never a billed API key. **Never set `ANTHROPIC_API_KEY` in the bot's environment or process** — if it's set, Claude Code silently bills the API. Verify it's unset at startup and fail loudly if present.
2. **Secrets** live in `.env` (gitignored). Commit a `.env.example` with keys, no values. Never commit tokens/keys.
3. **Supabase free tier + Row-Level Security on.** The hub holds the `service_role` key; any browser/dashboard surface uses the `anon` key bound by RLS.
4. **Do not impose a visual design on the dashboard.** Build it functional with minimal, neutral styling and a clean component structure so the owner can restyle it later. No opinionated theme.
5. **One feature per Git branch.** Branch, build until it meets the phase's acceptance criteria, then merge. Don't pile features onto one branch.
6. **Multi-session build.** Initialize `claude-mem` for cross-session memory and keep a `CLAUDE.md` updated with decisions and current state.
7. **Keep Claude out of deterministic paths.** Scheduled reminders, slash commands with structured args, and exact queries are plain Python + Supabase — no model calls. Invoke the agent only for fuzzy turns (free-form capture, loose recall, brainstorming).

---

## 2. Tech stack (decided — do not re-litigate)

- **Bot / router / scheduler:** Python — `discord.py`.
- **Agent / reasoning:** Claude Code (headless `claude -p`) or the Python **Claude Agent SDK**, subscription-authed.
- **Database:** Supabase (Postgres). `supabase-py` for deterministic CRUD; **Supabase MCP** to give the agent DB tools.
- **Scheduler:** `APScheduler` in-process (or `systemd` timers).
- **Process management:** run the bot as a long-lived service that restarts on crash/reboot — `systemd` (Linux), `launchd` (macOS), or NSSM/Task Scheduler (Windows), per the hub's confirmed OS.

---

## 3. Architecture in one breath

Discord is a dumb terminal (interface only). The **hub device** is the control plane: it runs the bot, the scheduler, and the subscription-authed agent. **Supabase** is the data plane (cloud Postgres). The bot routes a message by channel → mode, invokes the agent only when needed, the agent reads/writes Supabase via MCP, and the bot relays the reply back to Discord and logs it.

```
Discord  ──►  Bot (router + scheduler)  ──►  Claude Code (Max sub-auth + Supabase MCP)
                     │                                   │
                     └──────────────► Supabase (Postgres) ◄┘
```

---

## 4. Data model

Postgres. Use `timestamptz` throughout. Apply RLS per the access scope. Generate migrations from this; adapt names as needed but keep the semantics.

- **people** — `id`, `discord_user_id` (unique), `name`, `role` (owner | partner).
- **buckets** — `id`, `name`, `description`, `active` (bool). *(editable at runtime)*
- **projects** — `id`, `name`, `description`, `active`. *(editable)*
- **statuses** — `id`, `name`, `sort_order`, `active`. *(the content pipeline; editable)*
- **tags** — `id`, `name`.
- **ideas** — `id`, `title`, `notes` (text), `bucket_id` (fk), `project_id` (fk, nullable), `author_id` (fk people), `status_id` (fk), `created_at`, `updated_at`.
- **idea_tags** — `idea_id`, `tag_id` (join).
- **schedule_blocks** — `id`, `label`, `category`, `goal`, `start_at`, `end_at`, `recurring_rule` (nullable), `active`. *(shared schedule for now — no per-person scoping; add `person_id` later if split)*
- **block_logs** — `id`, `block_id` (fk), `date`, `state` (open | closed | unclosed | excluded), `finish_time` (nullable), `completed` (bool, nullable), `closed_by` (fk people, nullable), `created_at`. *(the timecard; one row per block-instance per day; `closed_by` records which person closed it)*
- **dead_time_tasks** — `id`, `content`, `priority` (int), `category`, `duration_est_min` (int), `state` (open | done), `created_at`, `done_at`.
- **settings** — `id`, `key`, `value`. *(global toggles, e.g. check-ins on/off)*
- **day_off** — `id`, `person_id` (fk, nullable for all), `start_at`, `end_at`, `reason`. *(pause windows that exclude blocks from analytics)*
- **channel_config** — `channel_id` (discord), `mode` (ideas | schedule | config | briefing | log | project), `system_prompt_ref`, `tools_enabled`. *(the routing table)*
- **integrations** — `id`, `name`, `type`, `config_json`, `channel_id`, `active`. *(future; leave table + interface, no adapters now)*
- **events** — `id`, `type`, `payload` (jsonb), `actor`, `created_at`. *(agent-action audit log → `#agent-log`)*

RLS intent: everything is shared between the two people (both read/write) for now — `ideas`, `dead_time_tasks`, `buckets`, `projects`, `tags`, `schedule_blocks`, `block_logs`. The hub's `service_role` key bypasses RLS; client surfaces use `anon` + policies. (If the schedule is split per-person later, scope `schedule_blocks`/`block_logs` by `person_id`.)

---

## 5. Behaviors — the functional spec

### 5.1 Idea capture (in `#ideas`)
1. User types one or more ideas in free text.
2. **Multi-idea split:** the agent splits only when it detects multiple ideas (blank lines, list markers, clear topic shifts). When it splits, it shows the proposed **titles** and asks the user to confirm the split before filing. A single idea flows straight through.
3. For each idea: agent **drafts a title** → asks **which bucket** (offer the active buckets as choices) → asks for an **optional project** → stores the idea with the original text in `notes`.
4. **Inline fixes:** in the same exchange the user can correct the title, bucket, or project; apply without restarting the flow.

### 5.2 Recall (in `#ideas` or dashboard)
- "Show me [bucket] / [project] ideas" → return a list of **titles** (not full text).
- "Tell me about [title]" → expand that one idea into a summary of its `notes`.

### 5.3 Schedule + timecard (in `#schedule`)
- Ingest the schedule into `schedule_blocks` (+ `recurring_rule` for the weekly template).
- **Start-of-block reminder** (templated, no model call): next block label + goal.
- **End-of-block close-out:** prompt "did you finish it?" → user answers; record `completed` + `finish_time` in `block_logs` (state `closed`).
- **Unclosed handling:** if no answer in time, log the instance `unclosed` and move on (never block the user). At night, nudge once (or point to the admin page) to backfill `finish_time`. If still no response, the instance stays blank and reads as **mismanaged time** in analytics — unless the day is excluded (see 5.4).

### 5.4 Check-in toggle / day-off
- A global switch (`settings`) and/or dated `day_off` windows turn check-ins off for holidays/birthdays/off-script days.
- **Off ≠ silent only. Off = excluded from analytics.** Suppress both the close-out prompts/nudges and the mismanaged-time penalty; mark affected `block_logs` `excluded` so they never count as dead spots.

### 5.5 Dead-time — `/dead N` (three lanes)
"Best use of an N-minute window." Return options drawn from:
1. **Tasks** from `dead_time_tasks` with `duration_est_min ≤ N` (priority-ordered).
2. **Ideas to act on** — actionable content ideas surfaced for the window.
3. **Ideas to develop** — user picks an idea; the agent **brainstorms it with them**, then **writes the result back into `ideas.notes`** and bumps `status` (`Idea → Developing`).
   Note: lane 3 means `/dead` can *write* to an idea, not just read.

### 5.6 Analytics
- Compute from `block_logs`: dead spots in the week, tasks finished under/over their `goal`/estimate, adherence over time. Exclude `excluded` instances.
- Surface proactively — a weekly recap posted to `#schedule` (or `#briefing`).

### 5.7 Dashboard / admin panel
- View all stored ideas; filter by bucket / project / tag.
- Retrieve, **edit**, and **delete** ideas. Delete is gated behind an **"are you sure?" confirmation modal**.
- Add / rename / archive **projects** and **tags**.
- Functional first, neutral styling (see guardrail #4).

### 5.8 Channel routing
- On each message, look up `channel_config` by `channel_id` → resolve `mode` → load that mode's system prompt + enabled tools → invoke the agent (if the turn needs it). Use a **session per conversation** so each channel keeps its own context.

---

## 6. Discord structure

```
SYSTEM      #briefing   (daily digest, agent-posted)
            #config     (edit buckets / statuses / settings via chat)
            #agent-log  (audit trail from events)
CONTENT HUB #ideas      (capture + recall)
SCHEDULE    #schedule   (blocks, reminders, timecard, /dead, weekly recap)
PROJECTS    (empty now — channels added per integration later)
```

---

## 7. Build phases

Aligns with the owner's pipeline (PRD → schema → scaffold → feature-by-feature). Each phase: branch, build to acceptance, merge. Update `CLAUDE.md` + `claude-mem` at each phase boundary.

### Phase 0 — Provisioning & scaffold  · branch `phase-0-scaffold`
- Repo, `.gitignore`, `.env.example`, project layout (`bot/`, `db/`, `agent/`, `dashboard/`).
- Confirm the hub **OS** and choose the process manager; capture both **Discord user IDs** and the partner's display name for the `people` seed.
- Verify Supabase connectivity from Python; verify `claude -p "ping"` returns via subscription; assert `ANTHROPIC_API_KEY` unset.
- Bot connects and shows online in the server.
- **Done when:** bot online, `supabase-py` reads a test row, `claude -p` responds, env-var guard passes, OS + both user IDs recorded.

### Phase 1 — Schema & config  · branch `phase-1-schema`
- Migrations for all Section 4 tables + RLS policies.
- Seed `people`, `buckets`, `projects`, `statuses`, `channel_config` from Section 0.
- **Done when:** tables exist with RLS, seed rows present, a script lists active buckets.

### Phase 2 — Content hub end-to-end  · branch `phase-2-ideas`
- Channel-routing layer; agent invocation wrapper with Supabase MCP tools.
- Capture handshake (5.1), recall (5.2), inline fixes, multi-idea split-with-confirm.
- **Done when:** in `#ideas`, a free-text idea is titled, bucketed, optionally projected, and stored; recall returns titles then a notes summary; corrections work inline.

### Phase 3 — Schedule engine + timecard + dead-time  · branch `phase-3-schedule`
- Schedule ingestion; `APScheduler` start/end events.
- Close-out flow + `block_logs` states; unclosed handling + nightly backfill nudge (5.3).
- Day-off toggle + analytics exclusion (5.4).
- `/dead N` all three lanes, including brainstorm writeback (5.5).
- **Done when:** reminders fire on block boundaries; blocks close out and persist; an ignored close-out logs `unclosed` and nudges at night; a day-off excludes its blocks; `/dead 20` returns fitting tasks/ideas and can develop an idea back into its notes.

### Phase 3.5 — Proactive dead-time (optional)  · branch `phase-3-5-proactive`
- Conservative idle-time pings (only clearly-free windows, dismissible). Add once schedule data is trusted.

### Phase 4 — Analytics, dashboard, briefing  · branch `phase-4-dashboard`
- Weekly recap (5.6); `#briefing`; `#agent-log` from `events`; `#config` editing.
- Functional admin dashboard (5.7) with delete-confirm modal, neutral styling.
- **Done when:** weekly recap posts with real numbers; dashboard does full idea CRUD + project/tag management; delete prompts a modal.

### Phase 5 — Integration framework (later)  · branch `phase-5-integrations`
- Build the adapter interface (listen → normalize → post to channel) and wire the first project (eBay) as the template. **Do not implement now** — leave the table + interface in place.

---

## 8. Recommended Claude Code setup

- **claude-mem** — initialize it; this is a 3+ session build and cross-session memory matters.
- **Supabase MCP** — add it so the agent gets DB read/write tools without hand-wiring.
- **CLAUDE.md** — seed it from Sections 1–3 (constraints, stack, architecture) and update it each phase with current state and decisions.
- Phase-based prompting: tackle one phase per working session; don't jump ahead.

---

## 9. Parking lot — do NOT build now

- **Local LLM fallback (Llama).** A local model for routine parsing/categorization so zero subscription/API usage is consumed — default-for-cheap-tasks or fallback. Revisit after the core works.
- **Backup database seeding.** A second (e.g. local) DB seeded from Supabase on a ~24-hour cadence as a backup of all records.
- **Project integrations** (eBay sold alerts, binder sales / preorder quotas) — Phase 5 only.
- **Voice capture** (Whisper → idea pipeline) — optional enhancement, text-first for v1.

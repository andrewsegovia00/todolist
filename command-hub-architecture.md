# Command Hub — Architecture & Flow Design

*(working name — swap it for whatever you like)*

A personal operating system with three jobs: run your **optimized schedule**, hold a **dead-time priority queue**, and act as a **content idea hub** sorted into editable buckets. The whole thing is operated through **Discord**, where you, your partner, and a **Claude agent** share a private server. Projects (eBay, binders, etc.) plug in later as their own channels without touching the core.

---

## 1. The big picture

There are only four "actors" in this system, and keeping them mentally separate is the key to the whole design:

```
        YOU (phone / laptop)        PARTNER (phone / laptop)
              │                          │
              └────────────┬─────────────┘
                           │  text / (optional) voice
                     ┌─────▼─────┐
                     │  DISCORD   │   ← interface ONLY (no logic, no data)
                     │  (server)  │
                     └─────┬─────┘
                           │  gateway events / REST
        ┌──────────────────▼──────────────────────────────┐
        │   ALWAYS-ON HUB DEVICE  (your full-access box)    │
        │                                                   │
        │   ┌─────────────┐        ┌────────────────────┐  │
        │   │ Discord Bot │ ◄────► │   Claude Code      │  │
        │   │  (router)   │        │ (Max sub-auth +    │  │
        │   └──────┬──────┘        │  Supabase MCP)     │  │
        │          │               └─────────┬──────────┘  │
        │          │                         │             │
        │   ┌──────▼──────┐         ┌────────▼─────────┐   │
        │   │  Scheduler  │ ──────► │   DB client      │   │
        │   │   (cron)    │         │  (→ Supabase ☁)  │   │
        │   └─────────────┘         └────────┬─────────┘   │
        │                                                   │
        │   ┌─────────────────────────────────────────┐    │
        │   │  Integration adapters  (pluggable, later)│    │
        │   └──────────┬───────────────┬──────────────┘    │
        └──────────────┼───────────────┼───────────────────┘
                       │               │
                 ┌─────▼────┐    ┌──────▼─────┐
                 │ eBay API │    │ Stripe /   │     (future)
                 │          │    │ Sheets     │
                 └──────────┘    └────────────┘
```

The mental model:

- **Discord is a dumb terminal.** It carries messages in and out. It never stores your data or runs logic. This matters because it means you're never locked into Discord — if you later want a phone app or web dashboard, you point it at the same hub and Discord becomes just one of several front ends.
- **The hub device is the control plane; Supabase is the data plane.** Your full-access machine runs the bot, the Claude agent, and the scheduler — but the database lives in **Supabase (cloud)**, not on the box. This is a deliberate split: the always-on device does the *work*, Supabase holds the *truth*. The upside is that a future dashboard, your other devices, or even a Claude artifact can read the same data directly without going through the hub. The agent's tools become Supabase queries (over the network, but latency is trivial here) instead of local file reads.
- **Claude is the brain, not the messenger — and it's free.** The reasoning runs as Claude Code authenticated to your Max subscription (no billed API key), so the bot routes raw messages and Claude interprets intent, decides what to store or retrieve, and writes the reply. The bot just relays the result back to the channel.
- **Integrations hang off the side.** Each future project is an adapter that watches an external source and posts into its own channel. The core never needs to know they exist.

---

## 2. Design principles

A few rules that the rest of the design follows, worth stating because they're what make it extensible:

**Channel = context.** Every Discord channel maps to a "mode." A message in `#ideas` gets idea-handling tools and an idea-focused system prompt; a message in `#schedule` gets schedule tools. This routing is *config*, not code — adding a new channel mode is a row in a table, not a deploy.

**Config is data, not code.** Your content buckets, your idea-pipeline stages, who's allowed to do what, and which channel does what all live in the database. You edit them by talking to the agent ("add a bucket called X") or in a `#config` channel — never by editing source.

**Single source of truth in Supabase.** One Supabase project holds everything. Any surface — this system's bot, the custom dashboard you have in mind, a mobile view, a future Claude artifact — reads the same store. No syncing problem because there's only one copy, and because it's hosted Postgres you get auth, row-level security, REST/RPC, and realtime out of the box. (This also lines up with the **Supabase MCP** already in your tooling stack: your agent can manage and query the DB through it, and so can anything else you build.)

**Integrations are plugins.** Each external project conforms to a small interface — *listen to a source → normalize the event → format a notification → post to a target channel*. New project = new adapter file + one config row. You explicitly don't want these now, so the core ships without them, but the seam is there from day one.

---

## 3. The three core subsystems

### A. Schedule Engine

Holds your optimized schedule as **time blocks**. A block is a window with a label, a category/project, and — importantly — a **goal** ("what I have to achieve" in this block). Blocks can be one-off or part of a recurring weekly template (your lifting days, study blocks, dev blocks, content blocks, etc.), so you define your normal week once and only edit the exceptions.

The **scheduler** (a cron-style loop on the hub) does the proactive work:
- At a block boundary it posts to `#schedule`: *"⏰ Wrapping up: [current block]. Next at 2:00 PM — Stats homework. Goal: finish one-proportion z-test problem set."*
- Each morning it posts a **daily briefing** (today's blocks + top dead-time priorities + any ideas captured overnight).

**Dead-time priorities** live in a separate prioritized queue, deliberately *not* on the calendar. Each task carries a priority and an **estimated duration**, so when you have a gap the system matches a task to the window you actually have.

**Trigger: manual-first, conservative-proactive-later** (decided). The primary path is manual — you say *"I've got 20 minutes"* or `/dead 20` and the agent returns the highest-priority task that fits. This always works and never nags. A **proactive layer** gets added afterward, but only firing under high-confidence conditions: a clearly unscheduled stretch, not adjacent to a lift or likely-commute block, and always snoozable/dismissible. The reason for the ordering is that proactive suggestions are only as good as the schedule data behind them, which doesn't exist until the Schedule Engine is in and trusted — so manual ships with Phase 3 and proactive lands right after.

Because Phoenix is MST year-round with no daylight-saving shifts, all the time math is simpler than usual — no DST edge cases to handle.

### B. Content Hub

Captures ideas daily and sorts them into **buckets** — your content accounts/channels (you'll hand me the list; it's fully editable later). Each idea carries: the content, its bucket, who suggested it (you or your partner), tags, a **status**, timestamps, and a notes field for development.

**Status** moves an idea through a pipeline you define. A sensible default to start (trim or rename freely): `Idea → Developing → Scripted → Producing → Editing → Scheduled → Published`. Because statuses are data, you can change the pipeline without code changes.

The two things you asked for both run through `#ideas`:
- **Capture:** you drop an idea in plain language; the agent extracts the bucket (or infers/asks), stores it, and confirms with an ID.
- **Recall + status:** you ask *"what Market ideas aren't published yet?"* and the agent queries and returns a clean, grouped list.

### C. Project Notifications *(scaffolded now, activated later)*

Each project becomes a channel under a `🚀 PROJECTS` category, fed by an integration adapter:
- **Bulk-card eBay** → `#bulk-card-ebay`: notification when an item sells.
- **Binders** → `#binders`: notification when a binder sells or a preorder quota is hit.

You don't want these wired up yet — and you shouldn't, since each needs its own external account/keys. The build just leaves the plug-in interface and the `integrations` config table in place so turning one on later is additive.

---

## 4. Discord layout

A single private server, organized by category. This doubles as a lightweight wireframe of the information architecture (not the look — that's yours):

```
🟦 COMMAND HUB  (private server)
│
├── 📋 SYSTEM
│     ├─ #briefing       daily digest, posted by the agent (read-mostly)
│     ├─ #config         edit buckets / statuses / settings via chat
│     └─ #agent-log      audit trail: what the agent did and when
│
├── 💡 CONTENT HUB
│     └─ #ideas          capture + recall + status
│
├── 🗓️ SCHEDULE
│     └─ #schedule       blocks, reminders, dead-time queue
│
└── 🚀 PROJECTS   (empty for now — add channels as projects come online)
      ├─ #bulk-card-ebay
      ├─ #binders
      └─ #…
```

A note on the multi-user piece: both you and your partner sit in this server, and every captured idea/task is attributed to its Discord author automatically. Worth an early decision (below): is `#schedule` *yours* (personal blocks) or *shared*? Easiest is to keep Schedule personal to you and make Content + Projects shared, but that's a knob, not a constraint.

---

## 5. The agent layer (how Claude actually works here)

**The brain is a local Claude Code / Agent SDK process authenticated to your Max subscription — not a billed API key.** This is what keeps reasoning at no extra cost. The bot never calls `api.anthropic.com` directly; it invokes the subscription-authed agent (via `claude -p` headless mode or the Python Agent SDK) running on your full-access device. Critical rule: **`ANTHROPIC_API_KEY` must be unset** in the bot's environment, or Claude Code silently switches to paid API billing.

**Not every message hits Claude.** Deterministic paths run as plain Python + Supabase with zero model calls: scheduled reminders, slash commands with structured args (`/dead 20`), and exact queries ("list Market ideas"). Claude is invoked only for the fuzzy turns — parsing a free-form idea, loose recall. This keeps subscription usage trivial, which matters because the real constraint on the free route is rate limits, not dollars.

When a message *does* need the agent, the flow is:

1. **Bot receives** the message and looks up the channel's mode from config.
2. **Bot assembles context**: the channel's system prompt, the toolset enabled for that mode, the author's identity, and recent channel history.
3. **The agent reasons and calls tools** to read/write your database — add an idea, query ideas, fetch the next block, push a dead-time task, etc.
4. **The agent writes the reply**; the bot posts it back to the channel and logs the action to `#agent-log`.

**Tools come from the Supabase MCP.** Rather than hand-wiring functions, point the agent at the **Supabase MCP server** (already on your adoption list) so it gets DB read/write capability out of the box. The conceptual tool catalog it operates with:

*Content* — `add_idea`, `list_ideas` (filter by bucket/status/author/tag), `update_idea`, `set_idea_status`, `add_bucket`, `list_buckets`, `rename_bucket`, `archive_bucket`.

*Schedule* — `get_schedule(date)`, `get_next_block`, `add_block`, `update_block`, `get_dead_time_tasks`, `add_dead_time_task`, `complete_dead_time_task`, `suggest_for_window(minutes)`.

*System* — `log_event`, `get_config`, `set_config`.

Use a **session per conversation** where you can (the Agent SDK supports resuming), so each Discord channel keeps its own thread of context rather than starting cold every message.

Two things worth calling out given your interests:

- Because the agent is Claude Code on your **full-access device**, you can hand it broader tools over time — run a script, kick off your bulk-card pipeline, touch a repo. The Discord layer stays the same; you're just expanding the toolset. This is the natural extension of your agentic Claude Code workflow, applied to a long-running agent instead of a coding session.
- **Optional voice capture:** since Whisper is already in your stack, you could add a voice channel where you literally *talk* an idea, the bot records and transcribes via Whisper, and the transcript flows into the exact same idea pipeline. Marked optional — text-first is the simpler v1.

---

## 6. Data model

Compact starting schema (column lists, not exhaustive):

- **people** — `id, discord_user_id, name, role` (you / partner)
- **buckets** — `id, name, type (account|channel), description, active` *(editable)*
- **statuses** — `id, name, order, active` *(your content pipeline, editable)*
- **ideas** — `id, content, bucket_id, author_id, status_id, tags, notes, created_at, updated_at`
- **schedule_blocks** — `id, person_id, label, category, goal, start, end, recurring_rule, active`
- **dead_time_tasks** — `id, content, priority, category, duration_est_min, status, created_at, done_at`
- **reminders** — `id, block_id, fire_at, message, sent`
- **channel_config** — `channel_id, mode, system_prompt_ref, tools_enabled` *(the routing table)*
- **integrations** — `id, name, type, config_json, channel_id, active` *(future)*
- **events** — `id, type, payload, actor, created_at` *(the agent-log / audit trail)*

`buckets`, `statuses`, and `channel_config` being tables (not constants) is what makes the system editable without redeploying. And because `ideas.author_id` and `schedule_blocks.person_id` tie rows to people, your "personal vs. shared" decision drops straight into RLS policies on those tables.

---

## 7. Key flows

**Capture an idea**
You (`#ideas`): "Idea for The Market — break down the post-set-rotation price dip." → agent infers bucket *The Market*, stores it, replies "Saved #142 to The Market (status: Idea)."

**Recall + status**
You (`#ideas`): "What's still unscripted for The Shop?" → agent queries, returns a grouped list with IDs and statuses.

**Schedule reminder (proactive)**
Scheduler fires at 1:55 PM → `#schedule`: "⏰ 5 min left on Agency outreach. Next: Lift (2:00–3:00). Goal: push day, top set 5×5."

**Dead-time fill**
You (`#schedule`): "got 15 before my next block" → agent runs `suggest_for_window(15)` → returns the top-priority task that fits.

**Daily briefing**
7:00 AM → `#briefing`: today's blocks, top 3 dead-time priorities, ideas captured since yesterday.

**Edit a bucket**
You (`#config`): "add a bucket called TikTok Shorts" → agent calls `add_bucket`, confirms.

**Future — eBay sale**
eBay adapter detects a sale → normalizes → `#bulk-card-ebay`: "💰 Sold: Charizard lot — $42.00."

---

## 8. Tech stack (decided)

- **Bot:** `discord.py`. Slash commands (`/dead`, `/idea`, etc.) plus a message handler for free-form chat. Keeps you in the Python momentum from your OCR/Whisper work, and means the Whisper voice path later is the same language.
- **Agent:** **Claude Code / Claude Agent SDK authenticated to your Max subscription** — invoked headless (`claude -p`) or via the Python Agent SDK, with `ANTHROPIC_API_KEY` left unset so usage draws from Max, not paid API billing. This also gives the agent room to do filesystem/script actions on the device later (the bridge to "kick off my bulk-card pipeline from Discord").
- **Database:** **Supabase (Postgres), free tier**. Bot uses `supabase-py` for the deterministic reads/writes; the agent gets DB access via the **Supabase MCP**. Lean on Postgres properly: `timestamptz` everywhere, lookup tables or enums for statuses/modes, and **Row-Level Security** so partner-visible vs. personal data is enforced at the DB, not just in app code. (Free tier is ample for two users; daily activity keeps the project from idle-pausing.)
- **Scheduler:** `APScheduler` in-process with the bot, or `systemd` timers if you want it OS-level robust and independent of the bot process. Reminders are templated — no model calls.
- **Process management:** run the bot as a `systemd` service so it survives reboots and restarts on crash.

**Cost model: $0 extra.** Discord, Supabase free tier, the scheduler, and hosting on your own device are all free; Claude reasoning is covered by your existing Max plan via subscription auth. The only real constraint on the free route is subscription **rate limits**, not cost — and routing only fuzzy turns through the model keeps usage well under them. Watch-outs: (1) never set `ANTHROPIC_API_KEY` in the bot's environment, or it silently bills the API; (2) this billing area is in flux — if metered programmatic billing returns, your volume is absorbed by the included Agent SDK credit ($100 Max 5x / $200 Max 20x), so out-of-pocket still stays ~$0.

One consequence of Supabase being cloud: the **service-role key** (which bypasses RLS) lives only on the trusted hub device, never in any browser/client surface. Anything client-side (a future dashboard) uses the anon key + RLS policies.

---

## 9. Networking & security

- **Inbound for the bot is not needed.** Discord bots connect *out* to Discord's gateway, and the bot/agent connect *out* to Supabase — so the hub never has to expose a port for the core system. Attack surface stays tiny (fits your interest in locking down dev machines).
- **RLS is your access-control layer.** Define Row-Level Security policies in Supabase so "personal vs. shared" is enforced at the data layer. The hub holds the service-role key; any client surface uses the anon key and is bound by RLS.
- **Webhooks for integrations are the only inbound exception.** If a future integration (Stripe for binders, eBay platform notifications) pushes events, route them through a **Cloudflare Tunnel** rather than opening ports — no inbound holes, and it slots into the Cloudflare setup you already use. Or have adapters **poll** the APIs on a timer and skip inbound entirely.
- **Secrets** (bot token, Supabase service key, future API keys) in an `.env` / secrets store, never committed. Note there's **no Anthropic API key** here by design — the agent uses subscription auth.
- **Private server, locked roles** — just you and your partner, with `#schedule` scoped to you if you want it personal.

---

## 10. What I need from you

To turn this into a build, the inputs that actually shape the design. **Decided:** Supabase/Postgres (free tier) for data, `discord.py` for the bot, dead-time manual-first, and the agent runs as subscription-authed Claude Code for $0 extra. Still open:

1. **Content buckets/accounts** — your list (The Shop / The Market / The World of Andrew + whatever else, including non-YouTube ones).
2. **Content pipeline stages** — confirm or edit the default (`Idea → Developing → Scripted → Producing → Editing → Scheduled → Published`).
3. **Schedule shape** — recurring weekly template vs. per-day, plus your actual blocks and their goals.
4. **Partner access scope** — *resolved:* everything shared between the two people, including the schedule (one shared schedule both follow for now; can split per-person later). No per-person RLS restriction yet.
5. **The hub device** — which machine, and its OS (so I tailor the `systemd` setup / scheduler).
6. **Provisioning** — a Discord application/bot token (with Message Content intent enabled), a Supabase project (URL + service-role key), and **Claude Code installed and logged into your Max account** on the hub device (no API key).
7. **Later, per integration** — eBay developer account, and Stripe/Sheets access for binders.

---

## 11. Suggested build order

Maps onto your usual wireframe → schema → MVC → features pipeline, in agent-friendly phases:

- **Phase 0 — Decisions & provisioning.** Lock the open answers above; create the Discord app + server and the Supabase project; install Claude Code on the hub and log it into Max (confirm `ANTHROPIC_API_KEY` is unset).
- **Phase 1 — Data + config.** Postgres schema + RLS policies, plus seed `buckets`, `statuses`, `people`, and `channel_config`.
- **Phase 2 — Bot + agent (Content first).** `discord.py` skeleton, channel routing, Claude wired with the content toolset. Capture + recall working end to end in `#ideas`.
- **Phase 3 — Schedule engine.** Blocks, scheduler, reminders, and the **manual** dead-time queue + matching in `#schedule`.
- **Phase 3.5 — Proactive dead-time.** Add the conservative proactive layer once schedule data is trusted.
- **Phase 4 — Briefing & polish.** Daily `#briefing`, `#agent-log`, `#config` editing flows.
- **Phase 5 — Integrations (later).** Build the adapter framework, then light up the first project (eBay) as the template for the rest.

---

## 12. Captured requirements — partner session

New user-flow requirements raised in review, to fold into the build:

**Idea capture handshake.** On capture, the agent (1) auto-drafts a *title*, (2) asks which *bucket*, (3) asks for an optional *project*. Multiple ideas can arrive in one message and should be processed one per idea. Recall returns *titles* first (by bucket or project); asking about a title expands it into a summary of the original notes.

**Dead-time (`/dead N`) — three lanes.** "Best use of an N-minute window," drawing from: (1) **tasks** that fit the window (duration-matched), (2) **ideas to act on** — actionable content ideas surfaced for that pocket of time, (3) **ideas to develop** — the agent pulls up a chosen idea and *brainstorms it with you*, then writes the result back into that idea's `notes` and bumps its status (`Idea → Developing`). Lane 3 makes dead time a feeder for the content hub. Data implication: `/dead` queries both `dead_time_tasks` and `ideas`, and can *write* to an idea, not just read.

**Schedule timecard + analytics.** Every schedule block closes out — the user responds whether it was completed, and can manually enter a finish time if they forgot (timecard behavior). This data feeds analytics: dead spots in the week, tasks finished under/over their estimate, schedule adherence over time. Analytics surface proactively (e.g. weekly recap).

**Check-in toggle / day-off mode.** The user can turn schedule check-ins off (global switch or a pause-until window) for holidays, birthdays, off-script days. Critical semantic: **off = the day is excluded from analytics**, not merely silenced — it suppresses both the close-out prompts and the "mismanaged time" penalty, so a paused day never counts as dead spots.

**Unclosed-block handling.** If the "did you finish?" ping goes unanswered in time: log the block as unclosed, move on (never blocks the user), then nudge once at night (or point to the admin page) to backfill the finish time. Still no response → the block stays blank and reads as mismanaged time in analytics — *unless* that day was toggled off.

**Dashboard / admin panel.** Central view of all stored ideas (retrieve, edit, delete). Add/manage projects and tags here. Delete must be gated behind an "are you sure?" confirmation modal. (Visual design reserved by Andrew — build to his look.)

### Resolved decisions
1. **`/dead` source** — three lanes: fitting tasks, ideas to act on, and ideas to develop (with brainstorm written back to the idea). See above.
2. **Inline correction at capture** — yes. The user can fix title/bucket/project in the same exchange.
3. **Multi-idea splitting** — agent only splits when it detects multiple ideas (blank lines, lists, topic shifts); when it does, it shows proposed titles and confirms the split before filing. Single ideas flow straight through. Misreads are fixed inline.
4. **Close-out fallback** — confirmed (see "Unclosed-block handling" above).
5. **Day-off semantics** — confirmed (see "Check-in toggle" above): paused days are excluded from analytics.

### Data-model touch-points these imply
- `schedule_blocks` need a close-out state: `open → closed (with finish_time) → unclosed/blank (mismanaged)`, plus an `excluded` flag for paused days.
- A `settings`/`day_off` concept for the check-in toggle (global switch and/or dated pause windows).
- `/dead` reads `dead_time_tasks` **and** `ideas`, and can update `ideas.notes` + `ideas.status`.

### Parking lot — deferred infrastructure (revisit at build)
- **Local LLM fallback (Llama).** A local model option so routine parsing/categorization consumes no subscription/API usage at all — either as the default for cheap tasks or as a zero-cost fallback. Quality tradeoff to weigh later.
- **Backup database seeding.** A second (e.g. local) database seeded from the cloud store on a recurring cadence (~every 24 hours) as a backup of all added messages/records.

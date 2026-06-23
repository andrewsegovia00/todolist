# Deploying Command Hub — provisioning runbook

Most of this can be done **remotely (phone/laptop)** before you're at the hub.
Only the last part needs the home machine. Do the parts in order; record values
in the worksheet at the bottom, then paste them into `.env` at the hub.

> 🔐 **Never paste tokens/keys into chat or commit them.** They go straight into
> `.env` (gitignored) on the hub. The non-secret decisions (schedule, OS,
> timezone, names, bucket/project lists, channel structure) are safe to share.

---

## Part A — Discord (remote, ~10 min)

1. **Create the app + bot.** https://discord.com/developers/applications → *New
   Application*. Open the **Bot** tab → *Reset Token* → copy it →
   `DISCORD_BOT_TOKEN`.
2. **Enable the Message Content intent.** Bot tab → *Privileged Gateway Intents*
   → turn on **Message Content Intent** (and **Server Members Intent**). Save.
3. **Invite the bot.** OAuth2 → *URL Generator* → scopes `bot` +
   `applications.commands`; bot permissions: *Send Messages*, *Read Message
   History*, *Use Slash Commands*. Open the generated URL, add it to your server.
4. **Create the private server** (if you don't have one) and invite your partner.
5. **Get IDs** (Discord Settings → Advanced → enable *Developer Mode*, then
   right-click → *Copy ID*):
   - Server (guild) → `DISCORD_GUILD_ID`
   - Your user → `OWNER_DISCORD_USER_ID`
   - Partner's user → `PARTNER_DISCORD_USER_ID` (and their display name)
6. **Create channels** under categories and copy each channel ID:
   ```
   SYSTEM      #briefing   -> CHANNEL_BRIEFING
               #config     -> CHANNEL_CONFIG
               #agent-log  -> CHANNEL_AGENT_LOG
   CONTENT HUB #ideas      -> CHANNEL_IDEAS
   SCHEDULE    #schedule   -> CHANNEL_SCHEDULE
   ```

## Part B — Supabase (remote, ~10 min)

1. **Create a project** at https://supabase.com (free tier). Pick a region near
   the hub.
2. **API keys** (Project Settings → API):
   - Project URL → `SUPABASE_URL`
   - `anon` `public` key → `SUPABASE_ANON_KEY`
   - `service_role` key → `SUPABASE_SERVICE_ROLE_KEY` (hub-only; keep secret)
3. **Connection string** (Project Settings → Database → Connection string →
   URI) → use as `DATABASE_URL` when running migrations.
4. **MCP access** (so the agent gets DB tools): create a Supabase **personal
   access token** (Account → Access Tokens) and note your **project ref** (the
   subdomain in the URL). These go into `agent/mcp_config.json` (copied from the
   example).

## Part C — Decisions to send me now (non-secret, optional)

If you send these, I'll bake them in so the hub step is shorter:
- **Hub OS** (Linux / macOS / Windows) — picks the process manager.
- **Timezone** (default `America/Phoenix`, no DST).
- **Partner display name.**
- **Buckets / projects** — defaults are The Shop, The Market, The World of
  Andrew / TCG Binders, Bulk-Card eBay. Tell me any changes.
- **Pipeline statuses** — default Idea → Developing → Scripted → Producing →
  Editing → Scheduled → Published.
- **Your weekly schedule blocks + goals** — I'll fill in
  `db/schedule_template.json` so `make load-schedule` just works.

## Part D — At the hub (home, ~15 min)

```bash
git clone <repo> command-hub && cd command-hub
git checkout claude/adoring-meitner-5686ws
make setup                       # venv + deps

cp .env.example .env             # paste all the values from Parts A & B
cp agent/mcp_config.example.json agent/mcp_config.json   # project ref + token

make check-env                   # asserts ANTHROPIC_API_KEY unset + config present

# Apply schema + seed (DATABASE_URL from Part B step 3):
DATABASE_URL='postgresql://...' make migrate
make seed                        # people + channel routes from .env
make load-schedule               # optional: your weekly blocks
make check-supabase

# Claude Code must be installed and LOGGED INTO MAX on this machine.
# Confirm `echo $ANTHROPIC_API_KEY` prints nothing, then:
make check-claude

make run                         # start the bot + scheduler
make dashboard                   # optional admin UI on http://127.0.0.1:5000
```

Then install the service so it survives reboots — see `deploy/` for your OS.

---

## `.env` worksheet

```env
# Discord
DISCORD_BOT_TOKEN=
DISCORD_GUILD_ID=
OWNER_DISCORD_USER_ID=
PARTNER_DISCORD_USER_ID=
PARTNER_DISPLAY_NAME=

# Supabase
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=

# Channel routing (optional here; can also set via #config later)
CHANNEL_IDEAS=
CHANNEL_SCHEDULE=
CHANNEL_CONFIG=
CHANNEL_BRIEFING=
CHANNEL_AGENT_LOG=

# Hub
HUB_OS=linux
TIMEZONE=America/Phoenix
```

> `CHANNEL_*` aren't read by `core/settings.py` directly — they're consumed by
> `db.seed` to populate `channel_config`. Put them in `.env` before `make seed`,
> or add routes later from `#config` / the dashboard.

## The one true blocker

Everything above except **"Claude Code installed + logged into Max on the hub"**
can be prepared remotely. That login can only happen on the home machine — it's
what keeps the agent on the $0 subscription path instead of a billed API key.

# Windows hub — run the bot as a service

Two options. NSSM is the simplest for a long-lived Python process.

## Option A — NSSM (recommended)

1. Install [NSSM](https://nssm.cc/).
2. From an elevated prompt:

   ```
   nssm install CommandHubBot "C:\command-hub\.venv\Scripts\python.exe" "-m bot.main"
   nssm set CommandHubBot AppDirectory "C:\command-hub"
   nssm set CommandHubBot AppStdout "C:\command-hub\logs\bot.out.log"
   nssm set CommandHubBot AppStderr "C:\command-hub\logs\bot.err.log"
   nssm start CommandHubBot
   ```

   NSSM picks up the user environment. Make sure `ANTHROPIC_API_KEY` is **not**
   set for the service account (the startup guardrail will refuse to start if it
   is).

## Option B — Task Scheduler

Create a task: trigger "At startup", action "Start a program" →
`C:\command-hub\.venv\Scripts\python.exe` with arguments `-m bot.main`, "Start
in" `C:\command-hub`. Enable "Run whether user is logged on or not" and
"Restart on failure".

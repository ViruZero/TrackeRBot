# TrackerBot Agent Rules & Autonomous Workflow

The user will give you plain-English requests. Translate their casual intent into the exact workflow below automatically without asking them for technical flags or filenames.

## 1. Codebase Map (Know Where to Look)
- `bot.py`: Main Discord bot entry point and cog loader.
- `ai_helper.py`: AI routing logic (`smart_ai_post` with Ollama local -> Groq Cloud fallback).
- `cogs/digest.py`: Daily Morning Briefing (weather, holidays, Groq daily quotes & jokes).
- `cogs/tracker.py` (or price tracking cogs): Product price monitoring, scanning schedules, and threshold alerts.
- `holiday.py` / `weather.py`: Helper modules for holiday info and Philadelphia weather forecasts.
- `deploy.py`: Syntax verification (`py_compile`), git commit/push to Oracle server, and `trackerbot.service` systemd restart.

## 2. Strict Coding Rules (When User Asks to Change/Fix/Add Code)
1. **NEVER use your built-in `edit_file`, `write_file`, or `patch` tools on `.py` files.** Always delegate code edits to Aider in the terminal.
2. **Always run Aider as a SINGLE-LINE terminal command (no newlines inside `--message`):**
   `aider --yes-always --message "<clear instructions based on user request>" <target_file.py>`
   *(Note: `.aider.conf.yml` already configures OpenRouter, `edit-format: diff`, and disables warnings).*
3. **Verify Syntax:** Immediately after Aider finishes, run `python -m py_compile <target_file.py>`.

## 3. Deployment Rules (When User Says "deploy", "push", "send to server", or "make it live")
- Do not search for deployment scripts—immediately run `python deploy.py` in the terminal and report the git commit hash and `trackerbot.service` status.
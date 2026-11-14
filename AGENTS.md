# Agent Workspace Rules for TrackerBot
- Local OS is Windows 10 PowerShell (C:\Users\Anthony\Desktop\TrackerBot). Use built-in file tools (read/write/list) instead of Linux bash commands locally.
- NEVER edit files directly on the remote Oracle server. Edit local files only.
- Do NOT remove existing functions (fetch_page_data, parse_with_ai, setup) when updating a cog.
- To view live Oracle logs, run: ssh oracle-bot "sudo journalctl -u trackerbot.service -n 30 --no-pager"
- To deploy changes, ALWAYS run: python deploy.py

## Multi-Agent Coder Workflow (Hermes Dispatcher -> Aider Gemini Coding Agent)
When the user asks to "draft a spec" or build/edit code in TrackerBot:
1. **Step 1 — Draft Spec (Architect Mode):** Do NOT edit `.py` files directly yourself. Run Aider in read-only chat mode to analyze the repo and write a concise spec:
   `aider --model gemini/gemini-2.5-flash --no-auto-commits --no-git --message "READ ONLY: Draft a concise PRD implementation spec for: <user task>. List Goal, Files to modify, and Step-by-step plan. Do NOT edit any files yet." bot.py ai_helper.py holiday.py deploy.py cogs/*.py`
   Show the spec to the user in Discord and wait for approval.
2. **Step 2 — Build Code:** Once the user replies "looks good, build it" (or approves the spec), run Aider to apply the code edits:
   `aider --model gemini/gemini-2.5-flash --no-auto-commits --yes-always --message "<approved task details>"`
3. **Step 3 — Verify & Report:** Run `python -m py_compile bot.py cogs/*.py` and `git status -s` to verify clean syntax, then post the summary back to Discord. Only run `python deploy.py` when the user explicitly asks to deploy.

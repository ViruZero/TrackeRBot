# Agent Workspace Rules for TrackerBot
- Local OS is Windows 10 PowerShell (C:\Users\Anthony\Desktop\TrackerBot). Use built-in file tools (read/write/list) instead of Linux bash commands locally.
- NEVER edit files directly on the remote Oracle server. Edit local files only.
- Do NOT remove existing functions (fetch_page_data, parse_with_ai, setup) when updating a cog.
- To view live Oracle logs, run: ssh oracle-bot "sudo journalctl -u trackerbot.service -n 30 --no-pager"
- To deploy changes, ALWAYS run: python deploy.py

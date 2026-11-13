# Agent Workspace Rules for TrackerBot
- NEVER edit files directly on the remote Oracle server. Edit local files only.
- Do NOT remove existing functions (etch_page_data, parse_with_ai, setup) when updating a cog.
- To view live Oracle logs, run: ssh oracle-bot "sudo journalctl -u trackerbot.service -n 50 --no-pager"
- To deploy changes, ALWAYS run: python deploy.py. Never push or restart the service manually without deploy.py.

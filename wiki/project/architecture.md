# Architecture (canonical decisions)

- UI: Discord **Components V2** (`ui.LayoutView`, `ui.Container`, accent_color) — see `cogs/tracker_price.py` (`/items` list). No legacy embed-only layouts for new UI.
- Storage: SQLite at `tracker.db` (project root). Tables:
  - `users(user_id PK, prefix, shopping_channel_id, digest_channel_id, alerts_channel_id)` — note `cogs/users.py` still has the older 3-col variant; `cogs/register.py` is the current 4-col one.
  - `items(id, url, title, target_price, original_price, current_price, image_url, user_id, PK(id, user_id))`
  - `user_banners(user_id PK, theme DEFAULT 'starry_night', custom_url TEXT NULL)` — custom_url added via ALTER if missing.
- Deploy: `python deploy.py` from repo root → py_compile all `*.py` + `cogs/*.py` → `git add/commit/push` → `ssh oracle-bot` → `sudo systemctl restart trackerbot.service` + journalctl tail.
- Entry point `bot.py` loads cogs from `cogs/`; price checks in `cogs/check.py` / `cogs/tracker_price.py`; digest in `cogs/digest.py`.
- AI routing: `ai_helper.py` `smart_ai_post` — Ollama local → Groq Cloud fallback.
- Digest banner: `cogs/digest.py` sends `[banner_embed, briefing_embed]` — banner_embed only sets `set_image(url='attachment://daily_digest_banner.png')` (same accent color), briefing_embed carries title/description; `discord.File('assets/banners/daily_digest_banner.png')` attached to the send. Keeps banner above the text.

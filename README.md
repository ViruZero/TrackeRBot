# TrackerBot

Discord bot for product price tracking, price alerts, and daily briefings.

## Repository layout

```text
bot.py                      Bot entry point and cog loading
ai_helper.py                Shared AI routing
holiday.py                  Holiday information
deploy.py                   Syntax checks and server deployment
backup.sh                   Server database backup entry point
cogs/                       Bot commands, scheduled jobs, and UI helpers
assets/                     Banner images and fonts
scripts/
  generate_banner.py        Cloudflare banner generator
  generate_banner_gemini.py Gemini banner generator
  maintenance/update_db.py  Legacy database column migration
archive/
  backup_20261113/           Historical source snapshot
  digest_repairs/            Historical repair scripts and their input snapshot
backups/                    Database backup files
wiki/                       Architecture, design standards, and research notes
requirements.txt            Runtime dependency manifest
AGENTS.md                   Repository automation instructions
```

## Entry points

Run commands from the repository root, using the Python environment configured
for the bot:

```sh
python bot.py
python scripts/generate_banner.py --help
python scripts/generate_banner_gemini.py --help
```

Both banner generators resolve `.env` and `assets/banners/` relative to the
repository. The optional migration at `scripts/maintenance/update_db.py` also
resolves `tracker.db` relative to the repository; it modifies the database and
is not part of normal startup.

`deploy.py` and `backup.sh` remain at the root for existing server integrations.
Deployment checks root, cog, and script Python files, excluding archived code.
See [the wiki](wiki/INDEX.md) for architecture and operational context.

## Historical files and local data

`archive/` contains reference material, not active bot modules. In particular,
the digest repair scripts are old source-rewriting tools and should not be run
against the current bot. See [the archive notes](archive/README.md).

Local credentials, logs, databases, and virtual environments should stay out
of version control. Ignore rules do not remove files already tracked by Git;
the existing tracked key and database snapshots still need separate cleanup.

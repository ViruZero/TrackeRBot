# Crew Roster

- **Chief of Staff (default profile, "Hermes")** — Orchestrator. Plans tasks, delegates to specialists, reports back. Owns #chief-of-staff and any unrouted channel. Direct edits only for non-.py files; .py edits go via Aider per AGENTS.md.
- **artist** (`hermes -p artist`, #art-studio / 1571766796070031383) — generates 16-bit cozy farming RPG / 8-bit pixel art banner templates via Gemini image API; saves text-free 4:1 PNGs into `assets/banners/`. Never touches code, text overlay, or deploy.
- **developer** (`hermes -p developer`, #dev-ops / 1571766833231695913) — edits TrackerBot code ONLY via Aider (single-line `--message`), then `python -m py_compile`; overlays pixel titles with NEAREST + PressStart2P.ttf; deploys via `python deploy.py`; reports commit hash + service status.
- Routing: `gateway.profile_routes` in `~/.hermes/config.yaml` (multiplexed gateway). Discord channel routing per above; #chief-of-staff and everything else → default.
- Shared memory: `wiki/` in repo root — read `wiki/INDEX.md` before acting; update wiki after tasks. `wiki/research/` holds external notes; `wiki/project/` holds canonical decisions.

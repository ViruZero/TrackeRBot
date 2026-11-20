# TrackerBot Wiki — INDEX

Shared memory for the crew (Chief of Staff, artist, developer). Read this first, then the relevant pages. Update the wiki + this index after finishing tasks.

Repository layout and entry points: [README](../README.md). Historical source
snapshots and one-off digest repairs are kept under [archive](../archive/README.md);
active maintenance and banner tools live under `scripts/`.

## project/ (canonical decisions — outside claims never overwrite these)
- [project/aliexpress.md](project/aliexpress.md) — current AliExpress fetch order, price validation, configuration, and tests
- [project/architecture.md](project/architecture.md) — Components V2 UI, SQLite tables, Oracle deploy.py
- [project/art_standards.md](project/art_standards.md) — 16-bit Stardew pixel style, banner sizes, NEAREST resampling, paths, text-free templates
- [project/crew_roster.md](project/crew_roster.md) — Chief of Staff / artist / developer roles

## research/ (external API/web notes — never promoted into project/ without a crew decision)
- [research/zenrows_aliexpress.md](research/zenrows_aliexpress.md) — autoparse=true on /item/ and /w/wholesale- returns image/i18n metadata only, zero price fields (2026-11-18)

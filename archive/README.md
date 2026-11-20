# Historical source material

- `backup_20261113/`: original source snapshot, preserved unchanged.
- `digest_repairs/`: one-off digest rewrite scripts, preserved unchanged.
  Their original input is retained at `digest_repairs/cogs/digest.py.backup`.

These files are retained for reference, excluded from deployment syntax checks,
and not loaded by the bot. The repair scripts use historical relative paths and
rewrite source files; they are not supported maintenance entry points.

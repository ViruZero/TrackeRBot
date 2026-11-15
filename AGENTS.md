# TrackerBot Agent Rules & Fast Aider Pipeline

## STRICT SPEED & DELEGATION RULES (CRITICAL)
1. **NEVER use your built-in file editing/patch tools (`edit_file`, `write_file`, `patch`) on `.py` files.** You are ONLY the dispatcher.
2. **NEVER write or run ad-hoc Python test scripts or multi-turn debugging loops.**
3. **Pass ONLY the 1 or 2 relevant files to Aider** (model, API key, `map-tokens: 0`, and `show-model-warnings: false` are already set in `.aider.conf.yml`).

## Two-Step Aider Workflow
1. **Step 1 — Draft Spec:** Run a SINGLE terminal command targeting only the relevant file(s):
   `aider --no-git --message "READ ONLY: In 10 bullet points max, write a spec for: <task>. Do NOT edit files." <target_file.py>`
2. **Step 2 — Build Code:** When the user says "looks good, build it", run ONLY this single terminal command (do NOT edit files yourself):
   `aider --yes-always --message "<approved spec>" <target_file.py>`
3. **Step 3 — Fast Verify:** Run `python -m py_compile <target_file.py>` once and immediately reply to the user in Discord.
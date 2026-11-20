import glob, py_compile, subprocess, sys

print("1. Running local Python syntax check...")
for path in glob.glob("*.py") + glob.glob("cogs/*.py") + glob.glob("scripts/**/*.py", recursive=True):
    try:
        py_compile.compile(path, doraise=True)
    except py_compile.PyCompileError as e:
        print(f"SYNTAX ERROR in {path}:\n{e}")
        sys.exit(1)
print("All files passed py_compile!")

print("2. Committing and pushing to Oracle Server...")
subprocess.run(["git", "add", "."], check=True)
subprocess.run(["git", "commit", "-m", "Validated update from PC"], check=False)
subprocess.run(["git", "push", "origin", "HEAD"], check=True)

print("3. Restarting trackerbot.service on Oracle...")
cmd = "sudo systemctl restart trackerbot.service && sleep 3 && sudo journalctl -u trackerbot.service -n 20 --no-pager"
subprocess.run(["ssh", "oracle-bot", cmd], check=True)

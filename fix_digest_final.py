#!/usr/bin/env python3
"""
Fix digested.py to split header_embed into banner_embed and header_embed
"""
import py_compile

# Read backup
with open('cogs/digest.py.backup', 'r', encoding='utf-8') as f:
    backup_lines = f.readlines()

# Keep everything before line 168 (indices 0-167)
result_lines = backup_lines[:168]

# Split the fixed section into individual lines
fixed_section = '''        # Create header embed with briefing content (no image)
        header_embed = discord.Embed(
            title=f"{holiday['emoji']} {holiday['title_prefix']} — {date_str}",
            description=(
                f"Here is your morning overview, Philadelphia weather forecast, and price check summary.\\n\\n"
                f"💡 **Inspirational Quote of the Day**\\n*{quote}*\\n\\n"
                f"😂 **Joke of the Day**\\n{joke_setup}\\n||{joke_answer}||\\n\\n"
                f"🌡️ **Philadelphia Weather (3-Hour Outlook)**\\n{weather_snippet}"
            ),
            color=holiday["color"]
        )

        # Create dedicated banner embed for the image at the top
        banner_embed = discord.Embed(color=holiday["color"])
        banner_embed.set_image(url='attachment://daily_digest_banner.png')

        # Return [banner_embed, header_embed, holiday] so banner appears first
        return [banner_embed, header_embed], holiday
'''

result_lines.extend(fixed_section.split('\n'))

# Add the rest of the file from line 188 (index 187)
result_lines.extend(backup_lines[187:])

# Write out
with open('cogs/digest.py', 'w', encoding='utf-8') as f:
    f.writelines(result_lines)

print(f"✓ Fixed digest.py: {len(backup_lines)} -> {len(result_lines)} lines (plus {len(result_lines)-len(backup_lines)} change)")

# Verify syntax
try:
    py_compile.compile('cogs/digest.py', doraise=True)
    print("✓ Syntax check passed")
except Exception as e:
    print(f"✗ Syntax error: {e}")
    import sys
    sys.exit(1)

# Update function calls to match new return value
print("\nUpdating function calls...")
with open('cogs/digest.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix manual_digest
content = content.replace(
    'header_embed, holiday = await self.build_briefing_embed()',
    'header_embed_list, holiday = await self.build_briefing_embed()\n        header_embed = header_embed_list[0]  # banner_embed\n        briefing_embed = header_embed_list[1]  # header_embed'
)

# Fix send_digest_for_user
content = content.replace(
    'async def send_digest_for_user(self, channel, user_id: int, header_embed: discord.Embed, holiday: dict):',
    'async def send_digest_for_user(self, channel, user_id: int, briefing_embeds: list, holiday: dict):'
)

# Fix run_all_digests (where it calls send_digest_for_user)
content = content.replace(
    'await self.send_digest_for_user(ch, user_id, header_embed, holiday)',
    'await self.send_digest_for_user(ch, user_id, briefing_embeds, holiday)'
)

# Write back if changes were made
if content != open('cogs/digest.py', 'r', encoding='utf-8').read():
    with open('cogs/digest.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("✓ Updated manual_digest function")
    print("✓ Updated send_digest_for_user signature")
    print("✓ Updated run_all_digests calls")
else:
    print("⚠ No function call updates needed")

# Verify syntax again
try:
    py_compile.compile('cogs/digest.py', doraise=True)
    print("✓ Final syntax check passed")
except Exception as e:
    print(f"✗ Syntax error: {e}")
    sys.exit(1)

print("\n✅ All changes complete!")
#!/usr/bin/env python3
"""
Complete rewrite of build_briefing_embed in digest.py
"""
import py_compile

# Read backup
with open('cogs/digest.py.backup', 'r', encoding='utf-8') as f:
    backup_lines = f.readlines()

# Keep everything before line 168 (indices 0-167)
result_lines = backup_lines[:168]

# Add the fixed lines for header_embed and banner_embed
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

result_lines.append(fixed_section)

# Add the rest of the file from line 188 (index 187)
result_lines.extend(backup_lines[187:])

# Write out
with open('cogs/digest.py', 'w', encoding='utf-8') as f:
    f.writelines(result_lines)

print(f"✓ Fixed digest.py: {len(backup_lines)} -> {len(result_lines)} lines")

# Verify syntax
try:
    py_compile.compile('cogs/digest.py', doraise=True)
    print("✓ Syntax check passed")
except Exception as e:
    print(f"✗ Syntax error: {e}")
    import sys
    sys.exit(1)

# Also need to update send_digest_for_user and manual_digest to handle the changed return value
print("\nChecking other function calls...")
with open('cogs/digest.py', 'r', encoding='utf-8') as f:
    content = f.read()

if 'header_embed, holiday = await self.build_briefing_embed()' in content:
    content = content.replace(
        'header_embed, holiday = await self.build_briefing_embed()',
        'header_embed_list, holiday = await self.build_briefing_embed()\n        header_embed = header_embed_list[0]  # Extract banner_embed\n        briefing_embed = header_embed_list[1]  # Extract header_embed'
    )
    print("✓ Updated manual_digest function")
elif '[header_embed, header_embed], holiday' in content:
    print("✓ Manual digest already updated (uses unpacking)")
else:
    print("⚠ Manual digest function may need manual update")

if 'header_embed, holiday = await self.build_briefing_embed()' in content:
    with open('cogs/digest.py', 'w', encoding='utf-8') as f:
        f.write(content)

print("\nDone!")
#!/usr/bin/env python3
"""
Fix digested.py to split banner embed from header embed
"""
import sys

# Read from backup
with open('cogs/digest.py.backup', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the section to replace
# The old pattern starts with the first comment "# Create header embed..."
# and ends just before the function definition "async def build_user_item_and_sale_embeds"

start_marker = '# Create header embed with briefing content (no image)'
end_marker = '\n            async def build_user_item_and_sale_embeds(self, user_id: int, embed_color: int):'

start_pos = content.find(start_marker)
if start_pos == -1:
    print("ERROR: Could not find start marker in digest.py.backup")
    sys.exit(1)

end_pos = content.find(end_marker, start_pos)
if end_pos == -1:
    print("ERROR: Could not find end marker in digest.py.backup")
    sys.exit(1)

# Extract the new code
new_code = '''# Create header embed with briefing content (no image)
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

# Replace in content
fixed_content = content[:start_pos] + new_code + content[end_pos:]

# Write to digest.py
with open('cogs/digest.py', 'w', encoding='utf-8') as f:
    f.write(fixed_content)

print(f"✓ Fixed digest.py (lines {start_pos+1}-{end_pos} replaced)")
print(f"  Total lines: {len(fixed_content.split(chr(10)))}")

# Verify syntax
import py_compile
try:
    py_compile.compile('cogs/digest.py', doraise=True)
    print("✓ Syntax check passed")
except SyntaxError as e:
    print(f"✗ Syntax error: {e}")
    sys.exit(1)
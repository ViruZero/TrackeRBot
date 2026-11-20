import discord
from discord.ext import commands

class Guide(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.guide_version = "v1.0" 

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            # Automatically find OR create the category
            category = discord.utils.get(guild.categories, name="commands-guide")
            if not category:
                category = await guild.create_category("commands-guide")
                # Automatically pin this category to the very top of the server
                try:
                    await category.edit(position=0)
                except Exception as e:
                    print(f"Could not reorder guide category: {e}")

            # Find or create the guide text channel inside that category
            channel = discord.utils.get(guild.text_channels, name="bot-guide", category=category)
            if not channel:
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(send_messages=False),
                    guild.me: discord.PermissionOverwrite(send_messages=True)
                }
                channel = await guild.create_text_channel("bot-guide", category=category, overwrites=overwrites)

            # Build the professional Guide Embed
            embed = discord.Embed(
                title="📚 TrackerPro Command Guide",
                description="Welcome to your automated shopping assistant! Here is the complete list of commands to manage your tracking ecosystem.",
                color=0x3498db
            )
            
            embed.add_field(
                name="⚙️ Account Setup", 
                value="`/register <name>`\nInitializes your private shopping channels. (Only used once in the gateway).", 
                inline=False
            )
            embed.add_field(
                name="🛒 Tracking", 
                value="`/track <url> <target_price>`\nAdds a product to your tracker. The bot checks it automatically.\n\n"
                      "`/untrack <item_id>`\nRemoves a specific item from your tracker.", 
                inline=False
            )
            embed.add_field(
                name="📋 Viewing Items", 
                value="`/items`\nLists all of your currently tracked items and their statuses.\n\n"
                      "`/items <item_id>`\nShows detailed info for a specific item, including 5-retailer comparison links.", 
                inline=False
            )
            embed.add_field(
                name="🔍 Manual Tools", 
                value="`/check <item_id>`\nRuns a manual check on a saved item by its ID.\n\n"
                      "`/search <query>`\nSearches Amazon and uses AI to recommend the top 3 matching products.", 
                inline=False
            )
            
            embed.set_footer(text=f"TrackerPro Guide | Version {self.guide_version}")

            # Check for an existing guide message to avoid duplicates
            bot_msg = None
            async for msg in channel.history(limit=10):
                if msg.author == self.bot.user:
                    bot_msg = msg
                    break
            
            if bot_msg:
                # Check if the version matches. If not, edit the message with the new update!
                current_footer = bot_msg.embeds[0].footer.text if bot_msg.embeds else ""
                if f"Version {self.guide_version}" not in current_footer:
                    await bot_msg.edit(embed=embed)
                    print("Command guide updated to new version.")
            else:
                # If no previous message exists, send it for the first time
                await channel.send(embed=embed)
                print("Initial command guide posted.")

async def setup(bot):
    await bot.add_cog(Guide(bot))
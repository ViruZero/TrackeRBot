import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()

class TrackerBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.default())

    async def setup_hook(self):
        await self.load_extension("cogs.search")
        await self.load_extension("cogs.check")
        await self.load_extension("cogs.tracker_price")
        await self.load_extension("cogs.register")
        await self.load_extension("cogs.digest")
        await self.load_extension("cogs.alert")
        await self.load_extension("cogs.guide")

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        try:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} slash command(s)")
        except Exception as e:
            print(f"Failed to sync commands: {e}")

if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("Error: DISCORD_TOKEN not found in .env file.")
    else:
        bot = TrackerBot()
        bot.run(token)
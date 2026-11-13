import os
import discord
from discord import app_commands
from discord.ext import commands
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'tracker.db')

class Register(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect(DB_PATH)
        self.c = self.conn.cursor()
        self.c.execute('''CREATE TABLE IF NOT EXISTS users
                         (user_id INTEGER PRIMARY KEY, prefix TEXT, 
                          shopping_channel_id INTEGER, digest_channel_id INTEGER, 
                          alerts_channel_id INTEGER)''')
        self.conn.commit()

    def cog_unload(self):
        self.conn.close()

    def sync_existing_channels(self, guild: discord.Guild):
        """Automatically restores existing user shopping categories into the users table on startup."""
        for category in guild.categories:
            if "'s Shopping" in category.name:
                shopping_ch = None
                digest_ch = None
                alerts_ch = None
                prefix = ""
                owner_id = None

                for ch in category.text_channels:
                    if ch.name.endswith("-shopping-bot"):
                        shopping_ch = ch
                        prefix = ch.name.replace("-shopping-bot", "")
                        for target, overwrite in ch.overwrites.items():
                            if isinstance(target, discord.Member) and not target.bot and overwrite.send_messages:
                                owner_id = target.id
                                break
                    elif ch.name.endswith("-daily-digests"):
                        digest_ch = ch
                    elif ch.name.endswith("-alerts"):
                        alerts_ch = ch

                if owner_id and shopping_ch and digest_ch and alerts_ch:
                    self.c.execute(
                        "INSERT OR IGNORE INTO users (user_id, prefix, shopping_channel_id, digest_channel_id, alerts_channel_id) VALUES (?, ?, ?, ?, ?)",
                        (owner_id, prefix, shopping_ch.id, digest_ch.id, alerts_ch.id)
                    )
        self.conn.commit()

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            self.sync_existing_channels(guild)

            # Updated to match your exact server channel name
            channel = discord.utils.get(guild.text_channels, name="registration")
            if channel:
                # Wipes all previous messages to remove clutter
                try:
                    await channel.purge(limit=100)
                except discord.Forbidden:
                    print(f"Missing 'Manage Messages' permission in {guild.name} to clear the registration channel.")
                
                # Posts a fresh instruction card
                embed = discord.Embed(
                    title="Welcome to the Tracker! 🛒",
                    description="To unlock the server and create your private shopping ecosystem, please register your account below.\n\n"
                                "**How to register:**\n"
                                "Type `/register` followed by your name.\n\n"
                                "**Example:** `/register ant`",
                    color=0x3498db
                )
                embed.set_footer(text="Your setup channels will be generated instantly.")
                await channel.send(embed=embed)

    @app_commands.command(name="register", description="Set up your private shopping and alert channels.")
    async def register(self, interaction: discord.Interaction, prefix: str):
        try:
            # Ephemeral ensures the command itself doesn't leave permanent chat logs
            await interaction.response.defer(ephemeral=True)
        except discord.errors.NotFound:
            return
        
        self.c.execute("SELECT * FROM users WHERE user_id=?", (interaction.user.id,))
        if self.c.fetchone():
            await interaction.followup.send("You already have an account set up!", ephemeral=True)
            return
            
        guild = interaction.guild
        verified_role = discord.utils.get(guild.roles, name="Verified")
        
        if verified_role:
            try:
                await interaction.user.add_roles(verified_role)
            except discord.Forbidden:
                await interaction.followup.send("⚠️ The bot is missing 'Manage Roles' permissions.", ephemeral=True)
                return
        else:
            await interaction.followup.send("⚠️ The 'Verified' role does not exist.", ephemeral=True)
            return
            
        category_name = f"{prefix.capitalize()}'s Shopping"
        
        ro_overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }
        
        rw_overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }
        
        category = await guild.create_category(category_name, overwrites=ro_overwrites)
        
        try:
            await category.edit(position=1)
        except Exception:
            pass
        
        digest_channel = await guild.create_text_channel(f"{prefix}-daily-digests", category=category, overwrites=ro_overwrites)
        shopping_channel = await guild.create_text_channel(f"{prefix}-shopping-bot", category=category, overwrites=rw_overwrites)
        alerts_channel = await guild.create_text_channel(f"{prefix}-alerts", category=category, overwrites=ro_overwrites)
        
        self.c.execute(
            "INSERT INTO users (user_id, prefix, shopping_channel_id, digest_channel_id, alerts_channel_id) VALUES (?, ?, ?, ?, ?)", 
            (interaction.user.id, prefix, shopping_channel.id, digest_channel.id, alerts_channel.id)
        )
        self.conn.commit()
        
        await interaction.followup.send(f"✅ Account created! Head over to {shopping_channel.mention} to start tracking.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Register(bot))
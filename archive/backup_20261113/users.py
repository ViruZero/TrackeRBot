import discord
from discord import app_commands
from discord.ext import commands
import sqlite3

class Users(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect('tracker.db')
        self.c = self.conn.cursor()
        
        self.c.execute('''CREATE TABLE IF NOT EXISTS users
                         (user_id INTEGER PRIMARY KEY, prefix TEXT, 
                          shopping_channel_id INTEGER, digest_channel_id INTEGER)''')
        self.conn.commit()

    @app_commands.command(name="register", description="Set up your private shopping and daily digest channels.")
    async def register(self, interaction: discord.Interaction, prefix: str):
        await interaction.response.defer()
        
        self.c.execute("SELECT * FROM users WHERE user_id=?", (interaction.user.id,))
        if self.c.fetchone():
            await interaction.followup.send("You already have an account set up!")
            return
            
        guild = interaction.guild
        
        # --- NEW: Assign the Verified Role ---
        verified_role = discord.utils.get(guild.roles, name="Verified")
        if verified_role:
            try:
                await interaction.user.add_roles(verified_role)
            except discord.Forbidden:
                await interaction.followup.send("⚠️ The bot is missing 'Manage Roles' permissions. I couldn't verify you.")
                return
        else:
            await interaction.followup.send("⚠️ The 'Verified' role does not exist in this server. Please create it first.")
            return
            
        category = discord.utils.get(guild.categories, name="Shopping Logs")
        if not category:
            category = await guild.create_category("Shopping Logs")
            
        shopping_overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }
        
        digest_overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }
        
        shopping_channel = await guild.create_text_channel(f"{prefix}-shopping", category=category, overwrites=shopping_overwrites)
        digest_channel = await guild.create_text_channel(f"{prefix}-daily-digests", category=category, overwrites=digest_overwrites)
        
        self.c.execute("INSERT INTO users VALUES (?, ?, ?, ?)", 
                       (interaction.user.id, prefix, shopping_channel.id, digest_channel.id))
        self.conn.commit()
        
        await interaction.followup.send(f"✅ Account created! Head over to {shopping_channel.mention} to start tracking.")

async def setup(bot):
    await bot.add_cog(Users(bot))
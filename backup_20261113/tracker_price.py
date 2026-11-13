from ai_helper import smart_ai_post
import os
import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
from urllib.parse import urlparse, quote_plus
import asyncio
import requests
from cogs.tracker_image import fetch_page_data, parse_with_ai

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'tracker.db')

class TrackerPrice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect(DB_PATH)
        self.c = self.conn.cursor()
        self.setup_database()

    def setup_database(self):
        # Create table with composite primary key (id, user_id) so each user has their own 1, 2, 3... IDs
        self.c.execute('''CREATE TABLE IF NOT EXISTS items
                         (id INTEGER, 
                          url TEXT, title TEXT, target_price REAL, 
                          original_price REAL, current_price REAL, 
                          image_url TEXT, user_id INTEGER,
                          PRIMARY KEY (id, user_id))''')
        
        # Check if existing table still uses old global AUTOINCREMENT schema and migrate it seamlessly
        self.c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='items'")
        row = self.c.fetchone()
        if row and "AUTOINCREMENT" in row[0].upper():
            print("Migrating items table to per-user IDs...")
            self.c.execute("ALTER TABLE items RENAME TO items_old")
            self.c.execute('''CREATE TABLE items
                             (id INTEGER, 
                              url TEXT, title TEXT, target_price REAL, 
                              original_price REAL, current_price REAL, 
                              image_url TEXT, user_id INTEGER,
                              PRIMARY KEY (id, user_id))''')
            
            self.c.execute("SELECT url, title, target_price, original_price, current_price, image_url, user_id FROM items_old ORDER BY id ASC")
            old_rows = self.c.fetchall()
            
            user_counters = {}
            for url, title, target_p, orig_p, curr_p, img, uid in old_rows:
                next_uid_id = user_counters.get(uid, 0) + 1
                user_counters[uid] = next_uid_id
                self.c.execute(
                    "INSERT INTO items (id, url, title, target_price, original_price, current_price, image_url, user_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (next_uid_id, url, title, target_p, orig_p, curr_p, img, uid)
                )
            self.c.execute("DROP TABLE items_old")
            print("Migration complete! Every user now starts at ID 1.")
            
        self.conn.commit()

    def cog_unload(self):
        self.conn.close()

    async def generate_comparison_links(self, full_title: str):
        prompt = "Take this messy e-commerce product title and extract just the core product name or model. Make it 4 words or less. Return ONLY the short name, nothing else.\n\nTitle: " + full_title
        payload = {"model": "llama3.1", "prompt": prompt, "stream": False}
        try:
            ai_resp = await asyncio.to_thread(smart_ai_post, "http://localhost:11434/api/generate", json=payload)
            short_name = ai_resp.json().get("response", "").strip()
        except Exception:
            short_name = full_title[:20] 
            
        encoded = quote_plus(short_name)
        return f"[AliExpress](https://www.aliexpress.com/w/wholesale-{encoded.replace('+', '-')}.html) | [Amazon](https://www.amazon.com/s?k={encoded}) | [Walmart](https://www.walmart.com/search?q={encoded}) | [Target](https://www.target.com/s?searchTerm={encoded}) | [eBay](https://www.ebay.com/sch/i.html?_nkw={encoded})"

    def generate_status(self, current, target, original):
        if current <= target:
            return "Under Target! 🚨"
        elif current < original:
            return "On Sale But Not Under 📉"
        else:
            return "Over Target 🔴"

    def build_item_embed(self, item_id, url, title, target_price, original_price, current_price, image_url, comparison_links):
        domain = urlparse(url).netloc.replace("www.", "")
        status = self.generate_status(current_price, target_price, original_price)
        
        embed = discord.Embed(title=f"Price Update: {title[:50]}...", url=url, color=0x2b2d31)
        embed.add_field(name="Direct Link", value=f"[Click Here to Buy]({url})", inline=True)
        embed.add_field(name="Current Price", value=f"${current_price:.2f}", inline=True)
        embed.add_field(name="Target Price", value=f"${target_price:.2f}", inline=True)
        embed.add_field(name="Retailer", value=domain.capitalize(), inline=True)
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True) 
        embed.add_field(name="Compare Prices", value=comparison_links, inline=False)
        
        if image_url:
            embed.set_thumbnail(url=image_url)
            
        embed.set_footer(text=f"Tracker Bot v3.0 | Item ID: {item_id}")
        return embed

    @app_commands.command(name="track", description="Track an item and alert when it hits your target price.")
    async def track(self, interaction: discord.Interaction, url: str, target_price: float):
        try:
            await interaction.response.defer()
        except discord.errors.NotFound:
            return
        
        self.c.execute("SELECT * FROM items WHERE url=? AND user_id=?", (url, interaction.user.id))
        if self.c.fetchone():
            await interaction.followup.send("You are already tracking this item!")
            return

        page_text, fetch_method, image_url = await fetch_page_data(url)
        if not page_text:
            await interaction.followup.send("Failed to fetch product page.")
            return
            
        title, current_price = await parse_with_ai(page_text)
        
        if current_price > 0:
            # 1. Fetch only THIS user's currently used IDs in order
            self.c.execute("SELECT id FROM items WHERE user_id=? ORDER BY id ASC", (interaction.user.id,))
            existing_ids = [row[0] for row in self.c.fetchall()]

            # 2. Find the lowest missing integer starting from 1 for THIS user
            item_id = 1
            for eid in existing_ids:
                if eid == item_id:
                    item_id += 1
                else:
                    break

            # 3. Insert with the user-specific item_id
            self.c.execute(
                """
                INSERT INTO items (id, url, title, target_price, original_price, current_price, image_url, user_id) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, 
                (item_id, url, title, target_price, current_price, current_price, image_url, interaction.user.id)
            )
            self.conn.commit()
            
            comparison_links = await self.generate_comparison_links(title)
            embed = self.build_item_embed(item_id, url, title, target_price, current_price, current_price, image_url, comparison_links)
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("Failed to extract price using Local AI.")

    @app_commands.command(name="items", description="List all tracking items, or view a specific one by ID.")
    async def list_items(self, interaction: discord.Interaction, item_id: int = None):
        try:
            await interaction.response.defer()
        except discord.errors.NotFound:
            return
        
        if item_id:
            self.c.execute("SELECT id, url, title, target_price, original_price, current_price, image_url FROM items WHERE id=? AND user_id=?", (item_id, interaction.user.id))
            item = self.c.fetchone()
            
            if not item:
                await interaction.followup.send(f"No item found with ID {item_id}.")
                return
                
            db_id, url, title, target, orig, curr, img = item
            comparison_links = await self.generate_comparison_links(title)
            embed = self.build_item_embed(db_id, url, title, target, orig, curr, img, comparison_links)
            await interaction.followup.send(embed=embed)
            
        else:
            self.c.execute("SELECT id, title, current_price, target_price FROM items WHERE user_id=? ORDER BY id ASC", (interaction.user.id,))
            items = self.c.fetchall()
            
            if not items:
                await interaction.followup.send("You are not tracking any items.")
                return
                
            embed = discord.Embed(title="Your Tracked Items", description="Use `/items <id>` to view full details.", color=0x3498db)
            for db_id, title, curr, target in items:
                status = self.generate_status(curr, target, curr)
                embed.add_field(name=f"ID {db_id}: {title[:40]}...", value=f"Current: ${curr:.2f} | Target: ${target:.2f}\nStatus: {status}", inline=False)
            await interaction.followup.send(embed=embed)

    @app_commands.command(name="untrack", description="Stop tracking an item by its ID.")
    async def untrack(self, interaction: discord.Interaction, item_id: int):
        self.c.execute("DELETE FROM items WHERE id=? AND user_id=?", (item_id, interaction.user.id))
        if self.c.rowcount == 0:
            await interaction.response.send_message(f"No item found with ID {item_id}.")
            return
            
        self.conn.commit()
        await interaction.response.send_message(f"Item ID {item_id} removed from tracker.")

async def setup(bot):
    await bot.add_cog(TrackerPrice(bot))
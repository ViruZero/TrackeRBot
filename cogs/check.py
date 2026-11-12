from ai_helper import smart_ai_post
import os
import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import asyncio
import requests
from urllib.parse import urlparse, quote_plus
from cogs.tracker_image import fetch_page_data, parse_with_ai

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'tracker.db')

class Check(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect(DB_PATH)
        self.c = self.conn.cursor()

    def cog_unload(self):
        self.conn.close()

    async def generate_comparison_links(self, full_title: str):
        prompt = "Take this messy e-commerce product title and extract just the core product name or model. Make it 4 words or less. Return ONLY the short name, nothing else.\n\nTitle: " + full_title
        payload = {"model": "llama3.1", "prompt": prompt, "stream": False}
        try:
            ai_resp = await asyncio.to_thread(smart_ai_post, "http://localhost:11434/api/generate", json=payload)
            short = ai_resp.json().get("response", "").strip()
        except Exception:
            short = full_title[:20] 
        encoded = quote_plus(short)
        return f"[AliExpress](https://www.aliexpress.com/w/wholesale-{encoded.replace('+', '-')}.html) | [Amazon](https://www.amazon.com/s?k={encoded}) | [Walmart](https://www.walmart.com/search?q={encoded}) | [Target](https://www.target.com/s?searchTerm={encoded}) | [eBay](https://www.ebay.com/sch/i.html?_nkw={encoded})"

    def generate_status(self, current, target, original):
        if current <= target:
            return "Under Target! 🚨"
        elif current < original:
            return "On Sale But Not Under 📉"
        else:
            return "Over Target 🔴"

    def build_item_embed(self, item_id, url, title, target_price, original_price, current_price, image_url, comparison_links, fetch_method):
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
            
        embed.set_footer(text=f"Tracker Bot v3.0 | Item ID: {item_id} | Engine: {fetch_method}")
        return embed

    @app_commands.command(name="check", description="Force a manual price check on a specific item by its ID.")
    async def check(self, interaction: discord.Interaction, item_id: int):
        try:
            await interaction.response.defer()
        except discord.errors.NotFound:
            return
        
        self.c.execute(
            "SELECT id, url, title, target_price, original_price, current_price, image_url FROM items WHERE id=? AND user_id=?",
            (item_id, interaction.user.id)
        )
        item = self.c.fetchone()
        
        if not item:
            await interaction.followup.send(f"No item found with ID {item_id}.")
            return
            
        db_id, url, title, target_price, original_price, old_price, image_url = item
        
        page_text, fetch_method, new_image = await fetch_page_data(url)
        if not page_text:
            await interaction.followup.send(f"Failed to fetch ID {item_id}. Anti-bot systems blocked both methods.")
            return
            
        _, new_price = await parse_with_ai(page_text)
        
        if new_price > 0:
            final_image = new_image if new_image else image_url
            if new_price != old_price or final_image != image_url:
                self.c.execute(
                    "UPDATE items SET current_price=?, image_url=? WHERE id=? AND user_id=?",
                    (new_price, final_image, db_id, interaction.user.id)
                )
                self.conn.commit()
                
            comparison_links = await self.generate_comparison_links(title)
            embed = self.build_item_embed(db_id, url, title, target_price, original_price, new_price, final_image, comparison_links, fetch_method)
            
            await interaction.followup.send(content="✅ **Manual Price Check Complete!**", embed=embed)
        else:
            await interaction.followup.send("Failed to extract the current price using Local AI.")

async def setup(bot):
    await bot.add_cog(Check(bot))
from ai_helper import smart_ai_post
import os
import discord
from discord import app_commands
from discord.ext import commands, tasks
import sqlite3
import datetime
import asyncio
import requests
from urllib.parse import quote_plus
from cogs.tracker_image import fetch_page_data, parse_with_ai

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'tracker.db')

class Alert(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect(DB_PATH)
        self.c = self.conn.cursor()
        self.scrape_routine.start()

    def cog_unload(self):
        self.scrape_routine.cancel()
        self.conn.close()

    tz = datetime.timezone(datetime.timedelta(hours=-5))
    times = [
        datetime.time(hour=8, minute=0, tzinfo=tz),
        datetime.time(hour=20, minute=0, tzinfo=tz)
    ]

    async def generate_comparison_links(self, full_title: str):
        prompt = "Take this messy e-commerce product title and extract just the core product name or model. Make it 4 words or less. Return ONLY the short name, nothing else.\n\nTitle: " + full_title
        payload = {"model": "qwen3.5:9b", "prompt": prompt, "stream": False}
        try:
            ai_resp = await asyncio.to_thread(smart_ai_post, "http://localhost:11434/api/generate", json=payload)
            short = ai_resp.json().get("response", "").strip()
        except Exception:
            short = full_title[:20] 
        encoded = quote_plus(short)
        return f"[AliExpress](https://www.aliexpress.com/w/wholesale-{encoded.replace('+', '-')}.html) | [Amazon](https://www.amazon.com/s?k={encoded}) | [Walmart](https://www.walmart.com/search?q={encoded}) | [Target](https://www.target.com/s?searchTerm={encoded}) | [eBay](https://www.ebay.com/sch/i.html?_nkw={encoded})"

    async def execute_market_scan(self) -> tuple[int, int]:
        """Runs the full market scan across all tracked items and returns (scanned_count, alerts_sent)."""
        print(f"\n[{datetime.datetime.now().strftime('%I:%M %p')}] Running Market Scan...")
        self.c.execute("SELECT id, url, title, target_price, original_price, current_price, image_url, user_id FROM items")
        items = self.c.fetchall()
        
        scanned_count = 0
        alerts_sent = 0

        for db_id, url, title, target_price, original_price, old_price, image_url, user_id in items:
            # 1. Fetch page with 1 automatic retry if proxy/browser times out
            page_text, fetch_method, new_image = await fetch_page_data(url)
            if not page_text:
                print(f"[Retry] Initial fetch failed for ID {db_id} ({title[:25]}...). Retrying in 5s...")
                await asyncio.sleep(5)
                page_text, fetch_method, new_image = await fetch_page_data(url)
                
            if not page_text:
                print(f"[Skip] Could not fetch ID {db_id} after retry. Keeping previous price (${old_price:.2f}).")
                await asyncio.sleep(4)
                continue
                
            _, new_price = await parse_with_ai(page_text)
            
            # 2. Sanity Guardrail: Ignore glitched scrapes (>85% sudden drop to an accessory/shipping fee)
            if old_price > 25 and 0 < new_price < (old_price * 0.15):
                print(f"[Sanity Block] Ignored suspicious price ${new_price:.2f} (was ${old_price:.2f}) for {title[:30]}...")
                await asyncio.sleep(4)
                continue

            scanned_count += 1
            print(f"[Scan] User {user_id} | ID {db_id} | Old: ${old_price:.2f} -> New: ${new_price:.2f} ({fetch_method})")
            
            if new_price > 0 and new_price != old_price:
                final_image = new_image if new_image else image_url
                self.c.execute(
                    "UPDATE items SET current_price=?, image_url=? WHERE id=? AND user_id=?",
                    (new_price, final_image, db_id, user_id)
                )
                self.conn.commit()
                
                if new_price < old_price:
                    drop_amount = original_price - new_price
                    drop_percent = (drop_amount / original_price) * 100 if original_price > 0 else 0
                    
                    hit_target = new_price <= target_price
                    major_sale = drop_percent >= 20.0
                    
                    if hit_target or major_sale:
                        try:
                            self.c.execute("SELECT alerts_channel_id FROM users WHERE user_id=?", (user_id,))
                            user_row = self.c.fetchone()
                            
                            if user_row:
                                alerts_channel = self.bot.get_channel(user_row[0])
                                if alerts_channel:
                                    links = await self.generate_comparison_links(title)
                                    
                                    if hit_target:
                                        ui_color = 0x2ecc71
                                        ui_header = "🎯 TARGET PRICE REACHED"
                                        msg = f"🚨 **TARGET REACHED!** <@{user_id}>"
                                    else:
                                        ui_color = 0x9b59b6
                                        ui_header = "⚡ FLASH SALE DETECTED"
                                        msg = f"🔥 **MAJOR SALE!** <@{user_id}>"

                                    embed = discord.Embed(title=f"Price Drop Alert: {title[:60]}...", url=url, color=ui_color)
                                    embed.set_author(name=ui_header)
                                    embed.add_field(name="Current Price", value=f"**${new_price:.2f}**", inline=True)
                                    embed.add_field(name="Discount", value=f"**{drop_percent:.0f}% OFF**", inline=True)
                                    embed.add_field(name="Savings", value=f"**-${drop_amount:.2f}**", inline=True)
                                    embed.add_field(name="Target Price", value=f"${target_price:.2f}", inline=True)
                                    embed.add_field(name="Original Price", value=f"~~${original_price:.2f}~~", inline=True)
                                    embed.add_field(name="\u200b", value="\u200b", inline=True) 
                                    embed.add_field(name="Compare Market", value=links, inline=False)
                                    
                                    if final_image:
                                        embed.set_thumbnail(url=final_image)
                                        
                                    embed.set_footer(text=f"TrackerPro Automated Market Watch | Item ID: {db_id}")
                                    await alerts_channel.send(content=msg, embed=embed)
                                    alerts_sent += 1
                        except Exception as e:
                            print(f"Alert Failed: {e}")

            # 3. Staggered pause between items so anti-bot systems don't flag rapid requests
            await asyncio.sleep(5)

        print("Market Scan complete!\n")
        return scanned_count, alerts_sent

    @app_commands.command(name="scan", description="[Owner Only] Force a full market scan across all tracked items.")
    @app_commands.default_permissions(administrator=True)
    async def manual_scan(self, interaction: discord.Interaction):
        if not interaction.guild or interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("⛔ Only the server owner can run a full market scan.", ephemeral=True)
            return

        try:
            await interaction.response.defer(ephemeral=True)
        except discord.errors.NotFound:
            return

        scanned, alerts = await self.execute_market_scan()
        await interaction.followup.send(
            f"✅ **Manual Market Scan Complete!**\n"
            f"• **Items Checked:** {scanned}\n"
            f"• **Price Drop Alerts Sent:** {alerts}",
            ephemeral=True
        )

    @tasks.loop(time=times)
    async def scrape_routine(self):
        await self.execute_market_scan()

    @scrape_routine.before_loop
    async def before_scrape_routine(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Alert(bot))

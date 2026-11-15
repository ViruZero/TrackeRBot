from ai_helper import smart_ai_post
import os
import tempfile
import uuid
import discord
from discord import app_commands, ui
from discord.ext import commands
import sqlite3
from urllib.parse import urlparse, urlunparse, quote_plus, parse_qsl, urlencode
import asyncio
import re
import traceback
import requests
from cogs.tracker_image import fetch_page_data, parse_with_ai
from cogs.items_banner import render_banner, THEME_LABELS

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'tracker.db')

def _shorten_url(url):
    """Return a Discord-API-safe URL of at most 512 characters, or None if it can't be shortened enough."""
    if not url or not isinstance(url, str):
        return None
    if len(url) <= 512:
        return url

    parsed = urlparse(url)

    # Amazon product URLs: rebuild as https://www.amazon.com/dp/<ASIN>/ keeping only the 'tag' param
    if 'amazon.' in parsed.netloc.lower():
        match = re.search(r'/dp/([A-Z0-9]{10})', parsed.path)
        if match:
            asin = match.group(1)
            short = f"https://www.amazon.com/dp/{asin}/"
            tag = dict(parse_qsl(parsed.query)).get('tag')
            if tag:
                short += f"?{urlencode({'tag': tag})}"
            return short if len(short) <= 512 else None

    # Otherwise strip the query string and fragment
    stripped = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
    return stripped if len(stripped) <= 512 else None

class TrackerPrice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect(DB_PATH)
        self.c = self.conn.cursor()
        self.setup_database()
        self.c.execute('''CREATE TABLE IF NOT EXISTS user_banners
                         (user_id INTEGER PRIMARY KEY,
                          theme TEXT NOT NULL DEFAULT 'pokeball')''')
        self.conn.commit()

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

    def _resolve_banner(self, user_id, fallback_name):
        self.c.execute("SELECT theme FROM user_banners WHERE user_id=?", (user_id,))
        row = self.c.fetchone()
        theme = row[0] if row else 'pokeball'

        self.c.execute("SELECT prefix FROM users WHERE user_id=?", (user_id,))
        row = self.c.fetchone()
        prefix = row[0] if row else None
        if prefix:
            if re.match(r'^[a-z]', prefix):
                name = prefix[0].upper() + prefix[1:]
            else:
                name = prefix
        else:
            name = fallback_name
        return (theme, name)

    def _make_banner_file(self, user_id, fallback_name):
        try:
            theme, name = self._resolve_banner(user_id, fallback_name)
            out_path = os.path.join(tempfile.gettempdir(), f'items_banner_{uuid.uuid4().hex}.png')
            render_banner(theme, name, out_path)
            return discord.File(out_path, filename='items_banner.png'), out_path
        except Exception:
            traceback.print_exc()
            return None, None

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

    @staticmethod
    def _valid_image_url(url):
        """Return True only for http(s) URLs ending in a Discord-supported image extension."""
        if not url or not isinstance(url, str):
            return False
        try:
            parsed = urlparse(url.strip())
        except Exception:
            return False
        if parsed.scheme not in ("http", "https"):
            return False
        return parsed.path.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))

    def _make_page_callback(self, custom_id):
        """Create a properly bound callback for a pagination button."""
        async def callback(interaction: discord.Interaction):
            await self._items_page_switch(interaction, custom_id)
        return callback

    def _build_items_layout(self, user_id, current_page, page_items, total_pages, with_banner: bool = True):
        """Build a Components V2 layout view for the items list."""
        lv = ui.LayoutView(timeout=None)
        container = ui.Container(accent_color=0x2b2d31)
        gallery = None
        if with_banner:
            gallery = ui.MediaGallery()
            gallery.add_item(media='attachment://items_banner.png')

        for item in page_items:
            db_id, url, title, curr, target, orig, img = item
            status = self.generate_status(curr, target, orig)
            display_title = title if len(title) <= 90 else title[:87] + "..."
            text = f"**#{db_id} - {display_title}**\n${curr:.2f}  |  Target ${target:.2f}"
            if self._valid_image_url(img):
                text += f"  •  [View]({url})  |  {status}"
                accessory = ui.Thumbnail(media=img)
            else:
                text += f"  |  {status}"
                short_url = _shorten_url(url)
                if short_url is not None:
                    accessory = ui.Button(label="View", style=discord.ButtonStyle.link, url=short_url)
                else:
                    accessory = ui.Button(label="View", style=discord.ButtonStyle.secondary, custom_id=f"items_goto_{user_id}_{db_id}")
                    accessory.callback = lambda interaction, full_url=url: interaction.response.send_message(full_url, ephemeral=True)
            container.add_item(ui.Section(ui.TextDisplay(text), accessory=accessory))

        prev_btn = ui.Button(label="Prev", style=discord.ButtonStyle.blurple, custom_id=f"items_prev_{user_id}_{current_page - 1}", disabled=(current_page == 1))
        prev_btn.callback = self._make_page_callback(prev_btn.custom_id)
        page_btn = ui.Button(label=f"Page {current_page} / {total_pages}", style=discord.ButtonStyle.gray, disabled=True)
        next_btn = ui.Button(label="Next", style=discord.ButtonStyle.primary, custom_id=f"items_next_{user_id}_{min(current_page + 1, total_pages)}", disabled=(current_page == total_pages))
        next_btn.callback = self._make_page_callback(next_btn.custom_id)
        container.add_item(ui.ActionRow(prev_btn, page_btn, next_btn))

        if gallery is not None:
            lv.add_item(gallery)
        lv.add_item(container)
        return lv

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
        
        if self._valid_image_url(image_url):
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
            try:
                await interaction.followup.send(embed=embed)
            except Exception as e:
                print(f"Failed to send item embed: {e}")
                try:
                    await interaction.followup.send("Failed to display item. Please try again.")
                except Exception:
                    pass
            
        else:
            self.c.execute("SELECT id, url, title, current_price, target_price, original_price, image_url FROM items WHERE user_id=? ORDER BY id ASC", (interaction.user.id,))
            items = self.c.fetchall()
            
            if not items:
                await interaction.followup.send("You are not tracking any items.")
                return
                
            total_pages = max(1, (len(items) + 9) // 10)
            current_page = 1
            
            # Calculate slice for current page (1-indexed in DB)
            start_idx = (current_page - 1) * 10
            end_idx = start_idx + 10
            page_items = items[start_idx:end_idx]
            
            banner_file, _banner_path = self._make_banner_file(interaction.user.id, interaction.user.display_name)
            layout = self._build_items_layout(interaction.user.id, current_page, page_items, total_pages, with_banner=banner_file is not None)

            try:
                if banner_file is not None:
                    await interaction.followup.send(view=layout, file=banner_file)
                else:
                    await interaction.followup.send(view=layout)
            except Exception as e:
                traceback.print_exc()
                print(f"Failed to send items layout: {e}", flush=True)
                try:
                    await interaction.followup.send("Failed to load your tracked items. Please try again.")
                except Exception:
                    pass
    
    async def _items_page_switch(self, interaction, custom_id):
        """Handle button clicks to switch pages"""
        try:
            # custom_id format: items_<direction>_<user_id>_<target_page>
            parts = custom_id.split("_")
            if len(parts) != 4:
                raise ValueError(f"Malformed custom_id: {custom_id}")
            user_id = int(parts[2])
            new_page = int(parts[3])

            # Verify the user owns this view and get their items
            if interaction.user.id != user_id:
                await interaction.response.send_message("This isn't your tracker view.", ephemeral=True)
                return

            self.c.execute("SELECT id, url, title, current_price, target_price, original_price, image_url FROM items WHERE user_id=? ORDER BY id ASC", (user_id,))
            all_items = self.c.fetchall()
            if not all_items:
                await interaction.response.send_message("No tracked items found.", ephemeral=True)
                return

            # Clamp the requested page (the button already encodes the target page)
            total_pages = max(1, (len(all_items) + 9) // 10)
            new_page = max(1, min(new_page, total_pages))

            # Get page slice
            start_idx = (new_page - 1) * 10
            end_idx = start_idx + 10
            page_items = all_items[start_idx:end_idx]

            layout = self._build_items_layout(user_id, new_page, page_items, total_pages, with_banner=True)
            try:
                await interaction.response.edit_message(view=layout)
            except Exception:
                await interaction.followup.send(view=layout)
        except Exception as e:
            print(f"Error handling page switch: {e}")
            try:
                await interaction.response.send_message("Error loading page. Try refreshing.", ephemeral=True)
            except Exception:
                try:
                    await interaction.followup.send("Error loading page. Try refreshing.", ephemeral=True)
                except Exception:
                    pass

    @app_commands.command(name="untrack", description="Stop tracking an item by its ID.")
    async def untrack(self, interaction: discord.Interaction, item_id: int):
        self.c.execute("DELETE FROM items WHERE id=? AND user_id=?", (item_id, interaction.user.id))
        if self.c.rowcount == 0:
            await interaction.response.send_message(f"No item found with ID {item_id}.")
            return
            
        self.conn.commit()
        await interaction.response.send_message(f"Item ID {item_id} removed from tracker.")

    @app_commands.command(name="theme", description="Pick the banner theme shown at the top of /items.")
    @app_commands.choices(choice=[app_commands.Choice(name=label, value=key) for key, label in THEME_LABELS.items()])
    async def theme(self, interaction: discord.Interaction, choice: app_commands.Choice[str]):
        await interaction.response.defer(ephemeral=True)
        try:
            self.c.execute("INSERT OR REPLACE INTO user_banners (user_id, theme) VALUES (?, ?)", (interaction.user.id, choice.value))
            self.conn.commit()
            await interaction.followup.send(f"Banner theme set to {choice.name}. Run /items to see it!", ephemeral=True)
        except Exception:
            traceback.print_exc()
            await interaction.followup.send("Failed to set banner theme. Please try again.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(TrackerPrice(bot))

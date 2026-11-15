import datetime
import discord
from discord import app_commands
from discord.ext import commands, tasks
import requests
import random
import sqlite3
import asyncio
from ai_helper import smart_ai_post
from holiday import get_holiday_info

EST_TZ = datetime.timezone(datetime.timedelta(hours=-5))

def get_philly_weather_forecast():
    """Fetches Philadelphia 3-hour interval weather from the free NWS API."""
    try:
        headers = {"User-Agent": "TrackerBot/1.0 (personal discord bot)"}
        pts_resp = requests.get("https://api.weather.gov/points/39.9526,-75.1652", headers=headers, timeout=8)
        if pts_resp.status_code != 200:
            return "Weather data currently unavailable."

        forecast_url = pts_resp.json()["properties"]["forecastHourly"]
        fc_resp = requests.get(forecast_url, headers=headers, timeout=8)
        if fc_resp.status_code != 200:
            return "Weather forecast offline."

        periods = fc_resp.json()["properties"]["periods"]
        sampled_periods = periods[::3][:6]

        weather_lines = []
        for idx, p in enumerate(sampled_periods):
            dt = datetime.datetime.fromisoformat(p["startTime"]).astimezone(EST_TZ)
            time_str = "Now" if idx == 0 else dt.strftime("%I%p").lstrip("0")
            temp = p["temperature"]
            short_desc = p["shortForecast"]
            is_day = p.get("isDaytime", True)

            d_lower = short_desc.lower()
            if "rain" in d_lower or "shower" in d_lower or "drizzle" in d_lower:
                emoji = "🌧️"
            elif "thunder" in d_lower or "storm" in d_lower:
                emoji = "⛈️"
            elif "snow" in d_lower or "ice" in d_lower or "sleet" in d_lower:
                emoji = "❄️"
            elif "partly" in d_lower or "mostly clear" in d_lower or "mostly sunny" in d_lower:
                emoji = "⛅" if is_day else "🌙"
            elif "sunny" in d_lower or "clear" in d_lower:
                emoji = "☀️" if is_day else "🌙"
            else:
                emoji = "☁️"

            weather_lines.append(f"`{time_str:>4}` {emoji} **{temp}°F** — {short_desc}")

        return "\n".join(weather_lines)
    except Exception as e:
        print(f"[Digest] Weather fetch error: {e}", flush=True)
        return "Weather data currently unavailable."


class Digest(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect("tracker.db", check_same_thread=False)
        self.c = self.conn.cursor()
        self.tz = EST_TZ
        self.daily_digest.start()

    def cog_unload(self):
        self.daily_digest.cancel()
        self.conn.close()

    async def build_briefing_embed(self):
        now = datetime.datetime.now(self.tz)
        date_str = now.strftime("%A, %B %d, %Y")

        holiday = get_holiday_info(now.date())
        weather_snippet = await asyncio.to_thread(get_philly_weather_forecast)
        THEMES = [
            "coffee", "sunrise", "walk", "rain", "coffee shop", "library", "park",
            "kitchen", "office", "gym", "road trip", "cooking", "baking", "reading",
            "writing", "music", "art", "painting", "gardening", "camping", "hiking",
            "stargazing", "morning pages", "journaling", "meditation", "stretching",
            "tea", "breakfast", "dinner party", "cleaning", "laundry", "commute"
        ]

        random.seed(now.timestamp())  # reproducible per day
        today_theme = random.choice(THEMES)

        quote = holiday["quote"]
        if not quote:
            quote_prompt = (
                f"Give me a short, unique, inspiring morning quote (1 sentence) about theme '{today_theme}' and date '{date_str}'. "
                "Return ONLY the quote text, no quotation marks or author needed."
            )
            quote_payload = {"model": "llama3.1", "prompt": quote_prompt, "stream": False}
            try:
                q_resp = await asyncio.to_thread(
                    smart_ai_post, "http://localhost:11434/api/generate", json=quote_payload, timeout=20
                )
                quote = q_resp.json().get("response", "").strip().strip('"')
            except Exception:
                today_doy = now.timetuple().tm_yday
                if today_doy % 10 == 0:
                    quote = f"Inspirational note for {date_str}: The best way to predict the future is to create it with today's theme of '{today_theme}'. 🔥"
                elif today_doy % 10 == 1:
                    quote = f"Morning wisdom: Embrace the day's theme — '{today_theme}' — and make every moment count. ✨"
                elif today_doy % 10 == 2:
                    quote = f"For {date_str}: Small steps in '{today_theme}' lead to big achievements. Keep going! 💪"
                elif today_doy % 10 == 3:
                    quote = f"The theme '{today_theme}' reminds us: Growth happens when we stretch beyond comfort zones. 🌱"
                elif today_doy % 10 == 4:
                    quote = f"Morning mantra: Today is a gift, themed '{today_theme}', to make the most of. 🎁"
                elif today_doy % 10 == 5:
                    quote = f"Wisdom for {date_str}: Let '{today_theme}' guide your heart and actions today. 💫"
                elif today_doy % 10 == 6:
                    quote = f"Daily spark: The theme '{today_theme}' means starting fresh with purpose every morning. 🌅"
                elif today_doy % 10 == 7:
                    quote = f"Quote for {date_str}: Focus on '{today_theme}', find joy in the simple moments. ☕"
                elif today_doy % 10 == 8:
                    quote = f"Inspiration: Today's theme '{today_theme}' shows us beauty is everywhere if we look. 🎨"
                elif today_doy % 10 == 9:
                    quote = f"Motivation for {date_str}: Let '{today_theme}' energize your day with fresh perspective. ⚡"
                else:
                    quote = "Rise and shine; today is yours to conquer."

        joke = holiday["joke"]
        if not joke:
            joke_prompt = (
                f"Tell me a short, clever, funny everyday joke about theme '{today_theme}' on date '{date_str}'. "
                "The joke must NOT be about programming or tech. "
                "Format it exactly as: 'Setup? ||Punchline||' where only the punchline is wrapped in double pipe spoiler markers."
            )
            joke_payload = {"model": "llama3.1", "prompt": joke_prompt, "stream": False}
            try:
                j_resp = await asyncio.to_thread(
                    smart_ai_post, "http://localhost:11434/api/generate", json=joke_payload, timeout=20
                )
                joke = j_resp.json().get("response", "").strip()
            except Exception:
                today_doy = now.timetuple().tm_yday
                if today_doy % 7 == 0:
                    joke = f"Why don't {today_theme} like to share? ||Because then it's not funny at all! 🤣||"
                elif today_doy % 7 == 1:
                    joke = f"What do you call a {today_theme} that tells secrets? ||A gossip {today_theme}! 😏||"
                elif today_doy % 7 == 2:
                    joke = f"A {today_theme}'s favorite hobby? ||Talking to itself in the mirror. 💬||"
                elif today_doy % 7 == 3:
                    joke = f"Why did the {today_theme} break up with algebra? ||It couldn't solve its own relationship! 🧮||"
                elif today_doy % 7 == 4:
                    joke = f"The {today_theme}'s favorite music is silence? ||Because noise ruins the vibes. 🎵||"
                elif today_doy % 7 == 5:
                    joke = f"What's a {today_theme}'s dream job? ||Juggling itself and laughing! 🤹||"
                else:
                    joke = f"Why did the {today_theme} walk into a library? ||To get some good stories and quiet fun! 📚||"

        # Parse the joke - extract only the punchline from ||...|| tags as requested
        import re
        joke_match = re.search(r'\|\|([^|]+)\|\|', joke)
        if joke_match:
            joke_answer = joke_match.group(1).strip()
            joke_setup = joke[:joke_match.start()].strip()
        else:
            # Fallback if no spoiler tags found - use full response as answer
            joke_answer = joke.strip().rstrip('?.!')
            joke_setup = joke.rstrip('?.!').split('?')[0].strip() + "?"

        header_embed = discord.Embed(
            title=f"{holiday['emoji']} {holiday['title_prefix']} — {date_str}",
            description=(
                f"Here is your morning overview, Philadelphia weather forecast, and price check summary.\n\n"
                f"💡 **Inspirational Quote of the Day**\n*{quote}*\n\n"
                f"😂 **Joke of the Day**\n{joke_setup}\n||{joke_answer}||\n\n"
                f"🌡️ **Philadelphia Weather (3-Hour Outlook)**\n{weather_snippet}"
            ),
            color=holiday["color"]
        )
        return header_embed, holiday

    async def build_user_item_and_sale_embeds(self, user_id: int, embed_color: int):
        self.c.execute(
            "SELECT title, url, current_price, target_price, original_price, image_url FROM items WHERE user_id = ?",
            (user_id,)
        )
        rows = self.c.fetchall()
        normal_embeds = []
        sale_items = []

        for title, url, current_price, target_price, original_price, image_url in rows:
            short_title = (title[:65] + "...") if title and len(title) > 68 else (title or "Tracked Item")
            base_price = original_price if (original_price and original_price > 0) else current_price

            is_on_sale = (
                current_price is not None
                and base_price is not None
                and current_price < base_price
            )

            if is_on_sale:
                pct_off = ((base_price - current_price) / base_price) * 100.0
                sale_items.append((short_title, url, current_price, target_price, base_price, image_url, pct_off))
            else:
                item_embed = discord.Embed(title=short_title, url=url, color=embed_color)
                item_embed.set_author(name="📊 TRACKING STATUS")
                price_str = f"${current_price:.2f}" if current_price is not None else "N/A"
                target_str = f"${target_price:.2f}" if target_price is not None else "N/A"
                item_embed.add_field(name="Price", value=f"**{price_str}**", inline=True)
                item_embed.add_field(name="Target", value=target_str, inline=True)
                if image_url and str(image_url).startswith("http"):
                    item_embed.set_thumbnail(url=image_url)
                normal_embeds.append(item_embed)

        sale_embeds = []
        if sale_items:
            # Find the highest percentage discount to classify the banner tier
            max_pct = max(item[6] for item in sale_items)
            top_item_name = sale_items[0][0][:30]

            if max_pct < 10.0:
                banner_title = "🏷️ MINI SALE / SMALL PRICE DROP DETECTED"
                banner_color = 0x5DADE2  # Soft Blue
                ai_prompt = (
                    f"The item '{top_item_name}' dropped in price by only {max_pct:.1f}%. "
                    f"Write 1 short, casual sentence noting that a mini sale or small price drop was detected, "
                    f"so it's a tiny dip worth keeping an eye on while waiting for a bigger drop."
                )
            elif max_pct <= 20.0:
                banner_title = "📉 ACTIVE SALES DETECTED"
                banner_color = 0x3498DB  # Bright Blue
                ai_prompt = (
                    f"The item '{top_item_name}' is on sale for {max_pct:.1f}% off! "
                    f"Write 1 upbeat, exciting sentence with a couple emojis letting the user know a solid sale is detected."
                )
            else:
                banner_title = "🔥🚨 MEGA SALE DETECTED 🚨🔥"
                banner_color = 0xE74C3C  # Hype Red/Orange
                ai_prompt = (
                    f"MEGA SALE! The item '{top_item_name}' just dropped by a massive {max_pct:.1f}% off! "
                    f"Write 1 super hyped, urgent sentence with fire and rocket emojis telling them to grab this MEGA Sale now!"
                )

            try:
                ai_payload = {"model": "llama3.1", "prompt": ai_prompt, "stream": False}
                ai_resp = await asyncio.to_thread(
                    smart_ai_post, "http://localhost:11434/api/generate", json=ai_payload, timeout=20
                )
                ai_analysis = ai_resp.json().get("response", "").strip().strip('"')
            except Exception:
                if max_pct < 10.0:
                    ai_analysis = f"A small price drop ({max_pct:.1f}% off) was detected—worth watching for a deeper discount!"
                elif max_pct <= 20.0:
                    ai_analysis = f"🔥 Nice sale detected ({max_pct:.1f}% off)—great time to check out this deal!"
                else:
                    ai_analysis = f"🔥🚀 MEGA SALE ({max_pct:.1f}% OFF)! Grab this deal before the price jumps back up! 🚀🔥"

            banner_embed = discord.Embed(
                title=banner_title,
                description=f"**AI Analysis:** {ai_analysis}",
                color=banner_color
            )
            sale_embeds.append(banner_embed)

            for short_title, url, current_price, target_price, base_price, image_url, pct_off in sale_items:
                if pct_off < 10.0:
                    tag_label = f"🛒 MINI SALE ({pct_off:.1f}% OFF)"
                elif pct_off <= 20.0:
                    tag_label = f"🛒 ON SALE ({pct_off:.1f}% OFF)"
                else:
                    tag_label = f"🔥 MEGA SALE ({pct_off:.1f}% OFF)"

                s_embed = discord.Embed(title=short_title, url=url, color=banner_color)
                s_embed.set_author(name=tag_label)
                s_embed.add_field(
                    name="Price",
                    value=f"~~${base_price:.2f}~~ **${current_price:.2f}**",
                    inline=True
                )
                s_embed.add_field(name="Target", value=f"${target_price:.2f}", inline=True)
                if image_url and str(image_url).startswith("http"):
                    s_embed.set_thumbnail(url=image_url)
                sale_embeds.append(s_embed)

        return normal_embeds + sale_embeds

    async def send_digest_for_user(self, channel, user_id: int, header_embed: discord.Embed, holiday: dict):
        item_embeds = await self.build_user_item_and_sale_embeds(user_id, holiday["color"])
        all_embeds = [header_embed] + item_embeds

        await channel.send(
            content=f"Good morning, <@{user_id}>! {holiday['emoji']}",
            embeds=all_embeds[:10]
        )
        for i in range(10, len(all_embeds), 10):
            await channel.send(embeds=all_embeds[i:i + 10])

    @app_commands.command(name="digest", description="Send your daily morning briefing and tracked item summary right now.")
    async def manual_digest(self, interaction: discord.Interaction):
        await interaction.response.defer()
        header_embed, holiday = await self.build_briefing_embed()
        item_embeds = await self.build_user_item_and_sale_embeds(interaction.user.id, holiday["color"])
        all_embeds = [header_embed] + item_embeds

        await interaction.followup.send(
            content=f"Good morning, {interaction.user.mention}! {holiday['emoji']}",
            embeds=all_embeds[:10]
        )
        for i in range(10, len(all_embeds), 10):
            await interaction.channel.send(embeds=all_embeds[i:i + 10])

    @app_commands.command(name="digest_all", description="Trigger the daily digest across all users' digest channels immediately.")
    async def manual_digest_all(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.run_all_digests()
        await interaction.followup.send("✅ Dispatched daily digests to all registered digest channels!", ephemeral=True)

    async def run_all_digests(self):
        self.c.execute("SELECT user_id, digest_channel_id FROM users WHERE digest_channel_id IS NOT NULL")
        users = self.c.fetchall()
        print(f"[Digest] Found {len(users)} users with registered digest channels.", flush=True)

        for user_id, channel_id in users:
            ch = self.bot.get_channel(channel_id)
            if ch is None:
                try:
                    ch = await self.bot.fetch_channel(channel_id)
                except Exception as e:
                    print(f"[Digest] Could not fetch channel {channel_id} for user {user_id}: {e}", flush=True)
                    continue

            try:
                header_embed, holiday = await self.build_briefing_embed()
                await self.send_digest_for_user(ch, user_id, header_embed, holiday)
                print(f"[Digest] Sent digest to channel {channel_id} for user {user_id}", flush=True)
            except Exception as e:
                print(f"[Digest] Error sending digest for user {user_id}: {e}", flush=True)

    # Locked in to 8:30 AM EST every morning
    @tasks.loop(time=datetime.time(hour=8, minute=30, tzinfo=EST_TZ))
    async def daily_digest(self):
        print(f"[Digest] Scheduled daily digest triggered at {datetime.datetime.now(self.tz)}", flush=True)
        await self.run_all_digests()

    @daily_digest.before_loop
    async def before_daily_digest(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(Digest(bot))

from ai_helper import smart_ai_post
import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import os
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import urllib.parse

class Search(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def fetch_page_text(self, url: str):
        page_text = ""
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.set_extra_http_headers({
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                })
                
                response = await page.goto(url, wait_until="domcontentloaded", timeout=10000)
                if response and response.status in [403, 429, 503]:
                    raise Exception(f"Blocked (Status {response.status})")
                    
                await asyncio.sleep(2)
                page_text = await page.evaluate("document.body.innerText")
                await browser.close()
        except Exception as e:
            page_text = ""

        if not page_text or len(page_text) < 500:
            try:
                zenrows_key = os.getenv("ZENROWS_API_KEY")
                proxy = f"http://{zenrows_key}:js_render=true&antibot=true&premium_proxy=true@proxy.zenrows.com:8001"
                proxies = {"http": proxy, "https": proxy}
                
                resp = await asyncio.to_thread(requests.get, url, proxies=proxies, verify=False, timeout=60)
                soup = BeautifulSoup(resp.text, "html.parser")
                for tag in soup(["script", "style", "noscript"]):
                    tag.decompose()
                page_text = soup.get_text(separator=" ", strip=True)
            except Exception:
                return ""
                
        return page_text

    @app_commands.command(name="search", description="Search for a product and get top recommendations.")
    async def search(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        
        search_url = f"https://www.amazon.com/s?k={urllib.parse.quote_plus(query)}"
        page_text = await self.fetch_page_text(search_url)
        
        if not page_text:
            await interaction.followup.send("Failed to load search results.")
            return

        prompt = (
            f"I searched an online store for '{query}'. Based on the following raw webpage text, "
            "identify the top 3 best matching products and their prices. "
            "Format the output strictly as a bulleted list with the Product Name and Price.\n\n"
            f"Text: {page_text[:15000]}" 
        )
        payload = {"model": "qwen3.5:9b", "prompt": prompt, "stream": False}
        
        try:
            ai_response = await asyncio.to_thread(smart_ai_post, "http://localhost:11434/api/generate", json=payload)
            recommendations = ai_response.json().get("response", "").strip()
            
            embed = discord.Embed(title=f"Top Recommendations for: {query}", description=recommendations, color=0xf1c40f)
            embed.add_field(name="Search Link", value=f"[View on Amazon]({search_url})", inline=False)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"Local AI Error: {e}")

async def setup(bot):
    await bot.add_cog(Search(bot))

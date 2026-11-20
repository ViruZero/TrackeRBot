"""AliExpress fetching: accept product prices, never prices from unrelated text."""

import asyncio
import json
import math
import os
import re
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

PRICE_SELECTOR = (
    '[data-pl="product-price"], [class*="price--currentPriceText"], '
    '[class*="price-default--current"], [class*="product-price-current"]'
)
RESULT_PREFIX = "ALIEXPRESS_PRODUCT:"


def is_aliexpress_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower()
    return any(host == domain or host.endswith("." + domain)
               for domain in ("aliexpress.com", "aliexpress.us"))


def extract_product(html, url):
    """Return a single USD price, title and image; reject walls and ambiguity."""
    soup = BeautifulSoup(html, "html.parser")
    if any(marker in (html + " " + url).lower() for marker in (
        "captcharecaptcha", "action=captcha", "_____tmd_____", "/punish?",
        "slide to verify", "verify you are human", "access denied",
        "unusual traffic from your computer",
    )):
        return None

    requested_sku = parse_qs(urlparse(url).query).get("sku_id", [])
    requested_sku += parse_qs(urlparse(url).query).get("skuId", [])
    title_tag = soup.select_one('h1, meta[property="og:title"], title')
    title = (title_tag.get("content") or title_tag.get_text(" ", strip=True)) if title_tag else ""
    image_tag = soup.select_one('meta[property="og:image"]')
    image = image_tag.get("content", "") if image_tag else ""

    def positive(value):
        try:
            number = float(value)
            return number if math.isfinite(number) and number > 0 else 0
        except (ValueError, TypeError):
            return 0

    def nodes(value):
        if isinstance(value, list):
            for entry in value:
                yield from nodes(entry)
        elif isinstance(value, dict):
            yield value
            yield from nodes(value.get("@graph", []))

    # Read actual Product offers, not arbitrary price keys or recommendation lists.
    products = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            products.extend(node for node in nodes(json.loads(script.get_text()))
                            if "Product" in ([node.get("@type")] if isinstance(node.get("@type"), str)
                                             else node.get("@type", [])))
        except (ValueError, TypeError):
            continue
    product_id = re.search(r'/item/(\d+)\.html', urlparse(url).path)
    prices = []
    for product in products:
        product_url = str(product.get("url", ""))
        if product_id and product_url and not re.search(
                r'/item/' + product_id.group(1) + r'\.html(?:[?#]|$)', product_url):
            continue
        if len(products) > 1 and not product_url:
            continue
        offers = product.get("offers", [])
        offers = [offers] if isinstance(offers, dict) else offers
        if not isinstance(offers, list):
            continue
        for offer in offers:
            if not isinstance(offer, dict) or offer.get("priceCurrency") != "USD":
                continue
            if requested_sku and str(offer.get("sku", product.get("sku", ""))) not in requested_sku:
                continue
            price = positive(offer.get("price"))
            if price:
                prices.append((price, str(product.get("name") or title), image))
    if prices and len({p[0] for p in prices}) == 1:
        price, name, image = prices[0]
        if name:
            return {"title": name, "price": price, "image": image}

    # A generic buybox cannot prove that a requested SKU was actually selected.
    if requested_sku or prices:
        return None
    dom_prices = set()
    currency_tag = soup.select_one('meta[property="product:price:currency"], meta[itemprop="priceCurrency"]')
    currency = currency_tag.get("content", "") if currency_tag else ""
    for element in soup.select(PRICE_SELECTOR):
        value = "".join(element.stripped_strings).replace("\xa0", " ")
        if currency == "USD" and value.strip().startswith("$"):
            value = "US" + value.strip()
        match = re.fullmatch(r'\s*(?:US\s*\$|USD\s*\$?)\s*(\d+(?:,\d{3})*(?:\.\d{1,2})?)\s*', value)
        if match:
            price = positive(match.group(1).replace(",", ""))
            if price:
                dom_prices.add(price)
    if title and len(dom_prices) == 1:
        return {"title": title, "price": dom_prices.pop(), "image": image}
    return None


async def fetch_product(url):
    """Try one browser request and each configured provider, stopping on a price."""
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                context = await browser.new_context(locale="en-US")
                page = await context.new_page()
                response = await page.goto(url, wait_until="domcontentloaded", timeout=25000)
                if response and response.ok:
                    try:
                        await page.wait_for_selector(PRICE_SELECTOR, timeout=10000)
                    except Exception:
                        pass  # Structured offers may exist without a visible buybox.
                    product = extract_product(await page.content(), url)
                    if product and is_aliexpress_url(page.url):
                        return _result(product, "Playwright")
            finally:
                await browser.close()
    except Exception:
        print("[AliExpress] Local browser unavailable or price not accessible.")

    providers = []
    if os.getenv("ZENROWS_API_KEY"):
        providers.append(("ZenRows rendered", "https://api.zenrows.com/v1/", {
            "apikey": os.environ["ZENROWS_API_KEY"], "url": url,
            "js_render": "true", "premium_proxy": "true",
            "proxy_country": "us", "wait": "4000",
        }))
    if os.getenv("SCRAPFLY_API_KEY") and os.getenv("ALIEXPRESS_SCRAPFLY_ENABLED", "true").lower() == "true":
        providers.append(("Scrapfly rendered", "https://api.scrapfly.io/scrape", {
            "key": os.environ["SCRAPFLY_API_KEY"], "url": url,
            "asp": "true", "render_js": "true", "country": "us",
            "rendering_wait": "4000",
        }))
    for name, endpoint, params in providers:
        try:
            response = await asyncio.to_thread(requests.get, endpoint, params=params, timeout=120)
            response.raise_for_status()
            html = response.text
            if name.startswith("Scrapfly"):
                result = response.json().get("result", {})
                if result.get("status_code", 200) != 200:
                    continue
                html = result.get("content", "")
            product = extract_product(html, url)
            if product:
                return _result(product, name)
            print(f"[AliExpress] {name}: no unambiguous USD product price; trying next provider.")
        except Exception:
            # Provider exceptions can contain API keys in their request URLs.
            print(f"[AliExpress] {name}: request failed; trying next provider.")
    return "", "AliExpress price unavailable", ""


def _result(product, method):
    return RESULT_PREFIX + json.dumps(product), method, product["image"]

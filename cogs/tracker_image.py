from ai_helper import smart_ai_post
import asyncio
import os
import re
import json
import requests
import urllib3
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from dotenv import load_dotenv

try:
    from curl_cffi import requests as cffi_requests
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False

load_dotenv()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def clean_product_url(url: str) -> str:
    """Strips tracking parameters, analytics bloat, and query strings from URLs."""
    parsed = urlparse(url)
    netloc = parsed.netloc.lower()
    path = parsed.path

    if "aliexpress." in netloc:
        match = re.search(r'/item/(\d+)\.html', path)
        if match:
            return f"https://www.aliexpress.us/item/{match.group(1)}.html"

    return f"{parsed.scheme}://{netloc}{path}"

def is_blocked_page(html_content: str, body_text: str, current_url: str = "") -> bool:
    """Detects Akamai, Cloudflare, Amazon Captcha, and AliExpress slider block pages."""
    lower_html = html_content.lower()
    lower_body = body_text.lower()
    
    block_phrases = [
        "access denied",
        "errors.edgesuite.net",
        "reference #",
        "enter the characters you see below",
        "slide to verify",
        "unusual traffic from your computer",
        "verify you are human",
        "pardon our interruption"
    ]
    for phrase in block_phrases:
        if phrase in lower_body or phrase in lower_html:
            return True

    if "punish" in current_url.lower() or "login.aliexpress" in current_url.lower():
        return True

    if len(html_content) < 2500 or len(body_text.strip()) < 300:
        return True

    return False

def extract_product_image(html_content: str) -> str:
    """Extracts the primary product image URL from HTML without touching price logic."""
    soup = BeautifulSoup(html_content, "html.parser")

    for prop in ["og:image", "twitter:image"]:
        meta = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
        if meta and meta.get("content"):
            content = meta["content"].strip()
            if content.startswith("http"):
                return content
            elif content.startswith("//"):
                return "https:" + content
            elif content.startswith("/") and "rei.com" in html_content.lower():
                return "https://www.rei.com" + content

    for selector in [
        "#landingImage", "#imgBlkFront", "#main-image", "#imgTagWrapperId img",
        ".magnifier-image", "[class*='image-view'] img", "[class*='slider--img'] img",
        "[itemprop='image']"
    ]:
        try:
            img = soup.select_one(selector)
        except Exception:
            continue
        if img:
            old_hires = img.get("data-old-hires", "").strip()
            if old_hires.startswith("http"):
                return old_hires

            dyn_img = img.get("data-a-dynamic-image", "")
            if dyn_img:
                urls = re.findall(r'"(https://[^"]+)"', dyn_img)
                if urls:
                    return urls[0]

            src = img.get("src", "").strip()
            if src.startswith("http"):
                return src
            elif src.startswith("//"):
                return "https:" + src

    for pattern in [
        r'"hiRes"\s*:\s*"(https://m\.media-amazon\.com/images/I/[^"]+)"',
        r'"large"\s*:\s*"(https://m\.media-amazon\.com/images/I/[^"]+)"',
        r'"imagePathList"\s*:\s*\[\s*"(https://[^"]+alicdn\.com[^"]+)"',
        r'(https://ae01\.alicdn\.com/kf/[A-Za-z0-9]+\.(?:jpg|png|webp))'
    ]:
        match = re.search(pattern, html_content)
        if match:
            return match.group(1)

    return ""

def extract_price_hints(html_content: str) -> tuple[str, float]:
    """Pulls structured prices directly from HTML before tags are stripped."""
    soup = BeautifulSoup(html_content, "html.parser")
    hints = []
    locked_price = 0.0

    def parse_num(val_str: str) -> float:
        match = re.search(r'(\d+(?:,\d{3})*(?:\.\d{2})?)', val_str)
        if match:
            try:
                return float(match.group(1).replace(',', ''))
            except ValueError:
                pass
        return 0.0

    primary_selectors = [
        "#apex-pricetopay-accessibility-label",
        "[data-cel-widget='corePriceDisplay_desktop_feature_div'] .aok-offscreen",
        "span.priceToPay",
        "span.apex-pricetopay-value",
        "#corePriceDisplay_desktop_feature_div .priceToPay",
        "#corePrice_feature_div .a-price",
        "#priceblock_ourprice",
        "#priceblock_dealprice",
        "#buy-box-product-price",
        "[data-ui='sale-price']",
        "[data-ui='full-price']",
        "[itemprop='price']",
        ".product-price-value",
        "[data-pl='product-price']",
        "[class*='price--currentPriceText']",
        "[class*='price-default--current']",
        "[class*='es--wrap']",
        "[class*='product-price-current']",
        ".product-price-current",
        "[class*='sale-price']"
    ]
    
    for selector in primary_selectors:
        try:
            elements = soup.select(selector)
        except Exception:
            continue
        for el in elements:
            text = ""
            joined_t = "".join(el.stripped_strings) or el.get("content", "")
            
            whole = el.select_one(".a-price-whole")
            frac = el.select_one(".a-price-fraction")
            sym = el.select_one(".a-price-symbol")
            if whole and frac:
                w_text = re.sub(r'[^\d]', '', whole.get_text(strip=True))
                f_text = re.sub(r'[^\d]', '', frac.get_text(strip=True))
                s_text = sym.get_text(strip=True) if sym else "$"
                if w_text and f_text:
                    text = f"{s_text}{w_text}.{f_text}"
            elif re.search(r'\d', joined_t):
                text = joined_t
                
            if text:
                val = parse_num(text)
                if val > 0:
                    hints.append(f"PRIMARY BUYBOX PRICE ({selector}): {text}")
                    if locked_price == 0.0 and not re.search(r'\b(NGN|INR|MXN|TRY|BRL|EUR|GBP|CAD|AUD|JPY)\b', text, re.IGNORECASE):
                        locked_price = val
                    break

    if soup.title and soup.title.string:
        title_str = soup.title.string.strip()
        if "access denied" not in title_str.lower():
            hints.append(f"Page Title: {title_str}")
            title_price = re.search(r'(?:US\s*\$\s*(\d+\.?\d*)|(\d+\.\d{2})\s*US\s*\$|\$\s*(\d+\.\d{2}))', title_str, re.IGNORECASE)
            if title_price:
                matched_str = title_price.group(1) or title_price.group(2) or title_price.group(3)
                val = parse_num(matched_str)
                if val > 0 and locked_price == 0.0:
                    hints.append(f"Title Price Signal: ${val}")
                    locked_price = val

    for prop in ["product:price:amount", "og:price:amount", "twitter:data1", "og:title", "description"]:
        meta = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
        if meta and meta.get("content"):
            content = meta["content"]
            if prop in ["og:title", "description"]:
                meta_p = re.search(r'(?:US\s*\$|\$)\s*(\d+(?:\.\d{2})?)', content, re.IGNORECASE)
                if meta_p:
                    val = parse_num(meta_p.group(1))
                    if val > 0:
                        hints.append(f"Meta Text Price ({prop}): ${val}")
                        if locked_price == 0.0:
                            locked_price = val
            else:
                val = parse_num(content)
                if val > 0:
                    hints.append(f"Meta Price ({prop}): {content}")
                    if locked_price == 0.0:
                        locked_price = val

    for script in soup.find_all("script", type="application/ld+json"):
        if script.string and "price" in script.string.lower():
            matches = re.findall(r'"(?:price|lowPrice)"\s*:\s*"?(\d+\.?\d*)"?', script.string, re.IGNORECASE)
            if matches:
                hints.append(f"Structured Data Prices: {', '.join(matches[:5])}")
                val = parse_num(matches[0])
                if val > 0 and locked_price == 0.0:
                    locked_price = val

    json_patterns = [
        r'"formatedActivityPrice"\s*:\s*"(?:US\s*)?\$\s*(\d+(?:\.\d{2})?)"',
        r'"formatedPrice"\s*:\s*"(?:US\s*)?\$\s*(\d+(?:\.\d{2})?)"',
        r'"targetSalePrice"\s*:\s*"(\d+(?:\.\d{2})?)"',
        r'"minActivityAmount"\s*:\s*\{\s*"value"\s*:\s*(\d+(?:\.\d+)?)',
        r'"discountPrice"\s*:\s*\{\s*"minActivityAmount"\s*:\s*\{\s*"value"\s*:\s*(\d+(?:\.\d+)?)',
        r'"actMinPrice"\s*:\s*"(\d+\.\d{2})"',
        r'"minPrice"\s*:\s*"(\d+\.\d{2})"',
        r'"salePrice"\s*:\s*\{\s*"min"\s*:\s*(\d+(?:\.\d+)?)',
        r'"salePrice"\s*:\s*"?(\d+\.\d{2})"?',
        r'"regularPrice"\s*:\s*"?(\d+\.\d{2})"?',
        r'US\s*\$\s*(\d+\.\d{2})'
    ]
    for pat in json_patterns:
        m = re.search(pat, html_content)
        if m:
            val = parse_num(m.group(1))
            if val > 0:
                hints.append(f"Embedded Script Price: ${val:.2f}")
                if locked_price == 0.0:
                    locked_price = val
                break

    return "\n".join(hints), locked_price

async def fetch_rei_direct(target_url: str):
    """Fetches REI product details via REI's lightweight JSON endpoints or Visible Chrome to bypass Akamai headless blocks."""
    prod_match = re.search(r'/product/(\d+)', target_url)
    if prod_match and HAS_CURL_CFFI:
        prod_id = prod_match.group(1)
        api_urls = [
            f"https://www.rei.com/rest/products/{prod_id}",
            f"https://www.rei.com/ product/{prod_id}".replace(" ", "")
        ]
        for browser_fp in ["chrome120", "safari15_5", "chrome110"]:
            try:
                resp = await asyncio.to_thread(
                    cffi_requests.get,
                    api_urls[0],
                    impersonate=browser_fp,
                    headers={"Accept": "application/json", "Referer": target_url},
                    timeout=10
                )
                if resp.status_code == 200 and "title" in resp.text.lower():
                    data = resp.json()
                    title = f"{data.get('brand', {}).get('name', '')} {data.get('title', '')}".strip()
                    price = 0.0
                    # Extract price from REI JSON structure
                    price_str = json.dumps(data)
                    m = re.search(r'"(?:salePrice|min|price)"\s*:\s*(\d+(?:\.\d{1,2})?)', price_str)
                    if m:
                        price = float(m.group(1))
                    img_m = re.search(r'"(?:heroImageUrl|uri|url)"\s*:\s*"([^"]+/media/[^"]+)"', price_str)
                    img = ""
                    if img_m:
                        img = img_m.group(1)
                        if img.startswith("/"):
                            img = "https://www.rei.com" + img
                    if price > 0 and title:
                        combined = f"LOCKED_PRICE:{price}\n--- HIGH PRIORITY PRICE SIGNALS ---\nPage Title: {title}\nPRIMARY BUYBOX PRICE: ${price:.2f}\n\n--- WEBPAGE TEXT ---\n{title} ${price:.2f}"
                        return combined, f"REI Direct JSON ({browser_fp} - Free)", img
            except Exception:
                continue
    return "", "", ""

async def fetch_page_data(url: str):
    target_url = clean_product_url(url)
    is_aliexpress = "aliexpress." in target_url.lower()
    is_rei = "rei.com" in target_url.lower()

    page_text = ""
    fetch_method = "Unknown"
    image_url = ""
    price_hints = ""
    locked_price = 0.0

    # 0. Fast REI JSON API Check
    if is_rei:
        rei_text, rei_method, rei_img = await fetch_rei_direct(target_url)
        if rei_text:
            return rei_text, rei_method, rei_img

    # 1. Fast TLS Impersonation via curl_cffi (Tests multiple browser fingerprints)
    if HAS_CURL_CFFI and not is_aliexpress:
        for fp in ["safari15_5", "chrome120", "chrome110"]:
            try:
                cffi_headers = {
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                }
                resp = await asyncio.to_thread(
                    cffi_requests.get,
                    target_url,
                    impersonate=fp,
                    headers=cffi_headers,
                    timeout=12
                )
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for tag in soup(["script", "style", "noscript"]):
                        tag.decompose()
                    candidate_text = soup.get_text(separator=" ", strip=True)

                    if not is_blocked_page(resp.text, candidate_text, target_url):
                        price_hints, locked_price = extract_price_hints(resp.text)
                        image_url = extract_product_image(resp.text)
                        page_text = candidate_text
                        fetch_method = f"curl_cffi ({fp} - Free)"
                        break
                else:
                    print(f"curl_cffi ({fp}) status: {resp.status_code}")
            except Exception as e:
                print(f"curl_cffi ({fp}) skipped: {e}")

    # 2. Local Playwright (Uses NON-HEADLESS minimized real Chrome for REI so Akamai sees a real GPU/Browser)
    if not page_text:
        extra_headers = {"Accept-Language": "en-US,en;q=0.9"}
        if is_aliexpress:
            extra_headers["Cookie"] = "i18n-prefs=USD; lc-main=en_US; aep_usuc_f=site=usa&c_tp=USD&region=US&b_locale=en_US;"

        try:
            async with async_playwright() as p:
                if is_rei:
                    # Akamai blocks ALL headless browsers; launching real Chrome with headless=True off-screen passes Akamai 100%
                    try:
                        browser = await p.chromium.launch(
                            channel="chrome",
                            headless=True,
                            args=[
                                "--disable-blink-features=AutomationControlled",
                                "--window-position=-32000,-32000",
                                "--window-size=1280,800"
                            ]
                        )
                    except Exception:
                        browser = await p.chromium.launch(
                            headless=True,
                            args=[
                                "--disable-blink-features=AutomationControlled",
                                "--window-position=-32000,-32000",
                                "--window-size=1280,800"
                            ]
                        )
                else:
                    browser = await p.chromium.launch(
                        headless=True,
                        args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
                    )

                context = await browser.new_context(
                    locale="en-US",
                    timezone_id="America/New_York",
                    extra_http_headers=extra_headers,
                    viewport={"width": 1280, "height": 800}
                )
                await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                page = await context.new_page()
                
                response = await page.goto(target_url, wait_until="domcontentloaded", timeout=20000)
                if response and response.status in [403, 429, 503]:
                    await browser.close()
                    raise Exception(f"Blocked (Status {response.status})")
                    
                if is_aliexpress:
                    try:
                        await page.wait_for_selector("[data-pl='product-price'], [class*='price--current'], [class*='es--wrap']", timeout=6000)
                    except Exception:
                        await asyncio.sleep(4)
                else:
                    await asyncio.sleep(2)

                html_content = await page.content()
                
                dom_price_text = await page.evaluate("""
                    () => {
                        let el = document.querySelector("[data-pl='product-price'], [class*='price--currentPriceText'], [class*='price-default--current'], [class*='es--wrap'], #buy-box-product-price, [data-ui='sale-price']");
                        return el ? el.textContent.replace(/\\s+/g, '') : '';
                    }
                """)
                body_text = await page.evaluate("document.body ? document.body.innerText : ''")
                current_url = page.url
                await browser.close()

                if is_blocked_page(html_content, body_text, current_url):
                    raise Exception("Anti-Bot / Access Denied Wall Detected")
                    
                price_hints, locked_price = extract_price_hints(html_content)
                if dom_price_text and locked_price == 0.0:
                    m = re.search(r'(\d+(?:,\d{3})*(?:\.\d{2})?)', dom_price_text)
                    if m:
                        locked_price = float(m.group(1).replace(',', ''))
                        price_hints = f"DOM PRICE ELEMENT: {dom_price_text}\n" + price_hints

                image_url = extract_product_image(html_content)
                page_text = body_text

                if is_aliexpress and locked_price == 0.0 and not re.search(r'\$\s*\d+', page_text):
                    raise Exception("AliExpress dynamic price not rendered locally")
                
                fetch_method = "Playwright (Local - Free)"
        except Exception as e:
            print(f"Local Playwright failed: {e}. Falling back to ZenRows API...")
            page_text = ""

    # 3. ZenRows Adaptive Stealth Mode (mode=auto) + Scrapfly Akamai Fallback
    if not page_text:
        zenrows_key = os.getenv("ZENROWS_API_KEY")
        if zenrows_key:
            try:
                # NOTE: mode=auto automatically manages js_render and premium_proxy.
                # Passing js_render or premium_proxy alongside mode=auto causes a 400 error.
                params = {
                    "url": target_url,
                    "apikey": zenrows_key,
                    "mode": "auto",
                    "proxy_country": "us"
                }
                if is_aliexpress:
                    params["wait"] = "4000"

                print(f"[ZenRows] Fetching {target_url[:55]} with Adaptive Stealth Mode (mode=auto)...", flush=True)
                resp = await asyncio.to_thread(
                    requests.get, "https://api.zenrows.com/v1/", params=params, timeout=120
                )

                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for tag in soup(["script", "style", "noscript"]):
                        tag.decompose()
                    candidate_text = soup.get_text(separator=" ", strip=True)

                    if not is_blocked_page(resp.text, candidate_text, target_url):
                        price_hints, locked_price = extract_price_hints(resp.text)
                        image_url = extract_product_image(resp.text)
                        page_text = candidate_text
                        cost = resp.headers.get("X-Request-Cost", "?")
                        fetch_method = f"ZenRows Auto (Cost: {cost})"
                    else:
                        print(f"[ZenRows] 200 OK but content matched block filter for {target_url[:55]}", flush=True)
                else:
                    print(f"[ZenRows] mode=auto returned Status {resp.status_code}: {resp.text[:180]}", flush=True)
            except Exception as e:
                print(f"[ZenRows] Fallback error: {e}", flush=True)

    # 4. Scrapfly Fallback (Specialized Akamai / DataDome Bypass)
    if not page_text:
        scrapfly_key = os.getenv("SCRAPFLY_API_KEY")
        if scrapfly_key:
            try:
                sf_params = {
                    "key": scrapfly_key,
                    "url": target_url,
                    "asp": "true",
                    "render_js": "true",
                    "country": "us",
                    "retry": "true"
                }
                print(f"[Scrapfly] ZenRows failed. Escalating {target_url[:55]} to Scrapfly ASP...", flush=True)
                sf_resp = await asyncio.to_thread(
                    requests.get, "https://api.scrapfly.io/scrape", params=sf_params, timeout=120
                )
                if sf_resp.status_code == 200:
                    sf_data = sf_resp.json()
                    html_content = sf_data.get("result", {}).get("content", "")
                    if html_content:
                        soup = BeautifulSoup(html_content, "html.parser")
                        for tag in soup(["script", "style", "noscript"]):
                            tag.decompose()
                        candidate_text = soup.get_text(separator=" ", strip=True)

                        if not is_blocked_page(html_content, candidate_text, target_url):
                            price_hints, locked_price = extract_price_hints(html_content)
                            image_url = extract_product_image(html_content)
                            page_text = candidate_text
                            fetch_method = "Scrapfly (ASP Akamai Bypass)"
                            print(f"[Scrapfly] Successfully bypassed Akamai for {target_url[:55]}!", flush=True)
                else:
                    print(f"[Scrapfly] Returned Status {sf_resp.status_code}: {sf_resp.text[:180]}", flush=True)
            except Exception as e:
                print(f"[Scrapfly] Fallback error: {e}", flush=True)

    if page_text and price_hints:
        page_text = f"HIGH PRIORITY PRICE SIGNALS:\n{price_hints}\n\nPAGE CONTENT:\n{page_text}"
    hint_count = len(price_hints.splitlines()) if price_hints else 0
    print(f"price_hints populated: {hint_count} entries", flush=True)
    if locked_price and locked_price > 0:
        page_text = f"LOCKED_PRICE:{locked_price}\n" + page_text
        print(f"locked_price extracted: {locked_price}", flush=True)

    return page_text, fetch_method, image_url


async def parse_with_ai(text: str):
    locked_price = 0.0
    if text.startswith("LOCKED_PRICE:"):
        first_line, text = text.split("\n", 1)
        try:
            locked_price = float(first_line.replace("LOCKED_PRICE:", "").strip())
        except Exception:
            locked_price = 0.0

    dollar_snippets = re.findall(r'.{0,60}\$\s?\d+(?:,\d{3})*(?:\.\d{2})?.{0,60}', text)
    if not dollar_snippets and locked_price <= 0:
        print("--- AI GUARDRAIL: No dollar prices found in page text. Aborting to prevent AI hallucination. ---", flush=True)
        print("--- AI GUARDRAIL: No dollar prices found, locked_price=", locked_price, flush=True)
        return "Unknown Product", 0.0

    focused_prices = "\n".join(dollar_snippets[:25])

    prompt = (
        "You are a precision e-commerce price extractor.\n"
        "Determine the main product title and the single current US Dollar ($ USD) purchase price of that main product.\n"
        "CRITICAL RULE: NEVER invent or guess a product name or price (such as 'Apple iPhone 13'). If the product price is missing, return price 0.0.\n"
        "1. PRIORITIZE 'PRIMARY BUYBOX PRICE', 'DOM PRICE ELEMENT', 'Title Price Signal', or 'Embedded Script Price' in 'HIGH PRIORITY PRICE SIGNALS' first.\n"
        "2. Ignore 'List Price', crossed-out prices, shipping fees, and other items down the page.\n"
        "3. Output strictly valid JSON with keys 'title' (string) and 'price' (float).\n\n"
        f"DETECTED DOLLAR MATCHES:\n{focused_prices}\n\n"
        f"PAGE CONTENT:\n{text[:3500]}"
    )

    payload = {
        "model": "llama3.1",
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.0, "top_p": 0.1}
    }

    try:
        ai_response = await asyncio.to_thread(
            smart_ai_post, "http://localhost:11434/api/generate", json=payload, timeout=30
        )
        raw_response = ai_response.json().get("response", "").strip()
        print(f"Raw AI Output: {raw_response}", flush=True)
        try:
            data = json.loads(raw_response)
            print(f"JSON parse result: {data}", flush=True)
        except Exception as je:
            print(f"JSON parse result: error: {je}", flush=True)
            m = re.search(r'\{.*\}', raw_response, re.DOTALL)
            try:
                data = json.loads(m.group(0)) if m else {}
                print(f"JSON parse result (regex fallback): {data}", flush=True)
            except Exception as e:
                print(f"JSON parse result: error: {e}", flush=True)
                data = {}

        title = str(data.get("title") or "Unknown Product").strip()
        raw_price_val = data.get("price", 0.0)
        if isinstance(raw_price_val, str):
            raw_price = re.sub(r'[^0-9.]', '', raw_price_val)
            ai_price = float(raw_price) if raw_price else 0.0
        else:
            ai_price = float(raw_price_val or 0.0)

        final_price = locked_price if (locked_price and locked_price > 0) else ai_price
        return title, final_price
    except Exception as e:
        print(f"Local AI Error: {e}", flush=True)
        return "Unknown Product", (locked_price if locked_price > 0 else 0.0)

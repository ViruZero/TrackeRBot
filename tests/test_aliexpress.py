import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from cogs.aliexpress import extract_product, fetch_product, is_aliexpress_url, RESULT_PREFIX
from cogs.tracker_image import clean_product_url, fetch_page_data, parse_with_ai


URL = "https://www.aliexpress.com/item/3256812732025510.html"


def product_html(price="16.92", currency="USD", **extra):
    product = {"@type": "Product", "name": "Monitor stand", "url": URL,
               "offers": {"@type": "Offer", "price": price, "priceCurrency": currency}}
    product.update(extra)
    return '<script type="application/ld+json">' + json.dumps(product) + '</script>'


class ExtractionTests(unittest.TestCase):
    def test_preserves_domain_variant_and_region(self):
        url = URL + "?sku_id=123&shipFromCountry=US&spm=tracking#details"
        self.assertEqual(clean_product_url(url), url.split("#")[0])

    def test_domain_check(self):
        self.assertTrue(is_aliexpress_url(URL))
        self.assertTrue(is_aliexpress_url(URL.replace(".com", ".us")))
        for url in ["https://aliexpress.com.attacker.org", "https://example.com/aliexpress.com", "file://aliexpress.com/item"]:
            self.assertFalse(is_aliexpress_url(url))

    def test_short_structured_page_is_valid(self):
        self.assertEqual(extract_product(product_html(), URL)["price"], 16.92)

    def test_captcha_with_price_is_rejected(self):
        self.assertIsNone(extract_product(product_html() + "action=captcharecaptcha", URL))

    def test_shipping_and_recommendation_text_are_not_prices(self):
        self.assertIsNone(extract_product('<title>Stand</title><p>Shipping US $2.99</p><script>window.runParams={}</script>', URL))

    def test_invalid_and_foreign_prices(self):
        for value in ["nan", "inf", "-1", "0", "10-20"]:
            self.assertIsNone(extract_product(product_html(value), URL))
        self.assertIsNone(extract_product(product_html(currency="CAD"), URL))

    def test_selected_sku_must_match(self):
        url = URL + "?sku_id=123"
        self.assertIsNone(extract_product(product_html(), url))
        self.assertIsNone(extract_product(product_html(sku="456"), url))
        self.assertEqual(extract_product(product_html(sku="123"), url)["price"], 16.92)

    def test_different_product_is_rejected(self):
        self.assertIsNone(extract_product(product_html(url=URL.replace("3256812732025510", "123")), URL))

    def test_multiple_offers_are_not_silently_minimized(self):
        offers = [{"price": value, "priceCurrency": "USD"} for value in [10, 20]]
        self.assertIsNone(extract_product(product_html(offers=offers), URL))

    def test_dom_price_currency_and_range(self):
        for text, expected in [("US $16.92", 16.92), ("US $10 - US $20", None), ("C$16.92", None), ("$16.92", None)]:
            html = f'<h1>Monitor stand</h1><span class="price-default--current--abc">{text}</span>'
            result = extract_product(html, URL)
            self.assertEqual(result["price"] if result else None, expected)
        html = '<h1>Stand</h1><meta property="product:price:currency" content="USD"><span class="price-default--current">$16.92</span>'
        self.assertEqual(extract_product(html, URL)["price"], 16.92)


class FetchTests(unittest.IsolatedAsyncioTestCase):
    async def test_browser_success_closes_browser_and_skips_paid_calls(self):
        page = AsyncMock()
        page.goto.return_value = MagicMock(ok=True)
        page.content.return_value = product_html()
        page.url = URL
        context = AsyncMock()
        context.new_page.return_value = page
        browser = AsyncMock()
        browser.new_context.return_value = context
        playwright = MagicMock()
        playwright.chromium.launch = AsyncMock(return_value=browser)
        manager = MagicMock()
        manager.__aenter__ = AsyncMock(return_value=playwright)
        manager.__aexit__ = AsyncMock()
        with patch("cogs.aliexpress.async_playwright", return_value=manager), \
             patch("cogs.aliexpress.requests.get", side_effect=AssertionError("No paid call")):
            text, method, _ = await fetch_product(URL)
            self.assertEqual(method, "Playwright")
            self.assertTrue(text.startswith(RESULT_PREFIX))
            browser.close.assert_awaited_once()

    async def test_missing_price_falls_through_to_scrapfly_without_ai(self):
        browser_context = MagicMock()
        browser_context.__aenter__ = AsyncMock(side_effect=RuntimeError("Browser unavailable"))
        browser_context.__aexit__ = AsyncMock()
        shell = MagicMock(text='<title>Stand</title><script>window.runParams={}</script>')
        good = MagicMock()
        good.json.return_value = {"result": {"status_code": 200, "content": product_html()}}
        with patch.dict("os.environ", {"ZENROWS_API_KEY": "test", "SCRAPFLY_API_KEY": "test"}, clear=True), \
             patch("cogs.aliexpress.async_playwright", return_value=browser_context), \
             patch("cogs.aliexpress.requests.get", side_effect=[shell, good]) as get, \
             patch("cogs.tracker_image.smart_ai_post", side_effect=AssertionError("AI must not run")):
            text, method, _ = await fetch_page_data(URL)
            self.assertTrue(text.startswith(RESULT_PREFIX))
            self.assertEqual(method, "Scrapfly rendered")
            self.assertEqual(await parse_with_ai(text), ("Monitor stand", 16.92))
            self.assertEqual(get.call_count, 2)
            params = get.call_args_list[0].kwargs["params"]
            self.assertNotIn("mode", params)
            self.assertEqual(params["js_render"], "true")
            self.assertEqual(params["url"], URL)

    async def test_opt_out_and_no_price_return_failure(self):
        context = MagicMock()
        context.__aenter__ = AsyncMock(side_effect=RuntimeError("Browser unavailable"))
        context.__aexit__ = AsyncMock()
        shell = MagicMock(text="captcha")
        with patch.dict("os.environ", {"ZENROWS_API_KEY": "test", "SCRAPFLY_API_KEY": "test", "ALIEXPRESS_SCRAPFLY_ENABLED": "false"}, clear=True), \
             patch("cogs.aliexpress.async_playwright", return_value=context), \
             patch("cogs.aliexpress.requests.get", return_value=shell) as get:
            text, _, _ = await fetch_product(URL)
            self.assertEqual(text, "")
            self.assertEqual(get.call_count, 1)


if __name__ == "__main__":
    unittest.main()

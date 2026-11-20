# AliExpress tracking

AliExpress `.com` and `.us` requests use `cogs/aliexpress.py`, routed from
`fetch_page_data`. Other retailers retain the existing fetch pipeline.

The supplied domain and query parameters are preserved, including SKU and
shipping selections. Only the fragment is removed.

## Fetch order

1. Local Playwright Chromium, waiting for the price element before extraction.
2. ZenRows when `ZENROWS_API_KEY` is set, using explicit JavaScript rendering,
   premium proxy, US proxy location, and a four-second render wait. This request
   does not combine rendering flags with `mode=auto`.
3. Scrapfly when `SCRAPFLY_API_KEY` is set, using ASP and JavaScript rendering.
   Set `ALIEXPRESS_SCRAPFLY_ENABLED=false` to skip this fallback and save credits.

Each configured provider receives at most one request per fetch invocation.
Existing scheduled scan retries can invoke the entire chain again. Paid
provider requests consume the corresponding account credits.

Provider options follow the [ZenRows developer reference](https://www.zenrows.com/for/developers)
and [Scrapfly SDK reference](https://scrapfly.github.io/python-scrapfly/scrapfly/scrape_config.html).

Install requirements and the local browser in the bot environment:

```sh
python -m pip install -r requirements.txt
python -m playwright install chromium
```

## Price acceptance

HTTP 200 alone is insufficient. A response must contain a Product JSON-LD USD
offer or a single explicit USD current-price element. Bare dollar DOM prices
require USD currency metadata. Shipping text, unrelated products, price ranges,
nonpositive/nonfinite prices, and CAPTCHA pages are rejected. Short valid
structured pages are accepted without a minimum body length.

When `sku_id` or `skuId` is supplied, the structured offer/product must confirm
that SKU. A generic buybox is not assumed to represent the requested variant.
Unsupported variant formats may therefore fail safely. Login-only, promotional,
and personalized prices are not guaranteed. Page schemas can change.

Verified product data bypasses AI extraction. If all providers fail to supply
a verifiable price, `/track` explains the failure and does not add an item.
Existing checks retain the previous price. Screenshot upload is not supported.

## Verification

Run offline regression tests from the repository root:

```sh
python -m unittest discover -s tests -v
```

Fixtures are synthetic and provider calls are mocked; no API credits are spent.
These tests establish parser and fallback behavior, not live CAPTCHA bypass.
Live success still needs checking in the configured server environment.

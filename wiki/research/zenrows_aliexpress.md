# ZenRows autoparse on AliExpress (2026-11-18)

Diagnostic run from Oracle (`oracle-bot`), single `autoparse=true` request each (~0.001 credit, "costs 0 extra" per ZenRows docs), key never printed.

Target item: `3256812732025510` (Dual Monitor Stand, aliexpress.us)

- `https://www.aliexpress.us/item/3256812732025510.html` → HTTP 200, ~2.9KB JSON list. Parsed content is `ItemDetailResp`: extParams, i18nMap, imagePathList/summImagePathList (ae-pic-a1 CDN URLs + slug), name, showMainImage. **Zero** occurrences of `price`/`Price`/`sku`/item_id. No `sale_price`.
- `https://www.aliexpress.us/w/wholesale-3256812732025510.html` → HTTP 200, identical ~2.9KB `ItemDetailResp` payload. Also **no** `products[].item_id`, **no** `products[].sale_price` despite the theory that wholesale pages server-render them.

Conclusions:
- ZenRows `autoparse=true` does NOT surface the current sale_price for this item on either URL. Autoparse extracts PDP metadata (images, i18n) only.
- Combined with the 2026-11-18 js_render+premium_proxy re-test (empty `window.runParams={}`, `action=captcharecaptcha`), AliExpress price remains unavailable via plain ZenRows paths as of this date.
- Do NOT wire autoparse into the TrackerPro AliExpress handler expecting a price — it will always miss. Remaining options: screenshot /track flow, Scrapfly ASP, or manual price entry.

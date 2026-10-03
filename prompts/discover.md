# Discover agent: find every brand that sells the product

Inputs (from the orchestrator): PRODUCT, MARKET, SCOPE (`local` or `global`), B2B (yes/no), OUT (file path), CHECK (command).

Task:
- **SCOPE = local:** find EVERY seller/brand of PRODUCT in MARKET. Cover:
  - specialist Shopify stores and brand sites
  - big retailers and marketplaces (Amazon, eBay, Google Shopping, local chains)
  - private/white-label sellers (e.g. VEVOR-style generic brands)
  - resellers that carry several brands (note which brands they carry)
- **SCOPE = global:** find every significant brand of PRODUCT in the US, Canada, UK, EU and Asia,
  including Amazon white-labels and the factories' own brands.
- **If B2B = yes:** also find the commercial/industrial version of the product and its suppliers
  (the high-value arm a consumer search misses).

Aim for completeness over depth. Don't trace manufacturers yet; that's the next stage.

Write OUT as:
```json
{"brands": [
  {"brand": "Name", "country": "AU", "url": "https://...", "arm": "consumer|b2b|both",
   "is_current_supplier": false, "note": "one line: what they sell / price range"}
]}
```
Then run CHECK. Reply with one line.

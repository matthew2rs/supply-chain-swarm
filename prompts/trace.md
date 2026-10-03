# Trace agent: brand -> who manufactures it

Inputs: PRODUCT, MARKET, BRANDS (a list), OUT, CHECK.

For EACH brand in BRANDS, find who manufactures its PRODUCT. Try these in order, and stop when you have high-confidence evidence:
1. **The brand's own pages:** site, FAQ, manual, warranty PDF, about page, image filenames, "made in" wording.
2. **The product feed:** for Shopify, the vendor field, SKUs and barcodes.
3. **Exact-phrase search:** search 1-2 distinctive sentences or spec strings from the brand's
   product copy, in quotes, on Alibaba, Made-in-China and Google.
4. **ImportYeti public page** for US brands: `https://www.importyeti.com/company/<slug>`.
5. **EU listings:** the GPSR manufacturer block, for EU-sold brands.
6. **Trademark / business-register owner** of the brand.

One row per brand. Add a second row if a brand clearly uses two factories. If a brand turns out
not to sell PRODUCT, skip it.

Write OUT as:
```json
{"rows": [{
  "brand": "", "brand_country": "", "brand_url": "", "arm": "consumer|b2b|both",
  "product_types": "", "price_signal": "retail price range + currency",
  "manufacturer": "Factory legal name, or Unknown", "manufacturer_country": "", "manufacturer_url": "",
  "confidence": "high|medium|low",
  "oem_approachable": "yes/no/unknown + why (will this factory make it under the user's own brand?)",
  "moq_signal": "", "evidence_type": "", "evidence": "what links them, specifically", "evidence_url": ""
}], "new_brands": ["other sellers you noticed that weren't in your list"]}
```
Then run CHECK (kind `pool`). Reply with one line.

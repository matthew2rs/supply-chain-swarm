# Anchor agent: what the user sells today

Inputs: PRODUCT, MARKET, STORE (the user's store URL, may be blank), SUPPLIERS (brands the user resells, may be blank), OUT_JSON, OUT_MD, CHECK.

This is the back-test. The swarm only works if it can find who makes what the user already sells.

1. If STORE is given, list every PRODUCT item on it: title, sizes, price, the vendor/brand field,
   SKUs and barcodes.
   - On Shopify, use `/products.json?limit=250`. It is rate-limited, so go slow and fall back to
     `/sitemap_products_1.xml` plus `/products/<handle>.js`.
2. For each brand the user resells (from STORE and from SUPPLIERS), collect what you can about the brand-owner:
   - legal entity and business number
   - address
   - "designed in / made in" wording
   - spec strings, carton sizes and model numbers (these are the fingerprints for matching factories later)
3. Write OUT_JSON in the discover format, with `"is_current_supplier": true` on those brands:
   `{"brands": [{"brand": "...", "country": "...", "url": "...", "arm": "consumer", "is_current_supplier": true, "note": "..."}]}`
4. Write OUT_MD: a short markdown note listing what the user sells today and the fingerprints per brand.

Run CHECK on OUT_JSON. Reply with one line.

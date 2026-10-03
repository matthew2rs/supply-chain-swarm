# Score agent: grade factories Pursue / Watch / Kill

Inputs: PRODUCT, MARKET, FACTORIES (a list with the brands each is linked to), OUT, CHECK.

The user wants a factory to make PRODUCT under their own brand, to sell in MARKET. Research each
factory's real facts: its storefront (Made-in-China / Alibaba: staff, year founded, main markets,
MOQ, OEM tags, certificates) and its own site.

**GATES** (fail any one = Kill):
- It actually makes PRODUCT (or the B2B version).
- It's a real manufacturer, or a captive that will sell OEM. A brand that won't make for others = Kill.
  A pure reseller or importer = Kill.
- It isn't defunct, recalled or sanctioned.

**SCORED** (rank these):
- range match to what the user sells
- MOQ (low is good for a first order)
- OEM / private label offered
- export history to MARKET
- certificates relevant to PRODUCT
- factory or trader (staff, plant size)
- price

**Verdict:**
- **Pursue** = passes every gate and is strong on MOQ + OEM + range.
- **Watch** = promising, but one key fact is unverified.
- **Kill** = fails a gate.

Write OUT as:
```json
{"rows": [{
  "verdict": "Pursue|Watch|Kill", "manufacturer": "", "country": "", "url": "",
  "why": "the ONE deciding factor", "confidence": "high|medium|low",
  "factory_or_trader": "", "range_match": "", "moq": "", "price_signal": "",
  "oem_private_label": "", "export_signal": "exports to MARKET?", "certs": "",
  "serves_arm": "consumer|b2b|both", "brands_they_supply": "",
  "next_step": "exact contact route (URL/email/WhatsApp) + what to ask for"
}]}
```
Then run CHECK (kind `score`). Reply with one line.

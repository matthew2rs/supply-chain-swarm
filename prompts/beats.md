# Beat agents: one search angle each, across the whole category

Inputs: PRODUCT, MARKET, BEAT (one of the three below), KNOWN_BRANDS, OUT, CHECK.
The output format is the same as the trace agent (`{"rows": [...], "new_brands": [...]}`, kind `pool`).

## BEAT = customs
Use US customs records, which are public. They name the factory behind US brands.
1. Open ImportYeti public company pages for the US brands in KNOWN_BRANDS:
   `https://www.importyeti.com/company/<slug>`. Find their suppliers whose goods description matches PRODUCT.
2. For each factory found, open its `/supplier/<slug>` page and list every other brand it ships to.
   This builds the factory -> brand graph.
3. Use ImportGenius public pages as a fallback.
4. Put the shipment count and the last shipment date in the evidence.
5. If you're blocked (403 or captcha), record what you couldn't reach and move on.

## BEAT = eu-gpsr
EU law now makes listings name the manufacturer. Search EU marketplaces and specialist shops for
PRODUCT in German, French, Dutch and Italian:
- bol.com "Fabrikant"
- Amazon.de / .fr / .it "Herstellerinformationen"
- specialist retailers

Record each brand -> named manufacturer + address. Target 15+ distinct pairs. These are
high-confidence links. Mark a manufacturer that's obviously a reseller or importer as such.

## BEAT = copy-match
For the brands in KNOWN_BRANDS that are sold in MARKET:
1. Take 2-3 distinctive product sentences and exact dimension/spec strings for each brand.
2. Search them in quotes on Google, Alibaba, Made-in-China, Tradewheel and AliExpress.
3. Report which factory listings share copy, images or specs with which brand. These are medium
   confidence unless the factory names the brand.
4. A factory listing that reuses a brand's own wording is the strongest lead for brands with no customs trail.

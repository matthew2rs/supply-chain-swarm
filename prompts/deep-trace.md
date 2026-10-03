# Deep-trace agent: who makes the user's current suppliers' products

Inputs: PRODUCT, MARKET, SUPPLIERS (the brands the user resells today, with fingerprints from the anchor note), ANCHOR_NOTE (path), OUT_MD, OUT_CHECKLIST.

The user wants to stop reselling these brands and import their own, so this is the most valuable
page in the output. Work it hard, one brand at a time, starting with their biggest supplier.

**For each supplier, investigate:**
- **The brand-owner:** legal entity, business number and trademark records. Is it a manufacturer
  with its own factory, or a pure importer? Read their corporate brochure if they have one.
- **Their own documents:** launch date, brochure/manual PDFs (and the PDF metadata), YouTube
  descriptions, image filenames.
- **Copy trail:** who copied whom? Compare the wording and specs with other brands and with
  factory listings.
- **Factory listings:** shapes, sizes, colours, fittings (D-rings, valves, handles), weights and
  pack sizes.
- **Import records:** where reachable.

**Be honest about what is proven and what is only suggested.** A copied sentence is a lead, not proof.

**Write OUT_MD (markdown) with:**
1. **Bottom line:** the most likely factory for each supplier, a confidence, and why.
2. **The evidence table:** finding | evidence type | source URL.
3. **What blocked you.**
4. **The exact next step:** a ready-to-send quote request (RFQ) to the 3-4 most likely factories.
   - Quote the supplier's exact specs, so a factory that already makes it recognises the product.
   - Ask for real factory photos, MOQ, prices at 10/50/100, lead time and test reports.
   - Ask "have you made this for the [MARKET] market before?"

**Write OUT_CHECKLIST (markdown):** a numbered 12-shot photo checklist the user should take of
their own stock to confirm the factory:
- carton shipping marks, "MADE IN", item codes
- QC / inspection slips
- valve or fitting brand
- fabric or material print
- barcode (a `69` prefix means it was registered in China)
- pump or accessory labels
- anything else specific to PRODUCT

End the checklist with what each clue tells them.

Reply with one line.

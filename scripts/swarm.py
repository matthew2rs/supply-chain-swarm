#!/usr/bin/env python3
"""supply-chain-swarm helper. Standard library only (no pip installs).

The /supply-swarm command drives this between agent stages:

  swarm.py init <run_dir> --product "..." --market "..." [--store URL] [--suppliers "a,b"] [--b2b yes|no] [--size quick|standard|deep]
  swarm.py check <file.json> <kind>      kind = discover | pool | score
  swarm.py brands <run_dir>              merge raw/discover-*.json -> work/brand-batches.json
  swarm.py factories <run_dir>           merge raw/trace-*.json + raw/beat-*.json -> work/pool.json + work/factory-batches.json
  swarm.py build <run_dir>               raw/score-*.json -> output/<slug>-supply-chain.xlsx + output/summary.md
  swarm.py status <run_dir>              what exists so far (for resuming)
"""
import argparse
import datetime as dt
import glob
import json
import os
import re
import sys
import zipfile
from xml.sax.saxutils import escape

SIZES = {  # brands per trace batch, max trace batches, factories per score batch, max score batches
    "quick": (8, 3, 10, 2),
    "standard": (6, 8, 8, 5),
    "deep": (5, 16, 6, 10),
}

# ── schemas (kept loose on purpose: required keys + a few enums) ─────────────────────────────
BRAND_KEYS = ["brand", "country", "url", "arm"]
POOL_KEYS = ["brand", "brand_country", "brand_url", "arm", "product_types", "price_signal", "manufacturer",
             "manufacturer_country", "manufacturer_url", "confidence", "oem_approachable", "moq_signal",
             "evidence_type", "evidence", "evidence_url"]
SCORE_KEYS = ["verdict", "manufacturer", "country", "url", "why", "confidence", "factory_or_trader", "range_match",
              "moq", "price_signal", "oem_private_label", "export_signal", "certs", "serves_arm",
              "brands_they_supply", "next_step"]
ENUMS = {"confidence": {"high", "medium", "low"}, "verdict": {"Pursue", "Watch", "Kill"}}


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _dump(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)


def check_file(path, kind):
    """Return a list of problems. Empty list = valid."""
    try:
        data = _load(path)
    except Exception as e:  # noqa: BLE001
        return [f"not valid JSON: {e}"]
    key, cols = {"discover": ("brands", BRAND_KEYS), "pool": ("rows", POOL_KEYS), "score": ("rows", SCORE_KEYS)}[kind]
    if not isinstance(data, dict) or not isinstance(data.get(key), list):
        return [f'top level must be an object with a "{key}" array']
    problems = []
    for i, row in enumerate(data[key]):
        missing = [c for c in cols if c not in row]
        if missing:
            problems.append(f"{key}[{i}] missing {missing}")
        for c, allowed in ENUMS.items():
            if c in row and c in cols and row[c] not in allowed:
                problems.append(f"{key}[{i}].{c} = {row[c]!r}, must be one of {sorted(allowed)}")
    return problems[:20]


# ── dedupe: parallel agents name one factory several ways ──────────────────────────────────────────────
STOP = {
    "co", "ltd", "limited", "company", "inc", "llc", "corp", "corporation", "group", "gmbh", "sa", "spa", "pty",
    "products", "product", "outdoor", "outdoors", "sport", "sports", "industrial", "industry", "trading",
    "technology", "tech", "manufacturing", "equipment", "goods", "factory", "the", "and", "international", "intl",
    "trade", "new", "material", "materials", "china", "guangzhou", "shenzhen", "shanghai", "ningbo", "qingdao",
    "xiamen", "foshan", "dongguan", "huizhou", "yiwu", "hangzhou", "suzhou", "tianjin", "beijing", "fujian",
    "guangdong", "shandong", "zhejiang", "jiangsu", "hebei", "jiangxi", "anhui", "henan",
}
VERDICT_ORDER = {"Pursue": 0, "Watch": 1, "Kill": 2}
CONF_ORDER = {"high": 0, "medium": 1, "low": 2}
UNKNOWN = re.compile(r"^\s*(unknown|unnamed|n/?a|not found|none)\b", re.I)


def factory_key(name):
    s = re.sub(r"\(.*?\)", " ", (name or "").lower())
    words = [w for w in re.findall(r"[a-z0-9]+", s) if w not in STOP]
    key = " ".join(words)
    return key if len(key) >= 3 else re.sub(r"[^a-z0-9]", "", (name or "").lower())


def brand_key(name):
    return re.sub(r"[^a-z0-9]", "", re.sub(r"\(.*?\)", "", (name or "").lower()))[:20]


def _merge(a, b, limit=900):
    a, b = (a or "").strip(), (b or "").strip()
    if not b or b.lower() in a.lower():
        return a
    if not a or a.lower() in b.lower():
        return b
    out = f"{a} | {b}"
    return out if len(out) <= limit else out[: limit - 1] + "…"


def dedupe_pool(rows):
    groups = {}
    for r in rows:
        groups.setdefault((brand_key(r.get("brand")), factory_key(r.get("manufacturer"))), []).append(r)
    out = []
    for grp in groups.values():
        grp.sort(key=lambda r: CONF_ORDER.get(r.get("confidence"), 3))
        best = dict(grp[0])
        for o in grp[1:]:
            best["evidence"] = _merge(best.get("evidence"), o.get("evidence"))
        out.append(best)
    return out


def dedupe_scorecard(rows):
    groups = {}
    for r in rows:
        groups.setdefault(factory_key(r.get("manufacturer")), []).append(r)
    out = []
    for grp in groups.values():
        grp.sort(key=lambda r: (VERDICT_ORDER.get(r.get("verdict"), 3), CONF_ORDER.get(r.get("confidence"), 3)))
        best = dict(grp[0])
        for o in grp[1:]:
            for k in ("why", "brands_they_supply", "moq", "oem_private_label", "export_signal", "certs", "next_step", "url"):
                best[k] = _merge(best.get(k), o.get(k))
            if o.get("manufacturer") and o["manufacturer"] not in best["manufacturer"]:
                best["manufacturer"] = _merge(best["manufacturer"], "aka " + o["manufacturer"], 300)
        out.append(best)
    return out


# ── stages ──────────────────────────────────────────────────────────────────────────────────
def cmd_init(a):
    slug = re.sub(r"[^a-z0-9]+", "-", a.product.lower()).strip("-")[:40] or "run"
    cfg = {
        "product": a.product, "market": a.market, "store": a.store or "", "suppliers": a.suppliers or "",
        "b2b": a.b2b, "size": a.size, "slug": slug, "started": dt.date.today().isoformat(),
    }
    for d in ("raw", "work", "output"):
        os.makedirs(os.path.join(a.run_dir, d), exist_ok=True)
    _dump(cfg, os.path.join(a.run_dir, "config.json"))
    print(json.dumps(cfg, indent=1))


def cmd_check(a):
    problems = check_file(a.file, a.kind)
    if problems:
        print("INVALID:\n- " + "\n- ".join(problems))
        sys.exit(1)
    print("OK")


def _local(country, market):
    m = (market or "").lower()
    c = (country or "").lower()
    toks = {t for t in re.findall(r"[a-z]+", m) if len(t) > 1}
    alias = {"australia": {"au", "aus", "australia", "nz", "zealand"}, "au": {"au", "aus", "australia"},
             "usa": {"us", "usa", "america"}, "us": {"us", "usa"}, "uk": {"uk", "england", "britain"}}
    for t in list(toks):
        toks |= alias.get(t, set())
    return any(t in re.findall(r"[a-z]+", c) for t in toks)


def cmd_brands(a):
    cfg = _load(os.path.join(a.run_dir, "config.json"))
    per, maxb, _, _ = SIZES[cfg["size"]]
    seen, brands = set(), []
    for f in sorted(glob.glob(os.path.join(a.run_dir, "raw", "discover-*.json"))) + \
            sorted(glob.glob(os.path.join(a.run_dir, "raw", "anchor*.json"))):
        try:
            data = _load(f)
        except Exception:  # noqa: BLE001
            print(f"skip unreadable {f}")
            continue
        for b in data.get("brands", []):
            k = brand_key(b.get("brand"))
            if k and k not in seen:
                seen.add(k)
                brands.append(b)
    brands.sort(key=lambda b: (0 if b.get("is_current_supplier") else 1, 0 if _local(b.get("country"), cfg["market"]) else 1))
    cap = per * maxb
    dropped = brands[cap:]
    brands = brands[:cap]
    batches = [brands[i:i + per] for i in range(0, len(brands), per)]
    _dump({"batches": batches, "dropped": dropped}, os.path.join(a.run_dir, "work", "brand-batches.json"))
    print(f"{len(brands)} brands in {len(batches)} batches (size={cfg['size']}).")
    if dropped:
        print(f"NOTE: {len(dropped)} brands over the '{cfg['size']}' cap were not traced: "
              + ", ".join(b['brand'] for b in dropped[:15]) + (" …" if len(dropped) > 15 else "")
              + ". Re-run with --size deep to include them.")


def cmd_factories(a):
    cfg = _load(os.path.join(a.run_dir, "config.json"))
    _, _, per, maxb = SIZES[cfg["size"]]
    rows = []
    for f in sorted(glob.glob(os.path.join(a.run_dir, "raw", "trace-*.json"))) + \
            sorted(glob.glob(os.path.join(a.run_dir, "raw", "beat-*.json"))):
        try:
            rows += _load(f).get("rows", [])
        except Exception:  # noqa: BLE001
            print(f"skip unreadable {f}")
    pool = dedupe_pool(rows)
    _dump({"rows": pool}, os.path.join(a.run_dir, "work", "pool.json"))
    facs = {}
    for r in pool:
        m = r.get("manufacturer") or ""
        if not m or UNKNOWN.match(m):
            continue
        k = factory_key(m)
        f = facs.setdefault(k, {"manufacturer": m, "country": r.get("manufacturer_country", ""),
                                "url": r.get("manufacturer_url", ""), "brands": [], "evidence": []})
        f["brands"].append(f"{r.get('brand')} ({r.get('confidence')})")
        if r.get("evidence_url"):
            f["evidence"].append(f"{r.get('evidence_type')}: {r.get('evidence_url')}")
    flist = sorted(facs.values(), key=lambda f: -len(f["brands"]))
    cap = per * maxb
    dropped = flist[cap:]
    flist = flist[:cap]
    batches = [flist[i:i + per] for i in range(0, len(flist), per)]
    _dump({"batches": batches, "dropped": dropped}, os.path.join(a.run_dir, "work", "factory-batches.json"))
    print(f"{len(pool)} pool rows ({len(rows) - len(pool)} duplicates merged); "
          f"{len(flist)} factories in {len(batches)} score batches.")
    if dropped:
        print(f"NOTE: {len(dropped)} factories over the cap were not scored (they stay in the Pool tab).")


# ── xlsx writer (stdlib) ────────────────────────────────────────────────────────────────────
def _col(n):
    s = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


STYLE_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="3"><font><sz val="10"/><name val="Arial"/></font><font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="Arial"/></font><font><b/><sz val="14"/><name val="Arial"/></font></fonts>
<fills count="6"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FF2B2E33"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFD1F0D6"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFFFF2C7"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFFAD6D6"/></patternFill></fill></fills>
<borders count="1"><border/></borders>
<cellStyleXfs count="1"><xf/></cellStyleXfs>
<cellXfs count="6">
<xf fontId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
<xf fontId="1" fillId="2" applyFont="1" applyFill="1" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>
<xf fontId="0" fillId="3" applyFill="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
<xf fontId="0" fillId="4" applyFill="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
<xf fontId="0" fillId="5" applyFill="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
<xf fontId="2" applyFont="1"/>
</cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>"""
CHIP = {"Pursue": 2, "high": 2, "Watch": 3, "medium": 3, "Kill": 4, "low": 4}


def _sheet_xml(rows, widths, header=True, chip_cols=()):
    out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">']
    if header:
        out.append('<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" xSplit="1" topLeftCell="B2" '
                   'activePane="bottomRight" state="frozen"/></sheetView></sheetViews>')
    out.append("<cols>" + "".join(f'<col min="{i+1}" max="{i+1}" width="{w}" customWidth="1"/>' for i, w in enumerate(widths)) + "</cols>")
    out.append("<sheetData>")
    for ri, row in enumerate(rows):
        cells = []
        for ci, v in enumerate(row):
            if v is None or v == "":
                continue
            ref = f"{_col(ci)}{ri+1}"
            if header and ri == 0:
                s = 1
            elif not header and ri == 0:
                s = 5
            else:
                s = CHIP.get(str(v), 0) if ci in chip_cols else 0
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                cells.append(f'<c r="{ref}" s="{s}"><v>{v}</v></c>')
            else:
                txt = escape(str(v))[:32000]
                cells.append(f'<c r="{ref}" s="{s}" t="inlineStr"><is><t xml:space="preserve">{txt}</t></is></c>')
        out.append(f'<row r="{ri+1}">' + "".join(cells) + "</row>")
    out.append("</sheetData>")
    if header and rows:
        out.append(f'<autoFilter ref="A1:{_col(len(rows[0])-1)}{len(rows)}"/>')
    out.append("</worksheet>")
    return "".join(out)


def write_xlsx(path, sheets):
    """sheets = [(name, rows, widths, header, chip_cols)]"""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                   '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                   + "".join(f'<Override PartName="/xl/worksheets/sheet{i+1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(len(sheets)))
                   + "</Types>")
        z.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr("xl/workbook.xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                   'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
                   + "".join(f'<sheet name="{escape(n[:31])}" sheetId="{i+1}" r:id="rId{i+1}"/>' for i, (n, *_r) in enumerate(sheets))
                   + "</sheets></workbook>")
        z.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   + "".join(f'<Relationship Id="rId{i+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i+1}.xml"/>' for i in range(len(sheets)))
                   + f'<Relationship Id="rId{len(sheets)+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        z.writestr("xl/styles.xml", STYLE_XML)
        for i, (_n, rows, widths, header, chips) in enumerate(sheets):
            z.writestr(f"xl/worksheets/sheet{i+1}.xml", _sheet_xml(rows, widths, header, chips))


def _md_lines(path):
    if not os.path.exists(path):
        return ["(not produced in this run)"]
    lines = []
    for l in open(path, encoding="utf-8").read().splitlines():
        l = re.sub(r"\*\*(.*?)\*\*", r"\1", l)
        l = re.sub(r"^#+\s*", "", l)
        lines.append(l.rstrip())
    return lines


def cmd_build(a):
    cfg = _load(os.path.join(a.run_dir, "config.json"))
    pool_path = os.path.join(a.run_dir, "work", "pool.json")
    pool = _load(pool_path)["rows"] if os.path.exists(pool_path) else []
    scored = []
    for f in sorted(glob.glob(os.path.join(a.run_dir, "raw", "score-*.json"))):
        try:
            scored += _load(f).get("rows", [])
        except Exception:  # noqa: BLE001
            print(f"skip unreadable {f}")
    scored = dedupe_scorecard(scored)
    scored.sort(key=lambda r: (VERDICT_ORDER.get(r.get("verdict"), 3), CONF_ORDER.get(r.get("confidence"), 3)))
    pool.sort(key=lambda r: (0 if _local(r.get("brand_country"), cfg["market"]) else 1,
                             CONF_ORDER.get(r.get("confidence"), 3), (r.get("brand") or "").lower()))
    named = sum(1 for r in pool if r.get("manufacturer") and not UNKNOWN.match(r["manufacturer"]))
    v = {k: sum(1 for r in scored if r.get("verdict") == k) for k in ("Pursue", "Watch", "Kill")}
    srcmap = os.path.join(a.run_dir, "raw", "source-map.json")
    sm = _load(srcmap).get("sources", []) if os.path.exists(srcmap) else []

    welcome = [
        [f"{cfg['product'].title()}: Manufacturer Research"],
        [f"Reverse supply-chain map for the {cfg['market']} market, built {cfg['started']}"],
        [""],
        ["What is this?"],
        [f"Every brand we could find selling {cfg['product']} ({cfg['market']} first, then the rest of the world), "
         "who manufactures each one, and which of those factories you can approach to make your own range."],
        [""],
        [f"In this file: {len(pool)} brand rows, {named} with a named maker; {len(scored)} factories graded "
         f"({v['Pursue']} Pursue, {v['Watch']} Watch, {v['Kill']} Kill)."],
        [""],
        ["Start here"],
        ["1. 'The trace' tab: who most likely makes your current suppliers' products, and the quote request to send."],
        ["2. 'Scorecard' tab: the factories, best first. Pursue = approach now. Watch = promising, one key fact unverified. "
         "Kill = fails a gate (doesn't make this product, won't do OEM, or a reseller only). Overrule any verdict you know better."],
        ["3. 'Pool' tab: every brand -> manufacturer, with the evidence and a link to check it yourself."],
        ["4. 'Photo checklist' tab: photos of your own stock that usually name the factory outright."],
        [""],
        ["Confidence"],
        ["high = a customs record, an EU product-safety label naming the maker, or the factory naming the brand itself."],
        ["medium = identical sales copy, images or specs between a brand and a factory listing."],
        ["low = an educated guess. Verify before acting."],
        [""],
        ["Before you order: get real factory photos (not renders), the relevant test reports/certificates, "
         "and a single sample before any container order."],
        [""],
        ["Tip: to use this in Google Sheets, open sheets.google.com -> File -> Import -> Upload this file."],
    ]
    sheets = [
        ("Welcome", welcome, [140], False, ()),
        ("Scorecard", [["Verdict", "Manufacturer", "Country", "URL", "Why (the deciding factor)", "Confidence",
                        "Factory or Trader", "Range Match", "MOQ", "Price Signal", "OEM / Private Label", "Export Signal",
                        "Certs", "Serves Which Arm", "Brands They Supply", "Next Step"]]
         + [[r.get(k, "") for k in SCORE_KEYS] for r in scored],
         [10, 34, 16, 30, 50, 11, 18, 36, 20, 20, 30, 30, 24, 14, 36, 50], True, (0, 5)),
        ("Pool", [["Brand", "Brand Country", "Brand URL", "Arm", "Product Types", "Retail Price", "Manufacturer",
                   "Manufacturer Country", "Manufacturer URL", "Confidence", "OEM Approachable", "MOQ Signal",
                   "Evidence Type", "Evidence", "Evidence URL"]]
         + [[r.get(k, "") for k in POOL_KEYS] for r in pool],
         [26, 16, 30, 10, 30, 18, 34, 16, 30, 11, 30, 20, 22, 60, 34], True, (9,)),
        ("The trace", [[l] for l in _md_lines(os.path.join(a.run_dir, "raw", "deep-trace.md"))], [160], False, ()),
        ("Photo checklist", [[l] for l in _md_lines(os.path.join(a.run_dir, "raw", "photo-checklist.md"))], [140], False, ()),
    ]
    if sm:
        sheets.append(("Source Map", [["Source", "URL", "What it reveals", "How to mine it", "Signal fit (1-5)"]]
                       + [[s.get("name", ""), s.get("url", ""), s.get("what_it_reveals", ""), s.get("how_to_mine", ""),
                           s.get("signal_fit", "")] for s in sm], [30, 34, 50, 50, 12], True, ()))
    out = os.path.join(a.run_dir, "output", f"{cfg['slug']}-supply-chain.xlsx")
    write_xlsx(out, sheets)

    top = [r for r in scored if r.get("verdict") == "Pursue"][:8]
    md = [f"# {cfg['product'].title()}: who makes it", "",
          f"- {len(pool)} brand rows, {named} with a named maker",
          f"- {len(scored)} factories graded: {v['Pursue']} Pursue, {v['Watch']} Watch, {v['Kill']} Kill",
          f"- Spreadsheet: `{out}`", "", "## Factories to approach first", ""]
    md += [f"{i+1}. **{r['manufacturer']}** ({r.get('country','')}). {r.get('why','')} MOQ: {r.get('moq','')}. "
           f"Next: {r.get('next_step','')}" for i, r in enumerate(top)] or ["(none graded Pursue)"]
    with open(os.path.join(a.run_dir, "output", "summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(f"Built {out}\n  {len(pool)} pool rows, {len(scored)} factories ({v}).")


def cmd_status(a):
    for sub in ("raw", "work", "output"):
        files = sorted(os.listdir(os.path.join(a.run_dir, sub))) if os.path.isdir(os.path.join(a.run_dir, sub)) else []
        print(f"{sub}/: {', '.join(files) or '(empty)'}")


def main():
    p = argparse.ArgumentParser()
    sp = p.add_subparsers(dest="cmd", required=True)
    i = sp.add_parser("init"); i.add_argument("run_dir"); i.add_argument("--product", required=True)
    i.add_argument("--market", default="Australia"); i.add_argument("--store"); i.add_argument("--suppliers")
    i.add_argument("--b2b", default="yes"); i.add_argument("--size", default="standard", choices=list(SIZES))
    c = sp.add_parser("check"); c.add_argument("file"); c.add_argument("kind", choices=["discover", "pool", "score"])
    for n in ("brands", "factories", "build", "status"):
        sp.add_parser(n).add_argument("run_dir")
    a = p.parse_args()
    {"init": cmd_init, "check": cmd_check, "brands": cmd_brands, "factories": cmd_factories,
     "build": cmd_build, "status": cmd_status}[a.cmd](a)


if __name__ == "__main__":
    main()

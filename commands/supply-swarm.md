---
description: Reverse-engineer a product's supply chain. Finds every brand selling it, who manufactures each one, and grades the factories you could approach. Outputs a spreadsheet.
argument-hint: "<product> [market] [your store URL] e.g. inflatable pontoons, Australia, https://mystore.com.au"
---

# /supply-swarm: run the pipeline (do not just discuss it)

You are the **orchestrator** of a multi-agent research pipeline. The user ran this command to get a
**spreadsheet file**, not a conversation. Your job is to run every stage below, in order, using the
**Agent tool** (called "Task" in older Claude Code versions) to launch sub-agents, and finish by
building the spreadsheet with the bundled script.

**Do not** summarise this file back to the user. **Do not** ask whether they want you to start.
**Do not** do the research yourself in this chat. Sub-agents do the research; you coordinate, run the
script between stages, and report.

Plugin folder (prompts + script live here): !`echo "${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$(find ~/.claude "$PWD" -path '*supply-chain-swarm/scripts/swarm.py' 2>/dev/null | head -1)")/.." 2>/dev/null && pwd)}"`

Below, `ROOT` means that folder and `RUN` means the run folder you create in Stage 0.
`SW` means `python3 ROOT/scripts/swarm.py`.

User's request: $ARGUMENTS

---

## Stage 0: Scope (one message, then go)

Work out four things from the request:
- **PRODUCT**: what is being reverse-engineered (required).
- **MARKET**: the country they sell in. Default: Australia.
- **STORE**: their store URL, if any.
- **SUPPLIERS**: the brands they currently resell, if any.

If PRODUCT is missing, or STORE and SUPPLIERS are both missing, ask **once**, with the
AskUserQuestion tool if you have it, otherwise in one short message:
1. product
2. market
3. their store URL and/or the brands they resell now
4. size: `quick` (~10 agents), `standard` (~20 agents, the default) or `deep` (~35 agents)

Also ask: include the B2B / commercial version of the product? (default yes)

If the user already gave enough, **don't ask**. Use the defaults and say which you used in one line.

Then create the run:
```
SW init ./supply-swarm-runs/<short-product-slug> --product "<PRODUCT>" --market "<MARKET>" --store "<STORE>" --suppliers "<SUPPLIERS>" --b2b yes --size standard
```
Tell the user, in 2 lines, what's about to happen:
- roughly how many agents
- that it takes 20-60 minutes and uses a lot of tokens

Then **go straight to Stage 1 in the same turn.**

## How to launch agents (applies to every stage)

- Launch every agent of a stage **in a single message** (parallel), with `run_in_background: true`
  if your Agent tool supports it. Then wait until they have all finished.
- Each agent's prompt must be:
  1. "Read `ROOT/prompts/_rules.md` and `ROOT/prompts/<file>.md` and follow them exactly."
  2. Then its inputs as `KEY: value` lines.
  3. **Always** include `OUT:` (an absolute file path inside RUN) and `CHECK: python3 ROOT/scripts/swarm.py check <OUT> <kind>`.
- Agents write their results to files and reply with one line. Don't ask them to paste data back.
- If an agent fails or its file is missing, re-launch **that one agent** once. Then carry on without it and note it.

## Stage 1: Map the market (3-4 agents, parallel)

| Agent | Prompt file | Inputs |
|---|---|---|
| anchor (only if STORE or SUPPLIERS given) | `anchor.md` | PRODUCT, MARKET, STORE, SUPPLIERS, OUT_JSON=`RUN/raw/anchor.json`, OUT_MD=`RUN/raw/anchor.md`, CHECK kind `discover` |
| discover-local | `discover.md` | PRODUCT, MARKET, SCOPE=local, B2B, OUT=`RUN/raw/discover-local.json`, CHECK kind `discover` |
| discover-global | `discover.md` | PRODUCT, MARKET, SCOPE=global, B2B, OUT=`RUN/raw/discover-global.json`, CHECK kind `discover` |

When all have finished, run `SW brands RUN`. It merges, de-duplicates and batches the brands into
`RUN/work/brand-batches.json`. Read that file.

## Stage 2: Trace who makes what (parallel; the big stage)

Launch **all** of these in one message:
- **One trace agent per batch** in `brand-batches.json`. Prompt file `trace.md`. Inputs:
  - BRANDS = that batch's list (name | country | url)
  - OUT=`RUN/raw/trace-<n>.json`, CHECK kind `pool`
- **Three beat agents**, prompt file `beats.md`, with BEAT = `customs`, `eu-gpsr` and `copy-match`. Inputs:
  - KNOWN_BRANDS = all brand names from the batches
  - OUT=`RUN/raw/beat-<beat>.json`, CHECK kind `pool`
- **One deep-trace agent** (only if there's an anchor), prompt file `deep-trace.md`. Inputs:
  - SUPPLIERS
  - ANCHOR_NOTE=`RUN/raw/anchor.md`
  - OUT_MD=`RUN/raw/deep-trace.md`
  - OUT_CHECKLIST=`RUN/raw/photo-checklist.md`

When all have finished, run `SW factories RUN`. It merges every row, removes duplicates, and
batches the factories into `RUN/work/factory-batches.json`. Read that file.

## Stage 3: Grade the factories (parallel)

- One score agent per batch in `factory-batches.json`. Prompt file `score.md`. Inputs:
  - FACTORIES = that batch (manufacturer | country | url | brands | evidence)
  - OUT=`RUN/raw/score-<n>.json`, CHECK kind `score`

When all have finished, run `SW build RUN`.

## Stage 4: Hand it over

1. Run `SW build RUN` if you haven't. It writes:
   - `RUN/output/<slug>-supply-chain.xlsx` with tabs Welcome / Scorecard / Pool / The trace /
     Photo checklist. Duplicate factories are already merged.
   - `RUN/output/summary.md`.
2. Read `summary.md` and reply to the user with:
   - the spreadsheet path (and open it: `open <path>` on Mac, `start <path>` on Windows)
   - the top 3-5 factories to approach, one line each: why + MOQ
   - who most likely makes their current suppliers' products, with the confidence level
   - what wasn't reachable (blocked sites, capped brands), stated honestly
   - one line: "To use it in Google Sheets: sheets.google.com → File → Import → Upload."
3. **Never contact a factory, send an email, or post anything.** The quote request in "The trace"
   tab is for the user to send.

## If the session is interrupted

Run `SW status RUN`. Every agent's output is a file in `RUN/raw/`, so re-launch only the missing
ones and carry on from the stage you were in.

# Supply Chain Swarm

**Find out who actually makes the products you sell, and which factories you can buy from direct.**

You type one command into Claude Code. It sends a team of research agents to:

1. find every brand selling your product (your country first, then the rest of the world)
2. trace each brand back to the factory that makes it, using US customs records, EU product-safety
   labels, copied sales text and factory listings
3. grade every factory **Pursue / Watch / Kill** on minimum order, private-label terms, export
   history and whether it's a real factory or a middleman

You get back a **spreadsheet** with these tabs:

| Tab | What's in it |
|---|---|
| **Welcome** | How to read it, plus the headline numbers |
| **Scorecard** | Every factory, best first, with the deciding reason and exactly how to contact them |
| **Pool** | Every brand → its manufacturer, with the evidence and a link to check it |
| **The trace** | Who most likely makes *your* current suppliers' products, plus a ready-to-send quote request |
| **Photo checklist** | 12 photos of your own stock that usually name the factory outright |

It has been used on saunas, outdoor water features and inflatable pontoons.

---

## Install (once, about 1 minute)

You need [Claude Code](https://claude.com/claude-code), either the terminal version or the
desktop app's Code tab. This won't work in the normal claude.ai chat: that chat can't launch
agents or write files, so it will just talk to you about the plan.

In Claude Code, type these two commands:

```
/plugin marketplace add matthew2rs/supply-chain-swarm
```

```
/plugin install supply-chain-swarm@supply-chain-swarm
```

Restart Claude Code. Then type `/supply` and you should see `/supply-swarm` in the list.

> **Private repo?** If the repo is private, you need to be invited to it on GitHub first, and
> logged in to GitHub on your computer (`gh auth login`).

## Run it

Open Claude Code in any folder (the results are saved there), then:

```
/supply-swarm inflatable pontoons, Australia, my store is https://mystore.com.au
```

Give it the following, and the more you give, the better:
- **the product** (required)
- **your market** (defaults to Australia)
- **your store URL** and/or **the brands you resell now**. This is what produces "The trace":
  who makes the products you already sell.
- **a size**:
  - `quick`: about 10 agents
  - `standard`: about 20 agents, the default
  - `deep`: about 35 agents

Then leave it. It takes **20–60 minutes**. When it's done it opens the spreadsheet and tells you
the top factories to approach.

**To use it in Google Sheets:** go to sheets.google.com → File → Import → Upload, and pick the
`.xlsx` file.

## What it costs

It runs many agents, so it uses a lot of your Claude usage: roughly 2–5 million tokens for a
standard run. Use a Claude **Max** plan, or run `quick` first.

## Good to know

- **It never contacts anyone.** The quote request it writes is for *you* to send.
- **Confidence matters.**
  - `high`: a customs record, an EU label or the factory naming the brand.
  - `medium`: copied text, photos or specs.
  - `low`: a lead to check, not a fact.
- **Some sites block research** (Shopify rate limits, ImportYeti, Alibaba captchas). The sheet
  tells you what couldn't be reached.
- **Your own stock is the shortcut.** Countries like Australia don't publish import records. The
  photo checklist (carton marks, QC slips, barcodes) often names the factory faster than any search.
- **Before you order:** get real factory photos (not renders), the test reports for your product,
  and one sample before a container.

## If it stops halfway

Everything each agent finds is saved as a file in `supply-swarm-runs/<product>/raw/`. Run the
same command again and say "resume". It checks what's there and only re-runs what's missing.

---

Built by [Matthew R Scott](https://matthewrscott.com) for the Escape Velocity crew. MIT licence.

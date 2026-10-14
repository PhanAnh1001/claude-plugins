---
name: citing-sources
description: Cite sources for every figure, fact and conclusion that comes from outside the project - in research reports and their summaries, research notes, solution docs, decision records, READMEs and chat answers. Each claim gets an inline http(s) link to the latest original source plus the date of the data, for example "(10/2026)"; newer figures replace older ones, which are labelled superseded; unverified, vendor-reported and inferred figures are labelled (inferences also link the URLs they rest on); a claim with no internet source says so explicitly; an internal link never replaces the internet link. Use whenever writing or summarising research, market, legal, pricing, vendor or statistical claims, in any project. Vietnamese triggers - "nguồn", "dẫn nguồn", "trích dẫn", "số liệu", "citation", "link nguồn", "ngày dữ liệu", "số liệu mới nhất".
---

# Citing sources

## Summary

- **Purpose:** a reader can check every external claim in one click and knows how fresh and how
  trustworthy it is.
- **Rule:** each figure, fact and conclusion taken from outside the project carries an inline
  `http(s)` link to the latest original source and the date of the data.
- **Labels:** superseded, unverified, vendor-reported, inference, and "no internet source" are
  written next to the claim, never hidden in a footnote.
- **Applies to:** research reports and summaries, research notes, solution docs, decision
  records, READMEs, and summaries given in chat.
- **Project rules win:** if AGENTS.md / CLAUDE.md sets a citation format, follow it; this skill
  fills the gaps.

## What needs a source

### Claims that must be cited

- Numbers from outside the project: market sizes, prices, fees, tax rates, limits, user counts,
  benchmarks published by others, dates of laws or releases.
- Facts about the outside world: what a law, standard, API, product or vendor says or does.
- Conclusions and recommendations that rest on external facts, including inferences.

### Claims that do not

- Facts about the project itself that a reader can verify in the repo (link the file instead):
  test counts from a command you ran, file layout, code behaviour.
- Plain definitions and common knowledge that no reasonable reader would dispute.

## How to cite

### Format

- Put the link inline, right next to the claim: `[source](https://...)`, with the link text in
  the document's language (for example `[nguồn](https://...)` in Vietnamese).
- Add the date of the data, not the date you read it, in the form the document uses, for
  example `(10/2026)`, `(2026-10-14)` or `(Q3/2026)`.
- Example: `The fee is 2.5% per transaction [source](https://example.com/pricing) (10/2026).`
- Link the original source (the regulator, the standard, the vendor's own page, the dataset)
  rather than an article quoting it. Use the most specific URL (page or section anchor).

### Freshness

- Look for the most recent figure before citing one. When a newer figure exists, use it and
  drop the older one, or keep it labelled "superseded by <newer figure + link>".
- When only older data exists, cite it and say how old it is, for example
  "latest available data (2024)".
- For laws and rules, cite the version in force and its effective date; mention a pending
  replacement if one is known.

### Labels

Write the label next to the claim, in the document's language:

| Label | When | Example |
|---|---|---|
| unverified | single source, not cross-checked | `~40,000 users (unverified) [source](...) (09/2026)` |
| vendor-reported | the vendor states it about itself | `99.99% uptime (vendor-reported) [source](...) (10/2026)` |
| inference | your estimate or conclusion from sources | `≈ 1.2M households (inference from [a](...), [b](...)) (2026)` |
| superseded | older figure kept for context | `5% (superseded by 3% [source](...) (07/2026))` |
| no internet source | nothing found online | `no internet source` / `chưa có nguồn internet` |

- An inference links every URL it is based on and may also link the internal note it comes
  from; it is never presented as a sourced fact.
- When no internet source can be found, write "no internet source" (or the document-language
  equivalent, for example "chưa có nguồn internet"). Do not fall back to an internal link.

### Internal links

- A link to a report or note inside the repo may be added next to the internet link, never in
  place of it.
- Internal links use paths relative to the project root.

## Chat answers

- Summaries of research given in chat follow the same rule: link each figure and conclusion
  inline with its data date.
- If you state something from memory without a source, label it as unverified and offer to
  look it up.

## Checklist

- [ ] Every external figure, fact and conclusion has an inline `http(s)` link.
- [ ] Every cited figure has the date of the data.
- [ ] The latest available figure is used; older ones are dropped or labelled superseded.
- [ ] Unverified, vendor-reported and inferred figures carry their label next to the claim.
- [ ] Inferences link the URLs they rest on.
- [ ] Claims without a source say "no internet source" (or the document-language equivalent).
- [ ] No internal link stands in for an internet source.

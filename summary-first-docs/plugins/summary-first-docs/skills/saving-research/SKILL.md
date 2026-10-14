---
name: saving-research
description: Save every multi-source research in the project repo instead of leaving it only in chat - a dated folder docs/research/<YYYY-MM-DD>-<slug>/ with report.md (opens with a summary, labels unverified, vendor-reported and inferred figures) and notes/<topic>.md (source notes, every fact dated and linked), plus an entry in the catalogue docs/research/README.md (date, question, 3-5 key conclusions, links). A new research on an earlier topic gets a new folder linking to the old one; old reports are not rewritten. Use whenever doing web research, comparing options, market, legal or vendor research, or running the deep-research skill (replace its default research_notes/ and reports/ folders with these paths). Vietnamese triggers - "nghiên cứu", "research", "lưu nghiên cứu", "báo cáo nghiên cứu", "tìm hiểu thị trường", "so sánh phương án", "deep research".
---

# Saving research

## Summary

- **Purpose:** research that informs the project stays in the repo, reviewable and citable,
  instead of disappearing with the chat.
- **Layout:** `docs/research/<YYYY-MM-DD>-<slug>/report.md` + `notes/<topic>.md`, catalogued in
  `docs/research/README.md`. Use the project's paths if AGENTS.md / CLAUDE.md sets others.
- **Applies to:** any research across several sources (web search, documentation, datasets),
  including runs of the `deep-research` skill.
- **Related skills:** structure the report and catalogue with `structuring-documents`; cite every
  claim with `citing-sources`.
- **Before reporting done:** report, notes and catalogue entry exist and pass the checklist.

## Project rules first

- **Paths:** use the project's research folder if it defines one; otherwise `docs/research/`.
- **Language:** follow the project's rule (for example report in the team's language, notes in
  English). If none is set, write the report in the language of the project's documents and the
  notes in the language of the sources or English.
- **Names:** `<YYYY-MM-DD>` is the date the research is done; `<slug>` and `<topic>` are English
  kebab-case.

## Layout

```
docs/research/
  README.md                         catalogue, newest first
  <YYYY-MM-DD>-<slug>/
    report.md                       the report: summary first, cited, labelled
    notes/<topic>.md                source notes by topic, input to the report
```

### The report `report.md`

- Opens with a summary (`structuring-documents`): the question, 3-5 key conclusions with
  sources and data dates, key figures, recommendation and what the reader must do.
- Body follows the summary's order: one section per conclusion or theme, then method and
  sources, then open questions.
- Every figure, fact and conclusion cites its source per `citing-sources`; unverified,
  vendor-reported and inferred figures carry their labels.
- Starting point: [template.md](template.md).

### Source notes `notes/<topic>.md`

- One file per topic (for example `pricing.md`, `regulation.md`, `competitors.md`).
- Each fact is one bullet with the fact, the source URL and the date of the data, for example
  `- Fee is 2.5% per transaction. https://example.com/pricing (10/2026)`.
- Quote short exact passages for legal or contractual wording; note when a page could not be
  accessed or contradicts another source.

### The catalogue `docs/research/README.md`

- Opens with a summary: purpose of the folder, number of researches, how to add one.
- One entry per research, newest first: date, question, 3-5 key conclusions (each with its
  internet source and data date), decisions it led to if the project records decisions, and
  links to the report and notes.
- Example entry:

  ```
  ### 2026-10-14 - Payment provider fees
  - **Question:** which provider is cheapest for small merchants?
  - **Conclusions:** A charges 2.5% [source](https://example.com/a) (10/2026); ...
  - **Links:** [report](2026-10-14-payment-fees/report.md), [notes](2026-10-14-payment-fees/notes/)
  ```

## Steps

1. **Check earlier work:** read `docs/research/README.md` for research on the same topic.
2. **Create the folder** `docs/research/<YYYY-MM-DD>-<slug>/` and `notes/`.
3. **Collect:** while researching, write facts into `notes/<topic>.md` with URL and data date.
4. **Write the report** from the notes, summary first, every claim cited.
5. **Add the catalogue entry** and update the catalogue summary counts.
6. **Run the checklist**, then report to the user with the key conclusions and their links.

### A new research on an earlier topic

- Create a new dated folder; link the earlier report from the new report's summary or method
  section ("updates <link>").
- Do not rewrite the earlier report; it records what was known on its date. Updating internal
  paths after a rename is allowed.
- In the new report, state which earlier figures are superseded (`citing-sources` labels).

### With the `deep-research` skill

- Replace its default output folders: `research_notes/` -> `docs/research/<YYYY-MM-DD>-<slug>/notes/`
  and `reports/` -> `docs/research/<YYYY-MM-DD>-<slug>/report.md`.
- Tell the research subagents these paths and the note format before they start.
- After it finishes, check the report against this skill (summary, citations, labels) and add
  the catalogue entry.

## Checklist

- [ ] `report.md` opens with a summary and follows the summary's order.
- [ ] Every claim in the report and catalogue has an `http(s)` source and data date.
- [ ] Unverified, vendor-reported and inferred figures are labelled; inferences link their URLs.
- [ ] Every fact in `notes/` has a URL and data date.
- [ ] Catalogue entry added (date, question, 3-5 conclusions, links), newest first.
- [ ] Earlier research on the topic linked, not rewritten.
- [ ] Folder and file names are English kebab-case with an ISO date prefix on the folder.
- [ ] Paths relative to the project root; no developer-machine absolute path.
- [ ] Each file within the project's line limit; split notes by topic if larger.

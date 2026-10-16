# Evidence and temporal policy

## Contents

- Source priority
- Historical cutoff
- Source ledger
- Data gaps

## Source priority

Use sources in this order when applicable:

1. Exchange data and regulator filings.
2. Company investor-relations releases, earnings materials, and transcripts.
3. Central banks, statistics agencies, and other primary public institutions.
4. Reputable market-data providers and established news organizations.
5. Clearly identified social or community sources for sentiment only.

Use multiple independent sources for material claims when practical. Treat search snippets as discovery, not final evidence. Link directly to the supporting page.

## Historical cutoff

For an analysis date earlier than today:

- Use only prices with timestamps on or before the cutoff.
- Use only articles, filings, guidance, estimates, and social posts published on or before the cutoff.
- Do not use later restatements, realized returns, subsequent earnings, or hindsight in analyst/debate reports.
- Keep later outcome data separate and use it only to resolve a prior memory entry.
- Reject undated evidence unless its availability before the cutoff can be established.

## Source ledger

Save `<run-root>/evidence/sources.json` as a JSON array. Each record should include:

```json
{
  "title": "Source title",
  "url": "https://example.com/page",
  "publisher": "Publisher",
  "date": "YYYY-MM-DD",
  "source_type": "filing|company|market-data|news|macro|social",
  "used_by": ["news", "bull", "portfolio"],
  "claim": "Short description of the supported claim"
}
```

Deduplicate by canonical URL. Keep quotations short; prefer paraphrases.

## Data gaps

Record missing, delayed, conflicting, or proxy data. Lower confidence when:

- the latest bar predates the requested cutoff materially;
- fundamentals are stale or unaudited;
- sentiment samples are small or platform-specific;
- currencies, corporate actions, or ticker mappings are ambiguous;
- benchmark comparison is not economically appropriate;
- a key claim relies on a single secondary source.

Do not fill gaps with model memory.

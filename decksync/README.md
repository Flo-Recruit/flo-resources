# decksync

Keeps Flo's sales decks (Claude Slides and Design artifacts) in step with the Legal Recruiting Tracker and with HubSpot client stats.

- **Every weekday ~7:40 AM Central** a Claude scheduled task rebuilds the tracker chart slides and refreshes student counts in nine sales assets, then posts a summary to #marketing_internal.
- **Mondays** the same run also pulls client stats (law firm clients, AmLaw/Vault coverage, ATS counts) from the HubSpot dashboard "Client Stats for Sales Team's Decks".

Owner: Hannah Kelly · Backup: Collin Katz

## Files

| File | What it is |
|---|---|
| `render.py` | Draws every generated slide and holds the wording rules for numbers swapped into existing slides. |
| `run.py` | The runner the scheduled task and CI call (`files`, `build`, `merge-clients`, `approve`, `check`). |
| `decks.json` | Which decks and slides are updated, and the tracker data URL. Edit this to add a deck or slide. |

**Not in this repo:** HubSpot numbers and held decreases live in the private Claude artifact "Deck Sync Settings" (https://claude.ai/artifact/RMUNNeFTHaadM2p8MbN1UT) as `client_stats.json`, because this repo is public. Never commit a `client_stats.json` here.

## Two kinds of slides

- **Owned slides** (`own` in `decks.json`) are rebuilt from scratch every run: chart, headline, subtitle, footer. Edits made in the Slides editor are overwritten the next morning, so wording changes go into `render.py`.
- **Patched files** (`patch`) keep everything as written; only recognised numbers change (student counts; client counts and percentages). If a patched file's wording changes so no number matches, the run reports it instead of guessing.

## Rules the numbers follow

- Headlines compare the latest full month with the same month last year, adding "with October up X% so far" when the month in progress already beats last year's full month. A drop switches to neutral wording; it never says "down".
- The month in progress is drawn dashed only through the 14th.
- Student count: "law students and new graduates" (all classes the tracker has) by default; "current law students" only where a slide says so. Rounded down to the nearest 500, with a "+".
- Client counts round down to the nearest 5 with a "+". Percentages round to the nearest 5%, with a "+" when that rounds down.
- A client stat that would make a deck show a lower figure is **held** until Hannah or Collin approves it.
- BigLaw slides use 500+ attorney data; Midsize slides use under-500 data, and say so in bold.

## Commands

```bash
python3 decksync/run.py check --data pipeline/data.json        # CI: every generator renders
python3 decksync/run.py files                                   # what the task must read from each deck
python3 decksync/run.py build --data data.json --work work --clients client_stats.json
python3 decksync/run.py merge-clients --fresh fresh.json --clients client_stats.json
python3 decksync/run.py approve amlaw100_forward --clients client_stats.json
```

## If the tracker data changes

`check` runs on every pull request that touches `pipeline/**`. If a field the slides use is renamed or removed, it fails there. If something slips through, the daily run keeps the old slide and lists it under "problems" in Slack rather than publishing a broken one.

## If the repo moves or goes private

Change `data_url` in `decks.json` (and the code URL in the scheduled task's prompt). If the repo becomes private, the scheduled task needs another way to read the data: keep the repo public, publish `charts.json` on resources.joinflo.com and allowlist that domain in Claude, or give the Claude GitHub app access to the repo.

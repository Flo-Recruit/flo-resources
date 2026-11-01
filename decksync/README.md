# decksync

Keeps Flo's sales decks (Claude Slides and Design artifacts) in step with the Legal Recruiting Tracker, the top-25 law school data, and HubSpot client stats.

**Every weekday around 7:40 AM Central** a Claude scheduled task does three things:
1. Rebuilds the tracker chart slides and patches the student and client numbers in 9 sales assets.
2. Refreshes the top-25 law school slide.
3. Posts one summary to #marketing_internal that starts "Deck data update · <date>".

**On Mondays** the same run also pulls the client stats from HubSpot.

Owner: Hannah Kelly · Backup: Collin Katz

## Files

| File | What it is |
|---|---|
| `render.py` | Draws every generated slide and holds the wording rules for numbers swapped into existing slides. |
| `run.py` | The runner the scheduled task and CI call (`files`, `build`, `merge-clients`, `approve`, `check`). |
| `decks.json` | Which decks and slides are updated, and the tracker data URL. Edit this to add a deck or slide. |
| `SCHEDULED_TASK.md` | The full prompt of the "decksync" scheduled task, so it can be recreated if it is lost or moves owner. |

**Not in this repo.** The private Claude artifact "Deck Sync Settings" (https://claude.ai/artifact/RMUNNeFTHaadM2p8MbN1UT) holds three files, because this repo is public:

- `client_stats.json` — the HubSpot numbers the decks use, plus `pending` (held decreases)
- `top25.json` — the top-25 school list, ranks, SQL and slide template
- `top25.py` — the script that builds the top-25 slide

The artifact's page shows the current numbers and anything waiting for approval. Whenever the run saves `client_stats.json` back, it must republish all three files, or the other two are lost. Never commit any of these here.

## Two kinds of slides

- **Owned slides** (`own` in `decks.json`) are rebuilt from scratch every run: chart, headline, subtitle, footer. Edits made in the Slides editor are overwritten the next morning, so wording changes go into `render.py`.
- **Patched files** (`patch`) keep everything as written; only recognised numbers change (student counts; client counts and percentages). If a patched file's wording changes so no number matches, the run reports it instead of guessing.

The top-25 law school slide is also owned by the run — see its own section below.

## Top-25 law school slide

- The slide compares the Class of 2029 with the Class of 2028 for the US News top-25 schools (28 schools, because of ties). It lives on two slides: BigLaw deck `b23` and Midsize deck `m20`.
- The data comes from Flo's production database through Metabase (database 2), not from the tracker.
- Its school list, ranks, SQL, logo blobs and slide template are in `top25.json` and `top25.py` in the private "Deck Sync Settings" artifact, not in this repo. They hold database table names and school IDs, and this repo is public. **Never commit them here.**
- How a run works: run the SQL → save the rows as `[[SCHOOL_ID, c29, c28_ly, c28_all], …]` (SCHOOL_ID 0 is the total row) → run `python3 -I top25.py top25.json rows.json "<Mon D, YYYY>" OUTDIR` → publish `OUTDIR/<deck id>/project/slides/<id>.html`.
- Safety rules:
  - It only publishes if the live slide still says "TOP 25 LAW SCHOOLS", so it never overwrites a slide someone replaced.
  - It doesn't publish if the query fails, a school is missing, or the total row is missing.
  - This step runs even when the tracker build fails.
- The slide is owned by the run: edits made in the Slides editor are overwritten the next weekday. To change the wording, ranks or school list, edit `top25.json` or `top25.py` in the settings artifact. Ask Claude in Cowork to do it.

## Rules the numbers follow

- Headlines compare the latest full month with the same month last year, adding "with October up X% so far" when the month in progress already beats last year's full month. A drop switches to neutral wording; it never says "down".
- The month in progress is drawn dashed only through the 14th.
- Student count: "law students and new graduates" (all classes the tracker has) by default; "current law students" only where a slide says so. Rounded down to the nearest 500, with a "+".
- Client counts round down to the nearest 5 with a "+". Percentages round to the nearest 5%, with a "+" when that rounds down.
- A client stat that would make a deck show a lower figure is **held** until Hannah or Collin approves it.
- BigLaw slides use 500+ attorney data; Midsize slides use under-500 data, and say so in bold.

### How approvals work

- A held decrease is listed under "Held for approval" in the daily Slack summary.
- To apply it, Hannah Kelly or Collin Katz replies in that summary's thread with `approve` (applies all) or `approve <key>`, for example `approve amlaw100_forward`.
- The next weekday run reads the newest "Deck data update" thread, applies the approvals, and saves `client_stats.json`.
- Replies from anyone else are ignored.
- Currently held: `amlaw100_forward` (decks keep 70%; HubSpot shows 65%+). It was kept at 70% on purpose at rollout.

## Monday client-stats pull

- Each entry in `client_stats.json` → `reports` is a saved report on the HubSpot dashboard "Client Stats for Sales Team's Decks" (15691105).
- A report's count is the sum of its "(Count) Companies" column. Some reports split this into rows by firm size, and the run adds them up.
- A report that fails to fetch keeps its stored value and is listed under "Problems".

## Commands

```bash
python3 decksync/run.py check --data pipeline/data.json        # CI: every generator renders
python3 decksync/run.py files                                   # what the task must read from each deck
python3 decksync/run.py build --data data.json --work work --clients client_stats.json
python3 decksync/run.py merge-clients --fresh fresh.json --clients client_stats.json
python3 decksync/run.py approve amlaw100_forward --clients client_stats.json
```

## Known issue: the tracker build is being blocked

- Since Oct 28, the scheduled run's safety settings have refused to run `render.py` / `run.py` downloaded from GitHub. They treat it as outside code.
- So the 9 tracker decks have not been rebuilt since data through Oct 26. The top-25 slide still updates, because `top25.py` comes from the private settings artifact, which the run accepts.
- Until this is fixed, run the build by hand (see below).

## Run it by hand

For whoever has Claude with the Artifact tool, when the scheduled run can't rebuild the tracker decks. Do it in this order:

1. `python3 decksync/run.py files` — lists, per deck, the files the build needs.
2. For each deck, read its listed paths with the Artifact tool and save them into `work/<deck id>/<path>`.
3. `python3 decksync/run.py build --data data.json --work work --clients client_stats.json` — writes `work/changes.json`.
4. Publish exactly what `work/changes.json` lists for each deck, and nothing else.

## If the tracker data changes

`check` runs on every pull request that touches `pipeline/**`. If a field the slides use is renamed or removed, it fails there. If something slips through, the daily run keeps the old slide and lists it under "problems" in Slack rather than publishing a broken one.

## If the repo moves or goes private

Change `data_url` in `decks.json` (and the code URL in the scheduled task's prompt, `SCHEDULED_TASK.md`). If the repo becomes private, the scheduled task needs another way to read the data: keep the repo public, publish `charts.json` on resources.joinflo.com and allowlist that domain in Claude, or give the Claude GitHub app access to the repo.

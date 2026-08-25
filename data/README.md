# Data Reproduction

This document describes how to reproduce the full dataset from scratch.

The final merged CSV (`ironman_merged.csv`, 516 MB, 2,706,922 records) is the dataset described in the manuscript. The de-identified file deposited on Zenodo carries 27 of its 28 columns and 2,706,867 of its records (475 MB): https://doi.org/10.5281/zenodo.19284673

To regenerate it from the original sources, follow the steps below.

## Prerequisites

```bash
pip install requests pandas
```

## Step 1 — Scrape official IRONMAN results

The primary source is the official IRONMAN® results platform (labs-v2.competitor.com). Event UUIDs are provided in `collection/event_uuids_full.csv` (128 event series).

```bash
cd collection
python scrape_official.py
```

- Downloads results for the race editions listed in `all_subevents.csv`; 1,172 of the 1,235 return results
- Saves individual JSON files in `results/{slug}_{year}.json`
- Progress is tracked in `scrape_progress.json` (resumable)
- Rate-limited: 2.0 s between API requests
- Estimated time: 2–4 hours

### UUID discovery

UUIDs were extracted from ironman.com result pages:

```
https://www.ironman.com/{race-slug}-results
```

The HTML source contains a link to `competitor.com/results/event/{UUID}`. The 128 discovered UUIDs are listed in `event_uuids_full.csv`. The subevent index (`all_subevents.csv`, 1,235 entries) maps each event series to its individual race editions by year.

Rows carrying `reconstructed = yes` were rebuilt from the collected results by `notebooks/r1_event_coverage.py`. The saved enumeration originally omitted four series that were nevertheless collected — the World Championship, Kalmar, Emilia-Romagna and Cascais — so the index did not describe what the pipeline had actually retrieved. Sixty-three of the 1,235 editions return no results at all; 28 of those belong to the 2021 season.

## Step 2 — Combine official JSONs into CSV

```bash
python combine_official.py
```

- Reads all JSON files from `results/`
- Outputs `ironman_official_all.csv` (~457 MB, 2,041,743 records)
- Derives finish_status, race_type, and race_year from raw fields

## Step 3 — Scrape CoachCox supplement

The secondary source (coachcox.co.uk) provides results for event series not available on the official platform.

```bash
python scrape_coachcox.py
```

- Race IDs are discovered from `race_metadata.csv` (587 known IDs) plus an automated scan of 500 consecutive IDs
- Saves individual JSON files in `results/race_{id}.json`
- Rate-limited: 1.5 s between requests
- Estimated time: ~30 minutes

## Step 4 — Combine CoachCox JSONs into CSV

```bash
python combine_coachcox.py
```

- Outputs `coachcox_all_results.csv` (~263 MB, 1,664,170 records)

## Step 5 — Merge sources

```bash
python merge_sources.py
```

- Official source is primary; CoachCox fills gaps only for race-years not represented in the official dataset
- Overlap detection via normalized event name + year + race type
- Adds `source` column ("official" or "coachcox") for provenance tracking
- Fields exclusive to official (AWA points, distance_km) are empty for CoachCox records
- Outputs `ironman_merged.csv` (516 MB, 2,706,922 records)

Dry run (no output, just shows what would be merged):

```bash
python merge_sources.py --dry-run
```

## Cross-source validation

Every race-year present in both sources was compared — 559 of them, spanning 2003 to 2026, 340 full-distance and 219 half-distance. Record counts differ by two or fewer athletes for 484 of the 559 (86.6%). Among matched athletes, 4,732,776 athlete-discipline pairs were compared across all six disciplines, of which 98.76% agree exactly to the second.

The two sources are not independent measurements: the supplementary source aggregates results published by the same timing operation that supplies the official platform. The agreement therefore demonstrates faithful transcription through two separate collection pipelines, not independent measurement of the underlying times.

Athlete matching is run under three rules — case-insensitive exact, NFKD-normalised, and order-invariant — because the supplementary source stores names as "Lastname, Firstname" for the 2017-2019 seasons while the official platform stores "Firstname Lastname". See `notebooks/r1_expanded_cross_source.py`.

## Schema

The merged CSV contains 28 columns. See Table 1 in the manuscript for the complete schema with data types, descriptions, and coverage percentages.

## Notes

- All scripts use only `requests` for HTTP communication (no browser automation)
- Self-imposed rate limiting respects both platforms' infrastructure
- The CoachCox scraper references a Kaggle races.csv for initial race IDs; this can be replaced with `race_metadata.csv`
- Large CSV files are not tracked in git — they are reproducible via the scripts above and available on Zenodo

# Data Reproduction

This document describes how to reproduce the dataset from scratch, and which version of it the article describes.

## Versions

| Version | Zenodo | Collected | Merged records | Deposited records | Notes |
|---|---|---|---|---|---|
| 3.0.0 | [10.5281/zenodo.22097794](https://doi.org/10.5281/zenodo.22097794) | 27–28 March 2026 | 2,706,922 | 2,706,867 | **The version described in the article** (*Sci* 2026, 8(9), 265). Carries the merge defect described below: 66 race-years are present from both sources (127,164 deposited records, 4.7%). |
| 4.0.0 | [10.5281/zenodo.23421027](https://doi.org/10.5281/zenodo.23421027) | 15 October 2026 (new material); March 2026 editions retained | 3,632,323 | 3,632,230 | 2026 season to 15 October; 49 event series added (177); the aggregator's full catalogue (2,330 races) instead of the 947 of March; merge corrected (athlete-level check). |

The concept DOI always resolves to the latest version. Cite the version you used.

### Version 3.0.0 — a defect in the merge, found on 15 October 2026

The merge (step 5) matched the two sources by normalised event name, year and race type. Race-years that the sources name differently ("Ironman Sweden" / "IRONMAN Kalmar-Sweden", "Ironman 70.3 Oceanside" / "IRONMAN 70.3 Oceanside California", "Ironman Frankfurt" / "IRONMAN European Championship Frankfurt") passed that check and were taken from both sources. In version 3.0.0 this affects 66 of the 388 supplementary race-years: 127,164 deposited records (4.70%), of which 8,963 DNF records. The article's counts for the aggregator share (24.6%) and for supplementary race-years (382) are overstated by that amount; the quality-assessment results are unaffected in kind, since the duplicated records are faithful copies of official records.

`notebooks/v3_duplicate_race_years.py` identifies the affected records on the deposited v3 file by athlete overlap (bib number and overall time against the official records of the same year and race type) and writes `notebooks/results/v3_duplicate_race_years.csv` (one row per affected race-year, with `event_id`); dropping the aggregator rows of those `event_id`s yields a file without the defect. Version 4.0.0 applies the same check inside the merge.

## Prerequisites

```bash
pip install requests pandas
```

## Step 0 — Discover event series (added for version 4.0.0)

```bash
cd collection
python discover_events.py            # ~5 minutes; --dry-run lists the candidate pages only
```

- Reads the sitemap of ironman.com, keeps the race pages whose slug starts with `im-` or `im703-`, and extracts the results-platform UUID from each `/races/<slug>/results` page
- Writes `event_uuids_discovered_<date>.csv` and prints the series not yet in `event_uuids_full.csv`
- In March 2026 the site refused programmatic requests and the 128 UUIDs were collected by hand; on 15 October 2026 the discovery found 189 candidate pages, 170 with a UUID, 49 of them new. Fourteen pages answered with an access error (HTTP 403) on repeated attempts and their series are not collected: `im703-bangsaen`, `im703-doha`, `im703-laoag`, `im703-mamaia`, `im703-marbella`, `im703-sharm-el-sheikh`, `im703-st-poelten`, `im703-veracruz`, `im703-vilamoura-algarve`, `im-knokke-heist`, `im-mossel-bay`, `im-oman`, `im-san-juan`, `im-valdivia`.

## Step 1 — Scrape official IRONMAN results

The primary source is the official IRONMAN® results platform (labs-v2.competitor.com). Event UUIDs are in `collection/event_uuids_full.csv` (177 event series; the 49 added on 15 October 2026 follow the comment line `# added 2026-10-15 refresh`).

```bash
python scrape_official.py            # first collection: every edition of every series
python scrape_official.py --refresh  # later: re-list the series, download the editions missing locally, re-download the seasons in REFRESH_YEARS
```

- Saves one JSON per edition in `results/{slug}_{year}.json`; progress in `scrape_progress.json` (resumable). `--refresh` ignores the progress file and writes the enumeration to `all_subevents_<date>.csv`
- Rate-limited: 2.0 s between API requests. Full collection 2–4 hours; the 15 October refresh (324 editions) took one hour
- `all_subevents.csv` is the enumeration of 15 October 2026: 1,571 editions, 1,478 of which return results (2,529,950 records). The 93 editions without results include 36 of the 2021 season (pandemic cancellations). One edition (2022 IRONMAN 70.3 Salalah) answered HTTP 500 during the refresh and was collected on a second attempt. The March 2026 enumeration is kept as `all_subevents_v3_2026-03.csv`; its 43 rows marked `reconstructed = yes` were rebuilt by `notebooks/r1_event_coverage.py` because the saved enumeration omitted four series (World Championship, Kalmar, Emilia-Romagna, Cascais); the platform lists all 43 editions now.
- For the IRONMAN® 70.3 World Championship (2017–2019, 2022–2026) and the IRONMAN® World Championship (2023–2025) the platform publishes the men's and women's races as separate editions; for some years only one of the two returns results.

## Step 2 — Combine official JSONs into CSV

```bash
python combine_official.py
```

- Reads all JSON files from `results/`; derives finish_status, race_type and race_year
- Outputs `ironman_official_all.csv` (v3: 2,041,743 records; v4: 2,529,950)

## Step 3 — Scrape the CoachCox supplement

The secondary source (coachcox.co.uk) provides results for race-years not available on the official platform.

```bash
python scrape_coachcox.py            # March 2026 method: race IDs from race_metadata.csv plus a scan above the highest known ID
python scrape_coachcox.py --refresh  # October 2026: list the full catalogue (/all/im and /all/him), download the races missing locally
```

- The March 2026 collection was seeded from a public race list (the Kaggle "Ironman 140.6" race table) and scanned only above its highest ID; it identified 947 races. The aggregator's own catalogue lists 2,330 (IDs 1–2859). `--refresh` requested the 1,383 missing races: 1,194 returned results, 189 are empty (future, cancelled or unpublished editions). `race_metadata.csv` now holds all 2,141 collected races; `all_races_<date>.csv` is the catalogue on the day
- Saves `results/race_{id}.json`; rate-limited 1.5 s between requests
- The catalogue lists IRONMAN 70.3 Japan 2012–2019 under two series with the same athletes (identical bib numbers and split times); one copy (race IDs 2005–2012) is excluded at the merge

## Step 4 — Combine CoachCox JSONs into CSV

```bash
python combine_coachcox.py
```

- Outputs `coachcox_all_results.csv` (v3: 1,664,170 records; v4: 3,592,917)

## Step 5 — Merge sources

```bash
python merge_sources.py --dry-run    # shows what would be merged, writes nothing
python merge_sources.py
```

- Official source is primary; CoachCox fills gaps only for race-years not represented in the official dataset
- Candidate detection by normalised event name + year + race type (as in version 3.0.0), **and, since version 4.0.0, an athlete-level check**: a candidate race whose records (bib number and overall time) are at least 50% already present among the official records of the same year and race type is the same race and is dropped. Measured shares are bimodal (≥ 0.99 for the same race, ≤ 0.13 otherwise). On 15 October 2026 the check dropped 192 races (366,926 records) that the name-based rule had kept
- `SUPPLEMENTARY_EXCLUDED_RACE_IDS` lists catalogue entries excluded by hand, with the reason (the duplicate Japan listing)
- Every race dropped is written to `supplement_excluded.csv` with its reason; the merge also prints race-years with more than one supplementary race ID (Arizona 2008 is two real races, April and November)
- Adds `source` column ("official" or "coachcox"); fields exclusive to the official platform (AWA points, distance_km) are empty for CoachCox records
- Outputs `ironman_merged.csv` (v4: 3,632,323 records, 651 MB; 2,529,950 official = 69.7%, 1,102,373 supplementary = 30.3%, 702 supplementary race-years)

## Step 6 — De-identified deposit

```bash
python ../../notebooks/r1_build_deposit.py
```

Drops the `name` column and the records carrying the aggregator's own redaction marker (55 in v3; 93 in v4). Output `ironman_dataset_deidentified.csv` (v4: 3,632,230 records, 626 MB), the file deposited on Zenodo.

## Quality assessment, by version

The scripts in `notebooks/` are those of the article. `notebooks/results/` holds their outputs on version 3.0.0 (the numbers printed in the article); `notebooks/results_v4/` holds the same scripts re-run on version 4.0.0 (`IRONMAN_RESULTS_DIR=$PWD/results_v4 python3 <script>`). Differences a reuser should know:

| | v3.0.0 | v4.0.0 |
|---|---|---|
| T1 / T2 coverage | 84.2% / 84.1% | 78.3% / 78.5% |
| `country_iso2` coverage | 74.2% | 68.6% |
| Half-distance (70.3) share of records | 50.5% | 64.2% |
| Internal consistency (splits sum to overall within 1 s) | 98.30% | 98.26% |
| Cross-source agreement (race-years in both sources; athlete-discipline pairs equal to the second) | 559 race-years; 98.76% of 4,732,776 pairs | 1,237 race-years; 99.23% of 9,600,332 pairs |

`notebooks/v4_conformance_audit.py` checks a new version against the previous deposit (schema, line endings, de-identification, domains, merge rule, duplicates, continuity of every v3 race-year) and writes `results_v4/v4_conformance_audit.txt`.

## Cross-source validation

Every race-year present in both raw sources is compared by `notebooks/r1_expanded_cross_source.py`. The two sources are not independent measurements: the supplementary source aggregates results published by the same timing operation that supplies the official platform. The agreement therefore demonstrates faithful transcription through two separate collection pipelines, not independent measurement of the underlying times. Athlete matching is run under three rules (case-insensitive exact, NFKD-normalised, order-invariant) because the supplementary source stores names as "Lastname, Firstname" for the 2017–2019 seasons while the official platform stores "Firstname Lastname".

## Schema

The merged CSV contains 28 columns; the deposit 27 (no `name`). See Table 1 in the article for the complete schema with data types and descriptions; coverage percentages in the article refer to version 3.0.0 (recomputed for v4 in `notebooks/results_v4/r1_table1_coverage_recomputed.csv`).

## Notes

- All scripts use only `requests` for HTTP communication (no browser automation); self-imposed rate limiting respects both platforms
- Large CSV files are not tracked in git; they are reproducible via the scripts above and available on Zenodo

## Note on the CoachCox API version

The article prints the supplementary endpoint as `.../imstats/v1.90/race/results/{race-id}` with the access date 27 March 2026, which was the namespace version that day. The maintainer has since moved it to `v1.92`; `scrape_coachcox.py` uses `v1.92`. If the scraper returns `404 rest_no_route`, look up the current namespace at https://www.coachcox.co.uk/wp-json/ and update `BASE_URL`.

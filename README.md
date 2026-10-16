# A Validated, Population-Scale Dataset of 2.7 Million IRONMAN® Triathlon Records with Separated Transition Times (2002–2026)

Companion repository — data-collection pipeline, analysis scripts, and figures — for the IRONMAN® triathlon dataset described in the published article:

> Seffrin, A.; Nikolaidis, P.T.; Andrade, M.S.; Villiger, E.; Rosemann, T.; Weiss, K.; Ferreira, D.; Knechtle, B. A Validated, Population-Scale Dataset of 2.7 Million IRONMAN® Triathlon Records with Separated Transition Times (2002–2026). *Sci* **2026**, *8*(9), 265. https://doi.org/10.3390/sci8090265

Open access (CC BY 4.0), published 19 September 2026 under Open Peer Review: the review reports and the authors' responses are available with the article.

## Authors

Aldo Seffrin¹ (ORCID 0000-0001-8229-8565), Pantelis Theodoros Nikolaidis² (0000-0001-8030-7122), Marilia Santos Andrade³ (0000-0002-7004-4565), Elias Villiger⁴ (0000-0001-8371-1390), Thomas Rosemann⁴ (0000-0002-6436-6306), Katja Weiss⁴ (0000-0003-1247-6754), Daniel Ferreira¹ (0000-0002-8958-9442), Beat Knechtle⁴ˌ⁵ (0000-0002-2412-9103)\*

¹ Nova O2 Sports Science, São Paulo 12246-020, Brazil
² School of Health and Caring Sciences, University of West Attica, 12243 Athens, Greece
³ Department of Physiology, Federal University of São Paulo (UNIFESP), São Paulo 04023-062, Brazil
⁴ Institute of Primary Care, University of Zurich, 8091 Zurich, Switzerland
⁵ Medbase St. Gallen Am Vadianplatz, Vadianstrasse 26, 9001 St. Gallen, Switzerland

\* Corresponding author

## Dataset versions

The concept DOI https://doi.org/10.5281/zenodo.19284673 always resolves to the latest version. **The article describes version 3.0.0.** Cite the version you used.

| | Version 3.0.0 (described in the article) | Version 4.0.0 |
|---|---|---|
| Zenodo | [10.5281/zenodo.22097794](https://doi.org/10.5281/zenodo.22097794) | latest version under the concept DOI |
| Collected | 27–28 March 2026 | 15 October 2026 (new material; March editions retained) |
| Records described / deposited | 2,706,922 / 2,706,867 | 3,632,323 / 3,632,230 |
| Race-years | 1,554 | 2,180 (1,478 official + 702 supplementary) |
| Years | 2002–2026 (2026 partial) | 2002–2026 (2026 to 15 October, partial) |
| Event series (official platform) | 128 | 177 |
| Full / half distance | 49.5% / 50.5% | 35.8% / 64.2% |
| Source: official / supplement | 75.4% / 24.6% | 69.7% / 30.3% |
| T1 / T2 coverage | 84.2% / 84.1% | 78.3% / 78.5% |
| Cross-source agreement | 98.76% of 4,732,776 pairs, 559 race-years | 99.23% of 9,600,332 pairs, 1,237 race-years |
| Redacted records withdrawn from the deposit | 55 | 93 |

Version 4.0.0 extends the 2026 season, adds 49 event series found by a systematic
discovery on the organizer's website, replaces the March 2026 supplementary
collection (947 races, seeded from a public race list) with the aggregator's full
catalogue (2,330 races), and corrects the merge.

**Defect in version 3.0.0, found on 15 October 2026.** The merge matched the two
sources by event name only, and 66 race-years that the sources name differently
("Ironman Sweden" / "IRONMAN Kalmar-Sweden") are present from both sources:
127,164 deposited records (4.70%), 8,963 of them DNF records. The article's
aggregator share (24.6%) and supplementary race-year count (382) are overstated by
that amount. `notebooks/v3_duplicate_race_years.py` lists the affected records on
the deposited v3 file (`notebooks/results/v3_duplicate_race_years.csv`); version
4.0.0 applies the same athlete-level check inside the merge. Details in
[`data/README.md`](data/README.md).

## Data availability

The de-identified dataset (athlete names removed) is openly deposited on Zenodo under a Creative Commons Attribution 4.0 International (CC BY 4.0) licence: https://doi.org/10.5281/zenodo.19284673 — a concept DOI that always resolves to the current version. The data derive from publicly available race results: the official IRONMAN® results platform and the CoachCox aggregator. The full dataset can also be reproduced from source with the collection scripts below.

## Reproduction

Collection scripts are in `data/collection/`; see [`data/README.md`](data/README.md) for step-by-step instructions.

```bash
pip install -r requirements.txt

cd data/collection
python discover_events.py      # ~5min, event series from ironman.com (v4)
python scrape_official.py      # ~2-4h, official IRONMAN® platform (--refresh to update)
python combine_official.py     # JSON to CSV

python scrape_coachcox.py      # supplementary source (--refresh lists the full catalogue)
python combine_coachcox.py     # JSON to CSV

python merge_sources.py        # Merge into unified dataset (athlete-level check since v4)
```

Analysis scripts are in `notebooks/`. Each writes a CSV to `notebooks/results/`
(version 3.0.0, the numbers in the article) or, with
`IRONMAN_RESULTS_DIR=$PWD/results_v4`, to `notebooks/results_v4/` (version 4.0.0),
carrying a provenance header — when it ran, against which input file, at what
size, and in which environment. Every quantitative claim in the manuscript is
checked against those files by `notebooks/r1_manuscript_number_audit.py`, which
exits non-zero on any mismatch.

These scripts read the merged dataset. Download the deposited file from Zenodo
and place it at `data/collection/ironman_merged.csv`, or rebuild it with the
collection scripts above; note that the deposited file has athlete names removed
and fewer records (55 in v3, 93 in v4), so analyses that depend on either will differ.

```bash
python notebooks/r1_manuscript_number_audit.py   # verifies 100 claims
python notebooks/generate_tables.py              # rebuilds Tables 1 and 2
python notebooks/generate_figures.py             # rebuilds Figures 1-5
```

## Structure

```
data/
├── collection/
│   ├── scrape_official.py       # Official IRONMAN® platform scraper
│   ├── scrape_coachcox.py       # Supplementary source scraper
│   ├── combine_official.py      # Official JSON to CSV consolidation
│   ├── combine_coachcox.py      # Supplementary JSON to CSV consolidation
│   ├── merge_sources.py         # Deterministic merge procedure (athlete-level check, v4)
│   ├── discover_events.py       # Event series discovery from ironman.com (v4)
│   ├── event_uuids_full.csv     # 177 event series (official platform; 128 in v3)
│   ├── all_subevents.csv        # 1,571 race editions (v4); all_subevents_v3_2026-03.csv: v3
│   ├── race_metadata.csv        # Supplementary race metadata (2,141 races)
│   └── supplement_excluded.csv  # Races dropped by the merge, with the reason
└── README.md                    # Reproduction instructions

notebooks/
├── _common.py                   # Paths, dtypes, colours, result writing
├── generate_figures.py          # Figures 1-5
├── generate_tables.py           # Tables 1 and 2
├── r1_manuscript_number_audit.py# Verifies every manuscript number
├── r1_*.py                      # One analysis per script
├── v4_conformance_audit.py      # New version vs previous deposit (schema, merge, duplicates, continuity)
├── v3_duplicate_race_years.py   # Race-years present from both sources in a deposit
├── results/                     # Outputs on version 3.0.0, with provenance headers
└── results_v4/                  # The same scripts on version 4.0.0

figures/
├── Figure1.tiff                 # Dataset composition by source and race type
├── Figure2.tiff                 # Temporal trends in participation and performance
├── Figure3.tiff                 # Split time distributions
├── Figure4.tiff                 # Participation by sex over time
└── Figure5.tiff                 # Transition time coverage, T1 and T2
```

## Notes on the revision history

Script docstrings reference the review comments they answer, using the identifiers
from the peer-review rounds (`R1-Rev1-*`, `R1-Rev2-*` for reviewer comments,
`R1-Int-*` for issues the authors found themselves). The article was reviewed under
Open Review, so the reports and the point-by-point responses are published with it.

The figures were renumbered in the second round to follow their order of first
citation (R1 → R2: 1→1, 4→2, 2→3, 5→4, 3→5); a figure number quoted in the
first-round response letter refers to the old numbering. At proofreading the
axis ticks and panel labels of Figures 1–3 were reformatted to the journal's number
style (thousands separator from five digits up); the data drawn did not change.

The two exploratory notebooks previously in `notebooks/` have been removed rather
than updated. Both computed field coverage with a null check, which overstates it
by roughly ten percentage points because the split-time columns store zero as well
as missing values, and the figure notebook assigned category labels positionally,
which transposed the two data sources in one figure. The scripts above replace
them and are checked by the numeric audit.

## Licence

MIT — Copyright (c) 2026 Nova O2 Sports Science

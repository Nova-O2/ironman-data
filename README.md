# A Validated, Population-Scale Dataset of 2.7 Million IRONMAN® Triathlon Records with Separated Transition Times (2002–2026)

Companion repository — data-collection pipeline, analysis scripts, and figures — for the IRONMAN® triathlon dataset described in the accompanying manuscript (under review).

## Authors

Aldo Seffrin¹ (ORCID 0000-0001-8229-8565), Pantelis Theodoros Nikolaidis² (0000-0001-8030-7122), Marilia Santos Andrade³ (0000-0002-7004-4565), Elias Villiger⁴ (0000-0001-8371-1390), Thomas Rosemann⁴ (0000-0002-6436-6306), Katja Weiss⁴ (0000-0003-1247-6754), Daniel Ferreira¹ (0000-0002-8958-9442), Beat Knechtle⁴ˌ⁵ (0000-0002-2412-9103)\*

¹ Nova O2 Sports Science, São Paulo, Brazil
² School of Health and Caring Sciences, University of West Attica, Athens, Greece
³ Department of Physiology, Federal University of São Paulo (UNIFESP), São Paulo, Brazil
⁴ Institute of Primary Care, University of Zurich, Zurich, Switzerland
⁵ Medbase St. Gallen Am Vadianplatz, St. Gallen, Switzerland

\* Corresponding author

## Dataset

| Metric | Value |
|--------|-------|
| Records described | 2,706,922 |
| Records deposited | 2,706,867 |
| Race-years | 1,554 |
| Years | 2002–2026 (2026 partial; collected 27–28 March 2026) |
| Full-distance (IRONMAN®) | 1,340,799 (49.5%) |
| Half-distance (IRONMAN® 70.3) | 1,366,123 (50.5%) |
| Source: official | 2,041,743 (75.4%) |
| Source: supplement | 665,179 (24.6%) |
| T1 / T2 coverage | 84.2% / 84.1% |
| Cross-source agreement | 98.76% of 4,732,776 athlete-discipline pairs, over all 559 race-years present in both sources |

The described and deposited record counts differ by 55. Those records carried an
explicit redaction applied by the supplementary source; that suppression is
propagated into the deposit rather than reversed.

## Data availability

The de-identified dataset (athlete names removed) is openly deposited on Zenodo under a Creative Commons Attribution 4.0 International (CC BY 4.0) licence: https://doi.org/10.5281/zenodo.19284673 — a concept DOI that always resolves to the current version. The data derive from publicly available race results: the official IRONMAN® results platform and the CoachCox aggregator. The full dataset can also be reproduced from source with the collection scripts below.

## Reproduction

Collection scripts are in `data/collection/`; see [`data/README.md`](data/README.md) for step-by-step instructions.

```bash
pip install -r requirements.txt

cd data/collection
python scrape_official.py      # ~2-4h, official IRONMAN® platform
python combine_official.py     # JSON to CSV

python scrape_coachcox.py      # ~30min, supplementary source
python combine_coachcox.py     # JSON to CSV

python merge_sources.py        # Merge into unified dataset
```

Analysis scripts are in `notebooks/`. Each writes a CSV to `notebooks/results/`
carrying a provenance header — when it ran, against which input file, at what
size, and in which environment. Every quantitative claim in the manuscript is
checked against those files by `notebooks/r1_manuscript_number_audit.py`, which
exits non-zero on any mismatch.

These scripts read the merged dataset. Download the deposited file from Zenodo
and place it at `data/collection/ironman_merged.csv`, or rebuild it with the
collection scripts above; note that the deposited file has athlete names removed
and 55 fewer records, so analyses that depend on either will differ.

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
│   ├── merge_sources.py         # Deterministic merge procedure
│   ├── event_uuids_full.csv     # 128 event series (official platform)
│   ├── all_subevents.csv        # 1,235 race editions
│   └── race_metadata.csv        # Supplementary race metadata
└── README.md                    # Reproduction instructions

notebooks/
├── _common.py                   # Paths, dtypes, colours, result writing
├── generate_figures.py          # Figures 1-5
├── generate_tables.py           # Tables 1 and 2
├── r1_manuscript_number_audit.py# Verifies every manuscript number
├── r1_*.py                      # One analysis per script
└── results/                     # Analysis outputs, with provenance headers

figures/
├── Figure1.tiff                 # Dataset composition by source and race type
├── Figure2.tiff                 # Split time distributions
├── Figure3.tiff                 # Transition time coverage, T1 and T2
├── Figure4.tiff                 # Temporal trends in participation and performance
└── Figure5.tiff                 # Participation by sex over time
```

## Notes on this revision

Script docstrings reference the review comments they answer, using the identifiers
from the peer-review round (`R1-Rev1-*`, `R1-Rev2-*` for reviewer comments,
`R1-Int-*` for issues the authors found themselves). The manuscript is under Open
Review, so the reports and the point-by-point response are published with it.

The two exploratory notebooks previously in `notebooks/` have been removed rather
than updated. Both computed field coverage with a null check, which overstates it
by roughly ten percentage points because the split-time columns store zero as well
as missing values, and the figure notebook assigned category labels positionally,
which transposed the two data sources in one figure. The scripts above replace
them and are checked by the numeric audit.

## Licence

MIT — Copyright (c) 2026 Nova O2 Sports Science

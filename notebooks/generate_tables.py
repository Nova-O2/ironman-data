"""Generate manuscript tables from audited results.

Table 1 was wrong in 20 of its 28 coverage values (R1-Int-2) because it was typed
once from an earlier data state and never regenerated. Hand-correcting twenty cells
would fix the instance and leave the mechanism intact. This builds the table from
`results/r1_table1_coverage_recomputed.csv`, so the only way for it to go stale is
for nobody to run it — which `r1_manuscript_number_audit.py` then catches.

Schema descriptions, types and examples are static editorial content and live here.
Coverage is never typed by hand.

Run:  uv run --no-project --with pandas python notebooks/generate_tables.py
"""

from pathlib import Path

import pandas as pd

import _common as C

TABLES_DIR = C.PAPER_DIR / 'manuscript' / 'tables'
COVERAGE_CSV = C.RESULTS_DIR / 'r1_table1_coverage_recomputed.csv'

# Records withdrawn from the deposit because the supplementary source had redacted
# them (R1-Int-4). Described N and deposited N are no longer the same file.
DESCRIBED_N = 2_706_922
REDACTION_COHORT = 55
DEPOSITED_N = DESCRIBED_N - REDACTION_COHORT

# field -> (type, description, example, in_deposit)
# The name row's example was a real athlete's name in the submitted version; it is a
# placeholder here (PC-Ed-3).
SCHEMA = [
    ('name', 'string', 'Athlete full name', '"[athlete name]"', False),
    ('bib', 'integer', 'Bib number', '31', True),
    ('country', 'string', 'Country of representation (free text; see Usage notes)', '"United States"', True),
    ('country_iso2', 'string', 'ISO 3166-1 alpha-2 country code', '"US"', True),
    ('age_group', 'string', 'Age group division or professional category', '"M35-39", "FPRO"', True),
    ('event_name', 'string', 'Full event name including year', '"2024 IRONMAN Florida"', True),
    ('event_id', 'string', 'Unique event identifier (UUID)', '"af3f560c-..."', True),
    ('swim_sec', 'integer', 'Swim split time in seconds', '3318', True),
    ('t1_sec', 'integer', 'Transition 1 time in seconds (swim→bike)', '291', True),
    ('bike_sec', 'integer', 'Cycling split time in seconds', '16863', True),
    ('t2_sec', 'integer', 'Transition 2 time in seconds (bike→run)', '146', True),
    ('run_sec', 'integer', 'Running split time in seconds', '10722', True),
    ('overall_sec', 'integer', 'Overall finish time in seconds', '31341', True),
    ('finish_status', 'string', 'Race completion status', '"FIN", "DNF", "DNS", "DQ"', True),
    ('rank_overall', 'integer', 'Overall finish rank', '1', True),
    ('rank_gender', 'integer', 'Finish rank within gender', '1', True),
    ('rank_group', 'integer', 'Finish rank within age group', '1', True),
    ('swim_rank', 'integer', 'Overall swim split rank', '9', True),
    ('bike_rank', 'integer', 'Overall cycling split rank', '4', True),
    ('run_rank', 'integer', 'Overall running split rank', '1', True),
    ('awa_points', 'integer', 'All World Athlete qualification points', '5000', True),
    ('swim_distance_km', 'float', 'Swim distance completed in kilometers', '3.8624', True),
    ('bike_distance_km', 'float', 'Cycling distance completed in kilometers', '180.279', True),
    ('run_distance_km', 'float', 'Running distance completed in kilometers', '42.036', True),
    ('total_distance_km', 'float', 'Total distance completed in kilometers', '226.178', True),
    ('race_type', 'string', 'Race distance category', '"im" (full), "him" (half)', True),
    ('race_year', 'integer', 'Year of the race', '2024', True),
    ('source', 'string', 'Data provenance', '"official", "coachcox"', True),
]

# Fields present only for records from the official source.
OFFICIAL_ONLY = {'country_iso2', 'awa_points', 'swim_distance_km', 'bike_distance_km',
                 'run_distance_km', 'total_distance_km'}


def build_table1() -> str:
    cov = pd.read_csv(COVERAGE_CSV, comment='#').set_index('field').actual_pct
    missing = [f for f, *_ in SCHEMA if f not in cov.index]
    if missing:
        raise KeyError(f'no recomputed coverage for {missing}; rerun '
                       'r1_consistency_and_coverage.py')

    lines = [
        f'**Table 1.** Dataset schema. Each row describes one column in the merged '
        f'CSV file (N = {DESCRIBED_N:,} records). The "Deposited" column indicates '
        f'whether the field is present in the de-identified file released on Zenodo '
        f'(N = {DEPOSITED_N:,}).',
        '',
        '| Column | Type | Description | Example | Coverage (%) | Deposited |',
        '|--------|------|-------------|---------|:------------:|:---------:|',
    ]
    for field, dtype, desc, example, deposited in SCHEMA:
        pct = f'{cov[field]:.1f}'
        if field in OFFICIAL_ONLY:
            pct += '*'
        lines.append(f'| {field} | {dtype} | {desc} | {example} | {pct} | '
                     f'{"Yes" if deposited else "No"} |')

    lines += [
        '',
        '*Fields marked with * are available only for records from the official '
        'source (75.4% of the dataset). Coverage percentages are computed over the '
        'full merged dataset, counting a field as present when it holds a non-empty '
        'value; the split-time fields store zero as well as missing values, and both '
        'are treated as absent. The example value in the name row is a placeholder; '
        'athlete names are not reproduced here and are absent from the deposited '
        f'file, from which a further {REDACTION_COHORT} records were withdrawn '
        'because the supplementary source had redacted them.',
    ]
    return '\n'.join(lines) + '\n'


def build_table2() -> str:
    """Cross-source agreement by season.

    The submitted Table 2 listed six hand-picked races and invited exactly the
    question Reviewer 2 asked: why those six, and are they representative. With
    the comparison run over every race-year both sources hold, there is no
    selection to defend — so the table now reports the whole overlap, by season,
    which also exposes the temporal structure a single pooled figure would hide.
    """
    by = pd.read_csv(C.RESULTS_DIR / 'r1_cross_source_by_year.csv', comment='#')
    summ = pd.read_csv(C.RESULTS_DIR / 'r1_cross_source_summary.csv', comment='#').iloc[0]

    lines = [
        f'**Table 2.** Cross-source agreement by season, over all '
        f'{int(summ.race_years)} race-years present in both sources '
        f'({int(summ.year_min)}–{int(summ.year_max)}; {int(summ.n_full)} full-distance, '
        f'{int(summ.n_half)} half-distance). Agreement is the proportion of matched '
        f'athlete-discipline pairs whose split times are identical to the second.',
        '',
        '| Season | Race-years | Matched pairs | Match rate, exact (%) | '
        'Match rate, order-invariant (%) | Exact time agreement (%) |',
        '|--------|:----------:|--------------:|:---------------------:|'
        ':------------------------------:|:------------------------:|',
    ]
    for r in by.itertuples():
        lines.append(f'| {int(r.year)} | {int(r.races)} | {int(r.pairs):,} | '
                     f'{r.match_exact:.1f} | {r.match_canon:.1f} | {r.agreement_pct:.2f} |')
    lines.append(f'| **All** | **{int(summ.race_years)}** | **{int(summ.split_pairs):,}** | '
                 f'**{summ.match_rate_exact_median:.1f}** | '
                 f'**{summ.match_rate_canon_median:.1f}** | '
                 f'**{summ.split_agreement_pct:.2f}** |')
    lines += [
        '',
        'Match rates in the "All" row are medians across race-years; the other '
        'columns are totals. The gap between the exact and order-invariant rules is '
        'concentrated in 2017–2019, where the supplementary source records names as '
        '"Lastname, Firstname" and exact matching therefore fails almost entirely.',
    ]
    return '\n'.join(lines) + '\n'


def main() -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    path = TABLES_DIR / 'Table1.md'
    path.write_text(build_table1())
    print(f'-> {path.relative_to(C.PAPER_DIR)}')
    path2 = TABLES_DIR / 'Table2.md'
    path2.write_text(build_table2())
    print(f'-> {path2.relative_to(C.PAPER_DIR)}')
    cov = pd.read_csv(COVERAGE_CSV, comment='#')
    changed = cov[cov.status == 'MISMATCH']
    print(f'   coverage taken from {COVERAGE_CSV.name}; '
          f'{len(changed)} of {len(cov)} values differ from the submitted table')


if __name__ == '__main__':
    main()

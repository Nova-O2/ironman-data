"""R1 — audit every quantitative claim in the manuscript against the dataset.

Built after two derived artefacts were found stale (R1-Int-1, Figure 1 with the
data sources transposed; R1-Int-2, Table 1 wrong in 20 of 28 coverage values)
while the Results prose matched the data exactly. Both had been generated from
an earlier data state and never regenerated after the final merge, and neither
was caught before submission.

Fixing those two instances does not prevent the class. This does: every number
the manuscript asserts is registered here with its printed value and its source
location, recomputed from the released dataset, and diffed. Any artefact that
drifts from the data fails loudly instead of shipping.

Run it after any regeneration of tables or figures, and again at the pre-resubmission bundle audit
bundle audit. Exit status is non-zero when anything fails, so it can gate a
build.

Adding a claim: append to CLAIMS with the value as printed, the tolerance the
claim deserves, and where it appears. Percentages printed to one decimal get
tol=0.05; counts get tol=0.

Run:  uv run --no-project --with pandas python notebooks/r1_manuscript_number_audit.py
"""

import sys
import re
from pathlib import Path

import pandas as pd

import _common as C

DATA = C.DATA_FALLBACK
OUT = Path(__file__).parent / 'results'
OUT.mkdir(exist_ok=True)

CHUNK = 250_000
SPLITS = ['swim_sec', 't1_sec', 'bike_sec', 't2_sec', 'run_sec', 'overall_sec']
SUMMED = ['swim_sec', 't1_sec', 'bike_sec', 't2_sec', 'run_sec']

# value as printed in the submitted manuscript -> (printed, tolerance, location)
CLAIMS = {
    'n_records': (2_706_922, 0, 'Abstract; Results §Dataset composition'),
    'n_full': (1_340_799, 0, 'Results §Dataset composition'),
    'pct_full': (49.5, 0.05, 'Results §Dataset composition'),
    'n_half': (1_366_123, 0, 'Results §Dataset composition'),
    'pct_half': (50.5, 0.05, 'Results §Dataset composition'),
    'n_official': (2_041_743, 0, 'Abstract; Results §Dataset composition'),
    'pct_official': (75.4, 0.05, 'Abstract; Results; Table 1 footnote'),
    'n_supplementary': (665_179, 0, 'Results §Dataset composition'),
    'pct_supplementary': (24.6, 0.05, 'Abstract; Results §Dataset composition'),

    'n_fin': (2_239_335, 0, 'Results §Finish status'),
    'pct_fin': (82.7, 0.05, 'Results §Finish status'),
    'n_dnf': (176_416, 0, 'Results §Finish status'),
    'pct_dnf': (6.5, 0.05, 'Results §Finish status'),
    'n_dns': (271_615, 0, 'Results §Finish status'),
    'pct_dns': (10.0, 0.05, 'Results §Finish status'),
    'n_dq': (9_214, 0, 'Results §Finish status'),
    'pct_dq': (0.3, 0.05, 'Results §Finish status'),
    'n_nostatus': (10_342, 0, 'Results §Finish status'),

    'cov_swim': (85.9, 0.05, 'Results §Split times'),
    'cov_bike': (85.9, 0.05, 'Results §Split times'),
    'cov_run': (82.9, 0.05, 'Results §Split times'),
    'cov_overall': (83.0, 0.05, 'Results §Split times'),
    'cov_t1': (84.2, 0.05, 'Abstract; Results §Split times; §Completeness'),
    'cov_t2': (84.1, 0.05, 'Results §Split times; §Completeness'),

    'n_awa': (1_478_052, 0, 'Results §Additional fields'),
    'pct_awa': (54.6, 0.05, 'Results §Additional fields'),
    'n_distance': (1_537_761, 0, 'Results §Additional fields'),
    'pct_distance': (56.8, 0.05, 'Results §Additional fields'),

    'n_male': (2_098_548, 0, 'Results §Demographics'),
    'pct_male': (77.5, 0.05, 'Results §Demographics'),
    'n_female': (594_978, 0, 'Results §Demographics'),
    'pct_female': (22.0, 0.05, 'Results §Demographics'),
    'n_gender_unknown': (13_396, 0, 'Results §Demographics'),
    # Now counted from country_iso2, the clean field (251 codes against ISO
    # 3166-1's 249). The free-text `country` field yields 478 distinct values
    # because it holds dropdown placeholders, US state abbreviations, bare
    # initials and misspellings — the 490 originally printed counted those
    # as countries (R1-Int-3).
    'n_iso_codes': (251, 0, 'Results §Demographics'),

    'n_fin_full': (1_094_780, 0, 'Results §Split times; Figure 2 caption'),
    'n_fin_half': (1_144_555, 0, 'Results §Split times'),

    'consistency_n': (2_139_756, 0, 'Results §Internal consistency'),
    'consistency_exact_pct': (76.9, 0.05, 'Results §Internal consistency'),
    'consistency_1s_pct': (98.3, 0.05, 'Results §Internal consistency'),
    'consistency_5s_pct': (100.0, 0.05, 'Results §Internal consistency — R1-Rev2-Q19'),
    'consistency_over60_n': (57, 0, 'Results §Internal consistency'),

    'n_t1_missing_full_fin': (42_972, 0, 'Results §Transition time coverage'),
    'n_t1_present_full_fin': (1_051_808, 0, 'Results §Transition time coverage'),
}

# Table 1's printed coverage column is PARSED from the table, never copied here.
# A hardcoded copy would be the same stale-duplicate risk that produced R1-Int-2:
# the auditor would keep passing against its own snapshot while the table drifted.
TABLE1_PATH = C.PAPER_DIR / 'manuscript' / 'tables' / 'Table1.md'
ROW = re.compile(r'^\|\s*(\w+)\s*\|[^|]*\|[^|]*\|[^|]*\|\s*([\d.]+)\*?\s*\|')


def parse_table1() -> dict:
    """Read the printed coverage column out of manuscript/tables/Table1.md."""
    if not TABLE1_PATH.exists():
        raise FileNotFoundError(f'{TABLE1_PATH} not found; run generate_tables.py')
    printed = {}
    for line in TABLE1_PATH.read_text().split('\n'):
        m = ROW.match(line)
        if m:
            printed[m.group(1)] = float(m.group(2))
    if not printed:
        raise ValueError(f'no schema rows parsed from {TABLE1_PATH}')
    return printed


TABLE1 = parse_table1()

STRING_FIELDS = {'name', 'country', 'country_iso2', 'age_group', 'event_name',
                 'event_id', 'finish_status', 'race_type', 'source'}


# Claims the manuscript takes from the R1 analyses rather than from the merged
# dataset directly. Without these the auditor would verify the old numbers and be
# blind to the new ones — which is how a stale artefact survives.
DERIVED_CLAIMS = {
    'r1_cross_source_summary.csv': [
        ('race_years', 559, 0, 'Results §Cross-source agreement; Table 2'),
        ('split_pairs', 4_732_776, 0, 'Results §Cross-source agreement'),
        ('split_agreement_pct', 98.76, 0.005, 'Results §Cross-source agreement'),
        ('n_full', 340, 0, 'Results §Cross-source agreement'),
        ('n_half', 219, 0, 'Results §Cross-source agreement'),
        ('match_rate_exact_median', 95.3, 0.05, 'Results §Cross-source agreement'),
        ('match_rate_canon_median', 96.4, 0.05, 'Results §Cross-source agreement'),
    ],
    'r1_event_coverage.csv': [
        ('event_series', 128, 0, 'Methods §Event discovery'),
        ('subevents_enumerated', 1_235, 0, 'Methods §Data collection — official platform'),
        ('official_race_years_with_results', 1_172, 0,
         'Methods §Data collection — official platform'),
        ('official_records_total', 2_041_743, 0,
         'Methods §Data collection — official platform'),
        ('discovered_without_results', 63, 0,
         'Methods §Data collection — official platform'),
        ('discovered_without_results_2021', 28, 0,
         'Methods §Data collection — official platform'),
        ('supplementary_race_years', 382, 0,
         'Methods §Data collection — supplementary source'),
        ('supplementary_records', 665_179, 0,
         'Methods §Data collection — supplementary source'),
        ('total_race_years', 1_554, 0, 'Methods §Data merging'),
    ],
    'r1_overlap_census.csv': [
        ('race_years_both', 559, 0, 'Methods §Data merging'),
        ('race_years_official_only', 613, 0, 'Methods §Data merging'),
        ('race_years_supplementary_only', 382, 0, 'Methods §Data merging'),
        ('race_years_total', 1_554, 0, 'Methods §Data merging'),
    ],
    'r1_transition_bias.csv': [],   # checked below, needs row selection
}

# Median finish times, quoted in Results §Physiological plausibility and Discussion
# §Practical guidance. Keyed by race_type on the overall_sec row. The full-distance
# median first entered the manuscript as 12:25:59, borrowed from the median among
# finishers *with T2 data* — a different denominator, 22 seconds out. Checked here
# so the denominator cannot drift again.
MEDIAN_CLAIMS = [
    ('him', '5:53:16', 'Results §Physiological plausibility; Discussion §Practical guidance'),
    ('im', '12:25:37', 'Discussion §Practical guidance'),
]

# Long-form results, keyed by a label column rather than one row per file. The
# merge-rule counts are quoted in Methods §Data merging (R1-Rev1-Q6) to show that
# normalization is what makes a collision detectable.
KEYED_CLAIMS = {
    'r1_merge_rule_counts.csv': ('stage', 'overlap', [
        ('baseline (no normalisation)', 0, 'Methods §Data merging'),
        ('generic rules only', 537, 'Methods §Data merging'),
        ('full (generic + championship prefixes)', 559, 'Methods §Data merging'),
    ]),
}


def check_derived(rows: list) -> int:
    """Verify manuscript claims that come from the R1 result files."""
    failures = 0
    print('\n=== claims derived from R1 analyses ===')
    print(f'{"claim":34s} {"printed":>12s} {"actual":>12s}  status')
    for fname, claims in DERIVED_CLAIMS.items():
        if not claims:
            continue
        df = pd.read_csv(C.RESULTS_DIR / fname, comment='#')
        row = df.iloc[0]
        for field, printed, tol, where in claims:
            actual = float(row[field])
            ok = abs(actual - printed) <= tol
            failures += not ok
            print(f'{field:34s} {printed:>12,.4g} {actual:>12,.4g}  '
                  f'{"ok" if ok else "FAIL"}')
            rows.append({'artefact': 'R1 analysis', 'claim': field,
                         'printed': printed, 'actual': round(actual, 4),
                         'delta': round(actual - printed, 4),
                         'status': 'ok' if ok else 'FAIL', 'location': where})

    for fname, (key_col, val_col, claims) in KEYED_CLAIMS.items():
        df = pd.read_csv(C.RESULTS_DIR / fname, comment='#').set_index(key_col)
        for key, printed, where in claims:
            actual = int(df.loc[key, val_col])
            ok = actual == printed
            failures += not ok
            label = key if len(key) <= 34 else key[:31] + '...'
            print(f'{label:34s} {printed:>12,} {actual:>12,}  {"ok" if ok else "FAIL"}')
            rows.append({'artefact': 'R1 analysis', 'claim': f'merge rule: {key}',
                         'printed': printed, 'actual': actual,
                         'delta': actual - printed,
                         'status': 'ok' if ok else 'FAIL', 'location': where})

    pct = pd.read_csv(C.RESULTS_DIR / 'r1_finish_percentiles.csv', comment='#')
    pct = pct[pct.field == 'overall_sec'].set_index('race_type')
    for rtype, printed, where in MEDIAN_CLAIMS:
        actual = str(pct.loc[rtype, 'median_hms'])
        ok = actual == printed
        failures += not ok
        print(f'{f"median finish ({rtype})":34s} {printed:>12s} {actual:>12s}  '
              f'{"ok" if ok else "FAIL"}')
        rows.append({'artefact': 'R1 analysis', 'claim': f'median finish ({rtype})',
                     'printed': printed, 'actual': actual,
                     'delta': '' if ok else 'differs',
                     'status': 'ok' if ok else 'FAIL', 'location': where})

    bias = pd.read_csv(C.RESULTS_DIR / 'r1_transition_bias.csv', comment='#').set_index('split')
    for split, n_with, n_without in (('T1', 1_051_808, 42_972), ('T2', 1_069_074, 25_706)):
        for label, printed, col in ((f'{split} n with', n_with, 'n_with'),
                                    (f'{split} n without', n_without, 'n_without')):
            actual = int(bias.loc[split, col])
            ok = actual == printed
            failures += not ok
            print(f'{label:34s} {printed:>12,} {actual:>12,}  {"ok" if ok else "FAIL"}')
            rows.append({'artefact': 'R1 analysis', 'claim': label, 'printed': printed,
                         'actual': actual, 'delta': actual - printed,
                         'status': 'ok' if ok else 'FAIL',
                         'location': 'Results §Transition time coverage'})
    return failures


def compute() -> dict:
    """Single streaming pass; medians need the values, so those are collected."""
    n = 0
    counts = {k: 0 for k in ('full', 'half', 'official', 'supplementary',
                             'fin', 'dnf', 'dns', 'dq', 'nostatus',
                             'awa', 'distance', 'male', 'female', 'gender_unknown')}
    present = {f: 0 for f in TABLE1}
    countries, iso_codes = set(), set()
    consistency = {'n': 0, 'exact': 0, 'w1': 0, 'w5': 0, 'over60': 0}
    t1_full_fin = {'present': 0, 'missing': 0}
    fin_full = fin_half = 0

    for c in pd.read_csv(DATA, chunksize=CHUNK, low_memory=False):
        n += len(c)
        counts['full'] += int((c.race_type == 'im').sum())
        counts['half'] += int((c.race_type == 'him').sum())
        counts['official'] += int((c.source == 'official').sum())
        counts['supplementary'] += int((c.source == 'coachcox').sum())
        for k, v in (('fin', 'FIN'), ('dnf', 'DNF'), ('dns', 'DNS'), ('dq', 'DQ')):
            counts[k] += int((c.finish_status == v).sum())
        counts['nostatus'] += int(c.finish_status.isna().sum())
        counts['awa'] += int((c.awa_points > 0).sum())
        counts['distance'] += int((c.total_distance_km > 0).sum())

        ag = c.age_group.fillna('').astype(str).str.upper()
        counts['male'] += int(ag.str.startswith('M').sum())
        counts['female'] += int(ag.str.startswith('F').sum())
        counts['gender_unknown'] += int((~ag.str.startswith(('M', 'F'))).sum())

        countries.update(c.country.dropna().astype(str).str.strip().unique())
        iso_codes.update(c.country_iso2.dropna().astype(str).str.strip().unique())

        for f in TABLE1:
            if f in STRING_FIELDS:
                present[f] += int((c[f].notna() & (c[f].astype(str).str.strip() != '')).sum())
            else:
                present[f] += int((c[f] > 0).sum())

        ok = c[(c[SPLITS] > 0).all(axis=1)]
        if len(ok):
            d = (ok[SUMMED].sum(axis=1) - ok.overall_sec).abs()
            consistency['n'] += len(ok)
            consistency['exact'] += int((d == 0).sum())
            consistency['w1'] += int((d <= 1).sum())
            consistency['w5'] += int((d <= 5).sum())
            consistency['over60'] += int((d > 60).sum())

        f_full = c[(c.race_type == 'im') & (c.finish_status == 'FIN')]
        fin_full += len(f_full)
        fin_half += int(((c.race_type == 'him') & (c.finish_status == 'FIN')).sum())
        t1_full_fin['present'] += int((f_full.t1_sec > 0).sum())
        t1_full_fin['missing'] += int((~(f_full.t1_sec > 0)).sum())
        print(f'  ...{n:,}', flush=True, end='\r')

    print(' ' * 40, end='\r')
    v = {'n_records': n, 'n_countries': len(countries - {''}), 'n_iso_codes': len(iso_codes - {''}),
         'n_fin_full': fin_full, 'n_fin_half': fin_half,
         'consistency_n': consistency['n'],
         'consistency_exact_pct': consistency['exact'] / consistency['n'] * 100,
         'consistency_1s_pct': consistency['w1'] / consistency['n'] * 100,
         'consistency_5s_pct': consistency['w5'] / consistency['n'] * 100,
         'consistency_over60_n': consistency['over60'],
         'n_t1_present_full_fin': t1_full_fin['present'],
         'n_t1_missing_full_fin': t1_full_fin['missing']}
    for k in ('full', 'half', 'official', 'supplementary', 'fin', 'dnf', 'dns',
              'dq', 'awa', 'distance', 'male', 'female'):
        v[f'n_{k}'] = counts[k]
        v[f'pct_{k}'] = counts[k] / n * 100
    v['n_nostatus'] = counts['nostatus']
    v['n_gender_unknown'] = counts['gender_unknown']
    for f in ('swim', 'bike', 'run', 'overall', 't1', 't2'):
        v[f'cov_{f}'] = present[f'{f}_sec'] / n * 100
    v['_table1'] = {f: present[f] / n * 100 for f in TABLE1}
    return v


def main() -> None:
    v = compute()
    rows, failures = [], 0

    print('=== manuscript claims ===')
    print(f'{"claim":26s} {"printed":>12s} {"actual":>12s} {"delta":>10s}  status')
    for key, (printed, tol, where) in CLAIMS.items():
        actual = v[key]
        delta = actual - printed
        ok = abs(delta) <= tol
        failures += not ok
        print(f'{key:26s} {printed:>12,.4g} {actual:>12,.4g} {delta:>+10.4g}  '
              f'{"ok" if ok else "FAIL"}')
        rows.append({'artefact': 'manuscript', 'claim': key, 'printed': printed,
                     'actual': round(float(actual), 4), 'delta': round(float(delta), 4),
                     'status': 'ok' if ok else 'FAIL', 'location': where})

    print('\n=== Table 1 coverage column ===')
    print(f'{"field":22s} {"printed":>9s} {"actual":>9s} {"delta":>9s}  status')
    for f, printed in TABLE1.items():
        actual = v['_table1'][f]
        delta = actual - printed
        # Compare at the precision the table prints, not against a fixed tolerance.
        # A one-decimal cell may legitimately differ from the true value by up to
        # 0.05, so a `<= 0.05` test sits exactly on a knife edge and lets binary
        # representation decide the verdict — rank_group (95.55 printed as 95.5)
        # failed for that reason alone. Formatting both sides the same way as
        # generate_tables.py makes auditor and generator agree by construction.
        ok = f'{actual:.1f}' == f'{printed:.1f}'
        failures += not ok
        print(f'{f:22s} {printed:>9.1f} {actual:>9.2f} {delta:>+9.2f}  '
              f'{"ok" if ok else "FAIL"}')
        rows.append({'artefact': 'Table 1', 'claim': f, 'printed': printed,
                     'actual': round(actual, 2), 'delta': round(delta, 2),
                     'status': 'ok' if ok else 'FAIL', 'location': 'Table 1 Coverage (%)'})

    failures += check_derived(rows)

    df = pd.DataFrame(rows)
    C.write_result(df, 'r1_manuscript_number_audit.csv')

    print(f'\n{"=" * 60}')
    print(f'{len(df) - failures} of {len(df)} claims verified; {failures} FAIL')
    if failures:
        print('\nfailing claims by artefact:')
        print(df[df.status == 'FAIL'].groupby('artefact').size().to_string())
        print('\nA FAIL means the artefact and the released dataset disagree.')
        print('Regenerate the artefact — do not edit the printed value by hand.')
    print(f'\nwritten to {OUT / "r1_manuscript_number_audit.csv"}')
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()

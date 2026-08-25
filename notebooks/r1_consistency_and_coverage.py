"""R1 · A7 — recompute Table 1 coverage and the internal-consistency figures.

R1-Rev2-Q18: Table 1's coverage column disagrees with the Results text. Verified
2026-08-25 — the Results text matches the data and Table 1 is wrong in four of
six split fields (swim, bike, run, overall). This recomputes every Table 1
coverage value from the data so the table can be rebuilt rather than patched.

R1-Rev2-Q19: the submitted text reports "100.0% were within five seconds" while
also reporting 57 records differing by more than 60 seconds. Rounding a
sub-100% figure to 100.0 reads as a contradiction. This reports the exact
percentage to enough decimal places that it is not 100, with the count of
records outside each tolerance alongside.

Coverage denominator is `> 0` for numeric fields; see
r1_verify_composition_coverage.py for why `notna()` overstates by ~10 points.

MEMORY NOTE: this is the only R1 script that needs all 28 columns, so it cannot
use `usecols` to stay small. Reading the 516 MB file whole was killed by the OOM
killer (exit 137) on two attempts. It now streams in chunks and accumulates
counters, which keeps resident memory flat regardless of file size.

Run:  uv run --no-project --with pandas python notebooks/r1_consistency_and_coverage.py
"""

from pathlib import Path

import pandas as pd

import _common as C

DATA = C.DATA_FALLBACK
OUT = Path(__file__).parent / 'results'
OUT.mkdir(exist_ok=True)

CHUNK = 250_000
SPLITS = ['swim_sec', 't1_sec', 'bike_sec', 't2_sec', 'run_sec', 'overall_sec']
SUMMED = ['swim_sec', 't1_sec', 'bike_sec', 't2_sec', 'run_sec']
TOLERANCES = (0, 1, 5, 10, 30, 60)

# As printed in the submitted Table 1, for a side-by-side diff.
TABLE1 = {'name': 99.5, 'bib': 95.2, 'country': 97.8, 'country_iso2': 75.4,
          'age_group': 99.5, 'event_name': 100.0, 'event_id': 100.0,
          'swim_sec': 82.8, 't1_sec': 84.2, 'bike_sec': 83.7, 't2_sec': 84.1,
          'run_sec': 83.0, 'overall_sec': 83.9, 'finish_status': 99.6,
          'rank_overall': 76.4, 'rank_gender': 76.3, 'rank_group': 76.3,
          'swim_rank': 75.0, 'bike_rank': 74.8, 'run_rank': 75.0,
          'awa_points': 54.6, 'swim_distance_km': 56.8, 'bike_distance_km': 56.8,
          'run_distance_km': 56.8, 'total_distance_km': 56.8,
          'race_type': 100.0, 'race_year': 100.0, 'source': 100.0}

STRING_FIELDS = {'name', 'country', 'country_iso2', 'age_group', 'event_name',
                 'event_id', 'finish_status', 'race_type', 'source'}


def main() -> None:
    present = {f: 0 for f in TABLE1}
    n = 0
    n_complete = 0
    within = {t: 0 for t in TOLERANCES}
    max_diff = 0.0
    n_over_60 = 0

    for chunk in pd.read_csv(DATA, chunksize=CHUNK, low_memory=False):
        n += len(chunk)
        for f in TABLE1:
            if f not in chunk.columns:
                continue
            if f in STRING_FIELDS:
                present[f] += int((chunk[f].notna()
                                   & (chunk[f].astype(str).str.strip() != '')).sum())
            else:
                present[f] += int((chunk[f] > 0).sum())

        ok = chunk[(chunk[SPLITS] > 0).all(axis=1)]
        if len(ok):
            n_complete += len(ok)
            diff = (ok[SUMMED].sum(axis=1) - ok.overall_sec).abs()
            for t in TOLERANCES:
                within[t] += int((diff <= t).sum())
            max_diff = max(max_diff, float(diff.max()))
            n_over_60 += int((diff > 60).sum())
        print(f'  ...{n:,} rows', flush=True)

    print(f'\nN = {n:,}\n')

    print('=== Table 1 coverage, recomputed ===')
    print(f'{"field":20s} {"actual":>8s} {"Table 1":>9s} {"delta":>8s}  status')
    rows = []
    for f, printed in TABLE1.items():
        actual = present[f] / n * 100
        delta = actual - printed
        status = 'ok' if abs(delta) < 0.05 else 'MISMATCH'
        print(f'{f:20s} {actual:8.2f} {printed:9.1f} {delta:+8.2f}  {status}')
        # Full precision, not two decimals. generate_tables.py formats this value
        # to one decimal for the printed table while r1_manuscript_number_audit.py
        # recomputes from the data — if the stored value is pre-rounded, the two
        # round twice by different routes and disagree at the boundary. rank_group
        # (95.5487%) printed as 95.5 from the rounded 95.55 but audited as 95.6.
        rows.append({'field': f, 'actual_pct': actual,
                     'submitted_pct': printed, 'delta': delta,
                     'status': status})
    tab = pd.DataFrame(rows)
    C.write_result(tab, 'r1_table1_coverage_recomputed.csv')
    bad = tab[tab.status == 'MISMATCH']
    print(f'\nfields needing correction in Table 1: {len(bad)} of {len(tab)}')
    if len(bad):
        print('  ' + ', '.join(bad.field))

    print('\n=== internal consistency ===')
    print(f'records with all six times present and > 0: {n_complete:,}'
          f'   (submitted text says 2,139,756)')
    print(f'\n{"tolerance":>11s} {"n within":>12s} {"pct":>12s} {"n outside":>11s}')
    out_rows = []
    for t in TOLERANCES:
        pct = within[t] / n_complete * 100
        # Enough decimals that a sub-100 value cannot render as 100.
        print(f'{t:>10d}s {within[t]:>12,} {pct:>11.4f}% {n_complete - within[t]:>11,}')
        out_rows.append({'tolerance_sec': t, 'n_within': within[t],
                         'pct_within': round(pct, 4),
                         'n_outside': n_complete - within[t]})
    C.write_result(pd.DataFrame(out_rows), 'r1_internal_consistency.csv')

    print(f'\nmax absolute difference: {int(max_diff):,} s')
    print(f'records differing by more than 60 s: {n_over_60:,}'
          f'   (submitted text says 57)')
    print(f'\nwritten to {OUT}')


if __name__ == '__main__':
    main()

"""R1 verification — dataset composition, field coverage, and Figure 1 source labels.

Answers R1-Rev2-Q18 (Table 1 coverage vs Results §Split times), supports
R1-Rev2-Q20 (Figure 1 content), and produced the internal finding R1-Int-1
(source categories swapped in Figure 1 panels a and c).

Denominator note: split fields carry 0 for records with no recorded time as well
as NaN, so `notna()` overstates coverage by roughly 10 percentage points. Coverage
is therefore computed as `> 0`. This is the discrepancy that has to be settled
before any coverage number in the manuscript is trusted.

Data path: `data/collection/ironman_merged.csv` symlinked to the pre-restructure
location (`02-research/projects/ironman/`) and was broken, so every notebook
reading the merged dataset failed. Repointed relatively on 2026-08-25 (task A0)
so it survives future moves. This script reads the absolute path directly.

Run:  uv run --no-project --with pandas python notebooks/r1_verify_composition_coverage.py
"""

import pandas as pd

import _common as C

DATA = C.DATA_FALLBACK
SPLITS = ['swim_sec', 't1_sec', 'bike_sec', 't2_sec', 'run_sec', 'overall_sec']
COLS = ['source', 'race_type', 'finish_status'] + SPLITS

# Values as printed in the submitted manuscript, for direct comparison.
TABLE1_COVERAGE = {'swim_sec': 82.8, 't1_sec': 84.2, 'bike_sec': 83.7,
                   't2_sec': 84.1, 'run_sec': 83.0, 'overall_sec': 83.9}
RESULTS_COVERAGE = {'swim_sec': 85.9, 't1_sec': 84.2, 'bike_sec': 85.9,
                    't2_sec': 84.1, 'run_sec': 82.9, 'overall_sec': 83.0}


def main() -> None:
    df = pd.read_csv(DATA, usecols=COLS, low_memory=False)
    n = len(df)
    print(f'N = {n:,}\n')

    print('--- composition by source ---')
    for src, count in df.source.value_counts().items():
        print(f'{src:10s} {count:>10,}  {count / n * 100:5.1f}%')

    print('\n--- source x race_type (what Figure 1a should show) ---')
    print(pd.crosstab(df.source, df.race_type))

    print('\n--- coverage (> 0) vs the two places the manuscript reports it ---')
    print(f'{"field":14s} {"actual":>8s} {"Table 1":>9s} {"Results":>9s}  verdict')
    for c in SPLITS:
        actual = (df[c] > 0).mean() * 100
        t1, res = TABLE1_COVERAGE[c], RESULTS_COVERAGE[c]
        ok_t1, ok_res = abs(actual - t1) < 0.1, abs(actual - res) < 0.1
        verdict = ('both agree' if ok_t1 and ok_res
                   else 'Table 1 wrong' if ok_res
                   else 'Results wrong' if ok_t1
                   else 'both wrong')
        print(f'{c:14s} {actual:8.2f} {t1:9.1f} {res:9.1f}  {verdict}')

    print('\n--- T1/T2 coverage (> 0) by source (what Figure 1c should show) ---')
    for src, g in df.groupby('source'):
        print(f'{src:10s} t1={(g.t1_sec > 0).mean() * 100:5.2f}%  '
              f't2={(g.t2_sec > 0).mean() * 100:5.2f}%  n={len(g):,}')

    print('\n--- finish status ---')
    for status, count in df.finish_status.value_counts(dropna=False).items():
        print(f'{str(status):10s} {count:>10,}  {count / n * 100:5.2f}%')


if __name__ == '__main__':
    main()

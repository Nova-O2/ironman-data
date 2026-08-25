"""R1 · A2 — T2 missingness, mirroring every assessment currently reported for T1.

R1-Rev2-Q16: the submitted manuscript assesses missing-transition bias for T1
only (§Transition time coverage) and reports T2 coverage as a bare percentage.
In a paper whose contribution is *separated* T1 and T2, there is no defensible
reason to report one and not the other.

Mirrors §Transition time coverage exactly, for both transitions:
  - coverage by year, source, race type and finish status
  - the missing-vs-present bias check among full-distance finishers
    (median overall finish time for athletes with and without the split)

Also feeds Figure 3 (R1-Rev2-Q22), which currently shows T1 panels only, and
Figure 1 panel (c) (R1-Int-1), which needs T2 alongside T1.

Coverage is `> 0`, not `notna()`: the split fields carry 0 as well as NaN, and
counting nulls alone overstates coverage by about ten points.

Run:  uv run --no-project --with pandas python notebooks/r1_t2_missingness.py
"""

from pathlib import Path

import pandas as pd

import _common as C

DATA = C.DATA_FALLBACK
OUT = Path(__file__).parent / 'results'
OUT.mkdir(exist_ok=True)


def fmt(seconds: float) -> str:
    if pd.isna(seconds):
        return 'n/a'
    s = int(round(seconds))
    return f'{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}'


def main() -> None:
    cols = ['source', 'race_type', 'race_year', 'finish_status',
            't1_sec', 't2_sec', 'overall_sec']
    df = pd.read_csv(DATA, usecols=cols, low_memory=False)
    n = len(df)
    df['has_t1'] = df.t1_sec > 0
    df['has_t2'] = df.t2_sec > 0
    print(f'N = {n:,}\n')

    print('=== overall coverage ===')
    for c in ('has_t1', 'has_t2'):
        print(f'  {c[4:].upper()}: {df[c].mean() * 100:.2f}%  ({int(df[c].sum()):,})')
    both = (df.has_t1 & df.has_t2).mean() * 100
    either = (df.has_t1 | df.has_t2).mean() * 100
    print(f'  both     : {both:.2f}%')
    print(f'  either   : {either:.2f}%')
    print(f'  T1 only  : {(df.has_t1 & ~df.has_t2).mean() * 100:.2f}%')
    print(f'  T2 only  : {(~df.has_t1 & df.has_t2).mean() * 100:.2f}%')

    print('\n=== bias check among full-distance finishers ===')
    print('(mirrors §Transition time coverage, which reports T1 only)')
    fin = df[(df.race_type == 'im') & (df.finish_status == 'FIN')]
    print(f'full-distance finishers: {len(fin):,}')
    rows = []
    for split in ('t1', 't2'):
        has = fin[fin[f'has_{split}']]
        hasnt = fin[~fin[f'has_{split}']]
        m_has = has.overall_sec[has.overall_sec > 0].median()
        m_not = hasnt.overall_sec[hasnt.overall_sec > 0].median()
        print(f'\n  {split.upper()}')
        print(f'    with    : n={len(has):>9,}  median overall {fmt(m_has)}')
        print(f'    without : n={len(hasnt):>9,}  median overall {fmt(m_not)}')
        print(f'    difference: {fmt(abs(m_has - m_not))} '
              f'({"faster" if m_not < m_has else "slower"} without)')
        rows.append({'split': split.upper(), 'n_with': len(has), 'n_without': len(hasnt),
                     'median_with_sec': m_has, 'median_without_sec': m_not,
                     'diff_sec': abs(m_has - m_not)})
    C.write_result(pd.DataFrame(rows), 'r1_transition_bias.csv')

    print('\n=== coverage by year ===')
    by_year = df.groupby('race_year')[['has_t1', 'has_t2']].mean().mul(100).round(2)
    by_year['n'] = df.groupby('race_year').size()
    C.write_result(by_year, 'r1_transition_coverage_by_year.csv', index=True)
    print(by_year.to_string())
    for c in ('has_t1', 'has_t2'):
        lo, hi = by_year[c].idxmin(), by_year[c].idxmax()
        print(f'  {c[4:].upper()} range: {by_year[c].min():.1f}% ({lo}) '
              f'to {by_year[c].max():.1f}% ({hi})')

    print('\n=== coverage by source / race type / finish status ===')
    frames = {}
    for dim in ('source', 'race_type', 'finish_status'):
        g = df.groupby(dim)[['has_t1', 'has_t2']].mean().mul(100).round(2)
        g['n'] = df.groupby(dim).size()
        frames[dim] = g
        print(f'\n[{dim}]')
        print(g.to_string())
    C.write_result(pd.concat(frames, names=['dimension']), 'r1_transition_coverage_by_dim.csv', index=True)

    print(f'\nwritten to {OUT}')


if __name__ == '__main__':
    main()

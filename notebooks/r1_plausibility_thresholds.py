"""R1 · A4 — physiological plausibility bounds: what they flag, and what 70.3 needs.

R1-Rev2-Q17 asks two things: how the full-distance cut-offs were established, and
what the corresponding IRONMAN® 70.3 thresholds are.

The first is a question of record, not computation — the manuscript states the
bounds without a source. This script does not invent a provenance; it reports what
the bounds actually flag so the answer can be written against evidence.

The second is the substantive risk. §Physiological plausibility says the bounds
were applied "for full-distance IRONMAN® finishers", and no half-distance bounds
are stated anywhere — yet half-distance is 50.5% of the dataset. Either the check
never ran on half the data, or full-distance bounds were applied to it. Both are
findings, and they differ. This script shows which by applying the stated bounds
to both distances and reporting the flag rates.

Observed percentiles are reported alongside so that any proposed 70.3 bounds are
derived from the data rather than halved by assumption.

Run:  uv run --no-project --with pandas python notebooks/r1_plausibility_thresholds.py
"""

from pathlib import Path

import pandas as pd

import _common as C

DATA = C.DATA_FALLBACK
OUT = Path(__file__).parent / 'results'
OUT.mkdir(exist_ok=True)

# Exactly as stated in the submitted manuscript, in seconds.
FULL_BOUNDS = {
    'swim_sec': (30 * 60, 150 * 60),
    't1_sec': (30, 30 * 60),
    'bike_sec': (3 * 3600, 10 * 3600),
    't2_sec': (30, 30 * 60),
    'run_sec': (2 * 3600, 8 * 3600),
    'overall_sec': (7 * 3600, 17 * 3600),
}
# Distance-specific bounds for the half distance, derived from the observed
# percentiles below. The submitted manuscript stated only full-distance bounds
# and reported "below 1% for all fields" — true for the full distance and
# meaningless for the half, where the full-distance bounds flag 85% of finishers
# on overall time (R1-Rev2-Q17).
HALF_BOUNDS = {
    'swim_sec': (15 * 60, 75 * 60),
    't1_sec': (30, 30 * 60),
    'bike_sec': (int(1.5 * 3600), 5 * 3600),
    't2_sec': (30, 30 * 60),
    'run_sec': (1 * 3600, 4 * 3600),
    'overall_sec': (int(3.5 * 3600), 9 * 3600),
}

PCTL = [0.001, 0.01, 0.05, 0.5, 0.95, 0.99, 0.999]


def hms(seconds: float) -> str:
    if pd.isna(seconds):
        return 'n/a'
    s = int(round(seconds))
    return f'{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}'


def main() -> None:
    cols = ['race_type', 'finish_status'] + list(FULL_BOUNDS)
    df = pd.read_csv(DATA, usecols=cols, low_memory=False)
    fin = df[df.finish_status == 'FIN']
    print(f'finishers: {len(fin):,}  '
          f'(full {int((fin.race_type == "im").sum()):,} / '
          f'half {int((fin.race_type == "him").sum()):,})\n')

    rows = []
    # Percentiles are persisted, not only printed. The manuscript quotes the median
    # 70.3 finish (5:53:16) in Results §Physiological plausibility and both medians in
    # Discussion §Practical guidance, and until now those numbers existed nowhere but
    # this script's stdout — the same untraceable-claim problem that let R1-Int-6
    # survive. Persisted here so the number auditor can check them.
    pctl_rows = []
    for rtype, label in (('im', 'full-distance'), ('him', 'half-distance (70.3)')):
        g = fin[fin.race_type == rtype]
        print(f'=== {label} ===')
        print(f'{"field":13s} {"lo bound":>10s} {"hi bound":>10s} '
              f'{"n valued":>10s} {"flagged":>9s} {"flag %":>8s}')
        for f, (lo, hi) in FULL_BOUNDS.items():
            v = g[f][g[f] > 0]
            flagged = int(((v < lo) | (v > hi)).sum())
            pct = flagged / len(v) * 100 if len(v) else float('nan')
            print(f'{f:13s} {hms(lo):>10s} {hms(hi):>10s} '
                  f'{len(v):>10,} {flagged:>9,} {pct:>7.3f}%')
            rows.append({'race_type': rtype, 'field': f,
                         'bound_lo_sec': lo, 'bound_hi_sec': hi,
                         'n_valued': len(v), 'n_flagged': flagged,
                         'flag_pct': round(pct, 4)})

        print(f'\nobserved percentiles ({label}):')
        print(f'{"field":13s} ' + ' '.join(f'{f"p{p * 100:g}":>9s}' for p in PCTL))
        for f in FULL_BOUNDS:
            v = g[f][g[f] > 0]
            q = v.quantile(PCTL)
            print(f'{f:13s} ' + ' '.join(f'{hms(q[p]):>9s}' for p in PCTL))
            pctl_rows.append({'race_type': rtype, 'field': f, 'n_valued': len(v),
                              **{f'p{p * 100:g}_sec': round(float(q[p]), 1)
                                 for p in PCTL},
                              'median_hms': hms(q[0.5])})
        print()

    print('=== proposed half-distance bounds, applied to half-distance finishers ===')
    g = fin[fin.race_type == 'him']
    for f, (lo, hi) in HALF_BOUNDS.items():
        v = g[f][g[f] > 0]
        flagged = int(((v < lo) | (v > hi)).sum())
        pct = flagged / len(v) * 100 if len(v) else float('nan')
        print(f'{f:13s} {hms(lo):>10s} {hms(hi):>10s} '
              f'{len(v):>10,} {flagged:>9,} {pct:>7.3f}%')
        rows.append({'race_type': 'him_proposed', 'field': f,
                     'bound_lo_sec': lo, 'bound_hi_sec': hi,
                     'n_valued': len(v), 'n_flagged': flagged,
                     'flag_pct': round(pct, 4)})
    prop = [r for r in rows if r['race_type'] == 'him_proposed']
    print(f"\nmax flag rate under the proposed half-distance bounds: "
          f"{max(r['flag_pct'] for r in prop):.3f}%\n")

    C.write_result(pd.DataFrame(rows), 'r1_plausibility_flags.csv')
    C.write_result(pd.DataFrame(pctl_rows), 'r1_finish_percentiles.csv')

    print('=== reading ===')
    full = pd.DataFrame(rows).query('race_type == "im"').flag_pct
    half = pd.DataFrame(rows).query('race_type == "him"').flag_pct
    print(f'max flag rate, full-distance : {full.max():.3f}%')
    print(f'max flag rate, half-distance : {half.max():.3f}%')
    print('\nIf the half-distance rates are large, the stated bounds were never')
    print('appropriate for 50.5% of the dataset and the manuscript must say so.')
    print(f'\nwritten to {OUT}')


if __name__ == '__main__':
    main()

"""R1 · A3 — did the age-group categories change over the covered years?

R1-Rev1-Q8 asks whether competitor age categories changed across 2002-2026. The
manuscript is silent on it. If the boundaries moved, that is a real caveat for
longitudinal reuse and belongs in Methods and Limitations; if they did not, we
can say so. Either way, do not assert stability without the query.

Run:  uv run --no-project --with pandas python notebooks/r1_age_group_stability.py
"""

import re
from pathlib import Path

import pandas as pd

import _common as C

DATA = C.DATA_FALLBACK
OUT = Path(__file__).parent / 'results'
OUT.mkdir(exist_ok=True)

AGE_BAND = re.compile(r'^[MF](\d{2})-(\d{2})$')


def main() -> None:
    df = pd.read_csv(DATA, usecols=['age_group', 'race_year'], low_memory=False)
    df['age_group'] = df.age_group.fillna('').str.strip().str.upper()
    df = df[(df.age_group != '') & df.race_year.notna()]
    df['race_year'] = df.race_year.astype(int)

    # Distinct band boundaries per year, ignoring the M/F prefix and pro categories.
    bands = {}
    for year, g in df.groupby('race_year'):
        found = set()
        for v in g.age_group.unique():
            m = AGE_BAND.match(v)
            if m:
                found.add((int(m.group(1)), int(m.group(2))))
        bands[year] = found

    years = sorted(bands)
    print(f'years covered: {years[0]}-{years[-1]}\n')

    print('distinct age bands per year (age-group codes only, PRO excluded):')
    for y in years:
        b = sorted(bands[y])
        print(f'  {y}: {len(b):>2} bands  {b[0] if b else "-"} .. {b[-1] if b else "-"}')

    reference = bands[max(years, key=lambda y: len(bands[y]))]
    print(f'\nreference set ({len(reference)} bands): {sorted(reference)}')

    print('\nyears whose band set differs from the reference:')
    changed = False
    for y in years:
        missing, extra = reference - bands[y], bands[y] - reference
        if extra or (missing and bands[y]):
            changed = True
            print(f'  {y}: extra={sorted(extra) or "-"}  absent={sorted(missing) or "-"}')
    if not changed:
        print('  none — band boundaries are stable across the period')

    print('\nnon-band category codes seen (PRO and other):')
    other = sorted({v for v in df.age_group.unique() if not AGE_BAND.match(v)})
    print(' ', other[:40], f'... ({len(other)} total)' if len(other) > 40 else '')

    rows = [{'race_year': y, 'n_bands': len(bands[y]),
             'bands': ';'.join(f'{a}-{b}' for a, b in sorted(bands[y]))} for y in years]
    C.write_result(pd.DataFrame(rows), 'r1_age_group_by_year.csv')
    print(f'\nwritten to {OUT / "r1_age_group_by_year.csv"}')


if __name__ == '__main__':
    main()

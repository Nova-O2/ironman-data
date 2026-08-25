"""R1 · A5 — how many race-years required the manual name-mapping rules?

R1-Rev1-Q6 asks how duplicate records across sources were identified and removed.
The Methods say ambiguous cases "were resolved by manual inspection of the
normalized-name mapping before the merge was finalized", without a count. No
record of that count was kept.

It does not need one. The manual inspection produced concrete rules, and they
are in `merge_sources.normalize_race_name`: strip the year, the brand words, the
":triathlon" suffix, and a list of championship prefixes. The race-years that
matched *because of* those rules are exactly the difference between matching with
them and matching without. That is a reconstruction from code, not from memory.

Reported separately:
  - baseline   : matches on raw lowercased names, no normalisation at all
  - generic    : + year / brand / suffix stripping
  - full       : + the championship-prefix rules (what the merge actually used)

Run:  uv run --no-project --with pandas python notebooks/r1_merge_rule_counts.py
"""

import csv
import re
from pathlib import Path

import pandas as pd

import _common as C

RAW = C.RAW_DIR
OFFICIAL = RAW / 'ironman_official' / 'ironman_official_all.csv'
CC_META = RAW / '_legacy' / 'coachcox' / 'race_metadata.csv'
OUT = Path(__file__).parent / 'results'
OUT.mkdir(exist_ok=True)

csv.field_size_limit(10 ** 7)

CHAMPIONSHIP_PREFIXES = [
    'african championship ', 'european championship ',
    'north american championship ', 'south american championship ',
    'asia-pacific championship ',
]


def norm(name: str, *, generic: bool = True, championships: bool = True) -> str:
    """Reimplements merge_sources.normalize_race_name with each stage switchable."""
    n = str(name).lower()
    if generic:
        n = re.sub(r'\d{4}', '', n)
        n = re.sub(r'ironman\s*', '', n)
        n = re.sub(r'70\.3\s*', '', n)
        n = re.sub(r':\s*triathlon', '', n)
    n = re.sub(r'\s+', ' ', n).strip()
    if championships:
        for p in CHAMPIONSHIP_PREFIXES:
            n = n.replace(p, '')
    return n.strip()


def official_races() -> pd.DataFrame:
    seen = {}
    with open(OFFICIAL, newline='') as f:
        for row in csv.DictReader(f):
            name, year, rtype = row.get('event_name', ''), row.get('race_year', ''), row.get('race_type', '')
            if name and year:
                seen[(name, year, rtype)] = True
    return pd.DataFrame([{'name': k[0], 'year': k[1], 'race_type': k[2]} for k in seen])


def main() -> None:
    off = official_races()
    cc = pd.read_csv(CC_META)
    cc = cc[cc.race_name.notna() & cc.race_year.notna()]
    cc = cc.rename(columns={'race_name': 'name', 'race_year': 'year'})
    cc['year'] = cc.year.astype(str)
    cc['race_type'] = cc.race_type.fillna('')
    print(f'official race-years : {len(off):,}')
    print(f'supplementary races : {len(cc):,}\n')

    stages = {
        'baseline (no normalisation)': dict(generic=False, championships=False),
        'generic rules only': dict(generic=True, championships=False),
        'full (generic + championship prefixes)': dict(generic=True, championships=True),
    }

    results, overlaps = [], {}
    for label, kw in stages.items():
        o = {(norm(r['name'], **kw), r['year'], r['race_type']) for _, r in off.iterrows()}
        c = {(norm(r['name'], **kw), str(r['year']), r['race_type']) for _, r in cc.iterrows()}
        both = o & c
        overlaps[label] = both
        print(f'{label:42s} overlap = {len(both):,}')
        results.append({'stage': label, 'overlap': len(both)})

    base = overlaps['baseline (no normalisation)']
    generic = overlaps['generic rules only']
    full = overlaps['full (generic + championship prefixes)']

    print('\n=== attribution ===')
    print(f'matched without any normalisation      : {len(base):,}')
    print(f'gained by the generic rules            : {len(generic - base):,}')
    print(f'gained by the championship-prefix rules: {len(full - generic):,}')
    print(f'total overlap used by the merge        : {len(full):,}')

    gained = sorted(full - generic)
    if gained:
        print('\nrace-years that matched only because of the championship rules:')
        for k in gained[:20]:
            print(f'  {k[0]:35s} {k[1]}  {k[2]}')
        if len(gained) > 20:
            print(f'  ... and {len(gained) - 20} more')

    n_champ = sum(any(p in str(v).lower() for p in CHAMPIONSHIP_PREFIXES)
                  for v in pd.concat([off.name, cc.name]))
    print(f'\nsource race names containing a championship designation: {n_champ:,}')

    C.write_result(pd.DataFrame(results), 'r1_merge_rule_counts.csv')
    print(f'\nwritten to {OUT / "r1_merge_rule_counts.csv"}')


if __name__ == '__main__':
    main()

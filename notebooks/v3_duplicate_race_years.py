"""Race-years present from both sources in a deposited file (v3.0.0 defect).

Version 3.0.0 matched the official platform and the aggregator by event name
only. Race-years that the two sources name differently ("Ironman Sweden" /
"IRONMAN Kalmar-Sweden") passed the name check and were deposited twice, once
from each source. This script identifies them on the deposited file itself, so
any user of version 3.0.0 can list and drop the affected records:

  for every aggregator race-year, the share of its comparable records (bib and
  overall time present) whose (bib, overall time) pair also exists among the
  official records of the same year and race type. Shares are bimodal: >= 0.99
  for the same race, <= 0.13 otherwise; the threshold is 0.5.

Writes <results dir>/v3_duplicate_race_years.csv (one row per flagged aggregator
race-year: event_id, event_name, race_year, race_type, records, dnf_records,
overlap_share) and prints the totals. Version 4.0.0 applies the same check inside
the merge (merge_sources.py), so running this on v4 should flag nothing.

Run:  python3 v3_duplicate_race_years.py [path to the deposited CSV]
      (default: the v3 deposit next to the raw data, _backup_v3/...)
"""

import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

import _common as C

OVERLAP_SHARE = 0.5
MIN_COMPARABLE = 50
DEFAULT = C.RAW_DIR / '_backup_v3' / 'ironman_dataset_deidentified_v3.csv'
COLS = ['event_id', 'event_name', 'race_year', 'race_type', 'bib', 'overall_sec',
        'finish_status', 'source']


def main() -> None:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    official = defaultdict(set)
    cc_pairs = defaultdict(list)
    cc_info: dict[str, dict] = {}
    total = 0
    for c in pd.read_csv(src, usecols=COLS, dtype=str, keep_default_na=False, chunksize=500_000):
        total += len(c)
        comp = c[(c['bib'] != '') & ~c['overall_sec'].isin(['', '0'])]
        off = comp[comp['source'] == 'official']
        for (y, t), g in off.groupby(['race_year', 'race_type']):
            official[(y, t)].update(zip(g['bib'], g['overall_sec']))
        cc = c[c['source'] == 'coachcox']
        for eid, g in cc.groupby('event_id'):
            info = cc_info.setdefault(eid, {'event_id': eid, 'event_name': g['event_name'].iat[0],
                                            'race_year': g['race_year'].iat[0],
                                            'race_type': g['race_type'].iat[0],
                                            'records': 0, 'dnf_records': 0})
            info['records'] += len(g)
            info['dnf_records'] += int((g['finish_status'] == 'DNF').sum())
            gc = g[(g['bib'] != '') & ~g['overall_sec'].isin(['', '0'])]
            cc_pairs[eid].extend(zip(gc['bib'], gc['overall_sec']))
    rows = []
    for eid, info in cc_info.items():
        pairs = cc_pairs[eid]
        if len(pairs) < MIN_COMPARABLE:
            continue
        ref = official[(info['race_year'], info['race_type'])]
        share = sum(p in ref for p in pairs) / len(pairs)
        if share >= OVERLAP_SHARE:
            rows.append({**info, 'overlap_share': round(share, 4)})
    columns = ['event_id', 'event_name', 'race_year', 'race_type', 'records', 'dnf_records', 'overlap_share']
    out = pd.DataFrame(rows, columns=columns).sort_values(['race_year', 'event_name'])
    path = C.write_result(out, 'v3_duplicate_race_years.csv', source_path=src)
    n = int(out['records'].sum()) if len(out) else 0
    d = int(out['dnf_records'].sum()) if len(out) else 0
    print(f'file: {src}  ({total:,} records)')
    print(f'aggregator race-years duplicating an official race-year: {len(out)}  '
          f'({n:,} records, {n / total * 100:.2f}%; {d:,} DNF)')
    print(f'-> {path}')


if __name__ == '__main__':
    main()

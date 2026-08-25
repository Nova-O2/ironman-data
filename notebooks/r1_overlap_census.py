"""R1 — census of race-years present in BOTH sources.

Feasibility gate for the decision on R1-Rev2-Q1 (author decision, 2026-08-25): expand the
cross-source validation beyond the six races of the 2024 season, provided the
overlap is large enough to be worth it.

The merge keeps official records and adds supplementary ones only for race-years
absent from the official source, so the merged CSV cannot show the overlap. This
reads the two raw sources and intersects them using the merge's own
`normalize_race_name`, so the census matches the merge's notion of "same race".

Also answers R1-Rev2-Q9 (were unavailable official race-years recovered through
CoachCox?) — that is the CoachCox-only set, which is the merge's supplement.

Run:  uv run --no-project --with pandas python notebooks/r1_overlap_census.py
"""

import csv
import importlib.util
import sys
from collections import Counter
from pathlib import Path

import _common as C

RAW = C.RAW_DIR
OFFICIAL = RAW / 'ironman_official' / 'ironman_official_all.csv'
COACHCOX = RAW / '_legacy' / 'coachcox' / 'coachcox_all_results.csv'
CC_META = RAW / '_legacy' / 'coachcox' / 'race_metadata.csv'

csv.field_size_limit(10 ** 7)

# Reuse the merge's normalisation so "same race" means the same thing here.
spec = importlib.util.spec_from_file_location('merge_sources', RAW / 'merge_sources.py')
merge = importlib.util.module_from_spec(spec)
sys.modules['merge_sources'] = merge
spec.loader.exec_module(merge)
normalize = merge.normalize_race_name


def index_official():
    counts = Counter()
    with open(OFFICIAL, newline='') as f:
        for row in csv.DictReader(f):
            name, year, rtype = row.get('event_name', ''), row.get('race_year', ''), row.get('race_type', '')
            if name and year:
                counts[(normalize(name), year, rtype)] += 1
    return counts


def index_coachcox():
    meta = {}
    with open(CC_META, newline='') as f:
        for row in csv.DictReader(f):
            meta[row['race_id']] = row
    counts = Counter()
    fields = None
    with open(COACHCOX, newline='') as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        for row in reader:
            rid = row.get('race_id') or row.get('rid') or ''
            m = meta.get(rid, {})
            name = m.get('race_name') or row.get('event_name', '')
            year = m.get('race_year') or row.get('race_year', '')
            rtype = m.get('race_type') or row.get('race_type', '')
            if name and year:
                counts[(normalize(name), str(year), rtype)] += 1
    return counts, fields, meta


def main() -> None:
    print('CoachCox metadata columns:')
    with open(CC_META, newline='') as f:
        print(' ', csv.DictReader(f).fieldnames)

    print('\nIndexing official source...')
    off = index_official()
    print(f'  official race-years: {len(off):,}  records: {sum(off.values()):,}')

    print('Indexing CoachCox source...')
    cc, cc_fields, meta = index_coachcox()
    print(f'  CoachCox result columns: {cc_fields}')
    print(f'  CoachCox race-years: {len(cc):,}  records: {sum(cc.values()):,}')

    both = set(off) & set(cc)
    cc_only = set(cc) - set(off)
    off_only = set(off) - set(cc)

    print('\n=== census ===')
    print(f'race-years in BOTH sources : {len(both):,}')
    print(f'  official records therein : {sum(off[k] for k in both):,}')
    print(f'  CoachCox records therein : {sum(cc[k] for k in both):,}')
    print(f'race-years CoachCox-only   : {len(cc_only):,}  (the merge supplement; answers Q9)')
    print(f'  records                  : {sum(cc[k] for k in cc_only):,}')
    print(f'race-years official-only   : {len(off_only):,}')

    if both:
        years = sorted({k[1] for k in both})
        print(f'\noverlap year span: {years[0]}–{years[-1]}  ({len(years)} distinct years)')
        print('overlap race-years per year:')
        per_year = Counter(k[1] for k in both)
        for y in years:
            print(f'  {y}: {per_year[y]:>4}')
        print('\noverlap by race_type:')
        for t, c in Counter(k[2] for k in both).items():
            print(f'  {t}: {c}')

    # Persist. The three-way split is quoted in Methods §Data merging (R1-Rev1-Q6,
    # R1-Rev2-Q9), and a manuscript number whose only record is this script's
    # stdout is exactly the untraceable claim the round's audit exists to prevent.
    import pandas as pd

    by_type = Counter(k[2] for k in both)
    summary = pd.DataFrame([{
        'race_years_both': len(both),
        'race_years_official_only': len(off_only),
        'race_years_supplementary_only': len(cc_only),
        'race_years_total': len(set(off) | set(cc)),
        'records_official_in_overlap': sum(off[k] for k in both),
        'records_supplementary_in_overlap': sum(cc[k] for k in both),
        'records_supplementary_only': sum(cc[k] for k in cc_only),
        'overlap_full_distance': by_type.get('im', 0),
        'overlap_half_distance': by_type.get('him', 0),
        'overlap_year_min': min(k[1] for k in both) if both else '',
        'overlap_year_max': max(k[1] for k in both) if both else '',
    }])
    path = C.write_result(summary, 'r1_overlap_census.csv', source_path=OFFICIAL)
    print(f'\n-> {path.relative_to(C.PAPER_DIR)}')


if __name__ == '__main__':
    main()

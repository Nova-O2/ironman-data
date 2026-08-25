"""R1 · A1 — cross-source validation over every race-year present in both sources.

Replaces the six races of the 2024 season with all 559 race-years that appear in
both the official platform and the supplementary source (2003-2026, both
distances). Decided by the authors, 2026-08-25 under R1-Rev2-Q1.

Closes, in one run:
  R1-Rev2-Q1   "validated" now rests on the full overlap, not a 6-race sample
  R1-Rev2-Q12  no selection rule left to defend — the validation set IS the overlap
  R1-Rev2-Q14  matching runs three ways — raw, NFKD-normalised, order-invariant —
               and the deltas between them are the answer. The first run refuted
               the manuscript's stated cause; see name_canonical() below.
  R1-Rev1-Q3   supplies the Abstract's validation figures

Does NOT close R1-Rev2-Q2 (continent count). The supplementary source's region
codes are too coarse and partly ambiguous to count continents from; the overlap
race slugs are emitted for a curated host-country map instead.

Reads the two RAW sources, never the merged file: the merge discards supplementary
records for overlapping race-years, so the merged CSV cannot support this analysis.

Matching is within race-year, so this is 559 small joins, not a cross-product.

Outputs (notebooks/results/):
  r1_cross_source_per_race.csv   one row per overlapping race-year
  r1_cross_source_summary.csv    headline figures for the manuscript
  r1_cross_source_by_year.csv    agreement by season, to expose any temporal drift

Run:  uv run --no-project --with pandas python notebooks/r1_expanded_cross_source.py
"""

import csv
import importlib.util
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

import _common as C

RAW = C.RAW_DIR
OFFICIAL = RAW / 'ironman_official' / 'ironman_official_all.csv'
COACHCOX = RAW / '_legacy' / 'coachcox' / 'coachcox_all_results.csv'
CC_META = RAW / '_legacy' / 'coachcox' / 'race_metadata.csv'
OUT = Path(__file__).parent / 'results'
OUT.mkdir(exist_ok=True)

SPLITS = ['swim_sec', 't1_sec', 'bike_sec', 't2_sec', 'run_sec', 'overall_sec']

csv.field_size_limit(10 ** 7)

spec = importlib.util.spec_from_file_location('merge_sources', RAW / 'merge_sources.py')
merge = importlib.util.module_from_spec(spec)
sys.modules['merge_sources'] = merge
spec.loader.exec_module(merge)
normalize_race = merge.normalize_race_name


def name_exact(s: pd.Series) -> pd.Series:
    """Case-insensitive exact match — what the submitted manuscript used."""
    return s.fillna('').str.strip().str.lower()


def name_normalised(s: pd.Series) -> pd.Series:
    """NFKD fold: strip diacritics, drop punctuation, collapse whitespace.

    The manuscript attributes the lower match rate on non-English fields to
    character-encoding differences. R1-Rev2-Q14 asks us to substantiate that.
    If this does not lift the rate, the stated cause is wrong.
    """
    out = (s.fillna('')
           .map(lambda x: unicodedata.normalize('NFKD', str(x)))
           .map(lambda x: x.encode('ascii', 'ignore').decode('ascii'))
           .str.lower()
           .map(lambda x: re.sub(r'[^a-z0-9 ]', ' ', x))
           .map(lambda x: re.sub(r'\s+', ' ', x).strip()))
    return out


def name_canonical(s: pd.Series) -> pd.Series:
    """Order-invariant form: NFKD fold, then sort the name tokens.

    The first run showed 63 race-years — every one of them 2017-2019 and
    full-distance — matching at exactly 0% despite record counts agreeing to
    within a couple of athletes. Inspection found the cause: for those seasons
    the supplementary source stores "Lastname, Firstname" while the official
    platform stores "Firstname Lastname". Diacritic folding cannot repair a
    reordering, which is why NFKD lifted the median rate by only 0.46 points.

    Sorting tokens makes the comparison order-invariant and covers both the
    comma form and any other permutation. It can in principle merge two
    distinct athletes whose name tokens coincide; ambiguous names are dropped
    from both sides before joining, so such cases are excluded rather than
    silently mismatched.
    """
    return name_normalised(s).map(lambda x: ' '.join(sorted(x.split())))


def load_official() -> pd.DataFrame:
    cols = ['name', 'event_name', 'race_year', 'race_type', 'finish_status'] + SPLITS
    df = pd.read_csv(OFFICIAL, usecols=cols, low_memory=False)
    df['key'] = (df.event_name.fillna('').map(normalize_race) + '|'
                 + df.race_year.astype('string').fillna('') + '|'
                 + df.race_type.fillna(''))
    return df


def load_coachcox() -> tuple[pd.DataFrame, pd.DataFrame]:
    meta = pd.read_csv(CC_META)
    meta['race_id'] = meta.race_id.astype('string')
    cols = ['name', 'race_id', 'finish_status'] + SPLITS
    df = pd.read_csv(COACHCOX, usecols=cols, low_memory=False)
    df['race_id'] = df.race_id.astype('string')
    df = df.merge(meta[['race_id', 'race_name', 'race_year', 'race_type', 'region']],
                  on='race_id', how='left')
    df['key'] = (df.race_name.fillna('').map(normalize_race) + '|'
                 + df.race_year.astype('string').fillna('') + '|'
                 + df.race_type.fillna(''))
    return df, meta


REGION_TO_CONTINENT = {
    'north america': 'North America', 'south america': 'South America',
    'europe': 'Europe', 'africa': 'Africa', 'asia': 'Asia',
    'oceania': 'Oceania', 'australia': 'Oceania', 'middle east': 'Asia',
    'caribbean': 'North America', 'central america': 'North America',
    'asia pacific': 'Asia', 'asia-pacific': 'Asia',
}


def main() -> None:
    print('Loading official source...', flush=True)
    off = load_official()
    print(f'  {len(off):,} records', flush=True)

    print('Loading supplementary source...', flush=True)
    cc, meta = load_coachcox()
    print(f'  {len(cc):,} records', flush=True)

    # Explicit rather than relying on `-` binding tighter than `&` (audit A1-08).
    EMPTY_KEY = '||'
    overlap = sorted((set(off.key) & set(cc.key)) - {EMPTY_KEY})
    print(f'\noverlapping race-years: {len(overlap):,}', flush=True)

    off = off[off.key.isin(overlap)].copy()
    cc = cc[cc.key.isin(overlap)].copy()
    print(f'  official records in overlap : {len(off):,}')
    print(f'  supplementary in overlap    : {len(cc):,}\n', flush=True)

    # Derive the three match keys, then drop every text column they came from.
    # Audit A1-10: holding the name and event-name strings for ~2M rows alongside
    # three derived copies of each name was enough to be killed by the OOM killer.
    keep = ['key', 'm_exact', 'm_norm', 'm_canon'] + SPLITS
    frames = []
    for df in (off, cc):
        df['m_exact'] = name_exact(df.name)
        df['m_norm'] = name_normalised(df.name)
        df['m_canon'] = name_canonical(df.name)
        frames.append(df[keep].copy())
    off, cc = frames

    # Emit the event-series slugs behind the overlap so a host-country map can be
    # curated by hand. The supplementary source's own `region` field is not usable
    # for the continent count R1-Rev2-Q2 needs: its values are Euro / Australia /
    # Asia / SA / Africa with 321 races unlabelled, and "SA" is ambiguous between
    # South America and South Africa. Guessing a continent from an ambiguous code is
    # exactly the class of error that produced the "five continents" claim.
    C.write_result(pd.DataFrame({'race': sorted({k.split('|')[0] for k in overlap})}),
                   'r1_overlap_race_slugs.csv', source_path=OFFICIAL)

    # Group once. The previous form scanned `off[off.key == key]` inside the loop,
    # allocating a full-length boolean mask 559 times over a million rows each —
    # O(n·k) work and a steady stream of large transient allocations (audit A1-10).
    off_groups = dict(tuple(off.groupby('key', sort=False)))
    cc_groups = dict(tuple(cc.groupby('key', sort=False)))
    empty = off.iloc[0:0]

    rows = []
    for i, key in enumerate(overlap, 1):
        if i % 100 == 0:
            print(f'  ...{i}/{len(overlap)}', flush=True)
        a = off_groups.get(key, empty)
        b = cc_groups.get(key, empty)
        rec = {'key': key,
               'race': key.split('|')[0], 'year': key.split('|')[1], 'race_type': key.split('|')[2],
               'n_official': len(a), 'n_supplementary': len(b),
               'count_diff': abs(len(a) - len(b))}

        # Initialised so a race-year with no matches contributes explicit zeros
        # rather than NaN that aggregations skip in silence (audit A1-03).
        for s_ in SPLITS:
            rec[f'{s_}_pairs'] = 0
            rec[f'{s_}_exact'] = 0
        rec['split_pairs'] = 0
        rec['split_exact'] = 0
        rec['split_agreement_pct'] = float('nan')

        for label, col in (('exact', 'm_exact'), ('norm', 'm_norm'), ('canon', 'm_canon')):
            # Ambiguous names within a race cannot be matched one-to-one; drop and count.
            da = a[a[col] != ''].drop_duplicates(subset=col, keep=False)
            db = b[b[col] != ''].drop_duplicates(subset=col, keep=False)
            j = da.merge(db, on=col, suffixes=('_o', '_c'))
            denom = min(len(da), len(db))
            rec[f'matched_{label}'] = len(j)
            rec[f'match_rate_{label}'] = len(j) / denom * 100 if denom else float('nan')
            rec[f'ambiguous_dropped_{label}'] = (len(a) - len(da)) + (len(b) - len(db))

            if label == 'canon' and len(j):
                agree = total = 0
                for s in SPLITS:
                    o, c = j[f'{s}_o'], j[f'{s}_c']
                    both = o.notna() & c.notna() & (o > 0) & (c > 0)
                    agree += int((both & (o == c)).sum())
                    total += int(both.sum())
                    rec[f'{s}_pairs'] = int(both.sum())
                    rec[f'{s}_exact'] = int((both & (o == c)).sum())
                rec['split_pairs'] = total
                rec['split_exact'] = agree
                rec['split_agreement_pct'] = agree / total * 100 if total else float('nan')
        rows.append(rec)

    per_race = pd.DataFrame(rows)
    C.write_result(per_race, 'r1_cross_source_per_race.csv')

    # ---- headline figures -------------------------------------------------
    tot_pairs = int(per_race.split_pairs.sum())
    tot_exact = int(per_race.split_exact.sum())
    disc = {s: (int(per_race[f'{s}_exact'].sum()), int(per_race[f'{s}_pairs'].sum()))
            for s in SPLITS}


    print('\n' + '=' * 62)
    print('EXPANDED CROSS-SOURCE VALIDATION')
    print('=' * 62)
    print(f'race-years compared       : {len(per_race):,}')
    print(f'season span               : {per_race.year.min()}-{per_race.year.max()}')
    print(f'full-distance / half      : {(per_race.race_type == "im").sum()} / '
          f'{(per_race.race_type == "him").sum()}')
    print('continents represented    : PENDING — needs a curated host-country map;')
    print('                            slugs written to r1_overlap_race_slugs.csv')
    print(f'record count within 2      : {(per_race.count_diff <= 2).sum()} of {len(per_race)}')
    print(f'\nmatch rate, exact          : median {per_race.match_rate_exact.median():.1f}%  '
          f'range {per_race.match_rate_exact.min():.1f}-{per_race.match_rate_exact.max():.1f}%')
    print(f'match rate, NFKD-normalised: median {per_race.match_rate_norm.median():.1f}%  '
          f'range {per_race.match_rate_norm.min():.1f}-{per_race.match_rate_norm.max():.1f}%')
    print(f'match rate, order-invariant: median {per_race.match_rate_canon.median():.1f}%  '
          f'range {per_race.match_rate_canon.min():.1f}-{per_race.match_rate_canon.max():.1f}%')
    print(f'  races still under 5%%      : {(per_race.match_rate_canon < 5).sum()}')
    print(f'  -> Q14 delta (median)    : '
          f'{per_race.match_rate_norm.median() - per_race.match_rate_exact.median():+.2f} pp')
    no_pairs = int((per_race.split_pairs == 0).sum())
    print(f'\nrace-years contributing no matched pairs: {no_pairs} of {len(per_race)}'
          f'  (excluded from the agreement figure)')
    print(f'matched athlete-discipline pairs: {tot_pairs:,}')
    print(f'exact split agreement           : {tot_exact / tot_pairs * 100:.2f}%')
    print('\nby discipline:')
    for s, (a, t) in disc.items():
        print(f'  {s:12s} {a / t * 100:6.2f}%  ({a:,}/{t:,})')
    print('\nper-race agreement distribution:')
    q = per_race.split_agreement_pct.quantile([0, .05, .25, .5, .75, .95, 1])
    for k, v in q.items():
        print(f'  p{int(k * 100):<3d} {v:6.2f}%')

    by_year = (per_race.groupby('year')
               .agg(races=('key', 'size'),
                    pairs=('split_pairs', 'sum'),
                    exact=('split_exact', 'sum'),
                    match_exact=('match_rate_exact', 'median'),
                    match_norm=('match_rate_norm', 'median'),
                    match_canon=('match_rate_canon', 'median')))
    by_year['agreement_pct'] = by_year.exact / by_year.pairs * 100
    C.write_result(by_year, 'r1_cross_source_by_year.csv', index=True)
    print('\nagreement by season:')
    print(by_year[['races', 'agreement_pct', 'match_exact', 'match_norm', 'match_canon']].round(2).to_string())

    C.write_result(pd.DataFrame([{
        'race_years': len(per_race),
        'year_min': per_race.year.min(), 'year_max': per_race.year.max(),
        'n_full': int((per_race.race_type == 'im').sum()),
        'n_half': int((per_race.race_type == 'him').sum()),
        'match_rate_exact_median': per_race.match_rate_exact.median(),
        'match_rate_norm_median': per_race.match_rate_norm.median(),
        'match_rate_canon_median': per_race.match_rate_canon.median(),
        'split_pairs': tot_pairs, 'split_exact': tot_exact,
        'split_agreement_pct': tot_exact / tot_pairs * 100,
        **{f'{s}_agreement_pct': a / t * 100 for s, (a, t) in disc.items()},
    }]), 'r1_cross_source_summary.csv', source_path=OFFICIAL)

    print(f'\nwritten to {OUT}')


if __name__ == '__main__':
    main()

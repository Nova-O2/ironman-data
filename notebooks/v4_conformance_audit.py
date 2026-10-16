"""v4 — conformance audit of the refreshed dataset before the Zenodo deposit.

Checks that version 4.0.0 (collected 15 October 2026) conforms to what the
published article (Sci 2026, 8(9), 265; describes v3.0.0) and the companion
repository say a release of this dataset is, and that nothing was lost or
duplicated on the way from v3 to v4. Mechanical checks only; the text of the
Zenodo description is audited separately.

Sections
  1. Deposit file: same 27 columns and order as the v3 deposit, CRLF, UTF-8,
     no `name`, no record carrying the source's redaction marker.
  2. Domains: source, race_type, race_year, finish_status; blank statuses are the
     official records without event attribution (10,342 in v3).
  3. Merge rule: no (normalised event name, year, type) present in both sources.
  4. Duplicates: exact duplicates on the identifying tuple, per source, v4 vs v3.
  5. Continuity: every official race-year of v3 is in v4 with the same record
     count, except the 2026 editions that were re-downloaded (listed); every v3
     supplementary race-year is either still supplementary or now covered by the
     official platform (listed by count).
  6. 2026 season: editions and records by source.

Outputs results_v4/v4_conformance_audit.txt and .csv (one row per check).
Run:  IRONMAN_RESULTS_DIR=$PWD/results_v4 python3 v4_conformance_audit.py
"""

import csv
import hashlib
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

import _common as C

sys.path.insert(0, str(C.RAW_DIR))
from merge_sources import normalize_race_name  # noqa: E402

V3_DIR = C.RAW_DIR / '_backup_v3'
V3_DEPOSIT = V3_DIR / 'ironman_dataset_deidentified_v3.csv'
V3_MERGED = V3_DIR / 'ironman_merged_v3_2026-03-28.csv'
V4_DEPOSIT = C.DEPOSIT_CSV
V4_MERGED = C.DATA_FALLBACK
REDACTION = '-Redacted-'
ID_COLS = ['event_name', 'race_year', 'bib', 'age_group', 'swim_sec', 'bike_sec',
           'run_sec', 'overall_sec', 'finish_status']
CHUNK = 500_000

checks: list[dict] = []
lines: list[str] = []


def check(name: str, ok: bool, detail: str) -> None:
    checks.append({'check': name, 'status': 'PASS' if ok else 'FAIL', 'detail': detail})
    lines.append(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")


def header_and_terminator(path: Path) -> tuple[list[str], str]:
    with open(path, 'rb') as f:
        first = f.readline()
    term = 'CRLF' if first.endswith(b'\r\n') else 'LF'
    return first.decode('utf-8').rstrip('\r\n').split(','), term


def scan(path: Path, with_hashes: bool) -> dict:
    """One streaming pass: domains, redaction, merge-rule keys, duplicate hashes,
    per (source, event key) record counts."""
    s = {'n': 0, 'source': Counter(), 'race_type': Counter(), 'year': Counter(),
         'status': Counter(), 'status_blank_by_source': Counter(), 'redacted': 0,
         'keys_by_source': defaultdict(set), 'hashes_by_source': defaultdict(Counter),
         'per_event': Counter(), 'year_source': Counter(), 'year_source_events': defaultdict(set)}
    for c in pd.read_csv(path, dtype=str, keep_default_na=False, chunksize=CHUNK):
        s['n'] += len(c)
        s['source'].update(c['source'].value_counts().to_dict())
        s['race_type'].update(c['race_type'].value_counts().to_dict())
        s['year'].update(c['race_year'].value_counts().to_dict())
        s['status'].update(c['finish_status'].value_counts().to_dict())
        blank = c[c['finish_status'] == '']
        s['status_blank_by_source'].update(blank['source'].value_counts().to_dict())
        s['redacted'] += int((c['country'].str.strip() == REDACTION).sum())
        if 'name' in c.columns:
            s['redacted'] += int((c['name'].str.strip() == REDACTION).sum())
        key = list(zip(c['event_name'].map(normalize_race_name), c['race_year'], c['race_type']))
        for src, k in zip(c['source'], key):
            s['keys_by_source'][src].add(k)
        ev = list(zip(c['source'], c['event_id'], c['event_name'], c['race_year']))
        s['per_event'].update(ev)
        s['year_source'].update(zip(c['race_year'], c['source']))
        for y, src, e in zip(c['race_year'], c['source'], c['event_id']):
            s['year_source_events'][(y, src)].add(e)
        if with_hashes:
            tup = c[ID_COLS].astype(str).agg('|'.join, axis=1)
            for src, t in zip(c['source'], tup):
                s['hashes_by_source'][src][hashlib.blake2b(t.encode(), digest_size=8).digest()] += 1
    return s


def dup_summary(hashes: Counter) -> tuple[int, int]:
    extra = sum(n - 1 for n in hashes.values() if n > 1)
    groups = sum(1 for n in hashes.values() if n > 1)
    return groups, extra


def main() -> None:
    lines.append(C.provenance(V4_DEPOSIT)[0] if hasattr(C, 'provenance') else '')
    lines.append('v4 conformance audit — 2026-10-15\n')

    # 1. deposit file
    h3, t3 = header_and_terminator(V3_DEPOSIT)
    h4, t4 = header_and_terminator(V4_DEPOSIT)
    check('deposit columns identical to v3', h3 == h4, f'{len(h4)} columns; v3 {len(h3)}; '
          f'diff {sorted(set(h3) ^ set(h4)) or "none"}; order {"same" if h3 == h4 else "DIFFERENT"}')
    check('deposit line terminator CRLF like v3', t4 == 'CRLF' and t3 == 'CRLF', f'v4 {t4}, v3 {t3}')
    check('deposit has no name column', 'name' not in h4, ', '.join(h4))

    lines.append('\nScanning v4 deposit ...')
    d4 = scan(V4_DEPOSIT, with_hashes=True)
    cf = pd.read_csv(C.RESULTS_DIR / 'r1_country_field_summary.csv', comment='#')
    expected = int(cf['deposited_n'].iat[0])
    check('deposit record count equals the QA count', d4['n'] == expected,
          f"{d4['n']:,} (r1_country_field: described {int(cf['described_n'].iat[0]):,} - redaction "
          f"{int(cf['redaction_cohort'].iat[0]):,} = {expected:,})")
    check('deposit carries no redaction marker', d4['redacted'] == 0, f"{d4['redacted']} records")

    # 2. domains
    check('source domain', set(d4['source']) == {'official', 'coachcox'}, dict(d4['source']))
    check('race_type domain', set(d4['race_type']) == {'im', 'him'}, dict(d4['race_type']))
    years = sorted(d4['year'])
    check('race_year range 2002-2026', years[0] == '2002' and years[-1] == '2026' and all(y.isdigit() for y in years),
          f'{years[0]}-{years[-1]}, {len(years)} seasons')
    check('finish_status domain', set(d4['status']) <= {'FIN', 'DNF', 'DNS', 'DQ', ''}, dict(d4['status']))
    check('blank finish_status only in unattributed official records',
          set(d4['status_blank_by_source']) <= {'official'} and d4['status'][''] == 10_342,
          f"{d4['status']['']:,} blank, by source {dict(d4['status_blank_by_source'])} (v3: 10,342 official)")

    # 3. merge rule
    both = d4['keys_by_source']['official'] & d4['keys_by_source']['coachcox']
    check('merge rule: no race-year in both sources', len(both) == 0,
          f"{len(both)} overlapping keys" + (f": {sorted(both)[:5]}" if both else ''))
    check('supplementary race-years (name, year, type)', True,
          f"{len(d4['keys_by_source']['coachcox']):,} supplementary, {len(d4['keys_by_source']['official']):,} official")

    # 4. duplicates, v4 vs v3
    lines.append('\nScanning v3 deposit (baseline) ...')
    d3 = scan(V3_DEPOSIT, with_hashes=True)
    for src in ('official', 'coachcox'):
        g4, e4 = dup_summary(d4['hashes_by_source'][src]); g3, e3 = dup_summary(d3['hashes_by_source'][src])
        n4, n3 = d4['source'][src], d3['source'][src]
        check(f'exact duplicates on identifying tuple — {src}', (e4 / n4) <= max(2 * (e3 / n3), 0.0005),
              f'v4 {e4:,} extra rows in {g4:,} groups ({e4 / n4 * 100:.3f}%); v3 {e3:,} in {g3:,} ({e3 / n3 * 100:.3f}%)')

    # 5. continuity v3 -> v4 (official race-years by event_id; supplementary by key)
    v3_off = {k[1:]: n for k, n in d3['per_event'].items() if k[0] == 'official'}
    v4_off = {k[1:]: n for k, n in d4['per_event'].items() if k[0] == 'official'}
    lost = [k for k in v3_off if k not in v4_off]
    changed = {k: (v3_off[k], v4_off[k]) for k in v3_off if k in v4_off and v3_off[k] != v4_off[k]}
    changed_2026 = {k: v for k, v in changed.items() if k[2] == '2026'}
    changed_other = {k: v for k, v in changed.items() if k[2] != '2026'}
    check('every v3 official race-year present in v4', len(lost) == 0,
          f'{len(lost)} lost' + (f': {lost[:5]}' if lost else ''))
    check('v3 official record counts unchanged outside 2026', len(changed_other) == 0,
          f'{len(changed_other)} race-years changed' + (f': {list(changed_other.items())[:5]}' if changed_other else ''))
    lines.append(f'  2026 editions re-downloaded with a different count: {len(changed_2026)}')
    for k, (a, b) in sorted(changed_2026.items()):
        lines.append(f'    {k[1]} ({k[0]}): {a:,} -> {b:,} ({b - a:+,})')
    v3_cc = d3['keys_by_source']['coachcox']; v4_cc = d4['keys_by_source']['coachcox']; v4_of = d4['keys_by_source']['official']
    # race-years the merge dropped on purpose (same race as an official race-year, or a duplicate listing)
    excluded = set()
    with open(C.RAW_DIR / 'supplement_excluded.csv', newline='') as f:
        for r in csv.DictReader(f):
            excluded.add((normalize_race_name(r['race_name']), r['race_year'], r['race_type']))
    still = v3_cc & v4_cc; covered = v3_cc & v4_of; dropped = (v3_cc - v4_cc - v4_of) & excluded
    gone = v3_cc - v4_cc - v4_of - excluded
    check('every v3 supplementary race-year accounted for in v4', len(gone) == 0,
          f'{len(still)} still supplementary, {len(covered)} now official, {len(dropped)} dropped by the merge '
          f'as the same race as an official race-year (v3 defect), {len(gone)} unexplained'
          + (f': {sorted(gone)[:5]}' if gone else ''))
    v3_cc_n = d3['source']['coachcox']
    lines.append(f"  v3 supplementary records {v3_cc_n:,}; v4 supplementary {d4['source']['coachcox']:,}")

    # 6. 2026
    for src in ('official', 'coachcox'):
        lines.append(f"  2026 {src}: {len(d4['year_source_events'][('2026', src)])} editions, "
                     f"{d4['year_source'][('2026', src)]:,} records")

    # year x source table
    rows = sorted({y for y, _ in d4['year_source']})
    tbl = pd.DataFrame({'race_year': rows,
                        'official': [d4['year_source'][(y, 'official')] for y in rows],
                        'coachcox': [d4['year_source'][(y, 'coachcox')] for y in rows],
                        'v3_official': [d3['year_source'][(y, 'official')] for y in rows],
                        'v3_coachcox': [d3['year_source'][(y, 'coachcox')] for y in rows]})
    C.write_result(tbl, 'v4_records_by_year_source.csv', source_path=V4_DEPOSIT)
    C.write_result(pd.DataFrame(checks), 'v4_conformance_audit.csv', source_path=V4_DEPOSIT)
    n_fail = sum(c['status'] == 'FAIL' for c in checks)
    lines.append(f'\n{len(checks)} checks, {n_fail} FAIL')
    out = C.RESULTS_DIR / 'v4_conformance_audit.txt'
    out.write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))
    print(f'-> {out}')


if __name__ == '__main__':
    main()

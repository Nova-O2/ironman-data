"""R1 — event-level coverage, measured, and repair of the discovery artefact.

Answers R1-Rev2-Q8 and R1-Rev2-Q9 with numbers that reconstruct from the files
in the repository, and repairs the artefact that made them fail to reconstruct.

Why this exists
---------------
The execution plan carried "1,192 race-years discovered -> 1,172 retrieved
(98.3%)". That ratio does not hold. The two sets are not nested: of the 1,172
race-years for which the official platform returned results, only 1,129 appear
in the saved discovery file `all_subevents.csv`. Dividing them produces a
coverage rate that describes nothing — inside the very answer that defends the
word "population-scale".

Two distinct causes, and only one of them is a defect:

1. **63 discovered subevents returned no results.** Real and worth reporting:
   28 of them are 2021 editions, consistent with pandemic cancellations, and the
   rest are scattered cancelled or never-published editions. A reuser looking for
   a missing race-year deserves this sentence.

2. **43 race-years were collected that the discovery file does not list.** These
   belong to four event series — the World Championship, Kalmar, Emilia-Romagna
   and Cascais — all four of which *are* present in `event_uuids_full.csv`, the
   127-series list, while `all_subevents.csv` holds zero subevent rows for them.
   None of the 43 duplicates a discovered race-year under a second UUID. So these
   are not undiscovered events; the saved enumeration is simply incomplete.

The second is a reproducibility defect in a paper about reproducibility: someone
running the pipeline from the repository would enumerate fewer race-years than
the dataset contains, with no way to see why. It is repaired here rather than
described in the Methods (author decision, 2026-08-25).

What the repair does and does not recover
-----------------------------------------
The missing rows are reconstructed from the collected results themselves:
`parent_slug`, `subevent_id` (the collected `event_id`), `subevent_name` and
`year` all come from the official records, and `parent_uuid` from
`event_uuids_full.csv`. `subevent_date` is **not** recoverable this way and is
left empty — the collected records carry no event date. Reconstructed rows are
marked in a `reconstructed` column so the provenance of every row stays legible;
rows from the original discovery run carry an empty value there.

Idempotent: after a repair there is nothing left to reconstruct, and a second run
rewrites byte-identical content.

Run:  uv run --no-project --with pandas python notebooks/r1_event_coverage.py
"""

import csv
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

import _common as C

csv.field_size_limit(10 ** 7)

COLLECTION_DIR = C.PAPER_DIR / 'data' / 'collection'
SUBEVENTS_CSV = COLLECTION_DIR / 'all_subevents.csv'
EVENT_UUIDS_CSV = COLLECTION_DIR / 'event_uuids_full.csv'

FIELDS = ['parent_slug', 'parent_uuid', 'subevent_name', 'subevent_id',
          'subevent_date', 'year', 'reconstructed']

# Race-years recovered from the supplementary source, i.e. those absent from the
# official platform. Measured by r1_overlap_census.py over the two raw sources and
# independently reproducible from the merged file by counting distinct
# (event_name, race_year) among source == 'coachcox'. The submitted Methods said
# 388; both routes give 382 for the same 665,179 records (R1-Int-6).
SUPPLEMENTARY_RACE_YEARS = 382
SUPPLEMENTARY_RECORDS = 665_179


def read_discovery() -> list[dict]:
    with open(SUBEVENTS_CSV, newline='') as f:
        return [dict(r) for r in csv.DictReader(f)]


def read_parent_uuids() -> dict[str, str]:
    """slug -> parent UUID, from the 127-series discovery list (headerless)."""
    uuids = {}
    with open(EVENT_UUIDS_CSV, newline='') as f:
        for row in csv.reader(f):
            if len(row) >= 2 and row[0].strip():
                uuids[row[0].strip()] = row[1].strip()
    return uuids


def read_collected() -> tuple[dict[str, dict], int, int]:
    """subevent_id -> one representative collected record, with a row count.

    Also returns the total official row count and how many of those rows carry no
    event attribution at all. Those two numbers differ by 10,342 records that hold
    neither `event_id` nor `event_name`, spread over 2003-2006 and 2023-2025 —
    which is why Table 1 gives `event_name` 99.6% coverage rather than the 100%
    the submitted version printed (R1-Int-2). Both totals are reported so this
    script's output cannot be read as contradicting the Methods.
    """
    out: dict[str, dict] = {}
    total = unattributed = 0
    with open(C.OFFICIAL_CSV, newline='') as f:
        for row in csv.DictReader(f):
            total += 1
            eid = (row.get('event_id') or '').strip()
            if not eid:
                unattributed += 1
                continue
            key = eid.lower()
            if key not in out:
                out[key] = {'subevent_id': eid,
                            'subevent_name': row.get('event_name', ''),
                            'year': row.get('race_year', ''),
                            'parent_slug': row.get('parent_slug', ''),
                            'records': 0}
            out[key]['records'] += 1
    return out, total, unattributed


def main() -> None:
    discovery = read_discovery()
    parent_uuids = read_parent_uuids()
    collected, official_total, unattributed = read_collected()

    # Reconstructed rows are excluded from the enumerated set on purpose. They are
    # this script's own output, not discovery output, so counting them would make
    # the run that repairs the file report nothing to repair — and the next run
    # would drop them again. The file then oscillates between 1,192 and 1,235 rows,
    # which is exactly what happened on the first attempt. Deriving the repair from
    # the original rows every time makes the output a pure function of the inputs.
    original_rows = [r for r in discovery if not r.get('reconstructed')]
    discovered_ids = {(r.get('subevent_id') or '').strip().lower()
                      for r in original_rows if (r.get('subevent_id') or '').strip()}

    missing_ids = sorted(set(collected) - discovered_ids,
                         key=lambda k: (collected[k]['parent_slug'],
                                        collected[k]['year'],
                                        collected[k]['subevent_id']))
    empty_ids = sorted(discovered_ids - set(collected))
    empty_rows = [r for r in discovery
                  if (r.get('subevent_id') or '').strip().lower() in set(empty_ids)]

    print(f'discovery file rows (original) : {len(original_rows):,}')
    print(f'official records collected     : {official_total:,}  '
          f'(of which {unattributed:,} carry no event_id or event_name)')
    print(f'race-years with results        : {len(collected):,}  '
          f'({sum(c["records"] for c in collected.values()):,} attributed records)')
    print(f'discovered but no results      : {len(empty_ids):,}')
    print(f'collected but not enumerated   : {len(missing_ids):,}  '
          f'({sum(collected[k]["records"] for k in missing_ids):,} records)')

    if empty_rows:
        by_year = Counter(r.get('year', '') for r in empty_rows)
        top = sorted(by_year.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
        print('  no-result editions by year (top): '
              + ', '.join(f'{y}: {n}' for y, n in top))

    if missing_ids:
        by_slug = Counter(collected[k]['parent_slug'] for k in missing_ids)
        print('  unenumerated by series: '
              + ', '.join(f'{s}: {n}' for s, n in by_slug.most_common()))
        unknown = sorted({collected[k]['parent_slug'] for k in missing_ids}
                         - set(parent_uuids))
        if unknown:
            raise KeyError(
                f'no parent UUID for {unknown}; these series are absent from '
                f'{EVENT_UUIDS_CSV.name}, so the discovery list itself is '
                f'incomplete and the repair would invent provenance')

    # --- repair -----------------------------------------------------------
    rebuilt = [
        {'parent_slug': collected[k]['parent_slug'],
         'parent_uuid': parent_uuids[collected[k]['parent_slug']],
         'subevent_name': collected[k]['subevent_name'],
         'subevent_id': collected[k]['subevent_id'],
         'subevent_date': '',
         'year': collected[k]['year'],
         'reconstructed': 'yes'}
        for k in missing_ids
    ]
    rows = [{**{f: r.get(f, '') for f in FIELDS}} for r in original_rows] + rebuilt
    rows.sort(key=lambda r: (r['parent_slug'], r['year'], r['subevent_id']))

    with open(SUBEVENTS_CSV, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    n_rebuilt = sum(1 for r in rows if r['reconstructed'] == 'yes')
    print(f'-> {SUBEVENTS_CSV.relative_to(C.PAPER_DIR)}: {len(rows):,} rows '
          f'({n_rebuilt:,} reconstructed)')

    # --- the numbers the Methods states ------------------------------------
    official_race_years = len(collected)
    summary = pd.DataFrame([{
        'event_series': len(parent_uuids),
        'subevents_enumerated': len(rows),
        'official_race_years_with_results': official_race_years,
        'official_records_total': official_total,
        'official_records_event_attributed': sum(c['records'] for c in collected.values()),
        'official_records_unattributed': unattributed,
        'discovered_without_results': len(empty_ids),
        'discovered_without_results_2021': sum(
            1 for r in empty_rows if r.get('year') == '2021'),
        'reconstructed_rows': n_rebuilt,
        'supplementary_race_years': SUPPLEMENTARY_RACE_YEARS,
        'supplementary_records': SUPPLEMENTARY_RECORDS,
        'total_race_years': official_race_years + SUPPLEMENTARY_RACE_YEARS,
    }])
    path = C.write_result(summary, 'r1_event_coverage.csv', source_path=C.OFFICIAL_CSV)
    print(f'-> {path.relative_to(C.PAPER_DIR)}')
    print(f'\ntotal race-years across both sources: '
          f'{official_race_years + SUPPLEMENTARY_RACE_YEARS:,}')
    print('No retrieval percentage is reported: the enumerated and retrieved sets '
          'were not nested before this repair, so any ratio between them described '
          'nothing.')


if __name__ == '__main__':
    main()

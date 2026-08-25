"""R1 — build the corrected de-identified file for Zenodo v3.

Three changes against the v1 deposit (ironman_dataset_anonymized.csv, 474 MB):

1. Drop the 55 records carrying "-Redacted-" in `country` or `name`. The source
   platform applied an explicit privacy action to those athletes and the v1
   deposit did not propagate it (R1-Int-4). Deposited N becomes 2,706,867
   against a described dataset of 2,706,922 — the two are no longer the same
   file, and the manuscript must say both.
2. Drop the `name` column, as v1 did. Direct identifiers stay out.
3. Keep `bib`. Decided by the authors, 2026-08-25, consistent with the position already
   put to the Academic Editor on 2026-08-09: removing bib narrows the
   re-identification path without closing it, since event, age group, finishing
   rank and exact split times remain and each is needed for the analyses the
   dataset exists to support. The residual risk is declared instead.

The output name says "deidentified", not "anonymized" — the distinction the
Academic Editor asked for at pre-check (PC-Ed-3), which the deposit had never
reflected.

Every column is read as text and written back unchanged. Parsing numerics would
round-trip them through float64 and rewrite "180" as "180.0" across millions of
rows — cosmetically different from the v1 deposit in fields we are not meant to
be touching, and about 35 MB larger for nothing. The output should differ from
v1 only in the two intended ways.

Streams in chunks; never holds the file in memory.

Run:  uv run --no-project --with pandas python notebooks/r1_build_deposit.py
"""

from pathlib import Path

import pandas as pd

import _common as C

SRC = C.DATA_FALLBACK
DST = C.DEPOSIT_CSV
CHUNK = 250_000
REDACTION = '-Redacted-'
# The v1 deposit and the source file are CRLF (csv.writer's default). Matching it
# keeps the only diff against v1 the 55 removed rows, rather than every line.
LINE_TERMINATOR = '\r\n'
DROP_COLUMNS = ['name']


def main() -> None:
    total_in = written = dropped_redacted = 0
    header = True
    if DST.exists():
        DST.unlink()

    for c in pd.read_csv(SRC, chunksize=CHUNK, dtype=str, keep_default_na=False):
        total_in += len(c)
        country = c.country.str.strip()
        name = c.name.str.strip()
        redacted = (country == REDACTION) | (name == REDACTION)
        dropped_redacted += int(redacted.sum())

        out = c[~redacted].drop(columns=[col for col in DROP_COLUMNS if col in c.columns])
        out.to_csv(DST, mode='a', header=header, index=False,
                   lineterminator=LINE_TERMINATOR)
        header = False
        written += len(out)
        print(f'  ...{total_in:,} read / {written:,} written', end='\r', flush=True)

    print(' ' * 60, end='\r')
    print(f'source records      : {total_in:,}')
    print(f'redaction cohort    : {dropped_redacted:,}  (removed)')
    print(f'deposited records   : {written:,}')
    print(f'columns dropped     : {DROP_COLUMNS}')
    print(f'bib retained        : yes (author decision, 2026-08-25)')
    print(f'\noutput: {DST}')
    print(f'size  : {DST.stat().st_size:,} bytes')

    check = pd.read_csv(DST, nrows=3, dtype=str, keep_default_na=False)
    print(f'\ncolumns ({len(check.columns)}): {list(check.columns)}')
    assert 'name' not in check.columns, 'name column leaked into the deposit'
    assert written == total_in - dropped_redacted, 'row accounting does not balance'
    print('\nassertions passed.')


if __name__ == '__main__':
    main()

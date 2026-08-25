"""R1 — the country field: corrected geographic claims and the redaction cohort.

Two decisions of 2026-08-25 are implemented here.

R1-Int-3. Results §Demographics claims "athletes from 490 countries". That counts
distinct strings in a free-text field holding dropdown placeholders, US state
abbreviations, bare initials and misspellings — not countries. Author decision:
recompute from `country_iso2`, the clean field, and state its coverage.

Redaction cohort. 55 records carry "-Redacted-" in both `country` and `name`,
all from the supplementary source, 2007-2026. That is an explicit upstream
privacy action by the source platform. Author decision: remove them from the
deposited file and report it. This script quantifies the cohort and the
resulting deposited N.

Also recomputes the leading-country figures, which the manuscript lists out of
rank order (Australia before the United Kingdom despite 5.7% against 6.8%).

Run:  uv run --no-project --with pandas python notebooks/r1_country_field.py
"""

from pathlib import Path

import pandas as pd

import _common as C

DATA = C.DATA_FALLBACK
OUT = Path(__file__).parent / 'results'
OUT.mkdir(exist_ok=True)

REDACTION = '-Redacted-'


def main() -> None:
    n = 0
    iso = {}
    name_counts = {}
    redacted = 0
    redacted_rows = []

    for c in pd.read_csv(DATA, chunksize=250_000,
                         usecols=['country', 'country_iso2', 'name', 'source',
                                  'race_year', 'race_type'], low_memory=False):
        n += len(c)
        c['country'] = c.country.fillna('').astype(str).str.strip()
        c['country_iso2'] = c.country_iso2.fillna('').astype(str).str.strip()

        for k, v in c.country_iso2[c.country_iso2 != ''].value_counts().items():
            iso[k] = iso.get(k, 0) + int(v)
        for k, v in c.country[c.country != ''].value_counts().items():
            name_counts[k] = name_counts.get(k, 0) + int(v)

        r = c[(c.country == REDACTION) | (c.name.fillna('').astype(str).str.strip() == REDACTION)]
        redacted += len(r)
        if len(r):
            redacted_rows.append(r[['source', 'race_year', 'race_type']])

    print(f'N = {n:,}\n')

    print('=== geographic claim (R1-Int-3) ===')
    iso_cov = sum(iso.values()) / n * 100
    print(f'distinct country_iso2 codes : {len(iso)}   (ISO 3166-1 defines 249)')
    print(f'country_iso2 coverage       : {iso_cov:.2f}% of records')
    print(f'distinct free-text country  : {len(name_counts)}   '
          f'(manuscript claims 490 — counts junk strings)')

    print('\nleading countries by ISO code:')
    top_iso = sorted(iso.items(), key=lambda kv: -kv[1])[:6]
    for code, cnt in top_iso:
        print(f'  {code:4s} {cnt:>9,}  {cnt / n * 100:5.2f}% of all records  '
              f'({cnt / sum(iso.values()) * 100:5.2f}% of coded records)')

    print('\nleading countries by free-text name (what the manuscript reports):')
    for nm, cnt in sorted(name_counts.items(), key=lambda kv: -kv[1])[:5]:
        print(f'  {nm:20s} {cnt:>9,}  {cnt / n * 100:5.2f}%')

    print('\n=== redaction cohort ===')
    rr = pd.concat(redacted_rows) if redacted_rows else pd.DataFrame()
    print(f'records carrying "{REDACTION}" in country or name: {redacted:,} '
          f'({redacted / n * 100:.5f}%)')
    if len(rr):
        print(f'  sources : {rr.source.value_counts().to_dict()}')
        print(f'  years   : {int(rr.race_year.min())}-{int(rr.race_year.max())}')
        print(f'  distance: {rr.race_type.value_counts().to_dict()}')

    print('\n=== consequence for the deposit ===')
    print(f'described dataset N : {n:,}')
    print(f'deposited N after removing the redaction cohort: {n - redacted:,}')
    print('Both N must appear in the manuscript; they are no longer the same file.')

    C.write_result(pd.DataFrame([{'described_n': n, 'redaction_cohort': redacted,
                                  'deposited_n': n - redacted,
                                  'distinct_iso': len(iso),
                                  'iso_coverage_pct': round(iso_cov, 2),
                                  'distinct_freetext_country': len(name_counts),
                                  'manuscript_claim': 490}]),
                   'r1_country_field_summary.csv')
    C.write_result(pd.DataFrame(top_iso, columns=['iso2', 'records']),
                   'r1_leading_countries.csv')
    print(f'\nwritten to {OUT}')


if __name__ == '__main__':
    main()

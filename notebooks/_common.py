"""Shared constants and loading for the IRONMAN® dataset paper.

Introduced during R1. The project had no `_common.py`, so the legacy figure
notebook carried its own copy of every constant — which is how the palette,
the labels and the data path drifted out of any single source of truth.

Colours and labels live here. Scripts import them; nothing hardcodes a
matplotlib default.
"""

import platform
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# Every path resolves relative to this file, so the scripts run from a clone rather
# than only on the machine they were written on. Audit finding A1-01: twelve of
# thirteen scripts hardcoded an absolute path into the author's working tree, in a paper whose
# contribution is a reproducible pipeline.
PAPER_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = PAPER_DIR.parents[1] / '_data_raw'

DATA_PATH = PAPER_DIR / 'data' / 'collection' / 'ironman_merged.csv'
DATA_FALLBACK = RAW_DIR / 'ironman_merged.csv'

OFFICIAL_CSV = RAW_DIR / 'ironman_official' / 'ironman_official_all.csv'
COACHCOX_CSV = RAW_DIR / '_legacy' / 'coachcox' / 'coachcox_all_results.csv'
CC_META_CSV = RAW_DIR / '_legacy' / 'coachcox' / 'race_metadata.csv'
MERGE_SCRIPT = RAW_DIR / 'merge_sources.py'
DEPOSIT_CSV = RAW_DIR / 'ironman_dataset_deidentified.csv'

FIG_DIR = PAPER_DIR / 'figures'
RESULTS_DIR = Path(__file__).resolve().parent / 'results'

LABEL_IM = 'IRONMAN®'
LABEL_HIM = 'IRONMAN® 70.3'
LABEL_OFFICIAL = 'Official'
LABEL_SUPPLEMENTARY = 'CoachCox'

COLOR_IM = '#1A3C8A'
COLOR_HIM = '#E8820C'
COLOR_OFFICIAL = '#1A3C8A'
COLOR_SUPPLEMENTARY = '#E8820C'
COLOR_T1 = '#1A3C8A'
COLOR_T2 = '#E8820C'
COLOR_COVID = '#D32F2F'

SPLIT_COLS = ['swim_sec', 't1_sec', 'bike_sec', 't2_sec', 'run_sec', 'overall_sec']

# Source and race-type codes as they appear in the data, with their display names.
# R1-Int-1 came from assigning display labels positionally to a groupby result whose
# order was set by category order, not alphabet. Always map by key, never by position.
SOURCE_LABELS = {'official': LABEL_OFFICIAL, 'coachcox': LABEL_SUPPLEMENTARY}
RACE_TYPE_LABELS = {'im': LABEL_IM, 'him': LABEL_HIM}

# Data were collected on 27-28 March 2026, so the final season is incomplete.
PARTIAL_SEASON = 2026
COVID_SPAN = (2019.5, 2021.5)
COVID_LABEL = 'COVID-19 pandemic period'


def provenance(source_path: Path | None = None) -> list[str]:
    """Comment lines identifying how and against what an output was produced.

    Audit A1-05. This round's central defect was artefacts generated from a stale
    data state and never regenerated (`R1-Int-1`, `R1-Int-2`). A result file that
    cannot say when it was written, from which input, at what size, is the exact
    thing that let that happen unnoticed.

    Environment is recorded because the analyses run on the server (15 GiB) rather
    than the container (2 GiB cap, audit A1-11), and the two carry different pandas
    versions. A result that differs between them should be visible, not silent.
    """
    src = source_path or (DATA_PATH if DATA_PATH.exists() else DATA_FALLBACK)
    stat = src.stat() if src.exists() else None
    return [
        f'# generated: {datetime.now(timezone.utc).isoformat(timespec="seconds")}',
        f'# host: {platform.node()}  python: {platform.python_version()}  '
        f'pandas: {pd.__version__}',
        f'# source: {src.name}'
        + (f'  bytes: {stat.st_size}  mtime: '
           f'{datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(timespec="seconds")}'
           if stat else '  (missing)'),
        '# deterministic: no sampling, no randomness, no seed required',
    ]


def write_result(df: pd.DataFrame, name: str, source_path: Path | None = None,
                 index: bool = False) -> Path:
    """Write a result CSV with a provenance header.

    The header lines are `#`-prefixed, so `pd.read_csv(path, comment='#')` reads
    the file unchanged.
    """
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / name
    with open(path, 'w', newline='') as f:
        f.write('\n'.join(provenance(source_path)) + '\n')
        df.to_csv(f, index=index)
    return path


def relabel(obj, mapping, axis=0):
    """Rename index or column labels by key, asserting every key was present.

    The assertion is the point. A silent rename that matches nothing leaves the
    original codes in place and looks fine; a positional assignment silently
    mislabels. Both failed us. This fails loudly instead.
    """
    labels = obj.columns if axis == 1 else obj.index
    unknown = set(labels) - set(mapping)
    if unknown:
        raise ValueError(f'unmapped labels {sorted(unknown)}; mapping covers {sorted(mapping)}')
    return obj.rename(columns=mapping) if axis == 1 else obj.rename(index=mapping)


# Explicit dtypes. Without them pandas infers object for every string column and
# int64 for every numeric one, and loading 2.7M rows is killed by the OOM killer.
# The legacy figure notebook carried this map; the first rewrite dropped it and
# died at exit 137 before printing a line.
DTYPES = {
    'age_group': 'str', 'country': 'str', 'country_iso2': 'str',
    'event_name': 'str', 'event_id': 'str', 'name': 'str',
    'race_type': 'category', 'finish_status': 'category', 'source': 'category',
    'race_year': 'Int16',
    'swim_sec': 'Int32', 't1_sec': 'Int32', 'bike_sec': 'Int32',
    't2_sec': 'Int32', 'run_sec': 'Int32', 'overall_sec': 'Int32',
    'awa_points': 'Int32', 'bib': 'Int32',
    'rank_overall': 'Int32', 'rank_gender': 'Int32', 'rank_group': 'Int32',
    'swim_rank': 'Int32', 'bike_rank': 'Int32', 'run_rank': 'Int32',
    'swim_distance_km': 'float32', 'bike_distance_km': 'float32',
    'run_distance_km': 'float32', 'total_distance_km': 'float32',
}


def load(usecols=None) -> pd.DataFrame:
    """Load the merged dataset with derived helper columns.

    Coverage flags use `> 0`, not `notna()`: the split fields carry 0 as well as
    NaN for records with no recorded time, and counting nulls alone overstates
    coverage by about ten percentage points.

    `source` and `race_type` are categoricals for memory. Note that groupby on a
    categorical returns *category order*, not alphabetical order — the trap
    behind R1-Int-1. Use `relabel()` for every display mapping; it matches by key
    and raises on anything unmapped.
    """
    path = DATA_PATH if DATA_PATH.exists() else DATA_FALLBACK
    if not path.exists():
        raise FileNotFoundError(
            'ironman_merged.csv not found. Run the collection scripts in '
            'data/collection/ or download from Zenodo.')
    cols = usecols if usecols else None
    dtypes = {k: v for k, v in DTYPES.items() if cols is None or k in cols}
    df = pd.read_csv(path, usecols=cols, dtype=dtypes)
    # fillna(False) is load-bearing. The split columns are nullable Int32, so
    # `t1_sec > 0` yields pandas' nullable boolean with NA wherever the value is
    # missing — and `.mean()` on that dtype SKIPS the NAs, silently changing the
    # denominator from "all records" to "records with a value". CoachCox T1
    # coverage then reads 99.6% instead of 83.3%. Caught by eye in Figure 1(c),
    # not by any assertion.
    if 't1_sec' in df.columns:
        df['has_t1'] = (df.t1_sec > 0).fillna(False).astype(bool)
    if 't2_sec' in df.columns:
        df['has_t2'] = (df.t2_sec > 0).fillna(False).astype(bool)
    if 'age_group' in df.columns:
        ag = df.age_group.fillna('').astype(str).str.upper()
        df['gender'] = 'Unknown'
        df.loc[ag.str.startswith('M'), 'gender'] = 'Male'
        df.loc[ag.str.startswith('F'), 'gender'] = 'Female'
    return df

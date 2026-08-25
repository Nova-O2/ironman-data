"""Combine all race JSONs into a single CSV — streaming, low memory."""
import json
import csv
import os
from pathlib import Path

FIELDS = [
    'aid', 'bi', 'n', 'c', 'g', 'di', 'kd', 'kdr', 'rid', 'rty',
    'st', 'sr', 'sdr', 'sgr',
    't1t', 't1r', 't1dr', 't1gr',
    'bt', 'br', 'bdr', 'bgr',
    't2t', 't2r', 't2dr', 't2gr',
    'rt', 'rr', 'rdr', 'rgr',
    'ot', 'or', 'odr', 'ogr',
    'qt', 'qgr',
    'fs', 'aq'
]

FIELD_NAMES = {
    'aid': 'athlete_id', 'bi': 'bib', 'n': 'name', 'c': 'country',
    'g': 'gender', 'di': 'division', 'kd': 'kona_division', 'kdr': 'kona_div_rank',
    'rid': 'race_id', 'rty': 'race_type',
    'st': 'swim_sec', 'sr': 'swim_rank', 'sdr': 'swim_div_rank', 'sgr': 'swim_gender_rank',
    't1t': 't1_sec', 't1r': 't1_rank', 't1dr': 't1_div_rank', 't1gr': 't1_gender_rank',
    'bt': 'bike_sec', 'br': 'bike_rank', 'bdr': 'bike_div_rank', 'bgr': 'bike_gender_rank',
    't2t': 't2_sec', 't2r': 't2_rank', 't2dr': 't2_div_rank', 't2gr': 't2_gender_rank',
    'rt': 'run_sec', 'rr': 'run_rank', 'rdr': 'run_div_rank', 'rgr': 'run_gender_rank',
    'ot': 'overall_sec', 'or': 'overall_rank', 'odr': 'overall_div_rank', 'ogr': 'overall_gender_rank',
    'qt': 'qualifier_sec', 'qgr': 'qualifier_gender_rank',
    'fs': 'finish_status', 'aq': 'auto_qualifier'
}

results_dir = Path(__file__).parent / 'results'
output_csv = Path(__file__).parent / 'coachcox_all_results.csv'

header = [FIELD_NAMES.get(k, k) for k in FIELDS]
json_files = sorted(
    [f for f in os.listdir(results_dir) if f.endswith('.json')],
    key=lambda x: int(x.replace('race_', '').replace('.json', ''))
)

total_athletes = 0
with open(output_csv, 'w', newline='') as out:
    writer = csv.writer(out)
    writer.writerow(header)

    for i, jf in enumerate(json_files):
        with open(results_dir / jf) as f:
            data = json.load(f)
        for row in data:
            writer.writerow([row.get(k, '') for k in FIELDS])
        total_athletes += len(data)

        if (i + 1) % 100 == 0:
            print(f'  {i+1}/{len(json_files)} files processed...')

print(f'CSV: {output_csv}')
print(f'Races: {len(json_files)}')
print(f'Athletes: {total_athletes:,}')
print(f'Size: {os.path.getsize(output_csv) / (1024*1024):.1f} MB')

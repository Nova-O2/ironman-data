"""
CoachCox Ironman Results Scraper
Downloads race results via the public JSON API.

API endpoint: https://www.coachcox.co.uk/wp-json/imstats/v1.92/race/results/{RACE_ID}  (v1.90 at collection time)
Returns: flat JSON array of athlete objects with swim/T1/bike/T2/run splits in seconds.

Usage:
    python scraper.py                    # Scrape all known races (Kaggle IDs + 2025 scan)
    python scraper.py --ids 2199 2166    # Scrape specific race IDs
    python scraper.py --scan-new         # Only scan for new race IDs above the known maximum
    python scraper.py --refresh          # List the full catalogue; download races missing locally (2026-10-15, v4)
"""

import requests
import json
import csv
import time
import os
import sys
from pathlib import Path

# The namespace version changes over time. v1.90 was current on the collection day
# (27 March 2026, the access date printed in the article); the site moved to v1.92
# afterwards. Check https://www.coachcox.co.uk/wp-json/ for the current one if this
# returns 404 rest_no_route.
BASE_URL = "https://www.coachcox.co.uk/wp-json/imstats/v1.92/race/results"
DELAY = 1.5  # seconds between requests (be respectful)
OUTPUT_DIR = Path(__file__).parent / "results"
COMBINED_CSV = Path(__file__).parent / "coachcox_all_results.csv"
PROGRESS_FILE = Path(__file__).parent / "progress.json"

# All fields from the API
FIELDS = [
    'aid', 'bi', 'n', 'c', 'g', 'di', 'kd', 'kdr', 'rid', 'rty',
    'st', 'sr', 'sdr', 'sgr',       # swim
    't1t', 't1r', 't1dr', 't1gr',   # T1
    'bt', 'br', 'bdr', 'bgr',       # bike
    't2t', 't2r', 't2dr', 't2gr',   # T2
    'rt', 'rr', 'rdr', 'rgr',       # run
    'ot', 'or', 'odr', 'ogr',       # overall
    'qt', 'qgr',                     # qualifier
    'fs', 'aq'                       # finish status, auto-qualifier
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


def load_progress():
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"completed": [], "failed": []}


def save_progress(progress):
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f)


def fetch_race(race_id):
    """Fetch results for a single race. Returns list of athlete dicts or None on failure."""
    url = f"{BASE_URL}/{race_id}"
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                return data
            return []  # empty race
        elif resp.status_code == 404:
            return []  # race doesn't exist
        else:
            print(f"  HTTP {resp.status_code} for race {race_id}")
            return None
    except Exception as e:
        print(f"  Error fetching race {race_id}: {e}")
        return None


def save_race_json(race_id, data):
    """Save individual race JSON for archival."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    with open(OUTPUT_DIR / f"race_{race_id}.json", 'w') as f:
        json.dump(data, f)


def scan_new_race_ids(start_id, end_id):
    """Scan a range of race IDs to find new races (e.g., 2025)."""
    found = []
    print(f"Scanning race IDs {start_id} to {end_id}...")
    for rid in range(start_id, end_id + 1):
        data = fetch_race(rid)
        if data and len(data) > 0:
            found.append(rid)
            print(f"  Found race {rid} ({len(data)} athletes)")
        time.sleep(0.5)  # faster scan, lighter requests
    return found




def list_all_races():
    """List every race CoachCox exposes (series index /all/im and /all/him).

    Added 2026-10-15 (dataset v4). The March 2026 collection seeded race IDs from the
    Kaggle 140.6 race list and scanned only above its maximum ID, so races CoachCox
    lists but Kaggle did not (mostly 70.3, 2006-2022) were never requested. The series
    index is the complete catalogue; returns {race_id: {rid, rn, ry, rd, exc, series,
    ty, rg}}.
    """
    races = {}
    for ty in ("im", "him"):
        url = BASE_URL.replace("/race/results", f"/all/{ty}")
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        for sid, series in resp.json().items():
            entries = series.get("races") or {}
            if isinstance(entries, list):
                entries = {str(r["rid"]): r for r in entries}
            for rid, r in entries.items():
                races[int(rid)] = {**r, "series": series.get("sn", ""),
                                   "ty": series.get("ty", ""), "rg": series.get("rg", "")}
        time.sleep(DELAY)
    return races


def fetch_race_info(race_id):
    """Race metadata (/race/info/{id}) in the race_metadata.csv row format."""
    from datetime import datetime
    url = BASE_URL.replace("/race/results", "/race/info") + f"/{race_id}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    d = resp.json()
    rd = d.get("rd") or ""
    date_str = datetime.fromtimestamp(int(rd)).strftime("%Y-%m-%d") if rd else ""
    return {"race_id": d.get("rid", race_id), "race_name": d.get("rn", ""),
            "race_type": d.get("ty", ""), "region": d.get("rg", ""),
            "race_date": date_str, "race_year": d.get("ry", ""), "unix_timestamp": rd}


def refresh():
    """--refresh: download every listed race whose race_{id}.json is missing.

    Writes all_races_<date>.csv (the full CoachCox catalogue on the day) and appends
    the metadata of the newly downloaded races to race_metadata.csv. Does not touch
    the combined CSV: run combine_coachcox.py afterwards.
    """
    from datetime import datetime
    stamp = f"{datetime.now():%Y-%m-%d}"
    races = list_all_races()
    index_path = Path(__file__).parent / f"all_races_{stamp}.csv"
    with open(index_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["race_id", "race_name", "race_year", "race_type",
                                          "region", "series", "exclusions"])
        w.writeheader()
        for rid in sorted(races):
            r = races[rid]
            w.writerow({"race_id": rid, "race_name": r.get("rn", ""), "race_year": r.get("ry", ""),
                        "race_type": r.get("ty", ""), "region": r.get("rg", ""),
                        "series": r.get("series", ""), "exclusions": r.get("exc", "")})
    missing = [rid for rid in sorted(races) if not (OUTPUT_DIR / f"race_{rid}.json").exists()]
    print(f"Catalogue: {len(races)} races (index -> {index_path.name}); missing locally: {len(missing)}")

    metadata_path = Path(__file__).parent / "race_metadata.csv"
    known_meta = set()
    if metadata_path.exists():
        with open(metadata_path) as f:
            known_meta = {row["race_id"] for row in csv.DictReader(f)}
    progress = load_progress()
    downloaded, empty, failed = [], [], []
    for i, rid in enumerate(missing, 1):
        print(f"[{i}/{len(missing)}] Race {rid} {races[rid].get('rn', '')}...", end=" ", flush=True)
        data = fetch_race(rid)
        if data is None:
            failed.append(rid)
            print("FAILED")
        elif len(data) == 0:
            empty.append(rid)
            print("empty")
        else:
            save_race_json(rid, data)
            downloaded.append(rid)
            print(f"{len(data)} athletes")
            if rid not in progress["completed"]:
                progress["completed"].append(rid)
            if str(rid) not in known_meta:
                try:
                    row = fetch_race_info(rid)
                    with open(metadata_path, "a", newline="") as f:
                        csv.DictWriter(f, fieldnames=list(row.keys())).writerow(row)
                    known_meta.add(str(rid))
                except Exception as e:  # noqa: BLE001
                    print(f"  metadata failed for {rid}: {e}")
            save_progress(progress)
        time.sleep(DELAY)
    progress["failed"] = sorted(set(progress.get("failed", [])) | set(failed))
    save_progress(progress)
    print(f"\nRefresh done: downloaded {len(downloaded)}, empty {len(empty)}, failed {len(failed)}: {failed}")


def scrape_all(race_ids):
    """Scrape all given race IDs, save JSON + combined CSV."""
    progress = load_progress()
    remaining = [rid for rid in race_ids if rid not in progress["completed"]]

    print(f"Total races: {len(race_ids)}")
    print(f"Already completed: {len(progress['completed'])}")
    print(f"Remaining: {len(remaining)}")

    all_athletes = []

    for i, rid in enumerate(remaining):
        print(f"[{i+1}/{len(remaining)}] Race {rid}...", end=" ", flush=True)
        data = fetch_race(rid)

        if data is None:
            progress["failed"].append(rid)
            save_progress(progress)
            print("FAILED")
        elif len(data) == 0:
            progress["completed"].append(rid)
            save_progress(progress)
            print("empty")
        else:
            save_race_json(rid, data)
            all_athletes.extend(data)
            progress["completed"].append(rid)
            save_progress(progress)
            print(f"{len(data)} athletes")

        time.sleep(DELAY)

    return all_athletes


def combine_to_csv(race_ids):
    """Read all saved JSONs and combine into one CSV."""
    all_rows = []
    for rid in race_ids:
        json_path = OUTPUT_DIR / f"race_{rid}.json"
        if json_path.exists():
            with open(json_path) as f:
                data = json.load(f)
                all_rows.extend(data)

    if not all_rows:
        print("No data to combine.")
        return

    # Get all unique keys across all records
    all_keys = set()
    for row in all_rows:
        all_keys.update(row.keys())

    # Use readable column names
    header = [FIELD_NAMES.get(k, k) for k in FIELDS if k in all_keys]
    fields_present = [k for k in FIELDS if k in all_keys]

    with open(COMBINED_CSV, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for row in all_rows:
            writer.writerow([row.get(k, '') for k in fields_present])

    print(f"\nCombined CSV: {COMBINED_CSV}")
    print(f"Total athletes: {len(all_rows):,}")
    print(f"Columns: {len(header)}")


if __name__ == "__main__":
    import csv as csv_mod

    # Load known race IDs from race_metadata.csv (shipped with this repo)
    METADATA_CSV = Path(__file__).parent / "race_metadata.csv"
    known_ids = []
    with open(METADATA_CSV) as f:
        for row in csv_mod.DictReader(f):
            rid = row.get("race_id", "")
            if rid.isdigit():
                known_ids.append(int(rid))
    known_ids = sorted(set(known_ids))
    print(f"Known race IDs from metadata: {len(known_ids)}")

    if '--refresh' in sys.argv:
        refresh()

    elif '--scan-new' in sys.argv:
        # Scan for new race IDs beyond the known maximum
        max_known = max(known_ids)
        new_ids = scan_new_race_ids(max_known + 1, max_known + 500)
        print(f"\nFound {len(new_ids)} new race IDs: {new_ids}")

    elif '--ids' in sys.argv:
        idx = sys.argv.index('--ids')
        ids = [int(x) for x in sys.argv[idx+1:]]
        athletes = scrape_all(ids)
        combine_to_csv(ids)

    elif '--combine' in sys.argv:
        progress = load_progress()
        combine_to_csv(progress["completed"])

    else:
        # Full scrape: known IDs + scan for new
        print("=== Phase 1: Scan for new races ===")
        max_known = max(known_ids)
        new_ids = scan_new_race_ids(max_known + 1, max_known + 400)
        all_ids = sorted(set(known_ids + new_ids))

        print(f"\n=== Phase 2: Scrape {len(all_ids)} races ===")
        scrape_all(all_ids)

        print(f"\n=== Phase 3: Combine to CSV ===")
        progress = load_progress()
        combine_to_csv(progress["completed"])

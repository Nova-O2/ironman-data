"""
Combine all official IRONMAN race JSONs into a single CSV — streaming, low memory.
JSONs already have clean field names (from scrape_all.py extract_athlete).

Usage:
    python combine_csv.py
"""

import json
import csv
import os
import re
from pathlib import Path

RESULTS_DIR = Path(__file__).parent / "results"
SUBEVENTS_FILE = Path(__file__).parent / "all_subevents.csv"
OUTPUT_CSV = Path(__file__).parent / "ironman_official_all.csv"

HEADER = [
    "name", "bib", "country", "country_iso2", "age_group",
    "event_name", "event_id",
    "swim_sec", "t1_sec", "bike_sec", "t2_sec", "run_sec", "overall_sec",
    "finisher", "dnf", "dns", "dq", "finish_status",
    "rank_overall", "rank_gender", "rank_group",
    "swim_rank", "bike_rank", "run_rank",
    "awa_points",
    "swim_distance_km", "bike_distance_km", "run_distance_km", "total_distance_km",
    "race_type", "race_year", "parent_slug",
]

# Fields that map directly from JSON (already clean)
DIRECT_FIELDS = [
    ("athlete", "name"),
    ("bib", "bib"),
    ("country", "country"),
    ("country_iso2", "country_iso2"),
    ("age_group", "age_group"),
    ("event_name", "event_name"),
    ("event_id", "event_id"),
    ("swim_sec", "swim_sec"),
    ("t1_sec", "t1_sec"),
    ("bike_sec", "bike_sec"),
    ("t2_sec", "t2_sec"),
    ("run_sec", "run_sec"),
    ("finish_sec", "overall_sec"),
    ("finisher", "finisher"),
    ("dnf", "dnf"),
    ("dns", "dns"),
    ("dq", "dq"),
    ("rank_overall", "rank_overall"),
    ("rank_gender", "rank_gender"),
    ("rank_group", "rank_group"),
    ("swim_rank_overall", "swim_rank"),
    ("bike_rank_overall", "bike_rank"),
    ("run_rank_overall", "run_rank"),
    ("points", "awa_points"),
    ("swim_distance_km", "swim_distance_km"),
    ("bike_distance_km", "bike_distance_km"),
    ("run_distance_km", "run_distance_km"),
    ("total_distance_km", "total_distance_km"),
]


def derive_finish_status(r):
    if r.get("dq"):
        return "DQ"
    if r.get("dns"):
        return "DNS"
    if r.get("dnf"):
        return "DNF"
    if r.get("finisher"):
        return "FIN"
    # Infer from splits
    if r.get("finish_sec") or r.get("swim_sec"):
        return "FIN"
    return ""


def derive_race_type(event_name):
    if "70.3" in str(event_name):
        return "him"
    return "im"


def extract_year(filename):
    match = re.search(r"_(\d{4})", filename)
    return match.group(1) if match else ""


def main():
    json_files = sorted(
        [f for f in os.listdir(RESULTS_DIR) if f.endswith(".json")],
    )

    # Build subevent metadata lookup
    meta_lookup = {}
    if SUBEVENTS_FILE.exists():
        with open(SUBEVENTS_FILE) as f:
            reader = csv.DictReader(f)
            for row in reader:
                meta_lookup[row["subevent_id"]] = row

    total = 0
    with open(OUTPUT_CSV, "w", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=HEADER)
        writer.writeheader()

        for i, jf in enumerate(json_files):
            filepath = RESULTS_DIR / jf
            try:
                with open(filepath) as f:
                    data = json.load(f)
            except Exception as e:
                print(f"  SKIP {jf}: {e}")
                continue

            if not data:
                continue

            year = extract_year(jf)
            # Derive parent slug from filename
            parent_slug = re.sub(r"_\d{4}\.json$", "", jf)

            for r in data:
                row = {}
                for json_key, csv_key in DIRECT_FIELDS:
                    val = r.get(json_key, "")
                    if val is None:
                        val = ""
                    row[csv_key] = val

                # Derived fields
                row["finish_status"] = derive_finish_status(r)
                event_name = r.get("event_name", "")
                row["race_type"] = derive_race_type(event_name)
                row["race_year"] = year
                row["parent_slug"] = parent_slug

                writer.writerow(row)
                total += 1

            if (i + 1) % 100 == 0:
                print(f"  {i+1}/{len(json_files)} files processed...")

    size_mb = os.path.getsize(OUTPUT_CSV) / (1024 * 1024)
    print(f"\nCSV: {OUTPUT_CSV}")
    print(f"Files: {len(json_files)}")
    print(f"Athletes: {total:,}")
    print(f"Size: {size_mb:.1f} MB")


if __name__ == "__main__":
    main()

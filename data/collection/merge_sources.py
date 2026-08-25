"""
Merge Official IRONMAN + CoachCox supplement into unified dataset.

Strategy:
- Official is primary (source="official")
- CoachCox fills IM gaps not in official (source="coachcox")
- Overlap detection by normalized race name + year
- Reversible: regenerate official-only CSV anytime via combine_csv.py

Usage:
    python merge_sources.py              # Merge and save
    python merge_sources.py --dry-run    # Show what would be merged, no output
"""

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

OFFICIAL_CSV = Path(__file__).parent / "ironman_official_all.csv"
COACHCOX_CSV = Path(__file__).parent / "coachcox_all_results.csv"
COACHCOX_META = Path(__file__).parent / "race_metadata.csv"
OUTPUT_CSV = Path(__file__).parent / "ironman_merged.csv"

UNIFIED_HEADER = [
    "name", "bib", "country", "country_iso2", "age_group",
    "event_name", "event_id",
    "swim_sec", "t1_sec", "bike_sec", "t2_sec", "run_sec", "overall_sec",
    "finish_status",
    "rank_overall", "rank_gender", "rank_group",
    "swim_rank", "bike_rank", "run_rank",
    "awa_points",
    "swim_distance_km", "bike_distance_km", "run_distance_km", "total_distance_km",
    "race_type", "race_year", "source",
]


def normalize_race_name(name):
    """Normalize race name for matching."""
    n = name.lower()
    n = re.sub(r"\d{4}", "", n)
    n = re.sub(r"ironman\s*", "", n)
    n = re.sub(r"70\.3\s*", "", n)
    n = re.sub(r":\s*triathlon", "", n)
    n = re.sub(r"\s+", " ", n).strip()
    for prefix in [
        "african championship ", "european championship ",
        "north american championship ", "south american championship ",
        "asia-pacific championship ",
    ]:
        n = n.replace(prefix, "")
    return n.strip()


def load_coachcox_meta():
    """Load CoachCox race metadata."""
    meta = {}
    with open(COACHCOX_META) as f:
        for row in csv.DictReader(f):
            meta[row["race_id"]] = row
    return meta


def build_official_index():
    """Build set of (normalized_name, year, type) from official data."""
    index = set()
    with open(OFFICIAL_CSV) as f:
        for row in csv.DictReader(f):
            name = row.get("event_name", "")
            year = row.get("race_year", "")
            rtype = row.get("race_type", "")
            if name and year:
                key = (normalize_race_name(name), year, rtype)
                index.add(key)
    return index


def cc_finish_status(row):
    """Map CoachCox finish_status to unified format."""
    fs = row.get("finish_status", "")
    if fs in ("FIN", "Finisher"):
        return "FIN"
    if fs == "DNF":
        return "DNF"
    if fs == "DNS":
        return "DNS"
    if fs == "DQ":
        return "DQ"
    if fs == "NC":
        return "DNF"  # NC → DNF
    return fs


def map_coachcox_row(row, meta):
    """Map a CoachCox row to unified schema."""
    return {
        "name": row.get("name", ""),
        "bib": row.get("bib", ""),
        "country": row.get("country", ""),
        "country_iso2": "",
        "age_group": row.get("division", ""),
        "event_name": meta.get("race_name", ""),
        "event_id": row.get("race_id", ""),
        "swim_sec": row.get("swim_sec", ""),
        "t1_sec": row.get("t1_sec", ""),
        "bike_sec": row.get("bike_sec", ""),
        "t2_sec": row.get("t2_sec", ""),
        "run_sec": row.get("run_sec", ""),
        "overall_sec": row.get("overall_sec", ""),
        "finish_status": cc_finish_status(row),
        "rank_overall": row.get("overall_rank", ""),
        "rank_gender": row.get("overall_gender_rank", ""),
        "rank_group": row.get("overall_div_rank", ""),
        "swim_rank": row.get("swim_rank", ""),
        "bike_rank": row.get("bike_rank", ""),
        "run_rank": row.get("run_rank", ""),
        "awa_points": "",
        "swim_distance_km": "",
        "bike_distance_km": "",
        "run_distance_km": "",
        "total_distance_km": "",
        "race_type": row.get("race_type", ""),
        "race_year": meta.get("race_year", ""),
        "source": "coachcox",
    }


def map_official_row(row):
    """Map an official row to unified schema (mostly pass-through)."""
    return {
        "name": row.get("name", ""),
        "bib": row.get("bib", ""),
        "country": row.get("country", ""),
        "country_iso2": row.get("country_iso2", ""),
        "age_group": row.get("age_group", ""),
        "event_name": row.get("event_name", ""),
        "event_id": row.get("event_id", ""),
        "swim_sec": row.get("swim_sec", ""),
        "t1_sec": row.get("t1_sec", ""),
        "bike_sec": row.get("bike_sec", ""),
        "t2_sec": row.get("t2_sec", ""),
        "run_sec": row.get("run_sec", ""),
        "overall_sec": row.get("overall_sec", ""),
        "finish_status": row.get("finish_status", ""),
        "rank_overall": row.get("rank_overall", ""),
        "rank_gender": row.get("rank_gender", ""),
        "rank_group": row.get("rank_group", ""),
        "swim_rank": row.get("swim_rank", ""),
        "bike_rank": row.get("bike_rank", ""),
        "run_rank": row.get("run_rank", ""),
        "awa_points": row.get("awa_points", ""),
        "swim_distance_km": row.get("swim_distance_km", ""),
        "bike_distance_km": row.get("bike_distance_km", ""),
        "run_distance_km": row.get("run_distance_km", ""),
        "total_distance_km": row.get("total_distance_km", ""),
        "race_type": row.get("race_type", ""),
        "race_year": row.get("race_year", ""),
        "source": "official",
    }


def main():
    dry_run = "--dry-run" in sys.argv

    print("Building official race index...")
    official_index = build_official_index()
    print(f"  Official races (normalized): {len(official_index)}")

    print("Loading CoachCox metadata...")
    cc_meta = load_coachcox_meta()

    # Identify CoachCox-only races
    print("Scanning CoachCox for supplement races...")
    cc_supplement_rids = set()
    cc_race_counts = defaultdict(int)

    with open(COACHCOX_CSV) as f:
        for row in csv.DictReader(f):
            rid = row.get("race_id", "")
            meta = cc_meta.get(rid, {})
            name = meta.get("race_name", "")
            year = meta.get("race_year", "")
            rtype = row.get("race_type", "")

            if not name or not year:
                continue

            key = (normalize_race_name(name), year, rtype)
            if key not in official_index:
                cc_supplement_rids.add(rid)
                cc_race_counts[rid] += 1

    supplement_athletes = sum(cc_race_counts.values())
    print(f"  CoachCox-only races: {len(cc_supplement_rids)}")
    print(f"  CoachCox-only athletes: {supplement_athletes:,}")

    if dry_run:
        print("\n=== DRY RUN — Supplement races ===")
        for rid in sorted(cc_supplement_rids, key=lambda x: -cc_race_counts[x]):
            meta = cc_meta.get(rid, {})
            print(f"  {meta.get('race_name','?'):50} {cc_race_counts[rid]:>6,} athletes")
        print(f"\nMerged total would be: ~{2041743 + supplement_athletes:,}")
        return

    # Write merged CSV
    print(f"\nWriting merged CSV...")
    total_official = 0
    total_cc = 0

    with open(OUTPUT_CSV, "w", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=UNIFIED_HEADER)
        writer.writeheader()

        # Pass 1: All official records
        print("  Pass 1: Official records...")
        with open(OFFICIAL_CSV) as f:
            for row in csv.DictReader(f):
                writer.writerow(map_official_row(row))
                total_official += 1

        # Pass 2: CoachCox supplement
        print("  Pass 2: CoachCox supplement...")
        with open(COACHCOX_CSV) as f:
            for row in csv.DictReader(f):
                rid = row.get("race_id", "")
                if rid in cc_supplement_rids:
                    meta = cc_meta.get(rid, {})
                    writer.writerow(map_coachcox_row(row, meta))
                    total_cc += 1

    import os
    size_mb = os.path.getsize(OUTPUT_CSV) / (1024 * 1024)
    total = total_official + total_cc

    print(f"\n{'='*50}")
    print(f"MERGE COMPLETE")
    print(f"{'='*50}")
    print(f"Official:  {total_official:>10,} ({total_official/total*100:.1f}%)")
    print(f"CoachCox:  {total_cc:>10,} ({total_cc/total*100:.1f}%)")
    print(f"Total:     {total:>10,}")
    print(f"CSV:       {OUTPUT_CSV}")
    print(f"Size:      {size_mb:.1f} MB")


if __name__ == "__main__":
    main()

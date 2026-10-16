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
EXCLUDED_CSV = Path(__file__).parent / "supplement_excluded.csv"  # races dropped by the merge, with the reason

# Supplementary race IDs excluded from the merge (added 2026-10-15, v4.0.0). The
# aggregator's catalogue lists IRONMAN 70.3 Japan 2012-2019 under two series,
# "Ironman 70.3 Centrair Chita Peninsula Japan" (race dates present) and "Ironman
# 70.3 Japan", with the same athletes: identical bib numbers and split times, names
# formatted differently. Keeping both double-counted 11,875 records (found by
# notebooks/v4_conformance_audit.py). The copy without dates is excluded. The merge
# prints every race-year with more than one supplementary race ID so a new case
# cannot pass unnoticed in a later refresh.
SUPPLEMENTARY_EXCLUDED_RACE_IDS = {
    "2005": "Ironman 70.3 Japan 2012: duplicate listing of race 1232",
    "2006": "Ironman 70.3 Japan 2013: duplicate listing of race 1284",
    "2007": "Ironman 70.3 Japan 2014: duplicate listing of race 940",
    "2008": "Ironman 70.3 Japan 2015: duplicate listing of race 941",
    "2009": "Ironman 70.3 Japan 2016: duplicate listing of race 942",
    "2010": "Ironman 70.3 Japan 2017: duplicate listing of race 943",
    "2011": "Ironman 70.3 Japan 2018: duplicate listing of race 944",
    "2012": "Ironman 70.3 Japan 2019: duplicate listing of race 581",
}

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


def official_athletes_by_year_type():
    """(race_year, race_type) -> set of (bib, overall_sec) from the official records.

    Used by the athlete-overlap check below. Only records with a bib and a positive
    overall time are comparable; DNS/DNF without a finish time are left out.
    """
    out = defaultdict(set)
    with open(OFFICIAL_CSV) as f:
        for row in csv.DictReader(f):
            o = row.get("overall_sec", "")
            if row.get("bib") and o not in ("", "0"):
                out[(row.get("race_year", ""), row.get("race_type", ""))].add((row["bib"], o))
    return out


# Athlete-overlap exclusion (added 2026-10-15, v4.0.0). The name-based rule above
# misses race-years that the two sources name differently ("Ironman 70.3 Oceanside
# 2019" vs "2019 IRONMAN 70.3 Oceanside California", "Ironman Sweden" vs "IRONMAN
# Kalmar-Sweden", "Ironman Frankfurt" vs "IRONMAN European Championship Frankfurt"),
# so those race-years were taken from both sources. Found by the v4 conformance
# audit; version 3.0.0 carried the same defect (see the data README). A candidate
# supplementary race is now also compared athlete by athlete with the official
# records of the same year and race type: if at least OVERLAP_SHARE of its
# comparable records (bib + overall time) already exist there, the race is the
# same race and is dropped. The measured shares are bimodal (>= 0.99 for the same
# race, <= 0.13 otherwise), so the threshold is not sensitive.
OVERLAP_SHARE = 0.5
OVERLAP_MIN_RECORDS = 50


def load_coachcox_meta():
    """Load CoachCox race metadata."""
    meta = {}
    with open(COACHCOX_META) as f:
        for row in csv.DictReader(f):
            meta[row["race_id"]] = row
    return meta


N_OFFICIAL = 0  # rows in OFFICIAL_CSV, counted by build_official_index (2026-10-15)


def build_official_index():
    """Build set of (normalized_name, year, type) from official data; counts rows."""
    global N_OFFICIAL
    index = set()
    with open(OFFICIAL_CSV) as f:
        for row in csv.DictReader(f):
            name = row.get("event_name", "")
            year = row.get("race_year", "")
            rtype = row.get("race_type", "")
            N_OFFICIAL += 1
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
            if rid in SUPPLEMENTARY_EXCLUDED_RACE_IDS:
                continue
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

    # Athlete-overlap pass over the name-based candidates
    print("Checking candidate supplement races against official athletes (bib + overall time)...")
    official_athletes = official_athletes_by_year_type()
    cc_pairs = defaultdict(list)
    with open(COACHCOX_CSV) as f:
        for row in csv.DictReader(f):
            rid = row.get("race_id", "")
            if rid in cc_supplement_rids:
                o = row.get("overall_sec", "")
                if row.get("bib") and o not in ("", "0"):
                    cc_pairs[rid].append((row["bib"], o))
    overlap_excluded = {}
    for rid in sorted(cc_supplement_rids):
        pairs = cc_pairs.get(rid, [])
        if len(pairs) < OVERLAP_MIN_RECORDS:
            continue
        meta = cc_meta.get(rid, {})
        ref = official_athletes.get((meta.get("race_year", ""), meta.get("race_type", "")), set())
        share = sum(p in ref for p in pairs) / len(pairs)
        if share >= OVERLAP_SHARE:
            overlap_excluded[rid] = (share, cc_race_counts[rid], meta.get("race_name", "?"))
    for rid in overlap_excluded:
        cc_supplement_rids.discard(rid)
        del cc_race_counts[rid]
    print(f"  Dropped as the same race as an official race-year (athlete overlap >= {OVERLAP_SHARE:.0%}): "
          f"{len(overlap_excluded)} races, {sum(v[1] for v in overlap_excluded.values()):,} records")
    for rid, (share, n, name) in sorted(overlap_excluded.items(), key=lambda kv: kv[1][2]):
        print(f"    {name:50} share {share:.2f}  {n:>6,} records (race id {rid})")
    print(f"  CoachCox-only races after the overlap check: {len(cc_supplement_rids)}")
    with open(EXCLUDED_CSV, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["race_id", "race_name", "race_year", "race_type", "records", "overlap_share", "reason"])
        for rid, (share, n, name) in sorted(overlap_excluded.items(), key=lambda kv: kv[1][2]):
            m = cc_meta.get(rid, {})
            w.writerow([rid, name, m.get("race_year", ""), m.get("race_type", ""), n, f"{share:.4f}",
                        "same race as an official race-year (athlete overlap)"])
        for rid, reason in SUPPLEMENTARY_EXCLUDED_RACE_IDS.items():
            m = cc_meta.get(rid, {})
            w.writerow([rid, m.get("race_name", ""), m.get("race_year", ""), m.get("race_type", ""), "", "", reason])
    print(f"  Excluded races written to {EXCLUDED_CSV.name}")

    supplement_athletes = sum(cc_race_counts.values())
    # Race-years with more than one supplementary race ID (same name, year, type).
    # Legitimate when the IDs are different races or days (World Championship
    # men's and women's days; Arizona April and November 2008); a duplicate listing
    # when the records coincide. Printed so a refresh cannot double-count silently.
    by_key = defaultdict(set)
    for rid in cc_supplement_rids:
        m = cc_meta[rid]
        by_key[(normalize_race_name(m["race_name"]), m["race_year"], m["race_type"])].add(rid)
    multi = {k: v for k, v in by_key.items() if len(v) > 1}
    print(f"  Excluded supplementary race IDs: {len(SUPPLEMENTARY_EXCLUDED_RACE_IDS)}")
    print(f"  Race-years with >1 supplementary race ID: {len(multi)} (check each for a duplicate listing)")
    for k, v in sorted(multi.items()):
        print(f"    {k[0]} {k[1]} ({k[2]}): {sorted(v)}")
    print(f"  CoachCox-only races: {len(cc_supplement_rids)}")
    print(f"  CoachCox-only athletes: {supplement_athletes:,}")

    if dry_run:
        print("\n=== DRY RUN — Supplement races ===")
        for rid in sorted(cc_supplement_rids, key=lambda x: -cc_race_counts[x]):
            meta = cc_meta.get(rid, {})
            print(f"  {meta.get('race_name','?'):50} {cc_race_counts[rid]:>6,} athletes")
        print(f"\nMerged total would be: {N_OFFICIAL + supplement_athletes:,} (official {N_OFFICIAL:,} + supplement)")
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

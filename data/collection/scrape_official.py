"""
Ironman Official Results — Full Scraper
Downloads ALL race results from competitor.com API using discovered event UUIDs.

Usage:
    python scrape_all.py                    # Scrape all events
    python scrape_all.py --list-subevents   # Just list subevents (dry run)
"""

import requests
import json
import csv
import re
import time
import sys
from pathlib import Path
from datetime import datetime

BASE_URL = "https://labs-v2.competitor.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
DELAY_EVENT = 1.5
DELAY_API = 2.0

SCRIPT_DIR = Path(__file__).parent
UUID_FILE = SCRIPT_DIR / "event_uuids_full.csv"
OUTPUT_DIR = SCRIPT_DIR / "results"
PROGRESS_FILE = SCRIPT_DIR / "scrape_progress.json"
SUBEVENTS_FILE = SCRIPT_DIR / "all_subevents.csv"


def load_progress():
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"completed": [], "failed": []}


def save_progress(progress):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f)


def load_uuids():
    events = []
    with open(UUID_FILE) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(",")
            if len(parts) >= 2:
                events.append({"slug": parts[0], "uuid": parts[1]})
    return events


def fetch_subevents(uuid):
    """Fetch the event page and extract subevents (years)."""
    url = f"{BASE_URL}/results/event/{uuid}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        resp.text,
    )
    if not match:
        return []

    data = json.loads(match.group(1))
    return data.get("props", {}).get("pageProps", {}).get("subevents", [])


def fetch_results(event_id):
    """Fetch full results for a subevent via the API."""
    url = f"{BASE_URL}/api/results"
    params = {"wtc_eventid": event_id}
    resp = requests.get(url, headers=HEADERS, params=params, timeout=120)
    resp.raise_for_status()

    data = resp.json()
    rj = data.get("resultsJson", {})
    if isinstance(rj, dict):
        return rj.get("value", [])
    return []


def extract_athlete(r):
    """Map competitor.com fields to flat dict."""
    return {
        "athlete": r.get("athlete", ""),
        "bib": r.get("bib", ""),
        "country": r.get("_wtc_countryrepresentingid_value_formatted", ""),
        "country_iso2": r.get("countryiso2", ""),
        "age_group": r.get("_wtc_agegroupid_value_formatted", ""),
        "event_name": r.get("_wtc_eventid_value_formatted", ""),
        "event_id": r.get("_wtc_eventid_value", ""),
        "swim_sec": r.get("wtc_swimtime", ""),
        "t1_sec": r.get("wtc_transition1time", ""),
        "bike_sec": r.get("wtc_biketime", ""),
        "t2_sec": r.get("wtc_transition2time", ""),
        "run_sec": r.get("wtc_runtime", ""),
        "finish_sec": r.get("wtc_finishtime", ""),
        "finisher": r.get("wtc_finisher", ""),
        "dnf": r.get("wtc_dnf", ""),
        "dns": r.get("wtc_dns", ""),
        "dq": r.get("wtc_dq", ""),
        "rank_overall": r.get("wtc_finishrankoverall", ""),
        "rank_gender": r.get("wtc_finishrankgender", ""),
        "rank_group": r.get("wtc_finishrankgroup", ""),
        "swim_rank_overall": r.get("wtc_swimrankoverall", ""),
        "bike_rank_overall": r.get("wtc_bikerankoverall", ""),
        "run_rank_overall": r.get("wtc_runrankoverall", ""),
        "points": r.get("wtc_points", ""),
        "swim_distance_km": r.get("wtc_swimdistancecompleted", ""),
        "bike_distance_km": r.get("wtc_bikedistancecompleted", ""),
        "run_distance_km": r.get("wtc_rundistancecompleted", ""),
        "total_distance_km": r.get("wtc_totaldistancecompleted", ""),
    }


def save_json(data, filepath):
    with open(filepath, "w") as f:
        json.dump(data, f)


def main():
    dry_run = "--list-subevents" in sys.argv

    events = load_uuids()
    progress = load_progress()
    OUTPUT_DIR.mkdir(exist_ok=True)

    print(f"Events: {len(events)}")
    print(f"Already completed: {len(progress['completed'])}")

    all_subevents = []
    total_athletes = 0

    for i, event in enumerate(events):
        slug = event["slug"]
        uuid = event["uuid"]

        print(f"\n[{i+1}/{len(events)}] {slug}")

        # Fetch subevents
        try:
            subs = fetch_subevents(uuid)
            print(f"  Subevents: {len(subs)}")
        except Exception as e:
            print(f"  ERROR fetching event page: {e}")
            progress["failed"].append({"slug": slug, "error": str(e)})
            save_progress(progress)
            time.sleep(DELAY_EVENT)
            continue

        for se in subs:
            se_name = se.get("wtc_name", "?")
            se_id = se.get("wtc_eventid", "")
            se_date = se.get("wtc_eventdate_formatted", "")

            # Extract year from name
            year_match = re.search(r"(\d{4})", se_name)
            year = year_match.group(1) if year_match else "unknown"

            all_subevents.append({
                "parent_slug": slug,
                "parent_uuid": uuid,
                "subevent_name": se_name,
                "subevent_id": se_id,
                "subevent_date": se_date,
                "year": year,
            })

            if dry_run:
                print(f"    {se_name} ({se_date})")
                continue

            # Check if already scraped
            safe_name = re.sub(r"[^a-z0-9_-]", "_", slug.lower())
            filename = f"{safe_name}_{year}.json"
            filepath = OUTPUT_DIR / filename

            if se_id in progress["completed"]:
                print(f"    {se_name} — already done")
                continue

            # Fetch results
            print(f"    {se_name}...", end=" ", flush=True)
            try:
                results = fetch_results(se_id)
                athletes = [extract_athlete(r) for r in results]
                save_json(athletes, filepath)
                progress["completed"].append(se_id)
                save_progress(progress)
                total_athletes += len(athletes)
                print(f"{len(athletes)} athletes")
            except Exception as e:
                print(f"ERROR: {e}")
                progress["failed"].append({"subevent": se_name, "id": se_id, "error": str(e)})
                save_progress(progress)

            time.sleep(DELAY_API)

        time.sleep(DELAY_EVENT)

    # Save subevents index
    if all_subevents:
        with open(SUBEVENTS_FILE, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=all_subevents[0].keys())
            writer.writeheader()
            writer.writerows(all_subevents)
        print(f"\nSubevents index: {SUBEVENTS_FILE} ({len(all_subevents)} entries)")

    if not dry_run:
        print(f"\n{'='*50}")
        print(f"Total athletes downloaded: {total_athletes:,}")
        print(f"Subevents completed: {len(progress['completed'])}")
        print(f"Failed: {len(progress['failed'])}")


if __name__ == "__main__":
    main()

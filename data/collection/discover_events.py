"""
Discover IRONMAN event series and their results-platform UUIDs from ironman.com.

Added 2026-10-15 for the dataset refresh (v4). In March 2026 the site answered 403 to
programmatic requests and the 128 UUIDs in event_uuids_full.csv were collected by
hand (collect_uuids.md). The sitemap and the "<slug>-results" pages now answer to a
plain request with a browser User-Agent, so the discovery can be reproduced.

Steps:
  1. Read the sitemap index and every sitemap page; keep /races/<slug> pages whose
     slug starts with "im-" or "im703-" (race series); results page = /races/<slug>/results.
  2. Fetch each results page and extract the first
     "competitor.com/results/event/<uuid>" link (the results iframe).
  3. Write event_uuids_discovered_<date>.csv (slug, uuid, url, status) and print the
     series whose UUID is not in event_uuids_full.csv (new) and the known series
     that were not found (gone / renamed).

Usage:
    python discover_events.py            # full discovery (~1 request/s)
    python discover_events.py --dry-run  # list candidate URLs only
"""

import csv
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

SITEMAP = "https://www.ironman.com/sitemap.xml"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
DELAY = 1.0
SCRIPT_DIR = Path(__file__).parent
KNOWN_FILE = SCRIPT_DIR / "event_uuids_full.csv"
OUT_FILE = SCRIPT_DIR / f"event_uuids_discovered_{datetime.now():%Y-%m-%d}.csv"
UUID_RE = re.compile(r"competitor\.com/results/event/([a-f0-9-]{36})")
LOC_RE = re.compile(r"<loc>(.*?)</loc>")
RACE_RE = re.compile(r"^https://www\.ironman\.com/races/([^/?#]+)/?$")
SERIES_RE = re.compile(r"^im(703)?-")


def get(url: str, timeout: int = 30) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def sitemap_urls() -> list[str]:
    index = get(SITEMAP)
    pages = [u for u in LOC_RE.findall(index) if "sitemap.xml" in u]
    urls: list[str] = []
    for p in pages:
        urls.extend(LOC_RE.findall(get(p)))
        time.sleep(DELAY)
    return urls


def load_known() -> dict[str, str]:
    known = {}
    with open(KNOWN_FILE) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(",")
            if len(parts) >= 2:
                known[parts[1]] = parts[0]
    return known


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    # Race pages live at /races/<slug> (sub-pages /races/<slug>/results, /course, ...).
    # Candidate series = top-level race slugs; the results page is /races/<slug>/results.
    # Only "im-" and "im703-" slugs are race series (the rest are programmes/pages).
    slugs = sorted({m.group(1) for u in sitemap_urls()
                    if (m := RACE_RE.match(u)) and SERIES_RE.match(m.group(1))})
    urls = [f"https://www.ironman.com/races/{s}/results" for s in slugs]
    print(f"Candidate race series in sitemap: {len(urls)}")
    if dry_run:
        print("\n".join(urls))
        return

    known = load_known()
    rows = []
    for i, url in enumerate(urls, 1):
        slug = url.rstrip("/").removesuffix("/results").rsplit("/", 1)[-1]
        try:
            html = get(url)
            m = UUID_RE.search(html)
            uuid = m.group(1) if m else ""
            status = "ok" if uuid else "no_uuid"
        except Exception as e:  # noqa: BLE001 — keep going, record the failure
            uuid, status = "", f"error: {e}"
        rows.append({"slug": slug, "uuid": uuid, "url": url, "status": status,
                     "known_slug": known.get(uuid, "")})
        tag = "known" if uuid in known else ("NEW" if uuid else status)
        print(f"[{i}/{len(urls)}] {slug}: {tag}")
        time.sleep(DELAY)

    with open(OUT_FILE, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["slug", "uuid", "url", "status", "known_slug"])
        w.writeheader()
        w.writerows(rows)

    found = {r["uuid"] for r in rows if r["uuid"]}
    new = [r for r in rows if r["uuid"] and r["uuid"] not in known]
    missing = [(u, s) for u, s in known.items() if u not in found]
    print(f"\nSaved {OUT_FILE.name}: {len(rows)} pages, {len(found)} UUIDs")
    print(f"NEW series (uuid not in {KNOWN_FILE.name}): {len(new)}")
    for r in new:
        print(f"  {r['slug']},{r['uuid']}")
    print(f"Known series not found on the site today: {len(missing)}")
    for u, s in missing:
        print(f"  {s},{u}")


if __name__ == "__main__":
    main()

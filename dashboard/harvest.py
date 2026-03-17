import sys
import json
import time
import argparse
import os
from datetime import datetime, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError


SEARCH_QUERIES = [
    "supply chain coordinator",
    "supply chain analyst",
    "supply chain planner",
    "operations analyst",
    "process improvement",
    "business operations",
    "business analyst",
    "junior business analyst",
    "systems analyst",
    "ERP specialist",
    "automation",
]


def scrape_jobspy(queries, country, hours):
    """Scrape Indeed, Glassdoor, and Google Jobs via python-jobspy."""
    try:
        from jobspy import scrape_jobs
    except ImportError:
        print("[jobspy] Not installed. Install with: pip install python-jobspy")
        return []

    jobs = []
    sites = ["indeed", "glassdoor", "google"]
    hours_old = int(hours)

    for query in queries:
        print(f"[jobspy] Searching: {query}")
        try:
            df = scrape_jobs(
                site_name=sites,
                search_term=query,
                location=country,
                country_indeed=country,
                results_wanted=30,
                hours_old=hours_old,
            )
            if df is None or df.empty:
                print(f"[jobspy]   0 results for '{query}'")
                continue

            count = 0
            for _, row in df.iterrows():
                job = {
                    "title": str(row.get("title", "")) if row.get("title") is not None else "",
                    "company": str(row.get("company_name", row.get("company", ""))) if row.get("company_name", row.get("company")) is not None else "",
                    "location": str(row.get("location", "")) if row.get("location") is not None else "",
                    "url": str(row.get("job_url", row.get("link", ""))) if row.get("job_url", row.get("link")) is not None else "",
                    "salary": _extract_salary(row),
                    "date_posted": str(row.get("date_posted", "")) if row.get("date_posted") is not None else "",
                    "description": str(row.get("description", "")) if row.get("description") is not None else "",
                    "source": str(row.get("site", "jobspy")) if row.get("site") is not None else "jobspy",
                }
                if job["url"]:
                    jobs.append(job)
                    count += 1

            print(f"[jobspy]   {count} results for '{query}'")

        except Exception as e:
            print(f"[jobspy]   Error searching '{query}': {e}")
            continue

    print(f"[jobspy] Total: {len(jobs)} jobs")
    return jobs


def _extract_salary(row):
    """Extract salary string from a jobspy row."""
    min_amt = row.get("min_amount", None)
    max_amt = row.get("max_amount", None)
    currency = row.get("currency", "EUR")
    interval = row.get("interval", "yearly")

    if min_amt is not None and max_amt is not None:
        try:
            min_val = int(float(min_amt))
            max_val = int(float(max_amt))
            if min_val > 0 and max_val > 0:
                return f"{currency} {min_val:,}-{max_val:,} {interval}"
        except (ValueError, TypeError):
            pass

    if min_amt is not None:
        try:
            min_val = int(float(min_amt))
            if min_val > 0:
                return f"{currency} {min_val:,}+ {interval}"
        except (ValueError, TypeError):
            pass

    return "not listed"


def fetch_arbeitnow():
    """Fetch jobs from Arbeitnow free API (no key needed)."""
    print("[arbeitnow] Fetching jobs...")
    jobs = []
    page = 1
    max_pages = 5

    while page <= max_pages:
        url = f"https://www.arbeitnow.com/api/job-board-api?page={page}"
        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0 job-harvester/1.0"})
            with urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            listings = data.get("data", [])
            if not listings:
                break

            for item in listings:
                location = item.get("location", "")
                # Only keep Netherlands-related jobs
                loc_lower = location.lower() if location else ""
                if not any(kw in loc_lower for kw in ["netherlands", "amsterdam", "rotterdam", "utrecht", "eindhoven", "den haag", "the hague", "nl", "dutch", "remote"]):
                    continue

                job = {
                    "title": item.get("title", ""),
                    "company": item.get("company_name", ""),
                    "location": location,
                    "url": item.get("url", ""),
                    "salary": "not listed",
                    "date_posted": item.get("created_at", ""),
                    "description": item.get("description", ""),
                    "source": "arbeitnow",
                }
                if job["url"]:
                    jobs.append(job)

            # Check if there are more pages
            if not data.get("links", {}).get("next"):
                break
            page += 1

        except (URLError, HTTPError) as e:
            print(f"[arbeitnow]   HTTP error on page {page}: {e}")
            break
        except Exception as e:
            print(f"[arbeitnow]   Error on page {page}: {e}")
            break

    print(f"[arbeitnow] Total: {len(jobs)} NL-relevant jobs")
    return jobs


def deduplicate(jobs):
    """Remove duplicate jobs by URL."""
    seen = set()
    unique = []
    for job in jobs:
        url = job.get("url", "").strip().rstrip("/")
        if not url or url in seen:
            continue
        seen.add(url)
        unique.append(job)
    return unique


def main():
    parser = argparse.ArgumentParser(description="Bulk harvest job listings from multiple sources")
    parser.add_argument("--output", default="raw_jobs.json", help="Output file path (default: raw_jobs.json)")
    parser.add_argument("--country", default="Netherlands", help="Country to search (default: Netherlands)")
    parser.add_argument("--hours", type=int, default=240, help="Freshness in hours (default: 240 = 10 days)")
    args = parser.parse_args()

    start = time.time()
    all_jobs = []
    sources_ok = 0

    # 1. python-jobspy (Indeed, Glassdoor, Google)
    print("=" * 60)
    print("Phase 1: python-jobspy (Indeed, Glassdoor, Google Jobs)")
    print("=" * 60)
    try:
        jobspy_results = scrape_jobspy(SEARCH_QUERIES, args.country, args.hours)
        all_jobs.extend(jobspy_results)
        if jobspy_results:
            sources_ok += 3  # indeed, glassdoor, google
    except Exception as e:
        print(f"[jobspy] Fatal error: {e}")

    # 2. Arbeitnow free API
    print()
    print("=" * 60)
    print("Phase 2: Arbeitnow API")
    print("=" * 60)
    try:
        arbeitnow_results = fetch_arbeitnow()
        all_jobs.extend(arbeitnow_results)
        if arbeitnow_results:
            sources_ok += 1
    except Exception as e:
        print(f"[arbeitnow] Fatal error: {e}")

    # Deduplicate
    before = len(all_jobs)
    all_jobs = deduplicate(all_jobs)
    dupes = before - len(all_jobs)

    # Write output
    output_path = args.output
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_jobs, f, indent=2, ensure_ascii=False, default=str)

    elapsed = time.time() - start

    print()
    print("=" * 60)
    print(f"Harvested {len(all_jobs)} jobs from {sources_ok} sources in {elapsed:.1f} seconds")
    if dupes > 0:
        print(f"Removed {dupes} duplicates")
    print(f"Output: {os.path.abspath(output_path)}")
    print("=" * 60)


if __name__ == "__main__":
    main()

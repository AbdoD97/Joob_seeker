"""
LinkedIn Job Search for Mohammad Emad — Netherlands market.
Uses LinkedIn's public guest API (no login required).
"""
import requests
import re
import json
import hashlib
import time
from datetime import datetime
from bs4 import BeautifulSoup
from pathlib import Path
from typing import List, Dict

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
DETAIL_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"

# Tailored search queries for Mohammad's profile
SEARCH_QUERIES = [
    {"keywords": "operations coordinator", "location": "Netherlands"},
    {"keywords": "supply chain analyst", "location": "Netherlands"},
    {"keywords": "training coordinator", "location": "Netherlands"},
    {"keywords": "learning development specialist", "location": "Netherlands"},
    {"keywords": "process improvement", "location": "Netherlands"},
    {"keywords": "business analyst operations", "location": "Netherlands"},
    {"keywords": "ERP consultant", "location": "Netherlands"},
    {"keywords": "supply chain coordinator", "location": "Netherlands"},
    {"keywords": "operations analyst", "location": "Netherlands"},
    {"keywords": "L&D coordinator", "location": "Netherlands"},
    {"keywords": "onboarding specialist", "location": "Netherlands"},
    {"keywords": "project coordinator operations", "location": "Netherlands"},
    {"keywords": "continuous improvement", "location": "Netherlands"},
    {"keywords": "logistics coordinator", "location": "Netherlands"},
    {"keywords": "lean specialist", "location": "Netherlands"},
]

RESULTS_PER_QUERY = 25


def job_id(title, company, location):
    raw = f"{title}|{company}|{location}".lower()
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def parse_job_listings(html: str) -> List[Dict]:
    soup = BeautifulSoup(html, "html.parser")
    jobs = []
    for card in soup.find_all("li"):
        try:
            title_el = card.find(class_="base-search-card__title")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)

            link_el = card.find("a", class_="base-card__full-link")
            url = link_el["href"] if link_el else ""
            linkedin_id = ""
            if url:
                m = re.search(r'/view/[^/]*-(\d+)', url)
                if m:
                    linkedin_id = m.group(1)

            company_el = card.find(class_="base-search-card__subtitle")
            company = company_el.get_text(strip=True) if company_el else "Unknown"

            loc_el = card.find(class_="job-search-card__location")
            location = loc_el.get_text(strip=True) if loc_el else "Unknown"

            jobs.append({
                "title": title,
                "company": company,
                "location": location,
                "url": url.strip(),
                "linkedin_id": linkedin_id,
                "id": job_id(title, company, location),
            })
        except Exception as e:
            print(f"  Parse error: {e}")
    return jobs


def scrape_jobs(keywords: str, location: str, max_results: int = 25) -> List[Dict]:
    all_jobs = []
    seen_ids = set()

    for offset in range(0, max_results, 25):
        params = {
            "keywords": keywords,
            "location": location,
            "start": offset,
            "f_TPR": "r604800",  # Past week
        }
        try:
            resp = requests.get(SEARCH_URL, params=params, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                print(f"  HTTP {resp.status_code} at offset {offset}")
                break
            jobs = parse_job_listings(resp.text)
            if not jobs:
                break
            for j in jobs:
                if j["id"] not in seen_ids:
                    seen_ids.add(j["id"])
                    all_jobs.append(j)
            time.sleep(1.5)  # Rate limit
        except Exception as e:
            print(f"  Request error: {e}")
            break

    return all_jobs


def fetch_description(linkedin_id: str) -> str:
    if not linkedin_id:
        return ""
    try:
        url = DETAIL_URL.format(job_id=linkedin_id)
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return ""
        soup = BeautifulSoup(resp.text, "html.parser")
        desc_el = soup.find(class_="show-more-less-html__markup")
        if desc_el:
            return desc_el.get_text(strip=True)[:2000]
    except:
        pass
    return ""


def score_job(job: Dict) -> Dict:
    """Score job based on keyword matching against Mohammad's profile."""
    title = (job.get("title", "") + " " + job.get("description", "")).lower()

    score = 0
    reasons = []

    # Strong title matches
    strong_matches = {
        "operations": 2, "supply chain": 3, "training": 2, "l&d": 3,
        "learning": 2, "development": 1, "coordinator": 2, "analyst": 2,
        "process improvement": 3, "continuous improvement": 3, "lean": 2,
        "erp": 3, "onboarding": 2, "logistics": 2, "procurement": 2,
        "business analyst": 2, "project coordinator": 2,
    }

    for kw, pts in strong_matches.items():
        if kw in title:
            score += pts
            reasons.append(kw)

    # Skills matches
    skills = ["power bi", "excel", "data analysis", "kpi", "stakeholder",
              "process", "workflow", "sap", "inventory", "forecasting",
              "demand planning", "warehouse", "python", "reporting"]
    for s in skills:
        if s in title:
            score += 1
            reasons.append(s)

    # Language bonus
    if "arabic" in title:
        score += 2
        reasons.append("arabic")
    if "english" in title and "dutch" not in title:
        score += 1

    # Penalty for senior/director level (overqualified barrier)
    if any(x in title for x in ["director", "vp ", "vice president", "head of", "c-level", "cto", "cfo"]):
        score -= 3

    # Penalty for heavy tech/dev roles (not matching)
    if any(x in title for x in ["software engineer", "developer", "devops", "full stack", "backend", "frontend"]):
        score -= 4

    # Cap score
    score = max(0, min(10, score))

    job["score"] = score
    job["match_reasons"] = reasons
    return job


def main():
    print(f"{'='*60}")
    print(f"LinkedIn Job Search for Mohammad Emad — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")

    all_jobs = []
    seen_ids = set()

    for q in SEARCH_QUERIES:
        print(f"Searching: '{q['keywords']}' in {q['location']}...")
        jobs = scrape_jobs(q["keywords"], q["location"], RESULTS_PER_QUERY)
        new = 0
        for j in jobs:
            if j["id"] not in seen_ids:
                seen_ids.add(j["id"])
                j["search_query"] = q["keywords"]
                all_jobs.append(j)
                new += 1
        print(f"  Found {len(jobs)} jobs, {new} new (deduped)")
        time.sleep(2)  # Between queries

    print(f"\nTotal unique jobs: {len(all_jobs)}")

    if not all_jobs:
        print("No jobs found!")
        return

    # Fetch descriptions for top jobs (limit to avoid rate limiting)
    print(f"\nFetching descriptions (up to 50 jobs)...")
    for i, job in enumerate(all_jobs[:50]):
        if job.get("linkedin_id"):
            desc = fetch_description(job["linkedin_id"])
            job["description"] = desc
            if (i + 1) % 10 == 0:
                print(f"  {i+1} descriptions fetched...")
            time.sleep(1)

    # Score all jobs
    print("Scoring jobs...")
    for job in all_jobs:
        score_job(job)

    # Sort by score
    all_jobs.sort(key=lambda x: x.get("score", 0), reverse=True)

    # Save full results
    output_dir = Path("D:/win_rev_claude/agents/linkedin-agent/data")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"jobs_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_jobs, f, indent=2, ensure_ascii=False)
    print(f"Full results saved to {output_file}")

    # Print top results
    print(f"\n{'='*60}")
    print(f"TOP MATCHES (score >= 4)")
    print(f"{'='*60}\n")

    top = [j for j in all_jobs if j.get("score", 0) >= 4]
    if not top:
        print("No high-scoring matches found. Showing top 15:")
        top = all_jobs[:15]

    for i, job in enumerate(top[:30], 1):
        print(f"{i}. [{job.get('score', '?')}/10] {job['title']}")
        print(f"   Company: {job['company']}")
        print(f"   Location: {job['location']}")
        print(f"   Matched: {', '.join(job.get('match_reasons', []))}")
        print(f"   URL: {job.get('url', 'N/A')}")
        if job.get("description"):
            print(f"   Desc: {job['description'][:150]}...")
        print()

    # Summary stats
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Total jobs found: {len(all_jobs)}")
    print(f"Score >= 7: {len([j for j in all_jobs if j.get('score', 0) >= 7])}")
    print(f"Score 4-6: {len([j for j in all_jobs if 4 <= j.get('score', 0) <= 6])}")
    print(f"Score < 4: {len([j for j in all_jobs if j.get('score', 0) < 4])}")
    print(f"Results saved to: {output_file}")


if __name__ == "__main__":
    main()

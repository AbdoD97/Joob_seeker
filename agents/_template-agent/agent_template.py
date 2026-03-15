"""
LinkedIn Job Agent — Scrapes, scores, tracks, and alerts on new job postings.
Targets the Netherlands market. Configurable via .env for any career profile.
Uses LinkedIn's public guest API (no login required).
"""

import os
import re
import json
import csv
import time
import hashlib
import logging
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

import anthropic
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# ── Config ──────────────────────────────────────────────────────────────────

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

SEARCH_KEYWORDS = os.getenv("SEARCH_KEYWORDS", "engineer")
SEARCH_LOCATION = os.getenv("SEARCH_LOCATION", "Netherlands")
RESULTS_PER_RUN = int(os.getenv("RESULTS_PER_RUN", "50"))
SCORE_THRESHOLD = int(os.getenv("SCORE_THRESHOLD", "6"))
PREFERRED_SKILLS = [
    s.strip()
    for s in os.getenv("PREFERRED_SKILLS", "").split(",")
    if s.strip()
]
EXCLUDED_COMPANIES = [
    s.strip().lower()
    for s in os.getenv("EXCLUDED_COMPANIES", "").split(",")
    if s.strip()
]

AGENT_DIR = Path(__file__).parent
DATA_DIR = AGENT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

SEEN_FILE = DATA_DIR / "seen_jobs.json"
CSV_FILE = DATA_DIR / "jobs.csv"
LOG_FILE = AGENT_DIR / "agent.log"

# ── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("linkedin-agent")

# ── Seen Jobs Tracker ───────────────────────────────────────────────────────


def load_seen() -> dict:
    if SEEN_FILE.exists():
        try:
            return json.loads(SEEN_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log.warning("Corrupt seen_jobs.json, starting fresh")
    return {}


def save_seen(seen: dict):
    tmp = SEEN_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(seen, indent=2), encoding="utf-8")
    tmp.replace(SEEN_FILE)


def job_id(job: dict) -> str:
    """Generate a stable ID from title + company + location."""
    raw = f"{job.get('title', '')}-{job.get('company', '')}-{job.get('location', '')}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


# ── LinkedIn Guest API Scraper ──────────────────────────────────────────────

LINKEDIN_JOBS_API = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
LINKEDIN_JOB_DETAIL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}


def scrape_linkedin_jobs() -> List[Dict]:
    """Scrape LinkedIn jobs using the public guest API."""
    log.info(f"Scraping: '{SEARCH_KEYWORDS}' in '{SEARCH_LOCATION}' (max {RESULTS_PER_RUN})")

    jobs = []
    page_size = 25  # LinkedIn returns 25 per page

    for start in range(0, RESULTS_PER_RUN, page_size):
        params = {
            "keywords": SEARCH_KEYWORDS,
            "location": SEARCH_LOCATION,
            "start": start,
            "f_TPR": "r259200",  # last 3 days (72h in seconds)
        }

        try:
            resp = requests.get(LINKEDIN_JOBS_API, params=params, headers=HEADERS, timeout=20)
            if resp.status_code != 200:
                log.warning(f"Page {start}: HTTP {resp.status_code}")
                break

            page_jobs = parse_job_listings(resp.text)
            if not page_jobs:
                log.info(f"No more jobs at offset {start}")
                break

            jobs.extend(page_jobs)
            log.info(f"Page offset {start}: got {len(page_jobs)} jobs")

            # Random delay between pages (2-5s)
            if start + page_size < RESULTS_PER_RUN:
                time.sleep(random.uniform(2, 5))

        except Exception as e:
            log.error(f"Scrape page {start} failed: {e}")
            break

    # Filter excluded companies
    jobs = [j for j in jobs if j["company"].lower() not in EXCLUDED_COMPANIES]

    log.info(f"Scraped {len(jobs)} jobs total (after exclusions)")

    # Fetch descriptions for top jobs (limit to save time)
    fetch_limit = min(len(jobs), RESULTS_PER_RUN)
    for i, job in enumerate(jobs[:fetch_limit]):
        if job.get("linkedin_id"):
            desc = fetch_job_description(job["linkedin_id"])
            if desc:
                job["description"] = desc[:3000]
            if i < fetch_limit - 1:
                time.sleep(random.uniform(1, 3))

    return jobs


def parse_job_listings(html: str) -> List[Dict]:
    """Parse job cards from LinkedIn search results HTML."""
    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    cards = soup.find_all("li")
    for card in cards:
        try:
            # Title and URL
            title_el = card.find("h3", class_=re.compile("base-search-card__title"))
            title = title_el.get_text(strip=True) if title_el else ""

            link_el = card.find("a", class_=re.compile("base-card__full-link"))
            job_url = link_el["href"].split("?")[0] if link_el and link_el.get("href") else ""

            # Extract LinkedIn job ID from URL
            linkedin_id = ""
            if job_url:
                match = re.search(r"/view/[^/]*-(\d+)", job_url)
                if match:
                    linkedin_id = match.group(1)

            # Company
            company_el = card.find("h4", class_=re.compile("base-search-card__subtitle"))
            company = company_el.get_text(strip=True) if company_el else ""

            # Location
            loc_el = card.find("span", class_=re.compile("job-search-card__location"))
            location = loc_el.get_text(strip=True) if loc_el else ""

            # Date
            date_el = card.find("time")
            date_posted = date_el.get("datetime", "") if date_el else ""

            if title:
                jobs.append({
                    "title": title,
                    "company": company,
                    "location": location,
                    "date_posted": date_posted,
                    "job_url": job_url,
                    "linkedin_id": linkedin_id,
                    "description": "",
                    "salary": "",
                })
        except Exception as e:
            log.debug(f"Failed to parse card: {e}")
            continue

    return jobs


def fetch_job_description(linkedin_job_id: str) -> Optional[str]:
    """Fetch full job description from LinkedIn job detail page."""
    url = LINKEDIN_JOB_DETAIL.format(job_id=linkedin_job_id)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        desc_el = soup.find("div", class_=re.compile("show-more-less-html__markup"))
        if desc_el:
            return desc_el.get_text(separator="\n", strip=True)
    except Exception as e:
        log.debug(f"Failed to fetch description for {linkedin_job_id}: {e}")

    return None


# ── Claude Scorer ───────────────────────────────────────────────────────────


def score_jobs(jobs: List[Dict]) -> List[Dict]:
    """Use Claude to score and rank jobs by relevance."""
    if not jobs or not ANTHROPIC_API_KEY:
        if not ANTHROPIC_API_KEY:
            log.warning("No ANTHROPIC_API_KEY — skipping scoring, returning unscored")
            for j in jobs:
                j["score"] = 5
                j["reason"] = "Unscored (no API key)"
        return jobs

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    skills_text = ", ".join(PREFERRED_SKILLS) if PREFERRED_SKILLS else "not specified"

    # Batch jobs into groups of 20 to stay within token limits
    batch_size = 20
    scored_jobs = []

    for batch_start in range(0, len(jobs), batch_size):
        batch = jobs[batch_start:batch_start + batch_size]

        job_summaries = []
        for i, j in enumerate(batch):
            desc = j.get("description", "No description available")
            job_summaries.append(
                f"[{i}] {j['title']} at {j['company']} ({j['location']})\n"
                f"Description: {desc[:1500]}"
            )

        prompt = f"""You are a job relevance scorer. Score each job from 1-10 based on how well it matches the candidate profile.

Candidate profile:
- Searching for: {SEARCH_KEYWORDS}
- Preferred skills: {skills_text}
- Location: {SEARCH_LOCATION}

Jobs to score:
{"---".join(job_summaries)}

Return ONLY a JSON array with objects like:
[{{"index": 0, "score": 8, "reason": "Strong match because..."}}]

Score criteria:
- 9-10: Perfect match (role + skills + location align)
- 7-8: Good match (most criteria met)
- 5-6: Partial match
- 3-4: Weak match
- 1-2: Irrelevant

Be concise in reasons (max 20 words each). Return valid JSON only."""

        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()

            # Extract JSON from response
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            scores = json.loads(text)
            for item in scores:
                idx = item["index"]
                if 0 <= idx < len(batch):
                    batch[idx]["score"] = item["score"]
                    batch[idx]["reason"] = item.get("reason", "")

        except Exception as e:
            log.error(f"Scoring batch failed: {e}")
            for j in batch:
                j.setdefault("score", 5)
                j.setdefault("reason", "Scoring error")

        scored_jobs.extend(batch)

    # Sort by score descending
    scored_jobs.sort(key=lambda x: x.get("score", 0), reverse=True)
    return scored_jobs


# ── CSV Export ──────────────────────────────────────────────────────────────


def export_csv(jobs: List[Dict]):
    """Append new jobs to CSV file."""
    file_exists = CSV_FILE.exists()
    fieldnames = ["date_added", "score", "title", "company", "location", "salary", "reason", "job_url", "date_posted"]

    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if not file_exists:
            writer.writeheader()

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        for j in jobs:
            j["date_added"] = now
            writer.writerow(j)

    log.info(f"Exported {len(jobs)} jobs to {CSV_FILE}")


# ── Telegram ────────────────────────────────────────────────────────────────


def send_telegram(text: str):
    """Send message to Telegram. Splits if over 4096 chars."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("Telegram not configured — skipping")
        print(f"[TELEGRAM PREVIEW]\n{text}")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    # Split into chunks at newline boundaries
    chunks = []
    while len(text) > 4096:
        split_at = text.rfind("\n", 0, 4096)
        if split_at == -1:
            split_at = 4096
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    chunks.append(text)

    for chunk in chunks:
        try:
            resp = requests.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": chunk,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            }, timeout=15)
            if not resp.ok:
                log.error(f"Telegram error: {resp.status_code} {resp.text}")
        except Exception as e:
            log.error(f"Telegram send failed: {e}")


def format_telegram_message(new_jobs: List[Dict], total_scraped: int) -> str:
    """Format job results for Telegram."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"*LinkedIn Jobs Report* \u2014 {now}", f"Scraped: {total_scraped} | New: {len(new_jobs)}", ""]

    if not new_jobs:
        lines.append("No new jobs found this run.")
        return "\n".join(lines)

    top = [j for j in new_jobs if j.get("score", 0) >= SCORE_THRESHOLD]

    if top:
        lines.append(f"*Top matches (score >= {SCORE_THRESHOLD}):*")
        lines.append("")
        for j in top[:15]:
            score = j.get("score", "?")
            title = j.get("title", "Unknown")
            company = j.get("company", "Unknown")
            reason = j.get("reason", "")
            url = j.get("job_url", "")
            lines.append(f"*[{score}/10]* {title}")
            lines.append(f"  {company} \u2014 {reason}")
            if url:
                lines.append(f"  [Apply]({url})")
            lines.append("")
    else:
        lines.append("No jobs scored above threshold this run.")

    below = len(new_jobs) - len(top)
    if below > 0:
        lines.append(f"_{below} more jobs below threshold (saved to CSV)_")

    return "\n".join(lines)


# ── Main ────────────────────────────────────────────────────────────────────


def main():
    log.info("=" * 50)
    log.info("LinkedIn Agent starting")

    # 1. Scrape
    jobs = scrape_linkedin_jobs()
    if not jobs:
        log.info("No jobs scraped — exiting")
        send_telegram("LinkedIn Agent: No jobs found this run.")
        return

    total_scraped = len(jobs)

    # 2. Filter out already-seen jobs
    seen = load_seen()
    new_jobs = []
    for j in jobs:
        jid = job_id(j)
        if jid not in seen:
            new_jobs.append(j)
            seen[jid] = {
                "title": j["title"],
                "company": j["company"],
                "first_seen": datetime.now().isoformat(),
            }

    log.info(f"New jobs: {len(new_jobs)} / {total_scraped} total")

    if not new_jobs:
        log.info("All jobs already seen — exiting")
        send_telegram(f"LinkedIn Agent: Scraped {total_scraped} jobs, all previously seen.")
        save_seen(seen)
        return

    # 3. Score with Claude
    new_jobs = score_jobs(new_jobs)

    # 4. Export to CSV
    export_csv(new_jobs)

    # 5. Send Telegram alert
    msg = format_telegram_message(new_jobs, total_scraped)
    send_telegram(msg)

    # 6. Save seen state
    save_seen(seen)

    # 7. Prune seen jobs older than 30 days
    cutoff = (datetime.now() - timedelta(days=30)).isoformat()
    seen = {k: v for k, v in seen.items() if v.get("first_seen", "") > cutoff}
    save_seen(seen)

    log.info(f"Done — {len(new_jobs)} new jobs processed")
    log.info("=" * 50)


if __name__ == "__main__":
    main()

"""
filter.py - Apply hard filters to raw job listings (no LLM).

Takes raw_jobs.json and produces filtered_jobs.json after applying:
  1. Title blacklist
  2. Experience cap (exclude 4+ years required)
  3. Dutch-required exclusion
  4. Dutch-preferred flag (kept, just flagged)
  5. Netherlands location filter
  6. URL deduplication
"""

import argparse
import json
import re
import sys

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TITLE_BLACKLIST = [
    "senior manager",
    "manager",
    "director",
    "head of",
    "lead",
    "vp",
    "vice president",
    "chief",
]

# Patterns that signal too many years of experience required
EXPERIENCE_EXCLUDE_PATTERNS = [
    re.compile(r"\b[4-9]\+?\s*years?\b.*?\bexperience\b", re.IGNORECASE),
    re.compile(r"\bexperience\b.*?\b[4-9]\+?\s*years?\b", re.IGNORECASE),
    re.compile(r"\b\d{2,}\+?\s*years?\b.*?\bexperience\b", re.IGNORECASE),
    re.compile(r"\bexperience\b.*?\b\d{2,}\+?\s*years?\b", re.IGNORECASE),
]

DUTCH_REQUIRED_PHRASES = [
    "dutch required",
    "dutch is mandatory",
    "dutch is required",
    "dutch vereist",
    "nederlands vereist",
]

DUTCH_PREFERRED_PHRASES = [
    "dutch preferred",
    "dutch is a plus",
    "dutch is an advantage",
    "dutch is preferred",
]

# Common Dutch words used for language-detection heuristic
COMMON_DUTCH_WORDS = {
    "de", "het", "een", "van", "en", "in", "is", "dat", "op", "te",
    "voor", "met", "zijn", "wordt", "aan", "er", "ook", "niet", "maar",
    "als", "dit", "die", "naar", "bij", "nog", "wel", "kan", "uit",
    "dan", "om", "zo", "hun", "meer", "over", "tot", "je", "we",
    "hebben", "heeft", "worden", "werd", "deze", "door", "wat", "geen",
    "alle", "moet", "zal", "veel", "onder", "zou", "ons", "wie",
    "haar", "hem", "zij", "wij", "jij", "mijn", "uw", "onze",
    "kunnen", "willen", "zullen", "moeten", "mogen",
    "werkzaamheden", "functie", "ervaring", "vacature", "organisatie",
    "taken", "verantwoordelijkheden", "profiel", "aanbod", "solliciteer",
}

NETHERLANDS_LOCATIONS = [
    "netherlands",
    "nederland",
    "amsterdam",
    "rotterdam",
    "utrecht",
    "eindhoven",
    "the hague",
    "den haag",
    "tilburg",
    "groningen",
    "breda",
    "arnhem",
    "leiden",
    "haarlem",
    "hoofddorp",
    "zoetermeer",
    "amstelveen",
    "delft",
    "almere",
    "schiphol",
]

DUTCH_LANGUAGE_THRESHOLD = 0.50  # >50% Dutch words -> assume Dutch text

# ---------------------------------------------------------------------------
# Filter helpers
# ---------------------------------------------------------------------------

def is_title_blacklisted(title):
    """Return True if the title contains any blacklisted term."""
    title_lower = title.lower()
    for term in TITLE_BLACKLIST:
        # Use word-boundary check so "team lead" matches but "leading" does not
        if re.search(r"\b" + re.escape(term) + r"\b", title_lower):
            return True
    return False


def has_excessive_experience(description):
    """Return True if the description requires 4+ years of experience."""
    for pattern in EXPERIENCE_EXCLUDE_PATTERNS:
        if pattern.search(description):
            return True
    return False


def is_dutch_required(description):
    """Return True if the description states Dutch language is mandatory."""
    desc_lower = description.lower()
    for phrase in DUTCH_REQUIRED_PHRASES:
        if phrase in desc_lower:
            return True
    return False


def is_description_dutch(description):
    """Heuristic: return True if >50% of words are common Dutch words."""
    words = re.findall(r"[a-zA-Z]+", description.lower())
    if len(words) < 20:
        # Too short to judge reliably
        return False
    dutch_count = sum(1 for w in words if w in COMMON_DUTCH_WORDS)
    return (dutch_count / len(words)) > DUTCH_LANGUAGE_THRESHOLD


def is_dutch_preferred(description):
    """Return True if Dutch is mentioned as preferred/advantage (not required)."""
    desc_lower = description.lower()
    for phrase in DUTCH_PREFERRED_PHRASES:
        if phrase in desc_lower:
            return True
    return False


def is_location_netherlands(job):
    """Return True if the job location appears to be in the Netherlands."""
    location = job.get("location", "")
    if not location:
        # If no location field, be lenient and keep the job
        return True
    loc_lower = location.lower()
    for place in NETHERLANDS_LOCATIONS:
        if place in loc_lower:
            return True
    return False


# ---------------------------------------------------------------------------
# Main filtering logic
# ---------------------------------------------------------------------------

def filter_jobs(jobs):
    """Apply all hard filters and return (kept_jobs, stats_dict)."""
    seen_urls = set()
    kept = []
    stats = {
        "title_blacklist": 0,
        "experience": 0,
        "dutch_required": 0,
        "dutch_description": 0,
        "location": 0,
        "duplicate": 0,
    }

    for job in jobs:
        title = job.get("title", "")
        description = job.get("description", "")
        url = job.get("url", job.get("link", ""))

        # 1. Dedup by URL
        if url and url in seen_urls:
            stats["duplicate"] += 1
            continue
        if url:
            seen_urls.add(url)

        # 2. Title blacklist
        if is_title_blacklisted(title):
            stats["title_blacklist"] += 1
            continue

        # 3. Experience cap
        if has_excessive_experience(description):
            stats["experience"] += 1
            continue

        # 4. Dutch required (explicit phrase or full-Dutch description)
        if is_dutch_required(description):
            stats["dutch_required"] += 1
            continue
        if is_description_dutch(description):
            stats["dutch_description"] += 1
            continue

        # 5. Location
        if not is_location_netherlands(job):
            stats["location"] += 1
            continue

        # 6. Dutch-preferred flag (not a filter, just annotation)
        job["dutch_preferred"] = is_dutch_preferred(description)

        kept.append(job)

    return kept, stats


def main():
    parser = argparse.ArgumentParser(
        description="Apply hard filters to raw job listings."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to raw_jobs.json",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to write filtered_jobs.json",
    )
    args = parser.parse_args()

    # Load input
    try:
        with open(args.input, "r", encoding="utf-8") as f:
            raw_jobs = json.load(f)
    except FileNotFoundError:
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"Error: invalid JSON in {args.input}: {exc}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(raw_jobs, list):
        print("Error: input JSON must be an array of job objects", file=sys.stderr)
        sys.exit(1)

    total_input = len(raw_jobs)

    # Filter
    filtered, stats = filter_jobs(raw_jobs)

    total_output = len(filtered)
    removed = total_input - total_output

    # Write output
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(filtered, f, indent=2, ensure_ascii=False)

    # Summary
    print(f"Filtered: {total_input} -> {total_output} jobs (removed {removed})")
    if removed > 0:
        print("  Breakdown:")
        if stats["title_blacklist"]:
            print(f"    Title blacklist:    {stats['title_blacklist']}")
        if stats["experience"]:
            print(f"    Experience (4+yr):  {stats['experience']}")
        if stats["dutch_required"]:
            print(f"    Dutch required:     {stats['dutch_required']}")
        if stats["dutch_description"]:
            print(f"    Dutch description:  {stats['dutch_description']}")
        if stats["location"]:
            print(f"    Location (not NL):  {stats['location']}")
        if stats["duplicate"]:
            print(f"    Duplicate URL:      {stats['duplicate']}")


if __name__ == "__main__":
    main()

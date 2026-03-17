"""
Score filtered jobs using Claude CLI and merge into tracker.json.

Usage:
    py -3.9 score.py --input filtered_jobs.json --tracker tracker.json
    py -3.9 score.py --input filtered_jobs.json --tracker tracker.json --batch-size 10
"""

import argparse
import json
import subprocess
import sys
from datetime import date


SCORING_PROMPT_TEMPLATE = """Score each job below for fit (0-100) based on these candidate skills:
- Tech literacy and analysis
- Software tools proficiency
- Excel / Power BI / data visualization
- Optimization and process improvement
- Automation (scripting, workflows)
- Training delivery and documentation

Rules:
- If the role is a deep supply chain position requiring specific SC software (SAP WMS, Oracle TMS, etc.) or specialized SC knowledge (customs brokering, freight forwarding), give it a lower score and note "risky - deep SC" in key_match.
- "interview_speed": "fast" if it is posted by a recruiter/agency, "normal" if by the company directly.
- "years_required": integer, best guess from the description. Use 0 if not stated.
- "dutch_preferred": true if the posting prefers or requires Dutch language.
- "language": primary language of the job posting (e.g. "English", "Dutch").

Respond with ONLY a JSON array, no other text. Each element:
{{"title": "...", "company": "...", "location": "...", "salary": "...", "fit_score": 85, "url": "...", "key_match": "one-line why it fits", "interview_speed": "fast", "years_required": 2, "language": "English", "dutch_preferred": false}}

Jobs to score:
{jobs_block}
"""


def load_json(path):
    """Load and return parsed JSON from a file path."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    """Write data as JSON to a file path."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def build_jobs_block(jobs):
    """Format a list of jobs into a numbered text block for the prompt."""
    lines = []
    for i, job in enumerate(jobs, 1):
        desc = (job.get("description") or "")[:300]
        lines.append(
            f"{i}. Title: {job.get('title', 'N/A')}\n"
            f"   Company: {job.get('company', 'N/A')}\n"
            f"   Location: {job.get('location', 'N/A')}\n"
            f"   Salary: {job.get('salary', 'not listed')}\n"
            f"   URL: {job.get('url', '')}\n"
            f"   Description: {desc}"
        )
    return "\n\n".join(lines)


def score_batch(jobs):
    """Send a batch of jobs to Claude CLI for scoring. Returns list of scored dicts or None on failure."""
    jobs_block = build_jobs_block(jobs)
    prompt = SCORING_PROMPT_TEMPLATE.format(jobs_block=jobs_block)

    try:
        # Write prompt to temp file and create a .ps1 runner to avoid cmd line limit
        import tempfile, os
        prompt_path = os.path.join(tempfile.gettempdir(), f'score-prompt-{os.getpid()}.txt')
        runner_path = os.path.join(tempfile.gettempdir(), f'score-runner-{os.getpid()}.ps1')

        with open(prompt_path, 'w', encoding='utf-8') as f:
            f.write(prompt)

        with open(runner_path, 'w', encoding='utf-8') as f:
            f.write(f'$p = Get-Content \'{prompt_path}\' -Raw\n')
            f.write(f'& "C:\\Users\\Administrator\\AppData\\Roaming\\npm\\claude.cmd" --print -m sonnet $p\n')

        try:
            result = subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass", "-File", runner_path],
                capture_output=True,
                text=True,
                timeout=180,
            )
        finally:
            for fp in [prompt_path, runner_path]:
                try: os.unlink(fp)
                except: pass
    except subprocess.TimeoutExpired:
        print("  ERROR: Claude CLI timed out after 120s")
        return None
    except FileNotFoundError:
        print("  ERROR: 'claude' CLI not found on PATH")
        return None

    if result.returncode != 0:
        print(f"  ERROR: Claude CLI exited with code {result.returncode}")
        stderr_snippet = (result.stderr or "")[:200]
        if stderr_snippet:
            print(f"  stderr: {stderr_snippet}")
        return None

    raw = result.stdout.strip()
    if not raw:
        print("  ERROR: Claude returned empty output")
        return None

    # Extract JSON array from response (handle markdown fences)
    text = raw
    if "```" in text:
        # Strip markdown code fences
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1:
            text = text[start : end + 1]
    else:
        # Try to find bare JSON array
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1:
            text = text[start : end + 1]

    try:
        scored = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"  ERROR: Failed to parse Claude response as JSON: {e}")
        print(f"  Raw output (first 300 chars): {raw[:300]}")
        return None

    if not isinstance(scored, list):
        print("  ERROR: Claude response is not a JSON array")
        return None

    return scored


def merge_into_tracker(tracker_path, scored_jobs):
    """Read tracker.json, append new scored jobs (deduplicated by URL), write back. Returns count added."""
    try:
        tracker = load_json(tracker_path)
    except (FileNotFoundError, json.JSONDecodeError):
        tracker = {"round": 1, "last_updated": str(date.today()), "jobs": []}

    existing_urls = {j.get("url") for j in tracker.get("jobs", []) if j.get("url")}
    max_id = max((j.get("id", 0) for j in tracker.get("jobs", [])), default=0)

    added = 0
    today = str(date.today())

    for sj in scored_jobs:
        url = sj.get("url", "")
        fit = sj.get("fit_score", 0)

        # Skip low-fit or duplicate
        if fit < 60:
            continue
        if url and url in existing_urls:
            continue

        max_id += 1
        job_entry = {
            "id": max_id,
            "title": sj.get("title", ""),
            "company": sj.get("company", ""),
            "location": sj.get("location", ""),
            "salary": sj.get("salary", "not listed"),
            "fit_score": fit,
            "url": url,
            "status": "active",
            "date_found": today,
            "date_posted": sj.get("date_posted", today),
            "deadline": sj.get("deadline", "unknown"),
            "language": sj.get("language", "English"),
            "years_required": sj.get("years_required", 0),
            "key_match": sj.get("key_match", ""),
            "interview_speed": sj.get("interview_speed", "normal"),
            "dutch_preferred": sj.get("dutch_preferred", False),
            "applicant_count": None,
        }
        tracker["jobs"].append(job_entry)
        existing_urls.add(url)
        added += 1

    tracker["last_updated"] = today
    if tracker.get("round", 0) == 0:
        tracker["round"] = 1

    save_json(tracker_path, tracker)
    return added


def main():
    parser = argparse.ArgumentParser(description="Score filtered jobs via Claude CLI")
    parser.add_argument("--input", required=True, help="Path to filtered_jobs.json")
    parser.add_argument("--tracker", required=True, help="Path to tracker.json")
    parser.add_argument("--batch-size", type=int, default=10, help="Jobs per Claude call (default: 10)")
    args = parser.parse_args()

    # Load filtered jobs
    try:
        jobs = load_json(args.input)
    except FileNotFoundError:
        print(f"ERROR: Input file not found: {args.input}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in {args.input}: {e}")
        sys.exit(1)

    if not isinstance(jobs, list):
        # Handle wrapper object with a "jobs" key
        if isinstance(jobs, dict) and "jobs" in jobs:
            jobs = jobs["jobs"]
        else:
            print("ERROR: Input JSON must be an array or object with 'jobs' key")
            sys.exit(1)

    if not jobs:
        print("No jobs to score.")
        sys.exit(0)

    total = len(jobs)
    batch_size = args.batch_size
    num_batches = (total + batch_size - 1) // batch_size
    total_added = 0

    print(f"Scoring {total} jobs in {num_batches} batch(es) of up to {batch_size}...")

    for i in range(num_batches):
        start = i * batch_size
        end = min(start + batch_size, total)
        batch = jobs[start:end]

        print(f"Scoring batch {i + 1}/{num_batches} ({len(batch)} jobs)...", end=" ", flush=True)

        scored = score_batch(batch)
        if scored is None:
            print("FAILED - skipping batch")
            continue

        added = merge_into_tracker(args.tracker, scored)
        total_added += added
        print(f"Added {added} jobs")

    print(f"\nDone. Total added to tracker: {total_added}")


if __name__ == "__main__":
    main()

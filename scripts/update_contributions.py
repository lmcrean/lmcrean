#!/usr/bin/env python3
"""
Clone ReadMe.md to test_readme.md and update relative timestamps.
Finds PR URLs, fetches merge dates, and injects relative timestamps into <summary> tags.
"""

import os
import re
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import urllib.request
import urllib.error

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
GITHUB_API = "https://api.github.com"

# Manual overrides for PR merge dates (keyed by "owner/repo#number")
PR_MERGE_DATES: Dict[str, str] = {
    "penpot/penpot#6982": "2025-07-26T12:15:30Z",
    "gocardless/woocommerce-gateway-gocardless#88": "2025-12-17T00:00:00Z",
    "google/guava#7988": "2025-09-14T13:00:00Z",
    "google/guava#7989": "2025-09-14T13:04:00Z",
    "google/guava#7987": "2025-09-14T11:44:42Z",
    "google/guava#7974": "2025-09-24T12:00:00Z",
    "google/guava#7986": "2025-10-30T14:00:00Z",
    "rropen/terraform-provider-cscdm#16": "2026-01-05T18:25:21Z",
}

if not GITHUB_TOKEN:
    print("Warning: No GITHUB_TOKEN found. API rate limits will be restrictive.")


def github_request(endpoint: str) -> dict:
    """Make authenticated request to GitHub API."""
    url = f"{GITHUB_API}{endpoint}"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "lmcrean-readme-updater",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code} for {url}: {e.reason}")
        return {}
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return {}


def get_relative_time(date_str: str) -> str:
    """Convert ISO date string to relative time (e.g., '6 days ago')."""
    if not date_str:
        return "unknown"

    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    diff = now - dt

    days = diff.days
    if days == 0:
        hours = diff.seconds // 3600
        if hours == 0:
            minutes = diff.seconds // 60
            if minutes <= 1:
                return "just now"
            return f"{minutes} minutes ago"
        if hours == 1:
            return "1 hour ago"
        return f"{hours} hours ago"
    if days == 1:
        return "1 day ago"
    if days < 7:
        return f"{days} days ago"
    if days < 14:
        return "1 week ago"
    if days < 30:
        weeks = days // 7
        return f"{weeks} weeks ago"
    if days < 60:
        return "1 month ago"
    if days < 365:
        months = days // 30
        return f"{months} months ago"
    if days < 730:
        return "1 year ago"
    years = days // 365
    return f"{years} years ago"


def fetch_pr_merge_date(owner: str, repo: str, pr_number: int) -> Optional[str]:
    """Fetch the merge date for a PR from GitHub API or overrides."""
    key = f"{owner}/{repo}#{pr_number}"

    # Check overrides first
    if key in PR_MERGE_DATES:
        return PR_MERGE_DATES[key]

    # Fetch from API
    pr_data = github_request(f"/repos/{owner}/{repo}/pulls/{pr_number}")
    if pr_data:
        return pr_data.get("merged_at") or pr_data.get("created_at")
    return None


def update_readme_with_timestamps():
    """Read ReadMe.md, inject relative timestamps, write to test_readme.md."""
    script_dir = os.path.dirname(__file__)
    readme_path = os.path.join(script_dir, "..", "ReadMe.md")
    output_path = os.path.join(script_dir, "..", "test_readme.md")

    # Read the source file
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Find all PR URLs and their positions
    pr_pattern = r'https://github\.com/([^/]+)/([^/]+)/pull/(\d+)'

    # Find all summary tags that need timestamps
    summary_pattern = r'(<details><summary><code>\+\d+/-\d+</code>)(</summary>)'

    # Build a list of (pr_url_match, summary_match) pairs by position
    pr_matches = list(re.finditer(pr_pattern, content))
    summary_matches = list(re.finditer(summary_pattern, content))

    print(f"Found {len(pr_matches)} PR URLs and {len(summary_matches)} summary tags")

    # For each summary, find the closest preceding PR URL
    replacements = []
    for summary_match in summary_matches:
        summary_pos = summary_match.start()

        # Find the closest PR URL before this summary
        closest_pr = None
        for pr_match in pr_matches:
            if pr_match.end() < summary_pos:
                closest_pr = pr_match
            else:
                break

        if closest_pr:
            owner, repo, pr_num = closest_pr.groups()
            merge_date = fetch_pr_merge_date(owner, repo, int(pr_num))

            if merge_date:
                relative_time = get_relative_time(merge_date)
                # Store the replacement: (start, end, new_text)
                new_summary = f"{summary_match.group(1)} | merged {relative_time}{summary_match.group(2)}"
                replacements.append((summary_match.start(), summary_match.end(), new_summary))
                print(f"  {owner}/{repo}#{pr_num}: merged {relative_time}")

    # Apply replacements in reverse order to maintain positions
    for start, end, new_text in reversed(replacements):
        content = content[:start] + new_text + content[end:]

    # Write the output file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\ntest_readme.md updated with {len(replacements)} timestamps!")


if __name__ == "__main__":
    update_readme_with_timestamps()

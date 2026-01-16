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

# ============================================================================
# CONFIGURATION - PR Overrides and Filtering
# ============================================================================

# Repositories to hide completely
HIDDEN_REPOSITORIES = [
    "team-5",
    "halloween-hackathon",
    "vitest-dev",
    "vitest"
]

# Repositories with special filtering rules
LIMITED_REPOSITORIES = {
    "penpot": "keep-latest-only"
}

# Manual overrides for PR data (keyed by PR node ID)
# Used when GitHub API returns incorrect data or to add custom descriptions
PR_OVERRIDES: Dict[int, Dict[str, Any]] = {
    # Penpot milestone lock feature PR
    2696869536: {
        "title": "✨ Enhance (version control): Add milestone lock feature to prevent accidental deletion and bad actor interventions",
        "description": "Implemented version locking system allowing users to protect saved milestones from accidental deletion or bad actors. Added database migration, RPC endpoints with authorization, and UI with visual lock indicators.",
        "state": "merged",
        "merged": True,
        "merged_at": "2025-07-26T12:15:30Z",
    },
    # GoCardless WooCommerce subscription fix
    2793359837: {
        "title": "Fix inconsistent subscription status after cancellation with centralized cancellation logic",
        "description": "Fixed subscription status incorrectly showing \"Pending Cancellation\" instead of \"Cancelled\" when users cancel before GoCardless payment confirmation. Added centralized cancellation handling with parent order status synchronization.",
        "state": "merged",
        "merged": True,
        "merged_at": "2025-12-17T00:00:00Z"
    },
    # Google Guava PR #7988
    2826673514: {
        "title": "Add tests demonstrating `Iterators.mergeSorted()` instability",
        "description": "Added test cases demonstrating the instability problem in `Iterators.mergeSorted()` as requested by maintainers, verifying the bug exists before the fix PR.",
        "state": "merged",
        "merged": True,
        "merged_at": "2025-09-14T13:00:00Z"
    },
    # Google Guava PR #7989
    2826689299: {
        "title": "Fix `Iterators.mergeSorted()` to preserve stability for equal elements",
        "description": "Fixed unstable ordering of equal elements by tracking iterator insertion order and using it as a tiebreaker, ensuring elements from earlier iterators appear before equal elements from later ones.",
        "state": "merged",
        "merged": True,
        "merged_at": "2025-09-14T13:04:00Z"
    },
    # Google Guava PR #7987
    2826631136: {
        "title": "Add test for putIfAbsent to catch implementations that incorrectly ignore null values",
        "description": "Added test to verify `putIfAbsent` correctly replaces existing null values, catching non-compliant Map implementations that pass the test suite despite violating the JavaDoc specification.",
        "state": "merged",
        "merged": True,
        "merged_at": "2025-09-14T11:44:42Z",
    },
    # Google Guava PR #7974
    2805908000: {
        "title": "Improve error messages for annotation methods on synthetic TypeVariables",
        "description": "Replaced unhelpful `UnsupportedOperationException(\"methodName\")` with descriptive error messages explaining why annotations aren't supported on synthetic TypeVariables created by TypeResolver.",
        "state": "merged",
        "merged": True,
        "merged_at": "2025-09-24T12:00:00Z"
    },
    # Google Guava PR #7986 - FileBackedOutputStream resource leak fix
    2826605057: {
        "title": "Fix resource leak in FileBackedOutputStream to prevent file handle exhaustion",
        "description": "Fixed file handle exhaustion by adding proper exception handling to ensure FileOutputStream is closed when IOException occurs during memory-to-file transition.",
        "state": "merged",
        "merged": True,
        "merged_at": "2025-10-30T14:00:00Z"
    },
    # terraform-provider-cscdm PR #16
    2867917251: {
        "title": "Fix: Add HTTP timeout to prevent Terraform from hanging indefinitely",
        "description": "Added 30-second HTTP request timeout to prevent the Terraform provider from hanging indefinitely when the CSC Domain Manager API accepts connections but doesn't respond.",
        "state": "merged",
        "merged": True,
        "merged_at": "2026-01-05T18:25:21Z",
    },
    # terraform-provider-cscdm PR #9
    2787729818: {
        "title": "Enhance(error handling): improve flush loop and trigger handling in cscdm",
        "description": "Replaced `sync.Cond` with buffered channels to fix goroutine leaks, added `sync.Once` to prevent panics, and enabled recovery from transient failures instead of permanent termination.",
    },
    # Stripe pg-schema-diff PR #232
    2746051142: {
        "title": "Fix: Support `GENERATED ALWAYS AS` columns to reduce migration failures",
        "description": "Fixed migration failures where generated columns were incorrectly treated as DEFAULT columns. Updated schema introspection to detect `pg_attribute.attgenerated`, extended the Column model, and fixed DDL generation to output proper `GENERATED ALWAYS AS ... STORED` syntax.",
    },
    # Microsoft TypeAgent PR #1478
    2759515533: {
        "title": "Return undefined instead of invalid action names for partial matches",
        "description": "Prevented exceptions when typing partial cached commands by returning `undefined` instead of invalid \"unknown.unknown\" action names, enabling graceful handling of partial matches.",
    },
}

if not GITHUB_TOKEN:
    print("Warning: No GITHUB_TOKEN found. API rate limits will be restrictive.")


def github_request(endpoint: str, return_list: bool = False):
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
        return [] if return_list else {}
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return [] if return_list else {}


def fetch_pr_diff(owner: str, repo: str, pr_number: int) -> str:
    """Fetch the diff content for a PR from GitHub API."""
    files = github_request(f"/repos/{owner}/{repo}/pulls/{pr_number}/files", return_list=True)
    if not files:
        return ""

    diff_parts = []
    for file_info in files:
        filename = file_info.get("filename", "")
        patch = file_info.get("patch", "")
        if patch:
            diff_parts.append(f"diff --git a/{filename} b/{filename}")
            # Add file header info
            diff_parts.append(f"--- a/{filename}")
            diff_parts.append(f"+++ b/{filename}")
            diff_parts.append(patch)

    return "\n".join(diff_parts)


def fetch_pr_data(owner: str, repo: str, pr_number: int, fetch_diff: bool = True) -> Optional[dict]:
    """Fetch PR data from GitHub API and apply overrides."""
    pr_data = github_request(f"/repos/{owner}/{repo}/pulls/{pr_number}")
    if not pr_data:
        return None

    pr_id = pr_data.get("id")

    # Check if blocked
    if pr_id in BLOCKED_PRS:
        print(f"  Skipping blocked PR: {owner}/{repo}#{pr_number}")
        return None

    result = {
        "id": pr_id,
        "number": pr_number,
        "owner": owner,
        "repo": repo,
        "title": pr_data.get("title", ""),
        "description": "",  # Will be populated from overrides
        "url": pr_data.get("html_url", f"https://github.com/{owner}/{repo}/pull/{pr_number}"),
        "state": pr_data.get("state", "unknown"),
        "merged": pr_data.get("merged", False),
        "merged_at": pr_data.get("merged_at"),
        "created_at": pr_data.get("created_at"),
        "additions": pr_data.get("additions", 0),
        "deletions": pr_data.get("deletions", 0),
        "diff": "",  # Will be populated if fetch_diff is True
    }

    # Fetch diff content
    if fetch_diff:
        result["diff"] = fetch_pr_diff(owner, repo, pr_number)

    # Apply overrides if available
    if pr_id and pr_id in PR_OVERRIDES:
        override = PR_OVERRIDES[pr_id]
        for key, value in override.items():
            result[key] = value
        print(f"  Applied override for PR #{pr_number} (ID: {pr_id})")

    return result


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

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
        # Add screenshot for Penpot (special case)
        if owner == "penpot":
            lines.append('<img src="screenshots/penpot.png" width="200" alt="Penpot milestone lock feature">')
            lines.append("")

        # Sort PRs by merge date (most recent first)
        prs.sort(
            key=lambda x: parse_date(x.get("merged_at") or x.get("created_at") or "") or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True
        )

        # Use numbered list for multiple PRs, bullet for single
        use_numbers = len(prs) > 1

        for idx, pr in enumerate(prs, 1):
            title = clean_title(pr["title"])
            url = pr["url"]
            additions = pr["additions"]
            deletions = pr["deletions"]
            merged_at = pr["merged_at"]
            is_merged = pr["merged"]
            description = pr.get("description", "")
            diff_content = pr.get("diff", "")

            # Get relative time
            if is_merged and merged_at:
                relative_time = get_relative_time(merged_at)
                time_str = f"merged {relative_time}"
            else:
                time_str = "open"

            # Format: numbered or bullet list item
            prefix = f"{idx}." if use_numbers else "-"

            # Build the PR entry with description
            if description:
                lines.append(f"{prefix} **[{title}]({url})**<br>*{description}*")
            else:
                lines.append(f"{prefix} **[{title}]({url})**")

            # Add collapsible diff stats with code diff
            lines.append(f"   <details><summary><code>+{additions}/-{deletions}</code> | {time_str}</summary>")
            lines.append("")
            if diff_content:
                lines.append("   ```diff")
                # Indent each line of the diff
                for diff_line in diff_content.split("\n"):
                    lines.append(f"   {diff_line}")
                lines.append("   ```")
            lines.append("   </details>")
            lines.append("")

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

#!/usr/bin/env python3
"""Recompute the figures in docs/WORK-RECORD-2026-09.md from primary sources.

The point of this script is that the work record never has to be taken on trust
or reconstructed from memory: every number in the document comes from a system
that recorded it at the time, and this re-reads those systems on demand.

Two sources, deliberately independent:

  * the local git history  — commit counts, line churn, hour/weekday rhythm
  * the GitHub REST API    — pull requests and Actions runs, stamped server-side

The second is the one that settles arguments. Local commit timestamps are
written by the machine making the commit and can in principle be rewritten;
GitHub stamps a PR and a workflow run on its own servers as the event arrives,
so the two agreeing is evidence in a way either alone is not.

Usage
    python3 tools/work-record/collect.py                 # git only
    GITHUB_TOKEN=ghp_... python3 tools/work-record/collect.py   # git + GitHub

A token is only needed for the GitHub half; without one the script still prints
the repository figures and says plainly that the API section was skipped rather
than silently reporting less.
"""
from __future__ import annotations

import collections
import json
import os
import statistics
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime

REPO = os.environ.get("WORK_RECORD_REPO", "3p4e/WEEKLY_WEED_FLOW")
API = "https://api.github.com"


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True
    ).stdout


def rule(title: str) -> None:
    print(f"\n{title}\n{'─' * len(title)}")


def histogram(counts: dict, order: list, width: int = 44) -> None:
    peak = max(counts.values()) or 1
    for key in order:
        n = counts.get(key, 0)
        bar = "#" * round(n / peak * width)
        print(f"  {key:>5} {n:>6}  {bar}")


# ---------------------------------------------------------------- git --------

def repository_figures() -> None:
    rule("THE REPOSITORY")

    dates = git("log", "--all", "--format=%ad", "--date=short").split()
    print(f"  commits                 {len(dates):,}")
    print(f"  first commit            {min(dates)}")
    print(f"  last commit             {max(dates)}")

    added = removed = 0
    for line in git("log", "--all", "--numstat", "--format=").splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
            added += int(parts[0])
            removed += int(parts[1])
    print(f"  lines added / removed   {added:,} / {removed:,}")

    tracked = git("ls-files").splitlines()
    source = [f for f in tracked if f.endswith((".py", ".js"))]
    tests = [f for f in source if "test" in os.path.basename(f).lower()]
    docs = [f for f in tracked if f.startswith("docs/") and f.endswith(".md")]
    print(f"  files tracked           {len(tracked):,}")
    print(f"  source files            {len(source):,}  ({len(tests)} test files)")
    print(f"  documents in docs/      {len(docs):,}")

    hours = collections.Counter(git("log", "--all", "--format=%ad", "--date=format:%H").split())
    rule("COMMITS BY HOUR (as recorded, UTC)")
    histogram(hours, [f"{h:02d}" for h in range(24)])
    night = sum(hours.get(f"{h:02d}", 0) for h in range(6))
    total = sum(hours.values())
    empty = [h for h in range(24) if not hours.get(f"{h:02d}")]
    print(f"\n  00:00–05:59             {night:,} of {total:,}  ({night / total:.1%})")
    print(f"  hours with no activity  {'none — all 24 occupied' if not empty else empty}")

    days = collections.Counter(git("log", "--all", "--format=%ad", "--date=format:%a").split())
    rule("COMMITS BY WEEKDAY")
    histogram(days, ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
    weekend = days.get("Sat", 0) + days.get("Sun", 0)
    print(f"\n  Saturday + Sunday       {weekend:,} of {total:,}  ({weekend / total:.1%})")


# ------------------------------------------------------------- github --------

def api(path: str, token: str) -> dict | list:
    request = urllib.request.Request(
        f"{API}{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "wwf-work-record",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def github_figures(token: str) -> None:
    rule("GITHUB'S OWN RECORD (stamped server-side)")

    pulls: list[dict] = []
    page = 1
    while True:
        batch = api(f"/repos/{REPO}/pulls?state=all&per_page=100&page={page}", token)
        if not batch:
            break
        pulls.extend(batch)
        page += 1

    merged = [p for p in pulls if p.get("merged_at")]
    print(f"  pull requests opened    {len(pulls)}")
    print(f"  merged                  {len(merged)}")

    runs = api(f"/repos/{REPO}/actions/runs?per_page=1", token)
    print(f"  workflow runs           {runs.get('total_count', 0):,}")

    stamp = "%Y-%m-%dT%H:%M:%SZ"
    events: list[datetime] = []
    turnarounds: list[tuple[float, int]] = []
    for pull in merged:
        opened = datetime.strptime(pull["created_at"], stamp)
        closed = datetime.strptime(pull["merged_at"], stamp)
        events += [opened, closed]
        turnarounds.append(((closed - opened).total_seconds() / 3600, pull["number"]))

    if not events:
        print("  (no merged pull requests yet)")
        return

    turnarounds.sort()
    median = statistics.median(t for t, _ in turnarounds)
    print(f"  median open → merge     {median:.1f} h")
    print(f"  fastest                 PR #{turnarounds[0][1]} in {turnarounds[0][0] * 60:.0f} min")
    print(f"  longest                 PR #{turnarounds[-1][1]} over {turnarounds[-1][0] / 24:.1f} days")

    hours = collections.Counter(f"{e.hour:02d}" for e in events)
    rule("PR OPEN/MERGE EVENTS BY HOUR (UTC)")
    histogram(hours, [f"{h:02d}" for h in range(24)])
    night = sum(hours.get(f"{h:02d}", 0) for h in range(6))
    weekend = sum(1 for e in events if e.weekday() >= 5)
    print(f"\n  events                  {len(events)}")
    print(f"  00:00–05:59             {night}  ({night / len(events):.1%})")
    print(f"  Saturday + Sunday       {weekend}  ({weekend / len(events):.1%})")


def main() -> int:
    print("WEEKLY_WEED_FLOW — work record, recomputed from primary sources")
    print(f"repository: {REPO}")

    repository_figures()

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        rule("GITHUB'S OWN RECORD")
        print("  skipped — set GITHUB_TOKEN (or GH_TOKEN) to include it.")
        print("  The repository figures above stand on their own; the GitHub half")
        print("  is what makes them independently attested.")
        return 0

    try:
        github_figures(token)
    except urllib.error.HTTPError as exc:
        rule("GITHUB'S OWN RECORD")
        print(f"  unavailable — HTTP {exc.code}. Check the token's repo scope.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

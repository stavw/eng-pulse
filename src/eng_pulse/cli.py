"""Command-line entry point for eng-pulse."""

import argparse
import re
import sys
from collections.abc import Sequence
from datetime import UTC, datetime

from eng_pulse.github import GitHubError, RepoNotFoundError, fetch_repo_data

# Checked before any gh call: gh looks up a name with no slash under the logged-in account.
_REPO_PATTERN = re.compile(r"[A-Za-z0-9-]+/[A-Za-z0-9._-]+")


def _repo_name(value: str) -> str:
    if not _REPO_PATTERN.fullmatch(value):
        raise argparse.ArgumentTypeError(f"invalid repo name {value!r}: expected owner/name")
    return value


def _days(value: str) -> int:
    try:
        days = int(value)
    except ValueError:
        days = 0
    if days < 1:
        raise argparse.ArgumentTypeError(f"invalid value {value!r}: must be a whole number of 1 or more")
    return days


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="eng-pulse", description="Weekly pulse for a GitHub repo.")
    parser.add_argument("repo", type=_repo_name, help="repository as owner/name")
    parser.add_argument("--days", type=_days, default=7, help="size of the window in days (default: 7)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    now = datetime.now(UTC)
    try:
        data = fetch_repo_data(args.repo, args.days, now)
    except RepoNotFoundError:
        print(f"error: repo {args.repo} not found, or not visible to your gh account", file=sys.stderr)
        return 1
    except GitHubError as error:
        print(f"error: could not fetch {args.repo} from GitHub: {error}", file=sys.stderr)
        return 1
    print(f"open PRs: {len(data.open_prs)}")
    print(f"merged PRs: {len(data.merged_prs)}")
    print(f"issues: {len(data.issues)}")
    return 0

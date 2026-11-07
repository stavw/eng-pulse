"""Bucket rules from SPEC.md, as pure functions: no I/O, no clock. Callers pass `now`."""

from datetime import datetime, timedelta

from eng_pulse.github import PullRequest


def _is_eligible(pr: PullRequest) -> bool:
    """Bots and drafts are left out of every section."""
    return not pr.author_is_bot and not pr.is_draft


def shipped(merged_prs: list[PullRequest], days: int, now: datetime) -> list[PullRequest]:
    """PRs merged in the window, which includes its exact start."""
    since = now - timedelta(days=days)
    return [
        pr
        for pr in merged_prs
        if _is_eligible(pr) and pr.merged_at is not None and pr.merged_at >= since
    ]

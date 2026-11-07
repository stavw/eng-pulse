"""Bucket rules from SPEC.md, as pure functions: no I/O, no clock. Callers pass `now`."""

from datetime import datetime, timedelta

from eng_pulse.github import PullRequest


_FAILING_CHECK_STATES = {"FAILURE", "ERROR"}
_IN_PROGRESS_WINDOW = timedelta(days=3)
_STUCK_AFTER = timedelta(days=7)


def _is_eligible(pr: PullRequest) -> bool:
    """Bots and drafts are left out of every section."""
    return not pr.author_is_bot and not pr.is_draft


def _has_failing_checks(pr: PullRequest) -> bool:
    """Pending or missing checks don't count as failing."""
    return pr.check_state in _FAILING_CHECK_STATES


def shipped(merged_prs: list[PullRequest], days: int, now: datetime) -> list[PullRequest]:
    """PRs merged in the window, which includes its exact start."""
    since = now - timedelta(days=days)
    return [
        pr
        for pr in merged_prs
        if _is_eligible(pr) and pr.merged_at is not None and pr.merged_at >= since
    ]


def in_progress(open_prs: list[PullRequest], now: datetime) -> list[PullRequest]:
    """Open PRs updated under 3 days ago. Failing ones belong to Stuck instead."""
    return [
        pr
        for pr in open_prs
        if _is_eligible(pr)
        and not _has_failing_checks(pr)
        and now - pr.updated_at < _IN_PROGRESS_WINDOW
    ]


def stuck(open_prs: list[PullRequest], now: datetime) -> list[PullRequest]:
    """Open PRs with no update for 7+ days or failing checks, in the order given."""
    return [
        pr
        for pr in open_prs
        if _is_eligible(pr)
        and (_has_failing_checks(pr) or now - pr.updated_at >= _STUCK_AFTER)
    ]

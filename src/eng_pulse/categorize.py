"""Bucket rules from SPEC.md, as pure functions: no I/O, no clock. Callers pass `now`."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from eng_pulse.github import Issue, PullRequest, RepoData


_FAILING_CHECK_STATES = {"FAILURE", "ERROR"}
_IN_PROGRESS_WINDOW = timedelta(days=3)
_STUCK_AFTER = timedelta(days=7)
_RISK_LABEL_TERMS = ("bug", "regression")


@dataclass(frozen=True)
class Buckets:
    shipped: list[PullRequest]
    in_progress: list[PullRequest]
    stuck: list[PullRequest]
    risks: list[Issue]


def _is_eligible(pr: PullRequest) -> bool:
    """Bots and drafts are left out of every section."""
    return not pr.author_is_bot and not pr.is_draft


def has_failing_checks(pr: PullRequest) -> bool:
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
        and not has_failing_checks(pr)
        and now - pr.updated_at < _IN_PROGRESS_WINDOW
    ]


def stuck(open_prs: list[PullRequest], now: datetime) -> list[PullRequest]:
    """Open PRs with no update for 7+ days or failing checks, most recently updated first.

    Returns every match. The top-15 limit is for display, which also needs the total.
    """
    matches = [
        pr
        for pr in open_prs
        if _is_eligible(pr)
        and (has_failing_checks(pr) or now - pr.updated_at >= _STUCK_AFTER)
    ]
    return sorted(matches, key=lambda pr: pr.updated_at, reverse=True)


def _has_risk_label(issue: Issue) -> bool:
    return any(
        term in label.lower() for label in issue.labels for term in _RISK_LABEL_TERMS
    )


def risks(open_issues: list[Issue], days: int, now: datetime) -> list[Issue]:
    """Open issues opened in the window whose label name contains a risk term."""
    since = now - timedelta(days=days)
    return [
        issue
        for issue in open_issues
        if not issue.author_is_bot and issue.created_at >= since and _has_risk_label(issue)
    ]


def categorize(data: RepoData, days: int, now: datetime) -> Buckets:
    return Buckets(
        shipped=shipped(data.merged_prs, days, now),
        in_progress=in_progress(data.open_prs, now),
        stuck=stuck(data.open_prs, now),
        risks=risks(data.issues, days, now),
    )

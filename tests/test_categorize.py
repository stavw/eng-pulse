from datetime import UTC, datetime, timedelta

from eng_pulse.categorize import in_progress, shipped
from eng_pulse.github import PullRequest

NOW = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


def _pr(
    number: int = 1,
    updated_at: datetime = NOW,
    merged_at: datetime | None = None,
    check_state: str | None = "SUCCESS",
    is_draft: bool = False,
    author_is_bot: bool = False,
) -> PullRequest:
    return PullRequest(
        number=number,
        title=f"PR {number}",
        url=f"https://github.com/acme/widgets/pull/{number}",
        author="dependabot" if author_is_bot else "alice",
        author_is_bot=author_is_bot,
        created_at=NOW - timedelta(days=30),
        updated_at=updated_at,
        labels=(),
        merged_at=merged_at,
        is_draft=is_draft,
        check_state=check_state,
    )


def test_shipped_includes_pr_merged_inside_the_window():
    pr = _pr(merged_at=NOW - timedelta(days=1))

    assert shipped([pr], days=7, now=NOW) == [pr]


def test_shipped_includes_pr_merged_exactly_at_the_window_start():
    pr = _pr(merged_at=NOW - timedelta(days=7))

    assert shipped([pr], days=7, now=NOW) == [pr]


def test_shipped_excludes_pr_merged_just_before_the_window():
    pr = _pr(merged_at=NOW - timedelta(days=7, seconds=1))

    assert shipped([pr], days=7, now=NOW) == []


def test_shipped_window_follows_days():
    pr = _pr(merged_at=NOW - timedelta(days=2))

    assert shipped([pr], days=1, now=NOW) == []
    assert shipped([pr], days=2, now=NOW) == [pr]


def test_shipped_excludes_unmerged_pr():
    assert shipped([_pr(merged_at=None)], days=7, now=NOW) == []


def test_shipped_excludes_bots():
    pr = _pr(merged_at=NOW - timedelta(days=1), author_is_bot=True)

    assert shipped([pr], days=7, now=NOW) == []


def test_shipped_excludes_drafts():
    pr = _pr(merged_at=NOW - timedelta(days=1), is_draft=True)

    assert shipped([pr], days=7, now=NOW) == []


def test_in_progress_includes_pr_updated_just_under_3_days_ago():
    pr = _pr(updated_at=NOW - timedelta(days=3) + timedelta(seconds=1))

    assert in_progress([pr], now=NOW) == [pr]


def test_in_progress_excludes_pr_updated_exactly_3_days_ago():
    assert in_progress([_pr(updated_at=NOW - timedelta(days=3))], now=NOW) == []


def test_in_progress_excludes_pr_updated_over_3_days_ago():
    assert in_progress([_pr(updated_at=NOW - timedelta(days=5))], now=NOW) == []


def test_in_progress_excludes_recent_pr_with_failing_checks():
    for state in ("FAILURE", "ERROR"):
        assert in_progress([_pr(check_state=state)], now=NOW) == []


def test_in_progress_includes_recent_pr_with_pending_or_missing_checks():
    prs = [_pr(1, check_state="PENDING"), _pr(2, check_state="EXPECTED"), _pr(3, check_state=None)]

    assert in_progress(prs, now=NOW) == prs


def test_in_progress_excludes_bots():
    assert in_progress([_pr(author_is_bot=True)], now=NOW) == []


def test_in_progress_excludes_drafts():
    assert in_progress([_pr(is_draft=True)], now=NOW) == []

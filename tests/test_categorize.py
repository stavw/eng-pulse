from datetime import UTC, datetime, timedelta

from eng_pulse.categorize import categorize, in_progress, risks, shipped, stuck
from eng_pulse.github import Issue, PullRequest, RepoData

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


def _issue(
    number: int = 1,
    created_at: datetime = NOW,
    labels: tuple[str, ...] = ("bug",),
    author_is_bot: bool = False,
) -> Issue:
    return Issue(
        number=number,
        title=f"Issue {number}",
        url=f"https://github.com/acme/widgets/issues/{number}",
        author="dependabot" if author_is_bot else "alice",
        author_is_bot=author_is_bot,
        created_at=created_at,
        updated_at=created_at,
        labels=labels,
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


def test_stuck_includes_pr_updated_exactly_7_days_ago():
    pr = _pr(updated_at=NOW - timedelta(days=7))

    assert stuck([pr], now=NOW) == [pr]


def test_stuck_excludes_passing_pr_updated_just_under_7_days_ago():
    pr = _pr(updated_at=NOW - timedelta(days=7) + timedelta(seconds=1))

    assert stuck([pr], now=NOW) == []


def test_stuck_excludes_passing_pr_updated_exactly_3_days_ago():
    assert stuck([_pr(updated_at=NOW - timedelta(days=3))], now=NOW) == []


def test_stuck_includes_failing_pr_however_recently_updated():
    for state in ("FAILURE", "ERROR"):
        for age in (timedelta(0), timedelta(days=3), timedelta(days=5)):
            pr = _pr(updated_at=NOW - age, check_state=state)

            assert stuck([pr], now=NOW) == [pr]


def test_stuck_excludes_recent_pr_with_pending_or_missing_checks():
    prs = [_pr(1, check_state="PENDING"), _pr(2, check_state="EXPECTED"), _pr(3, check_state=None)]

    assert stuck(prs, now=NOW) == []


def test_stuck_includes_stale_pr_with_pending_or_missing_checks():
    stale = NOW - timedelta(days=30)
    prs = [_pr(1, updated_at=stale, check_state="PENDING"), _pr(2, updated_at=stale, check_state=None)]

    assert stuck(prs, now=NOW) == prs


def test_stuck_excludes_bots_even_if_stale_or_failing():
    stale = _pr(1, updated_at=NOW - timedelta(days=30), author_is_bot=True)
    failing = _pr(2, check_state="FAILURE", author_is_bot=True)

    assert stuck([stale, failing], now=NOW) == []


def test_stuck_excludes_drafts_even_if_stale_or_failing():
    stale = _pr(1, updated_at=NOW - timedelta(days=30), is_draft=True)
    failing = _pr(2, check_state="FAILURE", is_draft=True)

    assert stuck([stale, failing], now=NOW) == []


def test_stuck_returns_every_match_so_the_total_count_stays_available():
    prs = [_pr(n, check_state="FAILURE") for n in range(20)]

    assert stuck(prs, now=NOW) == prs


def test_stuck_sorts_most_recently_updated_first():
    oldest = _pr(1, updated_at=NOW - timedelta(days=60))
    newest = _pr(2, updated_at=NOW - timedelta(hours=1), check_state="FAILURE")
    middle = _pr(3, updated_at=NOW - timedelta(days=8))

    assert stuck([oldest, newest, middle], now=NOW) == [newest, middle, oldest]


def test_risks_match_any_label_containing_bug_or_regression_in_any_case():
    names = ["bug", "Type: Bug", "BUG", "Regression", "perf-regression", "Type: Regression"]
    issues = [_issue(n, labels=(name,)) for n, name in enumerate(names)]

    assert risks(issues, days=7, now=NOW) == issues


def test_risks_contains_match_also_catches_debug_labels():
    issue = _issue(labels=("INTERNAL: Debug",))

    assert risks([issue], days=7, now=NOW) == [issue]


def test_risks_match_when_only_one_of_several_labels_qualifies():
    issue = _issue(labels=("area-auth", "Type: Bug"))

    assert risks([issue], days=7, now=NOW) == [issue]


def test_risks_excludes_issue_without_a_matching_label():
    issues = [_issue(1, labels=()), _issue(2, labels=("enhancement", "area-auth"))]

    assert risks(issues, days=7, now=NOW) == []


def test_risks_includes_issue_opened_exactly_at_the_window_start():
    issue = _issue(created_at=NOW - timedelta(days=7))

    assert risks([issue], days=7, now=NOW) == [issue]


def test_risks_excludes_issue_opened_just_before_the_window():
    issue = _issue(created_at=NOW - timedelta(days=7, seconds=1))

    assert risks([issue], days=7, now=NOW) == []


def test_risks_window_follows_days():
    issue = _issue(created_at=NOW - timedelta(days=2))

    assert risks([issue], days=1, now=NOW) == []
    assert risks([issue], days=2, now=NOW) == [issue]


def test_risks_excludes_bots():
    assert risks([_issue(author_is_bot=True)], days=7, now=NOW) == []


def test_categorize_puts_each_item_in_its_bucket():
    merged = _pr(1, merged_at=NOW - timedelta(days=1))
    active = _pr(2, updated_at=NOW - timedelta(days=1))
    quiet = _pr(3, updated_at=NOW - timedelta(days=8))
    between = _pr(4, updated_at=NOW - timedelta(days=5))
    issue = _issue(5)
    data = RepoData(open_prs=[active, quiet, between], merged_prs=[merged], issues=[issue])

    buckets = categorize(data, days=7, now=NOW)

    assert buckets.shipped == [merged]
    assert buckets.in_progress == [active]
    assert buckets.stuck == [quiet]
    assert buckets.risks == [issue]


def test_categorize_passes_days_and_now_through():
    merged = _pr(1, merged_at=NOW - timedelta(days=2))
    issue = _issue(2, created_at=NOW - timedelta(days=2))
    pr = _pr(3, updated_at=NOW - timedelta(days=1))
    data = RepoData(open_prs=[pr], merged_prs=[merged], issues=[issue])

    narrow = categorize(data, days=1, now=NOW)
    later = categorize(data, days=7, now=NOW + timedelta(days=30))

    assert narrow.shipped == [] and narrow.risks == []
    assert later.in_progress == [] and later.stuck == [pr]

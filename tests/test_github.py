from datetime import UTC, datetime, timedelta

import pytest

from eng_pulse.github import (
    GitHubError,
    RepoNotFoundError,
    fetch_issues,
    fetch_merged_prs,
    fetch_open_prs,
    fetch_repo_data,
    run_gh,
)

REPO = "acme/widgets"
NOW = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
SINCE = NOW - timedelta(days=7)


def _open_pr_node(number: int) -> dict:
    return {
        "number": number,
        "title": f"PR {number}",
        "url": f"https://github.com/acme/widgets/pull/{number}",
        "createdAt": "2026-01-10T09:00:00Z",
        "updatedAt": "2026-01-14T10:00:00Z",
        "author": {"login": "alice", "__typename": "User"},
        "labels": {"nodes": []},
        "isDraft": False,
        "mergedAt": None,
        "commits": {"nodes": []},
    }


def test_stale_open_pr_is_returned_even_with_a_one_day_window(gh):
    gh.queue_fixture("open_prs_page1", "open_prs_page2")
    gh.queue_page([])
    gh.queue_page([])

    data = fetch_repo_data(REPO, days=1, now=NOW)

    stale = next(pr for pr in data.open_prs if pr.number == 50)
    assert stale.updated_at == datetime(2024, 1, 15, 12, 0, tzinfo=UTC)


def test_open_prs_follow_pages_past_the_gh_default_of_30(gh):
    gh.queue_page([_open_pr_node(n) for n in range(30)], cursor="next")
    gh.queue_page([_open_pr_node(n) for n in range(30, 35)])

    prs = fetch_open_prs(REPO)

    assert len(prs) == 35
    assert len(gh.calls) == 2


def test_second_page_request_passes_the_cursor(gh):
    gh.queue_fixture("open_prs_page1", "open_prs_page2")

    fetch_open_prs(REPO)

    first, second = gh.calls
    assert first[:3] == ["gh", "api", "graphql"]
    assert "owner=acme" in first and "name=widgets" in first
    assert not any(arg.startswith("cursor=") for arg in first)
    assert "cursor=open-cursor-1" in second


def test_merged_prs_filter_on_merge_time_and_stop_paging_at_the_window(gh):
    # merged_prs_page2 says there are more pages; a third request would fail the test.
    gh.queue_fixture("merged_prs_page1", "merged_prs_page2")

    prs = fetch_merged_prs(REPO, SINCE)

    assert [pr.number for pr in prs] == [201, 203]


def test_issues_filter_on_created_time_and_stop_paging_at_the_window(gh):
    # issues_page1 says there are more pages; a second request would fail the test.
    gh.queue_fixture("issues_page1")

    issues = fetch_issues(REPO, SINCE)

    assert [issue.number for issue in issues] == [301]


def test_pull_request_fields_are_mapped(gh):
    gh.queue_fixture("open_prs_page1", "open_prs_page2")

    pr = fetch_open_prs(REPO)[0]

    assert pr.number == 101
    assert pr.title == "Add retry to client"
    assert pr.url == "https://github.com/acme/widgets/pull/101"
    assert pr.author == "alice"
    assert pr.author_is_bot is False
    assert pr.created_at == datetime(2026, 1, 10, 9, 0, tzinfo=UTC)
    assert pr.updated_at == datetime(2026, 1, 14, 10, 0, tzinfo=UTC)
    assert pr.merged_at is None
    assert pr.labels == ("enhancement", "area-client")
    assert pr.is_draft is False
    assert pr.check_state == "SUCCESS"


def test_merged_time_is_mapped(gh):
    gh.queue_fixture("merged_prs_page1", "merged_prs_page2")

    pr = fetch_merged_prs(REPO, SINCE)[0]

    assert pr.merged_at == datetime(2026, 1, 14, 14, 0, tzinfo=UTC)


def test_issue_fields_are_mapped(gh):
    gh.queue_fixture("issues_page1")

    issue = fetch_issues(REPO, SINCE)[0]

    assert issue.url == "https://github.com/acme/widgets/issues/301"
    assert issue.author == "dave"
    assert issue.labels == ("Type: Bug",)


def test_bot_author_is_flagged_and_kept(gh):
    gh.queue_fixture("open_prs_page1", "open_prs_page2")

    bot_pr = fetch_open_prs(REPO)[1]

    assert bot_pr.author == "dependabot"
    assert bot_pr.author_is_bot is True
    assert bot_pr.is_draft is True
    assert bot_pr.check_state == "FAILURE"


def test_deleted_author_becomes_ghost_and_is_not_a_bot(gh):
    gh.queue_fixture("open_prs_page1", "open_prs_page2")

    pr = fetch_open_prs(REPO)[2]

    assert pr.author == "ghost"
    assert pr.author_is_bot is False


def test_missing_check_data_is_none(gh):
    gh.queue_fixture("open_prs_page1", "open_prs_page2")

    assert fetch_open_prs(REPO)[2].check_state is None


def test_commit_list_with_no_commits_gives_no_check_state(gh):
    gh.queue_fixture("merged_prs_page1", "merged_prs_page2")

    assert fetch_merged_prs(REPO, SINCE)[1].check_state is None


def test_times_are_utc_even_if_the_response_uses_an_offset(gh):
    node = _open_pr_node(1) | {"updatedAt": "2026-01-14T14:00:00+02:00"}
    gh.queue_page([node])

    pr = fetch_open_prs(REPO)[0]

    assert pr.updated_at == datetime(2026, 1, 14, 12, 0, tzinfo=UTC)
    assert pr.updated_at.utcoffset() == timedelta(0)


def _queue_full_repo(gh) -> None:
    gh.queue_fixture(
        "open_prs_page1",
        "open_prs_page2",
        "merged_prs_page1",
        "merged_prs_page2",
        "issues_page1",
    )


def test_same_now_gives_the_same_result(gh):
    _queue_full_repo(gh)
    first = fetch_repo_data(REPO, days=7, now=NOW)
    _queue_full_repo(gh)
    second = fetch_repo_data(REPO, days=7, now=NOW)

    assert first == second
    assert [pr.number for pr in first.merged_prs] == [201, 203]
    assert [issue.number for issue in first.issues] == [301]


def test_window_comes_from_the_now_argument_not_the_clock(gh):
    gh.queue_page([])
    gh.queue_page([])
    gh.queue_fixture("issues_page1")
    gh.queue_page([])  # Issue 302 is now exactly on the boundary, so paging continues.

    data = fetch_repo_data(REPO, days=7, now=NOW - timedelta(seconds=1))

    assert [issue.number for issue in data.issues] == [301, 302]


def test_unknown_repo_raises_repo_not_found(gh):
    gh.queue_failure("gh: Could not resolve to a Repository with the name 'acme/nope'. (repository)")

    with pytest.raises(RepoNotFoundError):
        run_gh(["api", "graphql"])


def test_other_gh_failure_raises_github_error_with_its_message(gh):
    gh.queue_failure("HTTP 504: 504 Gateway Timeout (https://api.github.com/graphql)")

    with pytest.raises(GitHubError, match="504") as caught:
        run_gh(["api", "graphql"])

    assert not isinstance(caught.value, RepoNotFoundError)


def test_failure_with_no_stderr_still_has_a_message(gh):
    gh.queue_failure("")

    with pytest.raises(GitHubError, match="exited with code 1"):
        run_gh(["api", "graphql"])


def test_missing_gh_executable_raises_github_error(gh):
    gh.queue_error(FileNotFoundError("gh"))

    with pytest.raises(GitHubError, match="not installed"):
        run_gh(["api", "graphql"])


def test_unqueued_subprocess_call_fails_the_test(gh):
    with pytest.raises(AssertionError, match="unexpected subprocess call"):
        run_gh(["api", "graphql"])

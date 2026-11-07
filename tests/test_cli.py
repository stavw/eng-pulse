from datetime import datetime, timedelta

import pytest

from eng_pulse.cli import main
from eng_pulse.github import RepoData


@pytest.mark.parametrize("repo", ["fastapi", "a/b/c", "bad name/repo", "owner/bad name", "/repo", "owner/", ""])
def test_bad_repo_name_exits_non_zero_without_calling_gh(gh, capsys, repo):
    with pytest.raises(SystemExit) as caught:
        main([repo])

    assert caught.value.code != 0
    assert "invalid repo name" in capsys.readouterr().err
    assert gh.calls == []


@pytest.mark.parametrize("days", ["0", "-1", "abc", "1.5"])
def test_invalid_days_exits_non_zero_without_calling_gh(gh, capsys, days):
    with pytest.raises(SystemExit) as caught:
        main(["acme/widgets", "--days", days])

    assert caught.value.code != 0
    assert "must be a whole number of 1 or more" in capsys.readouterr().err
    assert gh.calls == []


def test_unknown_repo_exits_non_zero_with_a_clear_message(gh, capsys):
    gh.queue_failure("gh: Could not resolve to a Repository with the name 'acme/nope'. (repository)")

    assert main(["acme/nope"]) == 1

    captured = capsys.readouterr()
    assert "repo acme/nope not found" in captured.err
    assert captured.out == ""


def test_failure_part_way_through_prints_no_partial_output(gh, capsys):
    gh.queue_fixture("open_prs_page1")
    gh.queue_failure("HTTP 504: 504 Gateway Timeout (https://api.github.com/graphql)")

    assert main(["acme/widgets"]) == 1

    captured = capsys.readouterr()
    assert "504 Gateway Timeout" in captured.err
    assert captured.out == ""


def test_logged_out_gh_exits_non_zero_with_its_message(gh, capsys):
    gh.queue_failure("To get started with GitHub CLI, please run:  gh auth login")

    assert main(["acme/widgets"]) == 1

    assert "gh auth login" in capsys.readouterr().err


def test_missing_gh_exits_non_zero(gh, capsys):
    gh.queue_error(FileNotFoundError("gh"))

    assert main(["acme/widgets"]) == 1

    assert "gh CLI is not installed" in capsys.readouterr().err


def test_success_prints_counts_and_exits_zero(gh, capsys):
    gh.queue_fixture("open_prs_page1", "open_prs_page2")
    gh.queue_page([])
    gh.queue_page([])

    assert main(["acme/widgets", "--days", "1"]) == 0

    assert capsys.readouterr().out.splitlines() == ["open PRs: 3", "merged PRs: 0", "issues: 0"]


def test_days_defaults_to_seven_and_now_is_passed_in_as_utc(monkeypatch):
    calls = []

    def fake_fetch(repo: str, days: int, now: datetime) -> RepoData:
        calls.append((repo, days, now))
        return RepoData(open_prs=[], merged_prs=[], issues=[])

    monkeypatch.setattr("eng_pulse.cli.fetch_repo_data", fake_fetch)

    assert main(["acme/widgets"]) == 0

    [(repo, days, now)] = calls
    assert (repo, days) == ("acme/widgets", 7)
    assert now.utcoffset() == timedelta(0)

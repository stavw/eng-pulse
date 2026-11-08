from dataclasses import replace
from datetime import UTC, datetime, timedelta

from eng_pulse.categorize import Buckets
from eng_pulse.formatting import format_digest
from eng_pulse.github import Issue, PullRequest

NOW = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
REPO = "acme/widgets"


def _pr(
    number: int = 1,
    title: str | None = None,
    author: str = "alice",
    created_at: datetime = NOW,
    merged_at: datetime | None = None,
) -> PullRequest:
    return PullRequest(
        number=number,
        title=title or f"PR {number}",
        url=f"https://github.com/acme/widgets/pull/{number}",
        author=author,
        author_is_bot=False,
        created_at=created_at,
        updated_at=created_at,
        labels=(),
        merged_at=merged_at,
        is_draft=False,
        check_state="SUCCESS",
    )


def _issue(
    number: int = 1,
    title: str | None = None,
    author: str = "dave",
    created_at: datetime = NOW,
) -> Issue:
    return Issue(
        number=number,
        title=title or f"Issue {number}",
        url=f"https://github.com/acme/widgets/issues/{number}",
        author=author,
        author_is_bot=False,
        created_at=created_at,
        updated_at=created_at,
        labels=("bug",),
    )


def _buckets(
    shipped: list[PullRequest] | None = None,
    in_progress: list[PullRequest] | None = None,
    stuck: list[PullRequest] | None = None,
    risks: list[Issue] | None = None,
) -> Buckets:
    return Buckets(
        shipped=shipped or [],
        in_progress=in_progress or [],
        stuck=stuck or [],
        risks=risks or [],
    )


def _digest(buckets: Buckets, days: int = 7) -> str:
    return format_digest(REPO, days, buckets, NOW)


def _age_shown(item: PullRequest) -> str:
    """The age on the item's line, read from a digest where it's the only In progress item."""
    line = next(line for line in _digest(_buckets(in_progress=[item])).splitlines() if line.startswith("- "))
    return line.rsplit(" · ", 1)[1]


def test_full_digest_matches_the_expected_text():
    buckets = _buckets(
        shipped=[
            _pr(
                201,
                "Fix login redirect",
                "bob",
                created_at=NOW - timedelta(days=5),
                merged_at=NOW - timedelta(days=2),
            )
        ],
        in_progress=[_pr(101, "Add retry to client", created_at=NOW - timedelta(hours=5))],
        stuck=[_pr(90, "Abandoned refactor", "carol", created_at=NOW - timedelta(days=12))],
        risks=[_issue(301, "Crash on startup", created_at=NOW - timedelta(minutes=30))],
    )

    assert _digest(buckets) == """\
# eng-pulse: acme/widgets

Period: 2026-01-08 to 2026-01-15 UTC (last 7 days)
Generated: 2026-01-15 12:00 UTC

## Shipped

- [#201 Fix login redirect](https://github.com/acme/widgets/pull/201) · @bob · 5d · merged 2d ago

## In progress

- [#101 Add retry to client](https://github.com/acme/widgets/pull/101) · @alice · 5h

## Stuck

- [#90 Abandoned refactor](https://github.com/acme/widgets/pull/90) · @carol · 12d · idle 12d

## Risks

- [#301 Crash on startup](https://github.com/acme/widgets/issues/301) · @dave · <1h

---

Shipped: 1 · In progress: 1 · Stuck: 1 · Risks: 1"""


def test_empty_sections_show_none_and_zero_counts():
    assert _digest(_buckets()) == """\
# eng-pulse: acme/widgets

Period: 2026-01-08 to 2026-01-15 UTC (last 7 days)
Generated: 2026-01-15 12:00 UTC

## Shipped

None

## In progress

None

## Stuck

None

## Risks

None

---

Shipped: 0 · In progress: 0 · Stuck: 0 · Risks: 0"""


def _stuck_lines(count: int) -> list[str]:
    digest = _digest(_buckets(stuck=[_pr(n) for n in range(1, count + 1)]))
    section = digest.split("## Stuck\n\n")[1].split("\n\n## Risks")[0]
    return section.splitlines()


def test_stuck_with_exactly_15_items_has_no_more_line():
    lines = _stuck_lines(15)

    assert len(lines) == 15
    assert all(line.startswith("- ") for line in lines)


def test_stuck_with_16_items_shows_15_and_one_more():
    lines = _stuck_lines(16)

    assert len(lines) == 16
    assert lines[-1] == "…and 1 more"


def test_stuck_with_18_items_shows_the_first_15_and_counts_all_in_the_footer():
    lines = _stuck_lines(18)

    assert lines[0].startswith("- [#1 ")
    assert lines[14].startswith("- [#15 ")
    assert lines[15] == "…and 3 more"
    digest = _digest(_buckets(stuck=[_pr(n) for n in range(1, 19)]))
    assert digest.endswith("Stuck: 18 · Risks: 0")


def test_stuck_keeps_the_order_it_is_given():
    digest = _digest(_buckets(stuck=[_pr(3), _pr(1), _pr(2)]))
    numbers = [line.split()[1] for line in digest.splitlines() if line.startswith("- ")]
    assert numbers == ["[#3", "[#1", "[#2"]


def test_stuck_lines_end_with_the_reason():
    opened = NOW - timedelta(days=30)
    failing_recent = replace(
        _pr(1, created_at=opened), updated_at=NOW - timedelta(hours=5), check_state="FAILURE"
    )
    idle = replace(_pr(2, created_at=opened), updated_at=NOW - timedelta(days=12))
    failing_and_idle = replace(
        _pr(3, created_at=opened), updated_at=NOW - timedelta(days=9), check_state="ERROR"
    )

    digest = _digest(_buckets(stuck=[failing_recent, idle, failing_and_idle]))

    assert [line for line in digest.splitlines() if line.startswith("- ")] == [
        "- [#1 PR 1](https://github.com/acme/widgets/pull/1) · @alice · 30d · failing checks, idle 5h",
        "- [#2 PR 2](https://github.com/acme/widgets/pull/2) · @alice · 30d · idle 12d",
        "- [#3 PR 3](https://github.com/acme/widgets/pull/3) · @alice · 30d · failing checks, idle 9d",
    ]


def test_other_sections_are_not_limited():
    prs = [_pr(n) for n in range(1, 21)]

    digest = _digest(_buckets(shipped=prs, in_progress=prs))

    assert sum(line.startswith("- ") for line in digest.splitlines()) == 40
    assert "more" not in digest


def test_age_boundaries():
    cases = {
        timedelta(minutes=59, seconds=59): "<1h",
        timedelta(hours=1): "1h",
        timedelta(hours=23, minutes=59, seconds=59): "23h",
        timedelta(hours=24): "1d",
        timedelta(days=2, hours=23): "2d",
    }
    for age, expected in cases.items():
        assert _age_shown(_pr(created_at=NOW - age)) == expected


def test_item_created_at_now_is_under_an_hour_old():
    assert _age_shown(_pr(created_at=NOW)) == "<1h"


def test_recency_uses_the_same_format_as_age():
    cases = {timedelta(minutes=30): "merged <1h ago", timedelta(hours=5): "merged 5h ago"}
    for since_merge, expected in cases.items():
        pr = _pr(created_at=NOW - timedelta(days=3), merged_at=NOW - since_merge)

        line = next(line for line in _digest(_buckets(shipped=[pr])).splitlines() if line.startswith("- "))

        assert line.endswith(f" · 3d · {expected}")


def test_shipped_line_shows_age_since_opened_and_recency_since_merge():
    pr = _pr(201, created_at=NOW - timedelta(days=5), merged_at=NOW - timedelta(days=2))

    digest = _digest(_buckets(shipped=[pr]))

    line = next(line for line in digest.splitlines() if line.startswith("- [#201 "))
    fields = line.split(" · ")
    assert fields[1] == "@alice"
    assert fields[2] == "5d"
    assert len(fields) == 4 and "2d" in fields[3]


def test_open_pr_and_issue_age_run_to_now():
    created = NOW - timedelta(days=30)

    digest = _digest(_buckets(stuck=[_pr(1, created_at=created)], risks=[_issue(2, created_at=created)]))

    item_lines = [line for line in digest.splitlines() if line.startswith("- ")]
    assert [line.split(" · ")[2] for line in item_lines] == ["30d", "30d"]


def test_title_with_brackets_is_printed_unchanged():
    digest = _digest(_buckets(in_progress=[_pr(7, "[Blazor] Fix `render_tree` crash")]))

    assert "- [#7 [Blazor] Fix `render_tree` crash](https://github.com/acme/widgets/pull/7) · " in digest


def test_header_date_range_follows_days():
    digest = _digest(_buckets(), days=1)

    assert "Period: 2026-01-14 to 2026-01-15 UTC (last 1 day)\n" in digest

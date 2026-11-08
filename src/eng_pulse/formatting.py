"""Renders the digest as Markdown. Pure: no printing, no clock. Callers pass `now`."""

from collections.abc import Callable, Sequence
from datetime import datetime, timedelta

from eng_pulse.categorize import Buckets, has_failing_checks
from eng_pulse.github import Issue, PullRequest

_STUCK_LIMIT = 15
_DATE_FORMAT = "%Y-%m-%d"


def _format_age(age: timedelta) -> str:
    if age < timedelta(hours=1):
        return "<1h"
    if age < timedelta(days=1):
        return f"{age // timedelta(hours=1)}h"
    return f"{age.days}d"


def _item_line(item: Issue, now: datetime) -> str:
    """Age is time since opening; a merged PR also shows recency, the time since merge."""
    age = _format_age(now - item.created_at)
    line = f"- [#{item.number} {item.title}]({item.url}) · @{item.author} · {age}"
    if isinstance(item, PullRequest) and item.merged_at:
        line += f" · merged {_format_age(now - item.merged_at)} ago"
    return line


def _stuck_line(pr: PullRequest, now: datetime) -> str:
    """The item line plus why it's stuck. Idle is time since the last update."""
    idle = f"idle {_format_age(now - pr.updated_at)}"
    reason = f"failing checks, {idle}" if has_failing_checks(pr) else idle
    return f"{_item_line(pr, now)} · {reason}"


def _section[T: Issue](
    title: str,
    items: Sequence[T],
    now: datetime,
    limit: int | None = None,
    line: Callable[[T, datetime], str] = _item_line,
) -> str:
    shown = items[:limit]
    lines = [line(item, now) for item in shown]
    if len(items) > len(shown):
        lines.append(f"…and {len(items) - len(shown)} more")
    body = "\n".join(lines) or "None"
    return f"## {title}\n\n{body}"


def _header(repo: str, days: int, now: datetime) -> str:
    since = now - timedelta(days=days)
    window = "last 1 day" if days == 1 else f"last {days} days"
    period = f"{since.strftime(_DATE_FORMAT)} to {now.strftime(_DATE_FORMAT)} UTC ({window})"
    generated = now.strftime(f"{_DATE_FORMAT} %H:%M UTC")
    return f"# eng-pulse: {repo}\n\nPeriod: {period}\nGenerated: {generated}"


def _footer(buckets: Buckets) -> str:
    return (
        f"Shipped: {len(buckets.shipped)} · In progress: {len(buckets.in_progress)}"
        f" · Stuck: {len(buckets.stuck)} · Risks: {len(buckets.risks)}"
        f" · Abandoned: {len(buckets.abandoned)}"
    )


def format_digest(repo: str, days: int, buckets: Buckets, now: datetime) -> str:
    """Render the digest. `now` must be in UTC."""
    parts = [
        _header(repo, days, now),
        _section("Shipped", buckets.shipped, now),
        _section("In progress", buckets.in_progress, now),
        _section("Stuck", buckets.stuck, now, limit=_STUCK_LIMIT, line=_stuck_line),
        _section("Risks", buckets.risks, now),
        "---",
        _footer(buckets),
    ]
    return "\n\n".join(parts)

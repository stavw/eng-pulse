"""Renders the digest as Markdown. Pure: no printing, no clock. Callers pass `now`."""

from collections.abc import Sequence
from datetime import datetime, timedelta

from eng_pulse.categorize import Buckets
from eng_pulse.github import Issue, PullRequest

_STUCK_LIMIT = 15
_DATE_FORMAT = "%Y-%m-%d"


def _format_age(age: timedelta) -> str:
    if age < timedelta(hours=1):
        return "<1h"
    if age < timedelta(days=1):
        return f"{age // timedelta(hours=1)}h"
    return f"{age.days}d"


def _age(item: Issue, now: datetime) -> timedelta:
    """Time since creation, stopping at the merge for a merged PR."""
    end = item.merged_at if isinstance(item, PullRequest) and item.merged_at else now
    return end - item.created_at


def _item_line(item: Issue, now: datetime) -> str:
    age = _format_age(_age(item, now))
    return f"- [#{item.number} {item.title}]({item.url}) · @{item.author} · {age}"


def _section(title: str, items: Sequence[Issue], now: datetime, limit: int | None = None) -> str:
    shown = items[:limit]
    lines = [_item_line(item, now) for item in shown]
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
    )


def format_digest(repo: str, days: int, buckets: Buckets, now: datetime) -> str:
    """Render the digest. `now` must be in UTC."""
    parts = [
        _header(repo, days, now),
        _section("Shipped", buckets.shipped, now),
        _section("In progress", buckets.in_progress, now),
        _section("Stuck", buckets.stuck, now, limit=_STUCK_LIMIT),
        _section("Risks", buckets.risks, now),
        "---",
        _footer(buckets),
    ]
    return "\n\n".join(parts)

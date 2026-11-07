"""GitHub access through the `gh` CLI.

Uses `gh api graphql` rather than `gh pr list`, whose `statusCheckRollup` field
returns 504s on busy repos, and never uses search, which fails on renamed repos
(sometimes by returning nothing). Nothing here reads the clock: callers pass `now`.
"""

import json
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

Node = dict[str, Any]

_ITEM_FIELDS = """
  number title url createdAt updatedAt
  author { login __typename }
  labels(first: 30) { nodes { name } }
"""

_PR_FIELDS = (
    _ITEM_FIELDS
    + """
  isDraft mergedAt
  commits(last: 1) { nodes { commit { statusCheckRollup { state } } } }
"""
)


def _page_query(connection: str, arguments: str, fields: str) -> str:
    return f"""
query($owner: String!, $name: String!, $cursor: String) {{
  repository(owner: $owner, name: $name) {{
    items: {connection}(first: 100, after: $cursor, {arguments}) {{
      pageInfo {{ hasNextPage endCursor }}
      nodes {{ {fields} }}
    }}
  }}
}}
"""


_OPEN_PRS_QUERY = _page_query(
    "pullRequests",
    "states: OPEN, orderBy: {field: UPDATED_AT, direction: DESC}",
    _PR_FIELDS,
)
_MERGED_PRS_QUERY = _page_query(
    "pullRequests",
    "states: MERGED, orderBy: {field: UPDATED_AT, direction: DESC}",
    _PR_FIELDS,
)
_ISSUES_QUERY = _page_query(
    "issues",
    "states: OPEN, orderBy: {field: CREATED_AT, direction: DESC}",
    _ITEM_FIELDS,
)


class GitHubError(Exception):
    """A `gh` call failed."""


class RepoNotFoundError(GitHubError):
    """The repo doesn't exist or isn't visible to the logged-in account."""


@dataclass(frozen=True)
class Issue:
    number: int
    title: str
    url: str
    author: str
    author_is_bot: bool
    created_at: datetime
    updated_at: datetime
    labels: tuple[str, ...]


@dataclass(frozen=True)
class PullRequest(Issue):
    merged_at: datetime | None
    is_draft: bool
    check_state: str | None


@dataclass(frozen=True)
class RepoData:
    open_prs: list[PullRequest]
    merged_prs: list[PullRequest]
    issues: list[Issue]


def run_gh(args: list[str]) -> str:
    """Run `gh` and return its stdout, raising GitHubError if it fails."""
    try:
        result = subprocess.run(["gh", *args], capture_output=True, text=True)
    except FileNotFoundError as error:
        raise GitHubError("the gh CLI is not installed") from error
    if result.returncode == 0:
        return result.stdout
    message = result.stderr.strip()
    if "Could not resolve to a Repository" in message:
        raise RepoNotFoundError(message)
    raise GitHubError(message or f"gh exited with code {result.returncode}")


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(UTC)


def _item_fields(node: Node) -> Node:
    author = node["author"]
    return {
        "number": node["number"],
        "title": node["title"],
        "url": node["url"],
        "author": author["login"] if author else "ghost",
        "author_is_bot": bool(author) and author["__typename"] == "Bot",
        "created_at": _parse_time(node["createdAt"]),
        "updated_at": _parse_time(node["updatedAt"]),
        "labels": tuple(label["name"] for label in node["labels"]["nodes"]),
    }


def _check_state(node: Node) -> str | None:
    commits = node["commits"]["nodes"]
    rollup = commits[0]["commit"]["statusCheckRollup"] if commits else None
    return rollup["state"] if rollup else None


def _to_issue(node: Node) -> Issue:
    return Issue(**_item_fields(node))


def _to_pull_request(node: Node) -> PullRequest:
    merged_at = node["mergedAt"]
    return PullRequest(
        **_item_fields(node),
        merged_at=_parse_time(merged_at) if merged_at else None,
        is_draft=node["isDraft"],
        check_state=_check_state(node),
    )


def _pages(repo: str, query: str) -> Iterator[list[Node]]:
    """Yield every page of results. There's no cap, so nothing is silently cut off."""
    owner, name = repo.split("/")
    args = ["api", "graphql", "-f", f"query={query}", "-f", f"owner={owner}", "-f", f"name={name}"]
    cursor = None
    while True:
        cursor_args = ["-f", f"cursor={cursor}"] if cursor else []
        items = json.loads(run_gh(args + cursor_args))["data"]["repository"]["items"]
        yield items["nodes"]
        if not items["pageInfo"]["hasNextPage"]:
            return
        cursor = items["pageInfo"]["endCursor"]


def _nodes_until(repo: str, query: str, sort_field: str, since: datetime) -> Iterator[Node]:
    """Yield nodes newest first, stopping after the page that reaches `since`."""
    for nodes in _pages(repo, query):
        yield from nodes
        if nodes and _parse_time(nodes[-1][sort_field]) < since:
            return


def fetch_open_prs(repo: str) -> list[PullRequest]:
    """Fetch every open PR. There's no date filter, or Stuck would always be empty."""
    return [_to_pull_request(node) for nodes in _pages(repo, _OPEN_PRS_QUERY) for node in nodes]


def fetch_merged_prs(repo: str, since: datetime) -> list[PullRequest]:
    """Fetch PRs merged at or after `since`.

    Paging by `updatedAt` is safe because merging sets it, so a PR merged in the
    window can't sort below one last updated before the window.
    """
    prs = map(_to_pull_request, _nodes_until(repo, _MERGED_PRS_QUERY, "updatedAt", since))
    return [pr for pr in prs if pr.merged_at is not None and pr.merged_at >= since]


def fetch_issues(repo: str, since: datetime) -> list[Issue]:
    """Fetch open issues created at or after `since`."""
    issues = map(_to_issue, _nodes_until(repo, _ISSUES_QUERY, "createdAt", since))
    return [issue for issue in issues if issue.created_at >= since]


def fetch_repo_data(repo: str, days: int, now: datetime) -> RepoData:
    since = now - timedelta(days=days)
    return RepoData(
        open_prs=fetch_open_prs(repo),
        merged_prs=fetch_merged_prs(repo, since),
        issues=fetch_issues(repo, since),
    )

import json
import subprocess
from collections import deque
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


class FakeGh:
    """Stands in for subprocess.run. A call with nothing queued fails the test."""

    def __init__(self) -> None:
        self.responses: deque[subprocess.CompletedProcess[str] | Exception] = deque()
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        if not self.responses:
            raise AssertionError(f"unexpected subprocess call: {args[:3]}")
        response = self.responses.popleft()
        if isinstance(response, Exception):
            raise response
        return response

    def queue_output(self, stdout: str) -> None:
        self.responses.append(subprocess.CompletedProcess([], 0, stdout, ""))

    def queue_fixture(self, *names: str) -> None:
        for name in names:
            self.queue_output((FIXTURES / f"{name}.json").read_text())

    def queue_page(self, nodes: list[dict], cursor: str | None = None) -> None:
        page_info = {"hasNextPage": cursor is not None, "endCursor": cursor}
        items = {"pageInfo": page_info, "nodes": nodes}
        self.queue_output(json.dumps({"data": {"repository": {"items": items}}}))

    def queue_failure(self, stderr: str) -> None:
        self.responses.append(subprocess.CompletedProcess([], 1, "", stderr))

    def queue_error(self, error: Exception) -> None:
        self.responses.append(error)


@pytest.fixture(autouse=True)
def gh(monkeypatch: pytest.MonkeyPatch) -> FakeGh:
    fake = FakeGh()
    monkeypatch.setattr(subprocess, "run", fake)
    return fake

# eng-pulse — Spec

## Problem
A manager needs a weekly pulse on a codebase: what shipped, what's moving, what's stuck and what's risky. Getting that picture today means clicking through PRs and issues or asking people in standups and 1:1s. It's slow and uneven, and stuck work tends to stay hidden until it's late. `eng-pulse` produces that picture from a GitHub repo in one command.

## User
An engineering manager who reads the digest at the start of the week, decides on action items for the team (who to unblock, what to escalate) and prioritizes the week accordingly.

## Inputs
- `owner/name` — required (e.g. `fastapi/fastapi`)
- `--days N` — optional, default 7, must be ≥ 1
- Auth: the `gh` CLI, already logged in. No tokens to manage in v1.
- Errors: invalid repo name, unknown repo or `--days < 1` → clear message, non-zero exit.

## Output
Markdown printed to the terminal:

1. Header — repo, date range, generated-at time
2. **Summary** — 3 sentences + top 3 risks (AI-generated, Day 6)
3. **Shipped** — PRs merged in the window
4. **In progress** — open PRs updated in the last 3 days
5. **Stuck** — open PRs with no update for 7+ days, or failing checks; top 15 shown, plus the total count
6. **Risks** — issues still open whose label name contains `bug` or `regression` (case-insensitive), opened in the window
7. Footer — item counts per section; API cost of the run

Each item: title, author, age, link to the PR or issue.
Bot authors (dependabot, renovate, any `[bot]` account) are excluded.

## Out of scope (v1)
Private repos · multiple repos per run · lines changed · SonarQube or other external quality tools · Jira or any non-GitHub source · writing to files · scheduling.

## Acceptance criteria
1. Every item links to its PR or issue.
2. Runs without errors on `fastapi/fastapi`, `dotnet/aspnetcore` and `facebook/react`.
3. Finishes in under 60 seconds per repo.
4. Spot check: for one repo, bucket placement matches a manual review of 10 items.
5. AI summary costs under $0.05 per run.
6. `uv run pytest` passes.

## Decisions
- Auth via `gh`, not a token: zero setup for v1; revisit if others need to run it.
- Terminal output only: files and scheduling are v2.
- Bucket rules taken from the Day 5 plan; tune after seeing real output on Day 8.
- Removed Sprint/Epic/Story from output: those are Jira concepts; a public GitHub repo has none.
- All bots excluded, not just dependabot: bot PRs add noise without decisions.
- Open PRs are fetched in full, ignoring `--days`; only merged PRs and issues use the window, otherwise Stuck would always be empty.
- A PR with failing checks goes in Stuck, however recently it was updated; Stuck takes priority over In progress.
- Open PRs without failing checks, last updated at least 3 but under 7 days ago, are left out: they fit no bucket.
- Draft PRs are left out of every section.
- Stuck shows the top 15 items plus the total count.
- Pending checks don't count as failing.
- Issues already closed are left out of Risks.
- No retries: a failed GitHub call stops the run with a clear message and a non-zero exit.
- Risk = issue whose label name contains `bug` or `regression`, case-insensitive: an exact match would miss react's `Type: Bug`.

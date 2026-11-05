# CLAUDE.md

Product requirements live in SPEC.md. Read it before planning any change.

## Stack
- Python 3.12, managed with `uv`
- Tests: `pytest` (`uv run pytest`)
- CLI entry point: `eng-pulse`
- GitHub data via the `gh` CLI

## Conventions
- Small functions with type hints
- Don't create new files unless the task needs them
- Keep GitHub access, categorization and formatting in separate modules

## Rules
- Plan before editing, for anything beyond a one-line change
- Always run `uv run pytest` before saying a task is done
- Ask before adding any dependency
- Never commit secrets; keys live in `.env` (already in `.gitignore`)
